"""
Phase 1.5 — trend sleeve redesigned to PRESERVE positive skew.

Phase 2 showed the weight-target engine destroyed skew: vol-target sizing trimmed
winners as they ran, name/gross caps clipped large positions, and daily
rebalancing re-trimmed. This module fixes that with a position-based
(fixed-shares) event backtest that implements the philosophy literally:

    * size ONCE at entry to risk a small fixed fraction of NAV (ATR risk unit),
    * then HOLD the share count fixed — a winner's weight is allowed to GROW,
    * cut losers fast at a chandelier trailing stop (bounded left tail),
    * trade only on entries and stop-exits (low turnover -> low cost),
    * let winners run up to a generous winner cap (not the tight entry cap),
    * regime governor halts NEW entries in stress; never force-trims winners.

Fixed downside + open-ended upside == the positive skew the project wants. The
MR sleeve is dropped (Phase 2: net drag, failed OOS and the negative control).

Survivor-biased sandbox data -> results PROVISIONAL (see docs/).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from phase1_backtest import CostModel, daily_vol


@dataclass
class TrendV2Params:
    # signal
    rs_lookback: int = 252
    rs_skip: int = 21
    rs_top_pct: float = 0.40
    donchian: int = 100
    vol_mult: float = 1.2
    # exit / skew preservation
    chandelier_atr: float = 5.0     # WIDE stop: give winners room to run
    atr_window: int = 20
    # sizing / caps
    risk_fraction: float = 0.0015   # fixed risk per trade at entry
    entry_cap: float = 0.03         # max weight a NEW entry may take
    winner_cap: float = 0.20        # a winner may grow up to this (skew source)
    gross_cap: float = 1.5          # stop NEW entries above this gross
    # regime governor (halts new entries; never trims winners)
    regime_ma: int = 200
    regime_vol_thr: float = 0.20


def _signals(prices, volume, p: TrendV2Params):
    vol_frac = daily_vol(prices, p.atr_window)          # ATR-proxy, fraction
    atr_abs = prices * vol_frac
    donchian_hi = prices.rolling(p.donchian, min_periods=p.donchian).max().shift(1)
    breakout = prices >= donchian_hi
    vol_ok = volume > p.vol_mult * volume.rolling(50, min_periods=20).mean()
    rs = prices.shift(p.rs_skip) / prices.shift(p.rs_lookback) - 1.0
    rs_ok = rs.rank(axis=1, pct=True) >= (1 - p.rs_top_pct)
    entry = (breakout & vol_ok & rs_ok).fillna(False)
    return atr_abs, entry


def _regime_defensive(prices, p: TrendV2Params):
    rets = prices.pct_change()
    idx = (1 + rets.mean(axis=1)).cumprod()
    idx_ma = idx.rolling(p.regime_ma, min_periods=p.regime_ma).mean()
    idx_vol = rets.mean(axis=1).rolling(20).std() * np.sqrt(252)
    return ((idx < idx_ma) & (idx_vol > p.regime_vol_thr)).shift(1).fillna(False)


def backtest(prices: pd.DataFrame, volume: pd.DataFrame,
             p: TrendV2Params = TrendV2Params(),
             cost: CostModel = CostModel()) -> dict:
    """Position-based, fixed-shares trend backtest. Returns NAV series, daily
    net returns, turnover, and a trade log."""
    atr_abs, entry = _signals(prices, volume, p)
    defensive = _regime_defensive(prices, p)
    adv_dollar = (prices * volume.rolling(20, min_periods=5).mean())

    px = prices.values
    at = atr_abs.values
    en = entry.values
    adv = adv_dollar.values
    dfn = defensive.values
    T, N = px.shape
    cols = list(prices.columns)

    cash = 1.0
    shares = np.zeros(N)          # shares held (in NAV=1.0-at-t0 dollar units)
    entry_px = np.full(N, np.nan)
    high = np.full(N, np.nan)
    cost_basis = np.zeros(N)      # dollars paid to open (for R-multiple)
    proceeds = np.zeros(N)        # dollars realized from trims (for R-multiple)
    init_risk = np.zeros(N)       # intended $ risk at entry (~risk_fraction*NAV)
    navs, netret, turn = [], [], []
    trades = []                   # trade log: R-multiples on full close
    n_trades = 0
    prev_nav = 1.0
    trade_bps = (cost.slippage_bps + cost.half_spread_bps) / 1e4

    def close_trade(j, final_proceeds):
        pnl = (proceeds[j] + final_proceeds) - cost_basis[j]
        if init_risk[j] > 0:
            trades.append(pnl / init_risk[j])       # R-multiple
        proceeds[j] = 0.0; cost_basis[j] = 0.0; init_risk[j] = 0.0

    def trade_cost(notional, price, part):
        c_share = cost.commission_per_share * (abs(notional) / price) if price > 0 else 0
        c_impact = abs(notional) * (cost.impact_bps_per_1pct_adv / 1e4) * (
            min(part, cost.max_participation) / 0.01)
        return abs(notional) * trade_bps + c_share + c_impact

    for t in range(T):
        price = np.nan_to_num(px[t], nan=0.0)
        held = shares > 0
        # mark-to-market NAV
        nav = cash + float((shares * price).sum())
        traded_notional = 0.0
        costs = 0.0

        # ---- exits: chandelier trailing stop OR price gone (delisting) ----
        for j in np.where(held)[0]:
            if price[j] <= 0:                       # data gap -> flat at last
                fp = shares[j] * (px[t - 1, j] if t > 0 else 0.0)
                cash += fp; close_trade(j, fp)
                shares[j] = 0.0; continue
            high[j] = np.nanmax([high[j], price[j]])
            stop = high[j] - p.chandelier_atr * at[t, j]
            if price[j] < stop:
                notion = shares[j] * price[j]
                part = notion / adv[t, j] if adv[t, j] > 0 else 0
                c = trade_cost(notion, price[j], part)
                cash += notion - c
                traded_notional += notion; costs += c; n_trades += 1
                close_trade(j, notion - c)
                shares[j] = 0.0; entry_px[j] = np.nan; high[j] = np.nan

        # ---- winner cap: trim only the part above winner_cap (rare) --------
        nav = cash + float((shares * price).sum())
        for j in np.where(shares > 0)[0]:
            w = shares[j] * price[j] / nav if nav > 0 else 0
            if w > p.winner_cap:
                excess = (w - p.winner_cap) * nav
                sh = excess / price[j]
                part = excess / adv[t, j] if adv[t, j] > 0 else 0
                c = trade_cost(excess, price[j], part)
                cash += excess - c
                traded_notional += excess; costs += c
                proceeds[j] += excess - c            # partial realization
                shares[j] -= sh

        # ---- entries: size once, only if not defensive & gross has room ----
        if not dfn[t]:
            nav = cash + float((shares * price).sum())
            gross = float((shares * price).sum()) / nav if nav > 0 else 0
            cand = np.where(en[t] & (shares <= 0))[0]
            for j in cand:
                if gross >= p.gross_cap or price[j] <= 0 or not np.isfinite(at[t, j]):
                    continue
                stop_dist = p.chandelier_atr * at[t, j]
                if stop_dist <= 0:
                    continue
                w = min(p.risk_fraction / (p.chandelier_atr * (at[t, j] / price[j])),
                        p.entry_cap)
                notion = w * nav
                if gross + w > p.gross_cap:
                    continue
                sh = notion / price[j]
                part = notion / adv[t, j] if adv[t, j] > 0 else 0
                c = trade_cost(notion, price[j], part)
                cash -= notion + c
                shares[j] = sh; entry_px[j] = price[j]; high[j] = price[j]
                cost_basis[j] = notion + c; proceeds[j] = 0.0
                init_risk[j] = p.risk_fraction * nav        # intended $ risk
                traded_notional += notion; costs += c; n_trades += 1
                gross += w

        nav = cash + float((shares * price).sum())
        navs.append(nav)
        netret.append(nav / prev_nav - 1.0 if prev_nav else 0.0)
        turn.append(traded_notional / prev_nav if prev_nav else 0.0)
        prev_nav = nav

    idx = prices.index
    nav_s = pd.Series(navs, index=idx, name="nav")
    return {
        "nav": nav_s,
        "net_ret": pd.Series(netret, index=idx, name="net_ret"),
        "turnover": pd.Series(turn, index=idx, name="turnover"),
        "n_trades": n_trades,
        "trade_R": np.array(trades),   # R-multiples of closed trades
    }
