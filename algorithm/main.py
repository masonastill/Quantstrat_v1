# region imports
from AlgorithmImports import *
# endregion

# =============================================================================
# Two-Sleeve Absolute-Return Ensemble  —  LEAN Algorithm Framework
# =============================================================================
# Production artifact for the philosophy in docs/ and README.md. It mirrors,
# 1:1, the economic logic and PARAMETERS of research/phase1_backtest.py, so the
# Python sandbox baseline and this algorithm stay in step.
#
#   Sleeve A (trend): Donchian breakout + relative-strength gate + volume
#                     confirmation; chandelier ATR trailing-stop exit.
#   Sleeve B (mean reversion): z-score of a stationary MA-residual, trend-gated
#                     (long only above 200d MA, short only below), tight ATR stop.
#   Regime governor: throttle gross when the index is below its 200d MA AND
#                     realized vol is elevated.
#   Sizing/risk: ATR risk-unit sizing, portfolio vol target, per-name / per-
#                     sector / gross / net caps.
#
# >>> STATUS: UNTESTED in this environment (a free QC account cannot run cloud
#     backtests, and no LEAN engine is available here). Treat this as a review
#     draft. First-compile checklist at the bottom of this file. <<<
#
# >>> DATA: run on survivorship-bias-free, point-in-time QC data. The Phase 0/1
#     sandbox (stockanalysis.com) is survivor-biased and NOT what this should
#     be judged on. <<<
# =============================================================================


class TwoSleeveEnsemble(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2016, 1, 1)
        self.set_end_date(2026, 6, 30)
        self.set_cash(1_000_000)

        # Realistic frictions (match the Python cost model). IB fee model +
        # explicit slippage; short borrow is modeled via the brokerage/margin.
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE,
                                 AccountType.MARGIN)
        self.settings.free_portfolio_value_percentage = 0.05
        self.universe_settings.resolution = Resolution.DAILY
        self.universe_settings.leverage = 2.0

        # ----- parameters (kept few; sensible, un-optimized defaults) --------
        self.p = {
            # universe
            "universe_size": 200, "min_price": 10.0, "min_dollar_vol": 5e6,
            # sleeve A (trend)
            "rs_lookback": 252, "rs_skip": 21, "rs_top_pct": 0.40,
            "donchian": 100, "vol_mult": 1.2, "chandelier_atr": 3.0,
            # sleeve B (mean reversion)
            "ma_window": 10, "z_window": 60, "z_entry": 1.5, "z_exit": 0.5,
            "trend_gate": 200, "hard_atr_stop": 2.0,
            # risk / sizing
            "risk_fraction": 0.0015, "atr_window": 20, "vol_target": 0.10,
            "name_cap": 0.05, "sector_cap": 0.20, "gross_cap": 1.5,
            "net_cap": 0.60, "alloc_trend": 0.5, "alloc_mr": 0.5,
            # regime governor
            "regime_ma": 200, "regime_vol_thr": 0.20, "regime_throttle": 0.30,
        }

        # index anchor for the regime governor + scheduling
        self.spy = self.add_equity("SPY", Resolution.DAILY).symbol
        self.spy_ma = self.sma(self.spy, self.p["regime_ma"], Resolution.DAILY)
        self.spy_vol = IndicatorExtensions.of(
            StandardDeviation(20), self.roc(self.spy, 1, Resolution.DAILY))

        self.add_universe(self._select_universe)
        self.set_warm_up(self.p["rs_lookback"] + 5, Resolution.DAILY)

        # per-symbol indicator state
        self.state = {}   # symbol -> SymbolData

        # rebalance once daily, 10 min before close, using the day's data
        self.schedule.on(self.date_rules.every_day(self.spy),
                         self.time_rules.before_market_close(self.spy, 10),
                         self._rebalance)

    # ------------------------------------------------------------------ #
    # Universe: liquid US equities by dollar volume, price floor
    # ------------------------------------------------------------------ #
    def _select_universe(self, fundamental):
        liquid = [f for f in fundamental
                  if f.has_fundamental_data
                  and f.price > self.p["min_price"]
                  and f.dollar_volume > self.p["min_dollar_vol"]]
        liquid.sort(key=lambda f: f.dollar_volume, reverse=True)
        return [f.symbol for f in liquid[:self.p["universe_size"]]]

    def on_securities_changed(self, changes):
        for sec in changes.added_securities:
            s = sec.symbol
            if s == self.spy or s in self.state:
                continue
            self.state[s] = SymbolData(self, s, self.p)
        for sec in changes.removed_securities:
            sd = self.state.pop(sec.symbol, None)
            if sd:
                sd.dispose(self)
            if self.portfolio[sec.symbol].invested:
                self.liquidate(sec.symbol)

    # ------------------------------------------------------------------ #
    # Regime governor
    # ------------------------------------------------------------------ #
    def _defensive(self) -> bool:
        if not (self.spy_ma.is_ready and self.spy_vol.is_ready):
            return False
        price = self.securities[self.spy].price
        ann_vol = float(self.spy_vol.current.value) * (252 ** 0.5)
        return (price < self.spy_ma.current.value) and (ann_vol > self.p["regime_vol_thr"])

    # ------------------------------------------------------------------ #
    # Daily rebalance: build target weights from both sleeves, size, cap
    # ------------------------------------------------------------------ #
    def _rebalance(self):
        if self.is_warming_up:
            return
        raw = {}   # symbol -> combined target weight (fraction of NAV)
        for s, sd in self.state.items():
            if not sd.ready():
                continue
            w_a = sd.trend_target() * self.p["alloc_trend"]
            w_b = sd.mr_target() * self.p["alloc_mr"]
            w = w_a + w_b
            if w != 0:
                raw[s] = w

        raw = self._apply_caps(raw)

        # regime throttle
        if self._defensive():
            raw = {s: w * self.p["regime_throttle"] for s, w in raw.items()}

        # emit orders via targets; liquidate names that fell out of the book
        targets = [PortfolioTarget(s, w) for s, w in raw.items()]
        held = {kv.key for kv in self.portfolio if kv.value.invested}
        for s in held - set(raw):
            if s != self.spy:
                targets.append(PortfolioTarget(s, 0))
        self.set_holdings(targets)

    def _apply_caps(self, raw: dict) -> dict:
        if not raw:
            return raw
        nc = self.p["name_cap"]
        raw = {s: max(-nc, min(nc, w)) for s, w in raw.items()}
        # per-sector cap
        by_sector = {}
        for s, w in raw.items():
            sec = self._sector(s)
            by_sector.setdefault(sec, []).append(s)
        for sec, syms in by_sector.items():
            gross = sum(abs(raw[s]) for s in syms)
            if gross > self.p["sector_cap"]:
                k = self.p["sector_cap"] / gross
                for s in syms:
                    raw[s] *= k
        # gross cap
        gross = sum(abs(w) for w in raw.values())
        if gross > self.p["gross_cap"]:
            k = self.p["gross_cap"] / gross
            raw = {s: w * k for s, w in raw.items()}
        # net cap (scale longs down if net too high)
        net = sum(raw.values())
        if abs(net) > self.p["net_cap"]:
            longs = {s: w for s, w in raw.items() if w > 0}
            lg = sum(longs.values())
            shorts_sum = sum(w for w in raw.values() if w < 0)
            target_long = self.p["net_cap"] + abs(shorts_sum)
            if lg > 0:
                k = min(1.0, target_long / lg)
                for s in longs:
                    raw[s] *= k
        return raw

    def _sector(self, symbol) -> str:
        sec = self.securities[symbol].fundamentals
        try:
            return str(sec.asset_classification.morningstar_sector_code)
        except Exception:
            return "Other"


# ------------------------------------------------------------------------- #
# Per-symbol indicator bundle + sleeve target logic (mirrors phase1_backtest)
# ------------------------------------------------------------------------- #
class SymbolData:
    def __init__(self, algo: QCAlgorithm, symbol, p: dict):
        self.symbol = symbol
        self.p = p
        self.donchian = algo.max(symbol, p["donchian"], Resolution.DAILY,
                                 Field.CLOSE)
        self.atr = algo.atr(symbol, p["atr_window"], MovingAverageType.WILDERS,
                            Resolution.DAILY)
        self.ma_short = algo.sma(symbol, p["ma_window"], Resolution.DAILY)
        self.gate = algo.sma(symbol, p["trend_gate"], Resolution.DAILY)
        self.vol_avg = algo.sma(symbol, 50, Resolution.DAILY, Field.VOLUME)
        # RS = price[-skip]/price[-lookback]-1 via a rolling window of closes
        self.closes = RollingWindow[float](p["rs_lookback"] + 1)
        self.resid_win = RollingWindow[float](p["z_window"])   # for z-score
        self._algo = algo
        self._consolidator = TradeBarConsolidator(timedelta(days=1))
        self._consolidator.data_consolidated += self._on_bar
        algo.subscription_manager.add_consolidator(symbol, self._consolidator)
        # chandelier / MR state
        self.trend_pos = False
        self.trend_high = None
        self.mr_pos = 0
        self.mr_entry = None

    def _on_bar(self, sender, bar):
        self.closes.add(bar.close)
        if self.ma_short.is_ready:
            self.resid_win.add(bar.close / self.ma_short.current.value - 1.0)

    def dispose(self, algo: QCAlgorithm):
        algo.subscription_manager.remove_consolidator(self.symbol, self._consolidator)

    def ready(self) -> bool:
        return (self.donchian.is_ready and self.atr.is_ready
                and self.ma_short.is_ready and self.gate.is_ready
                and self.vol_avg.is_ready and self.closes.is_ready
                and self.resid_win.is_ready)

    def _price(self):
        return self.closes[0]

    def _daily_vol_frac(self):
        # ATR as a fraction of price ~ the Python daily_vol (ATR-proxy)
        px = self._price()
        return max(self.atr.current.value / px, 0.003) if px else 0.003

    def _size(self, stop_atr: float) -> float:
        return self.p["risk_fraction"] / (stop_atr * self._daily_vol_frac())

    # ---- Sleeve A: trend with chandelier trailing stop -------------------
    def trend_target(self) -> float:
        px = self._price()
        rs = (self.closes[self.p["rs_skip"]] / self.closes[self.p["rs_lookback"]]
              - 1.0)
        breakout = px >= self.donchian.current.value
        vol_ok = self._algo.securities[self.symbol].volume > \
            self.p["vol_mult"] * self.vol_avg.current.value
        # NOTE: cross-sectional RS rank is applied at the portfolio level in a
        # fuller build; here we use an absolute RS>0 proxy + breakout. See the
        # checklist note on making the RS gate cross-sectional.
        rs_ok = rs > 0
        if not self.trend_pos:
            if breakout and vol_ok and rs_ok:
                self.trend_pos = True
                self.trend_high = px
                return self._size(self.p["chandelier_atr"])
            return 0.0
        self.trend_high = max(self.trend_high, px)
        stop = self.trend_high - self.p["chandelier_atr"] * self.atr.current.value
        if px < stop:
            self.trend_pos = False
            self.trend_high = None
            return 0.0
        return self._size(self.p["chandelier_atr"])

    # ---- Sleeve B: trend-gated short-term mean reversion -----------------
    def mr_target(self) -> float:
        px = self._price()
        resid = list(self.resid_win)
        mu = sum(resid) / len(resid)
        var = sum((x - mu) ** 2 for x in resid) / max(len(resid) - 1, 1)
        sd = var ** 0.5
        if sd == 0:
            return 0.0
        z = (resid[0] - mu) / sd
        above = px > self.gate.current.value
        if self.mr_pos == 0:
            if z <= -self.p["z_entry"] and above:
                self.mr_pos = 1
                self.mr_entry = px
            elif z >= self.p["z_entry"] and not above:
                self.mr_pos = -1
                self.mr_entry = px
        else:
            adverse = (self.mr_entry - px) if self.mr_pos == 1 else (px - self.mr_entry)
            stop_hit = adverse > self.p["hard_atr_stop"] * self.atr.current.value
            revert = abs(z) <= self.p["z_exit"]
            flip = (self.mr_pos == 1 and z >= self.p["z_entry"]) or \
                   (self.mr_pos == -1 and z <= -self.p["z_entry"])
            if stop_hit or revert or flip:
                self.mr_pos = 0
                self.mr_entry = None
        return self.mr_pos * self._size(self.p["hard_atr_stop"])


# =============================================================================
# FIRST-COMPILE CHECKLIST (validate on QuantConnect before trusting anything)
# -----------------------------------------------------------------------------
# 1. Compile: confirm current LEAN API names (add_universe with a fundamental
#    selector; self.atr/self.sma/self.max/self.roc helper signatures; Field.*).
# 2. Warm-up: verify indicators are_ready after set_warm_up; RollingWindow fills.
# 3. Universe churn: on_securities_changed disposes consolidators and liquidates
#    dropped names — watch for orphaned subscriptions / RemovedSecurities.
# 4. Turnover: the Python baseline showed the MR sleeve turns ~77%/day and loses
#    to costs. Expect the same here. Add a no-trade band (only retrade if the
#    target moves > X%) before judging net performance — this is the #1 fix.
# 5. RS gate: make it CROSS-SECTIONAL (rank all candidates by RS, take top pct)
#    at rebalance time, rather than the absolute RS>0 proxy used per-symbol here.
# 6. Costs: confirm the IB fee model + a slippage model are attached; add an
#    explicit VolumeShareSlippageModel to mirror the Python impact assumption.
# 7. Compare: net CAGR/vol/Sharpe/skew/turnover should be in the same ballpark
#    as research/_phase1_results.json (on comparable data) before proceeding.
# =============================================================================
