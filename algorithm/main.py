# region imports
from AlgorithmImports import *
# endregion

# =============================================================================
# Trend-v2 — positive-skew trend sleeve (LEAN)
# =============================================================================
# Production artifact for the design that SURVIVED Phases 0-3. Mirrors
# research/phase15_trend.py 1:1 (same parameters, same economics).
#
# WHY NOT THE ALGORITHM FRAMEWORK: the framework's PortfolioConstruction
# rebalances to target WEIGHTS every emission, which continuously trims winners
# back to target — the exact mechanism Phase 2 proved destroys positive skew.
# The philosophy ("let winners run, cut losers fast") requires holding a FIXED
# SHARE COUNT after entry, so this is implemented as a direct-position
# QCAlgorithm. This is a deliberate, documented departure from the framework.
#
# Sleeve B (mean reversion) was REJECTED in Phase 2 (net drag, failed OOS and
# the negative control) and is not present.
#
# >>> STATUS: UNTESTED (free QC account cannot run cloud backtests; no engine
#     here). Review draft. First-compile checklist at the bottom. <<<
# >>> DATA: run on survivorship-bias-free, point-in-time QC data. <<<
# =============================================================================


class TrendV2(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2008, 1, 1)
        self.set_end_date(2026, 6, 30)
        self.set_cash(1_000_000)
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE,
                                 AccountType.MARGIN)
        self.settings.free_portfolio_value_percentage = 0.05
        self.universe_settings.resolution = Resolution.DAILY

        # ---- parameters (skew-honoring final config from Phase 3) -----------
        self.p = {
            "universe_size": 300, "min_price": 10.0, "min_dollar_vol": 5e6,
            "rs_lookback": 252, "rs_skip": 21, "rs_top_pct": 0.40,
            "donchian": 100, "vol_mult": 1.2, "chandelier_atr": 4.0,
            "atr_window": 20, "risk_fraction": 0.0015,
            "entry_cap": 0.03, "winner_cap": 0.20, "gross_cap": 1.5,
            "regime_ma": 200, "regime_vol_thr": 0.20,
        }

        self.spy = self.add_equity("SPY", Resolution.DAILY).symbol
        self.spy_ma = self.sma(self.spy, self.p["regime_ma"], Resolution.DAILY)
        self.spy_std = IndicatorExtensions.of(
            StandardDeviation(20), self.roc(self.spy, 1, Resolution.DAILY))

        self.add_universe(self._select_universe)
        self.set_warm_up(self.p["rs_lookback"] + 5, Resolution.DAILY)

        self.sd = {}           # symbol -> SymbolData
        self.highest = {}      # symbol -> highest close since entry (chandelier)

        self.schedule.on(self.date_rules.every_day(self.spy),
                         self.time_rules.before_market_close(self.spy, 10),
                         self._rebalance)

    # ------------------------------------------------------------------ #
    def _select_universe(self, fundamental):
        liquid = [f for f in fundamental
                  if f.has_fundamental_data and f.price > self.p["min_price"]
                  and f.dollar_volume > self.p["min_dollar_vol"]]
        liquid.sort(key=lambda f: f.dollar_volume, reverse=True)
        return [f.symbol for f in liquid[:self.p["universe_size"]]]

    def on_securities_changed(self, changes):
        for s in changes.added_securities:
            if s.symbol != self.spy and s.symbol not in self.sd:
                self.sd[s.symbol] = SymbolData(self, s.symbol, self.p)
        for s in changes.removed_securities:
            sym = s.symbol
            self.sd.pop(sym, None); self.highest.pop(sym, None)
            if self.portfolio[sym].invested:
                self.liquidate(sym)   # drop names that leave the universe

    def _defensive(self) -> bool:
        if not (self.spy_ma.is_ready and self.spy_std.is_ready):
            return False
        ann_vol = float(self.spy_std.current.value) * (252 ** 0.5)
        return (self.securities[self.spy].price < self.spy_ma.current.value
                and ann_vol > self.p["regime_vol_thr"])

    # ------------------------------------------------------------------ #
    def _rebalance(self):
        if self.is_warming_up:
            return
        nav = self.portfolio.total_portfolio_value

        # ---- EXITS: chandelier trailing stop (cut losers, trail winners) ---
        for sym in [s for s in self.sd if self.portfolio[s].invested]:
            sd = self.sd[sym]
            if not sd.ready():
                continue
            price = self.securities[sym].price
            self.highest[sym] = max(self.highest.get(sym, price), price)
            stop = self.highest[sym] - self.p["chandelier_atr"] * sd.atr.current.value
            if price < stop:
                self.liquidate(sym)
                self.highest.pop(sym, None)

        # ---- WINNER CAP: trim only the excess above winner_cap (rare) ------
        for sym in [s for s in self.sd if self.portfolio[s].invested]:
            w = self.portfolio[sym].holdings_value / nav
            if w > self.p["winner_cap"]:
                self.set_holdings(sym, self.p["winner_cap"])   # trim excess only

        # ---- ENTRIES: size ONCE at entry; never resize winners -------------
        if self._defensive():
            return
        gross = sum(abs(self.portfolio[s].holdings_value) for s in self.sd) / nav
        # cross-sectional RS gate: rank ready candidates, keep the top pct
        cands = [s for s in self.sd if self.sd[s].ready()
                 and not self.portfolio[s].invested and self.sd[s].entry_signal()]
        ranked = sorted(self.sd, key=lambda s: self.sd[s].rs()
                        if self.sd[s].ready() else -9e9, reverse=True)
        n_top = max(1, int(len(ranked) * self.p["rs_top_pct"]))
        top = set(ranked[:n_top])
        for sym in cands:
            if gross >= self.p["gross_cap"] or sym not in top:
                continue
            sd = self.sd[sym]
            price = self.securities[sym].price
            atr = sd.atr.current.value
            if atr <= 0 or price <= 0:
                continue
            # ATR risk-unit sizing, capped at entry_cap; fixed from here on
            w = min(self.p["risk_fraction"] / (self.p["chandelier_atr"] * (atr / price)),
                    self.p["entry_cap"])
            if gross + w > self.p["gross_cap"]:
                continue
            self.set_holdings(sym, w)
            self.highest[sym] = price
            gross += w


# ------------------------------------------------------------------------- #
class SymbolData:
    """Indicators + entry signal for one name (mirrors phase15_trend signals)."""

    def __init__(self, algo: QCAlgorithm, symbol, p: dict):
        self.symbol = symbol
        self.algo = algo
        self.p = p
        self.donchian = algo.max(symbol, p["donchian"], Resolution.DAILY, Field.CLOSE)
        self.atr = algo.atr(symbol, p["atr_window"], MovingAverageType.WILDERS,
                            Resolution.DAILY)
        self.vol_avg = algo.sma(symbol, 50, Resolution.DAILY, Field.VOLUME)
        self.closes = RollingWindow[float](p["rs_lookback"] + 1)
        self._cons = TradeBarConsolidator(timedelta(days=1))
        self._cons.data_consolidated += self._on_bar
        algo.subscription_manager.add_consolidator(symbol, self._cons)

    def _on_bar(self, sender, bar):
        self.closes.add(bar.close)

    def ready(self) -> bool:
        return (self.donchian.is_ready and self.atr.is_ready
                and self.vol_avg.is_ready and self.closes.is_ready)

    def rs(self) -> float:
        return self.closes[self.p["rs_skip"]] / self.closes[self.p["rs_lookback"]] - 1.0

    def entry_signal(self) -> bool:
        price = self.closes[0]
        breakout = price >= self.donchian.current.value
        vol_ok = self.algo.securities[self.symbol].volume > \
            self.p["vol_mult"] * self.vol_avg.current.value
        return bool(breakout and vol_ok)   # RS gate applied cross-sectionally

    def dispose(self):
        self.algo.subscription_manager.remove_consolidator(self.symbol, self._cons)


# =============================================================================
# FIRST-COMPILE CHECKLIST (validate on QuantConnect)
# -----------------------------------------------------------------------------
# 1. Confirm current LEAN API: add_universe(fundamental selector), self.atr/sma/
#    max/roc signatures, Field.CLOSE/VOLUME, set_holdings vs market_order.
# 2. set_holdings is used for entries + winner-cap trims; because we only call it
#    ONCE per name at entry and never again (except a rare cap trim), the
#    fixed-share / let-winners-run property holds. Verify no other code path
#    resizes an open winner.
# 3. Warm-up: indicators + RollingWindow ready after set_warm_up.
# 4. Universe churn: on_securities_changed disposes consolidators (call
#    sd.dispose()); currently pop() drops the ref — add explicit dispose() to
#    avoid leaking consolidators on large universes.
# 5. Costs: attach an explicit slippage model (e.g. VolumeShareSlippageModel) to
#    match the Python cost assumptions; IB fee model gives commissions.
# 6. Compare net CAGR / maxDD / monthly-skew / turnover to
#    research/_phase3_results.json on comparable (survivorship-free) data.
# =============================================================================
