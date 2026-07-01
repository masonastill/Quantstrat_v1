"""
Phase 1 — minimal two-sleeve backtest with realistic costs (sandbox data).

This is the Python baseline that produces Phase 1's performance + cost
breakdown. It mirrors the logic intended for the LEAN algorithm (algorithm/),
sharing the SAME parameters and economic defaults, so the two stay in step.
Numbers come from the survivor-biased stockanalysis.com sandbox (see
data_stockanalysis.py) and are PROVISIONAL.

Design goals (per brief): fewest parameters possible, economically sensible
UN-optimized defaults, realistic frictions from the first run, no lookahead.

Lookahead discipline: every signal at day t uses data <= t; target weights set
at close t are earned on t+1 (simulate applies weights.shift(1)). Donchian/MA/
vol/RS/z all use backward windows.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# Parameters (kept small and named; defaults are sensible, not optimized)
# --------------------------------------------------------------------------- #
@dataclass
class TrendParams:
    rs_lookback: int = 252       # relative-strength window (~12m)
    rs_skip: int = 21            # skip last ~1m (avoid short-term reversal)
    rs_top_pct: float = 0.40     # only names in top 40% RS are eligible to enter
    donchian: int = 100          # breakout window (~5 months of highs)
    vol_mult: float = 1.2        # entry needs volume > vol_mult * 50d avg volume
    chandelier_atr: float = 3.0  # trailing stop = highest_close - 3*ATR


@dataclass
class MRParams:
    ma_window: int = 10          # short residual MA (price/MA - 1)
    z_window: int = 60           # z-score lookback for the residual
    z_entry: float = 1.5         # enter when |z| >= 1.5
    z_exit: float = 0.5          # exit as |z| reverts <= 0.5
    trend_gate: int = 200        # long only above 200d MA; short only below
    hard_atr_stop: float = 2.0   # tight stop: exit if adverse move > 2*ATR


@dataclass
class RiskParams:
    risk_fraction: float = 0.0015   # ~0.15% NAV risk per trade (ATR risk unit)
    atr_window: int = 20            # vol/ATR estimation window
    vol_target_annual: float = 0.10  # 10% annualized portfolio vol target
    name_cap: float = 0.05          # max |weight| per name
    sector_cap: float = 0.20        # max gross |weight| per sector
    gross_cap: float = 1.5          # max gross leverage
    net_cap: float = 0.60           # max |net| leverage (long-biased profile)
    alloc_trend: float = 0.5        # sleeve budget split
    alloc_mr: float = 0.5


@dataclass
class CostModel:
    commission_per_share: float = 0.005   # $/share
    slippage_bps: float = 3.0             # adverse fill vs decision price
    half_spread_bps: float = 2.0          # cross half the bid/ask
    impact_bps_per_1pct_adv: float = 8.0  # market impact per 1% of ADV traded
    borrow_apr: float = 0.005             # 0.5%/yr borrow on short notional
    max_participation: float = 0.05       # cap modeled ADV participation


@dataclass
class Config:
    trend: TrendParams = field(default_factory=TrendParams)
    mr: MRParams = field(default_factory=MRParams)
    risk: RiskParams = field(default_factory=RiskParams)
    cost: CostModel = field(default_factory=CostModel)
    regime_ma: int = 200            # index trend filter
    regime_vol_thr: float = 0.20    # elevated realized vol threshold (annual)
    regime_throttle: float = 0.30   # gross multiplier when stressed


# --------------------------------------------------------------------------- #
# Indicators
# --------------------------------------------------------------------------- #
def daily_vol(prices: pd.DataFrame, window: int) -> pd.DataFrame:
    """ATR-proxy daily volatility (EWM std of close-to-close returns), floored."""
    r = prices.pct_change()
    v = r.ewm(span=window, min_periods=window).std()
    return v.clip(lower=0.003)   # floor 0.3%/day to avoid blow-up sizing


def vol_target_weight(vol_d: pd.DataFrame, risk: RiskParams,
                      stop_atr: float) -> pd.DataFrame:
    """Per-name target gross weight from vol sizing:
    w = risk_fraction / (stop_atr * daily_vol).  Lower vol -> larger weight."""
    return risk.risk_fraction / (stop_atr * vol_d)


# --------------------------------------------------------------------------- #
# Sleeve A: time-series trend (Donchian breakout + RS gate + chandelier stop)
# --------------------------------------------------------------------------- #
def trend_sleeve(prices: pd.DataFrame, volume: pd.DataFrame,
                 cfg: Config) -> pd.DataFrame:
    p = cfg.trend
    vol_d = daily_vol(prices, cfg.risk.atr_window)
    size = vol_target_weight(vol_d, cfg.risk, p.chandelier_atr)
    atr_abs = (prices * vol_d)                       # dollar volatility ~ ATR

    # entry conditions (all known at close t)
    donchian_hi = prices.rolling(p.donchian, min_periods=p.donchian).max().shift(1)
    breakout = prices >= donchian_hi
    vol_avg = volume.rolling(50, min_periods=20).mean()
    vol_ok = volume > p.vol_mult * vol_avg
    rs = prices.shift(p.rs_skip) / prices.shift(p.rs_lookback) - 1.0
    rs_rank = rs.rank(axis=1, pct=True)
    rs_ok = rs_rank >= (1 - p.rs_top_pct)
    entry = (breakout & vol_ok & rs_ok).fillna(False)

    # per-name long/flat state machine with chandelier trailing stop
    px = prices.values; en = entry.values; sz = size.values; at = atr_abs.values
    T, N = px.shape
    w = np.zeros((T, N))
    for j in range(N):
        in_pos = False; high = np.nan
        for t in range(T):
            if not np.isfinite(px[t, j]):
                in_pos = False; w[t, j] = 0.0; continue
            if not in_pos:
                if en[t, j] and np.isfinite(sz[t, j]):
                    in_pos = True; high = px[t, j]; w[t, j] = sz[t, j]
            else:
                high = max(high, px[t, j])
                stop = high - p.chandelier_atr * at[t, j]
                if px[t, j] < stop:
                    in_pos = False; w[t, j] = 0.0
                else:
                    w[t, j] = sz[t, j] if np.isfinite(sz[t, j]) else w[t - 1, j]
    return pd.DataFrame(w, index=prices.index, columns=prices.columns)


# --------------------------------------------------------------------------- #
# Sleeve B: short-term mean reversion on a stationary residual, trend-gated
# --------------------------------------------------------------------------- #
def mr_sleeve(prices: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    p = cfg.mr
    vol_d = daily_vol(prices, cfg.risk.atr_window)
    size = vol_target_weight(vol_d, cfg.risk, p.hard_atr_stop)
    atr_abs = prices * vol_d

    ma = prices.rolling(p.ma_window, min_periods=p.ma_window).mean()
    resid = prices / ma - 1.0
    z = ((resid - resid.rolling(p.z_window, min_periods=p.z_window).mean())
         / resid.rolling(p.z_window, min_periods=p.z_window).std())
    gate = prices.rolling(p.trend_gate, min_periods=p.trend_gate).mean()
    above = prices > gate

    px = prices.values; zz = z.values; ab = above.values
    sz = size.values; at = atr_abs.values
    T, N = px.shape
    w = np.zeros((T, N))
    for j in range(N):
        pos = 0; entry_px = np.nan
        for t in range(T):
            if not np.isfinite(px[t, j]) or not np.isfinite(zz[t, j]):
                pos = 0; w[t, j] = 0.0; continue
            if pos == 0:
                if zz[t, j] <= -p.z_entry and ab[t, j]:           # oversold + uptrend
                    pos = 1; entry_px = px[t, j]
                elif zz[t, j] >= p.z_entry and not ab[t, j]:       # overbought + downtrend
                    pos = -1; entry_px = px[t, j]
            else:
                # tight ATR stop (the fat-left-tail control for this sleeve)
                adverse = (entry_px - px[t, j]) if pos == 1 else (px[t, j] - entry_px)
                stop_hit = adverse > p.hard_atr_stop * at[t, j]
                revert = abs(zz[t, j]) <= p.z_exit
                flip = (pos == 1 and zz[t, j] >= p.z_entry) or \
                       (pos == -1 and zz[t, j] <= -p.z_entry)
                if stop_hit or revert or flip:
                    pos = 0
            w[t, j] = pos * (sz[t, j] if np.isfinite(sz[t, j]) else 0.0)
    return pd.DataFrame(w, index=prices.index, columns=prices.columns)


# --------------------------------------------------------------------------- #
# Combine sleeves: caps, vol target, regime throttle
# --------------------------------------------------------------------------- #
def _apply_caps(W: pd.DataFrame, sectors: dict, risk: RiskParams) -> pd.DataFrame:
    W = W.clip(-risk.name_cap, risk.name_cap)                 # per-name cap
    sec = pd.Series({c: sectors.get(c, "Other") for c in W.columns})
    for s in sec.unique():                                    # per-sector cap
        cols = sec[sec == s].index
        gross = W[cols].abs().sum(axis=1)
        scale = (risk.sector_cap / gross).clip(upper=1.0).fillna(1.0)
        W[cols] = W[cols].mul(scale, axis=0)
    gross = W.abs().sum(axis=1)                               # gross cap
    W = W.mul((risk.gross_cap / gross).clip(upper=1.0).fillna(1.0), axis=0)
    net = W.sum(axis=1)                                       # net cap (scale longs)
    over = net.abs() > risk.net_cap
    if over.any():
        longs = W.clip(lower=0); shorts = W.clip(upper=0)
        lg = longs.sum(axis=1)
        target_long = (risk.net_cap + shorts.sum(axis=1).abs())
        s = (target_long / lg).clip(upper=1.0).fillna(1.0)
        W = longs.mul(np.where(over, s, 1.0), axis=0) + shorts
    return W


def build_portfolio(prices, volume, sectors, cfg: Config):
    """Returns (final_weights, components) with both sleeves combined, capped,
    vol-targeted and regime-throttled."""
    w_a = trend_sleeve(prices, volume, cfg) * cfg.risk.alloc_trend
    w_b = mr_sleeve(prices, cfg) * cfg.risk.alloc_mr
    W = (w_a.fillna(0) + w_b.fillna(0))
    W = _apply_caps(W, sectors, cfg.risk)

    # portfolio vol target (reactive, lagged): scale by target/realized
    rets = prices.pct_change()
    unscaled = (W.shift(1) * rets).sum(axis=1)
    realized = unscaled.rolling(60, min_periods=20).std() * np.sqrt(252)
    scale = (cfg.risk.vol_target_annual / realized).clip(0.25, 1.5).shift(1).fillna(1.0)
    W = W.mul(scale, axis=0)

    # regime governor: defensive when index < MA AND realized vol elevated
    idx = (1 + rets.mean(axis=1)).cumprod()
    idx_ma = idx.rolling(cfg.regime_ma, min_periods=cfg.regime_ma).mean()
    idx_vol = rets.mean(axis=1).rolling(20).std() * np.sqrt(252)
    stressed = ((idx < idx_ma) & (idx_vol > cfg.regime_vol_thr)).shift(1).fillna(False)
    throttle = pd.Series(np.where(stressed, cfg.regime_throttle, 1.0), index=W.index)
    W = W.mul(throttle, axis=0)
    return W, {"w_a": w_a, "w_b": w_b, "scale": scale, "throttle": throttle,
               "stressed": stressed}


# --------------------------------------------------------------------------- #
# Simulation with explicit cost accounting
# --------------------------------------------------------------------------- #
def simulate(prices, volume, W, cost: CostModel):
    rets = prices.pct_change().fillna(0.0).values
    px = prices.values
    adv_dollar = (prices * volume.rolling(20, min_periods=5).mean()).values
    Wv = W.fillna(0.0).values
    T, N = Wv.shape
    nav = 1.0
    prev = np.zeros(N)
    navs, gross_ret, c_trade, c_comm, c_impact, c_borrow, turn = (
        [], [], [], [], [], [], [])
    for t in range(1, T):
        r = np.nan_to_num(rets[t])
        pr = np.nan_to_num(prev * r).sum()              # gross return on held book
        drift = (prev * (1 + r)) / (1 + pr) if (1 + pr) else prev
        tgt = np.nan_to_num(Wv[t])
        dw = tgt - drift                                 # rebalancing trades (frac NAV)
        adw = np.abs(dw)
        turnover = adw.sum()
        # costs (as fraction of NAV)
        spread_slip = turnover * (cost.slippage_bps + cost.half_spread_bps) / 1e4
        with np.errstate(divide="ignore", invalid="ignore"):
            shares = np.where(px[t] > 0, adw * nav / px[t], 0.0)
            commission = cost.commission_per_share * np.nansum(shares) / nav
            part = np.where(adv_dollar[t] > 0, adw * nav / adv_dollar[t], 0.0)
            part = np.clip(part, 0, cost.max_participation)
            impact = np.nansum(adw * (cost.impact_bps_per_1pct_adv / 1e4) * (part / 0.01))
        borrow = np.clip(-tgt, 0, None).sum() * cost.borrow_apr / 252.0
        nav *= (1 + pr)
        nav *= (1 - spread_slip - commission - impact - borrow)
        prev = tgt
        navs.append(nav); gross_ret.append(pr); turn.append(turnover)
        c_trade.append(spread_slip); c_comm.append(commission)
        c_impact.append(impact); c_borrow.append(borrow)
    idx = prices.index[1:]
    out = pd.DataFrame({
        "nav": navs, "gross_ret": gross_ret, "turnover": turn,
        "cost_spread_slip": c_trade, "cost_commission": c_comm,
        "cost_impact": c_impact, "cost_borrow": c_borrow}, index=idx)
    out["net_ret"] = out["nav"].pct_change().fillna(out["nav"].iloc[0] - 1.0)
    return out
