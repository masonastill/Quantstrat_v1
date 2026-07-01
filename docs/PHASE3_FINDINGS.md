# Phase 3 — Skew-Aware Evaluation & Stress Windows

**Subject:** trend-v2 final, skew-honoring config (chandelier **4×ATR**,
RS top 0.40, donchian 100, risk_fraction 0.0015).
**Status:** complete on the sandbox. **Awaiting review.**
**Date:** 2026-07-01 · **Reproduce:** `python3 research/run_phase3.py`
(`_phase3_results.json`).

---

## 1. Full metric table (net of costs)

| Metric | Value | Read |
|---|---|---|
| CAGR | **+2.8%** | modest (skew-honoring config trades return for skew) |
| Ann. vol | 10.8% | ~ on the 8–12% target |
| Sharpe | **0.31** | modest, as expected for a positive-skew book |
| Sortino | 0.33 | — |
| MAR / Calmar | 0.18 | low (slow recovery, see below) |
| **Max drawdown** | **−16.1%** | acceptable in *magnitude* |
| Recovery time | **387 days** | **slow** |
| Longest underwater | **578 days (~2.3y)** | **a real weakness for "absolute return"** |
| Skew (daily) | −0.94 | negative — normal for long equity |
| **Skew (monthly)** | **+0.28** | ✅ positive-skew objective met |
| Excess kurtosis (daily) | 7.6 | fat tails |
| Tail ratio | 0.91 | — |
| Win rate | 39.6% | lose more often than win (trend-typical) |
| Avg win / loss | **+1.25R / −0.71R** | payoff **1.78** |
| **Expectancy** | **+0.07 R/trade** | positive edge per trade |
| Best / worst trade | **+12.0R** / −3.6R | open-ended right tail ✅ |
| Trades | 2,364 | — |
| Turnover | **10×/yr** | costs are not the story |
| Est. capacity | **~$1.4B** | median name ADV $281M, 2% position, 10% ADV cap |

**Positive skew: YES** (monthly +0.28, R-multiple distribution positive, best
trade +12R vs worst −3.6R, expectancy +0.07R). The defining objective is met.

**The honest weakness is not the drawdown depth (−16%) but its DURATION** —
387 days to recover and ~2.3 years as the longest underwater stretch. For an
"absolute return" product that is a genuine investor-experience problem and
should be weighed heavily.

---

## 2. Stress windows (as-is — NO avoidance fitting)

| Window | Strategy return | Strategy maxDD | Worst day | Eq-wt market |
|---|---|---|---|---|
| 2018-Q4 sell-off | −11.0% | −11.6% | −3.2% | −12.1% |
| 2020 COVID crash | −11.8% | −12.6% | −4.4% | −13.6% |
| 2022 bear | −6.9% | −10.8% | −2.7% | −8.7% |

In **all three** available stress windows the strategy **lost less than the
equal-weight market** — the chandelier stops + regime governor provide modest,
genuine downside cushioning (not crash *alpha*, but it does not amplify losses).
These are the true, un-fitted numbers.

**Critical caveat:** **2008 and the 2010 flash crash are NOT in this data.** The
worst-case left tail — the exact regime this whole philosophy is meant to
survive — is **untested.** This is the single most important open risk.

---

## 3. Did the portfolio achieve the design intent?

| Design goal | Verdict |
|---|---|
| Positive skew | **✅** monthly +0.28, trade-R positive, +12R best trade |
| Small, bounded per-trade loss | **✅** avg loss −0.71R, tight stop; worst −3.6R |
| Survive all regimes | **Partial** — cushioned 2018/2020/2022, but **2008-class untested** |
| Absolute return | **Weak** — +2.8% CAGR and ~2.3y underwater stretches |
| Two negatively-correlated sleeves | **✗** — reduced to one sleeve (MR rejected in Phase 2) |

Net: a **legitimately positive-skew, small-loss, downside-cushioned trend
strategy** — but a **modest-return, single-sleeve** one whose worst-case tail is
unverified. It honors the *risk* philosophy more than the *return* ambition.

---

## 4. Open risks carried into any live decision

1. **Untested 2008-class tail** — must re-run on survivorship-free, 2008-
   inclusive data before trusting "survives all regimes."
2. **Survivorship bias** inflates every absolute number here.
3. **Long underwater periods (~2.3y)** — real drawdown-duration risk.
4. **Single sleeve** — the diversification thesis is unrealized; a genuine
   second stream (managed futures / small-cap reversion) remains future work.
5. **LEAN algorithm still encodes rejected v1** — must be rewritten to trend-v2
   before any paper trading.

---

## 5. Gate — Phase 4 (paper/live staging)

**STOP — awaiting review.** The brief's Phase 4 is paper-trading staging, and it
requires my Phase 3 approval. My honest recommendation is **NOT to advance to
paper staging yet**, because two prerequisites are unmet:

- the worst-case tail is untested (no 2008-class data), and
- the LEAN algorithm doesn't yet match the validated design.

**Recommended path before Phase 4:**
1. **Re-validate on survivorship-free, 2008-inclusive data** (funded QC org or
   CRSP) — this is the highest-value step and gates the "survives all regimes"
   claim.
2. **Rewrite `algorithm/main.py` to trend-v2** and reconcile it against this
   Python baseline.
3. Then, if the tail behaves, proceed to Phase 4 paper staging with the
   pre-live checklist / kill-switch the brief specifies.

Alternatively, if you accept the sandbox caveats for now, I can proceed to
**Phase 4 paper-staging scaffolding** (live-vs-backtest tracking, exposure
monitoring, kill-switch, go/no-go checklist) on trend-v2 as-is — explicitly
labeled provisional. Your call:
- **(A)** Get survivorship-free data + rewrite LEAN algo first *(recommended)*.
- **(B)** Build Phase 4 paper-staging scaffolding now on the sandbox design.
- **(C)** Revisit the return profile (e.g. add leverage to the vol target, or
  the second sleeve) before staging.
