# Phase 1 — Minimal Backtest + Cost Breakdown

**Phase:** 1 — Minimal, simple backtest with realistic costs (no optimization).
**Status:** Baseline complete on the sandbox. **Awaiting your review.**
**Date:** 2026-07-01
**Reproduce:** `cd research && python3 run_phase1.py` (writes
`_phase1_results.json`). LEAN artifact: `algorithm/main.py` (untested — see its
first-compile checklist).

---

## 0. What was built

Both sleeves + regime governor + sizing/risk, with the **fewest parameters
practical** (6 trend, 6 MR, a shared risk block, 3 regime) and **economically
sensible, un-optimized defaults** (`phase1_backtest.py :: Config`):

- **Sleeve A — trend:** Donchian(100) breakout, relative-strength gate (top 40%
  of 12-1m RS), volume confirmation (>1.2× 50d avg), **chandelier ATR(20)×3
  trailing stop.**
- **Sleeve B — mean reversion:** z-score(60) of a `price/MA(10)−1` residual,
  **trend-gated** (long only >200d MA, short only <200d MA), **tight 2×ATR
  hard stop.**
- **Regime governor:** throttle gross to 30% when the equal-weight index is
  below its 200d MA **and** 20d realized vol > 20% annualized.
- **Sizing/risk:** ATR risk-unit sizing (0.15% NAV/trade), 10% vol target,
  caps: name 5% / sector 20% / gross 1.5× / net 0.6×, 50-50 sleeve split.
- **Costs from bar one:** commission $0.005/sh, slippage 3 bps, half-spread
  2 bps, market impact 8 bps per 1% ADV, short borrow 0.5%/yr.

Same parameters drive the LEAN algorithm (`algorithm/main.py`), so the two stay
in step.

---

## 1. Baseline result — the strategy loses money after costs

| Metric | Gross | **Net of costs** |
|---|---|---|
| Ann. return | +3.8% | **−1.2%** |
| CAGR | — | **−1.6%** |
| Ann. vol | — | 9.7% |
| Sharpe | — | **−0.12** |
| Sortino | — | −0.14 |
| Max drawdown | — | **−27.7%** |
| Skew | — | **−0.83** |
| Excess kurtosis | — | 4.8 |
| Tail ratio | — | 0.94 |

**Two findings that matter:**

### (a) Costs dominate — the mean-reversion sleeve turns over ~77%/day
| Cost component | Drag |
|---|---|
| Spread + slippage | **417 bps/yr** |
| Commission | 66 bps/yr |
| Short borrow | 11 bps/yr |
| Market impact | ~0 bps/yr (large-caps, small size) |
| **Total** | **≈ 494 bps/yr** |

The MR sleeve holds positions **2.3 days on average** and churns **77.5%/day
(1-way)**; the trend sleeve is a tame 12%/day. Blended turnover ≈ **83×/year**.
At 5 bps round-trip-ish per unit turnover, that's a ~5%/yr drag that **erases
the entire 3.8% gross return.** This is the single most important Phase-1 fact:
*the naive mean-reversion sleeve is uneconomic at realistic spreads without
turnover control.*

### (b) The blend has NEGATIVE skew — the core "positive skew" goal is not met
Portfolio skew is **−0.83**. The convergent MR sleeve dominates gross exposure
(0.79 vs 0.43 for trend), and the chandelier exit alone did not deliver the
open-ended right tail the philosophy depends on. **Positive skew has to be
engineered and was not achieved by this naive construction.** (Consistent with
the Phase 0 warning that trend's positive skew is not automatic.)

### Exposure / regime (sanity)
- Avg gross leverage **0.81×** (cap 1.5), avg net **0.37×** (cap 0.6) — caps not
  binding; the profile is genuinely unlevered/long-biased as intended.
- Time in the defensive regime: **8.9%** — the governor fires occasionally, not
  constantly (good; it's not just sitting in cash).

---

## 2. Honest interpretation

This is a **legitimate, informative baseline, not a failure of process.** Phase
1's mandate — realistic costs from the start — did its job: it exposed that the
thin gross edge (already flagged as statistically weak in Phase 0) does not
survive frictions, with MR turnover as the mechanism. Nothing was optimized to
hide this.

What it implies for Phase 2 (robustness), in priority order:
1. **Turnover control on the MR sleeve is the #1 lever** — a no-trade/rebalance
   band, wider z-entry, longer minimum holds, or trading fewer/higher-conviction
   names. This is execution realism, not curve-fitting, but each choice is a
   parameter to stress on a *plateau*, not tune to a peak.
2. **Re-earn positive skew** — verify whether a *lower-turnover, trend-heavier*
   blend (or asymmetric sleeve allocation) restores portfolio-level positive
   skew, which is the whole point.
3. **Question whether the MR sleeve earns its keep at all** in liquid large-caps
   net of costs; it may belong in a different (smaller/less-liquid) universe or
   be dropped.
4. **Everything re-checked on survivorship-free, 2008-inclusive data** before
   any of these numbers are trusted (carried over from Phase 0).

---

## 3. Caveats (unchanged from Phase 0, still binding)

- **Sandbox data:** survivor-biased, ~2016 start (no 2008/2010), large/mid-cap
  only. Absolute return, drawdown and tail figures are **optimistic**; the
  measured edge is likely **understated**. Provisional throughout.
- **LEAN algorithm is UNTESTED** (free QC account can't run cloud backtests;
  no engine here). `algorithm/main.py` is a review draft with a first-compile
  checklist; its RS gate is a per-symbol proxy that must be made cross-sectional.
- **No optimization** was performed. Defaults are first-principles, not tuned.

---

## 4. Deliverables

| File | What |
|---|---|
| `research/phase1_backtest.py` | Sleeves + governor + sizing/caps + cost model + simulator |
| `research/run_phase1.py` | Baseline driver → performance + cost breakdown |
| `research/_phase1_results.json` | Machine-readable results |
| `algorithm/main.py` | LEAN Algorithm Framework implementation (untested draft) |
| `docs/PHASE1_FINDINGS.md` | This report |

---

## 5. Gate

**STOP — awaiting review.** Honest bottom line: **the strategy as minimally
specified does not survive costs (net −1.2%/yr) and does not yet deliver
positive skew.** That's a useful, expected result at this stage — the edge, if
it exists, must come from turnover discipline and construction, which is exactly
what Phase 2 is for.

Recommendation before Phase 2: I'd start Phase 2 by testing **MR turnover
control** (rebalance band / longer holds) as a *robustness plateau*, and check
whether a trend-heavier blend restores positive skew — **not** by hunting for
the parameter set with the best return. Say **"proceed"** (and flag if you want
the short MR leg kept or dropped) and I'll begin Phase 2.
