# Phase 2 (re-run) — Robustness Validation of the Redesigned Trend Sleeve

**What:** the full Phase 2 battery, re-run on **trend-v2** (`phase15_trend.py`).
**Status:** complete on the sandbox. **Awaiting review.**
**Date:** 2026-07-01 · **Reproduce:** `python3 research/run_phase2_v2.py`
(`_phase2_v2_results.json`).

Verdict: **trend-v2 is materially more robust than the rejected v1.** It passes
the universal-principle and walk-forward tests, is not overfit (PBO 0.10), and
its Deflated Sharpe improved from 0.65 to 0.87 (still < 0.95). The negative
control is inconclusive (weak test instrument). The design's justification
remains **positive skew + positive expectancy**, not a statistically-significant
high Sharpe.

---

## 1. Parameter robustness — plateaus and a clean Sharpe↔skew tradeoff

Sharpe / monthly-skew as each parameter varies:

| Param | Sweep | Shape |
|---|---|---|
| Donchian | 50→.47/+.06, 100→.41/+.08, 150→.44/+.10, 200→.44/+.07 | **flat plateau** ✅ |
| risk_fraction | .001→.38/+.09, .0015→.41/+.08, .002→.44/+.12, .003→.52/+.09 | **stable skew**, Sharpe scales with size ✅ |
| Chandelier ATR | 3→.31/**+.82**, 4→.31/+.28, 5→.41/+.08, 6→.57/−.09, 7→.57/−.32 | **Sharpe↔skew tradeoff** |
| RS top pct | .2→.36/**+.29**, .4→.41/+.08, .6→.48/−.10, 1.0→.49/−.27 | **Sharpe↔skew tradeoff** |

**Key insight:** there is no knife-edge peak anywhere, but two parameters
(stop width, RS selectivity) trade Sharpe against skew. **Wider stops / less
selectivity raise Sharpe but turn skew negative.** Because the project ranks
*positive skew* above Sharpe, the honest default is the **tighter/selective**
end (chandelier ≈4, RS top ≈0.2–0.4 → monthly skew +0.28 to +0.29, Sharpe
≈0.31–0.36), NOT the Sharpe-maximizing wide-stop end. My Phase 1.5 default of
chandelier 5 sits mid-tradeoff (skew +0.08); I now recommend **moving it to 4**
to honor the objective — see §6.

> This also corrects the Phase 2 "wider stop is always better" note: that was
> Sharpe-only. With skew in view, wider is *worse*.

---

## 2. Universal-principle ✅

Across 12 random universe halves: **Sharpe 0.39 ± 0.07, positive in 100%**;
monthly skew positive in **75%**. The edge and (mostly) the skew are a broad
cross-sectional property, not a few names.

---

## 3. Negative control ("map to market") — INCONCLUSIVE

| Index regime | Trend-v2 Sharpe | Ann. return | % days |
|---|---|---|---|
| Up-trend (60d idx > +10%) | 0.41 | +5.2% | 15% |
| Choppy | 0.42 | +4.8% | 81% |
| Down-trend (60d idx < −10%) | 0.01 | +0.0% | 3% |

We wanted trend to **underperform in chop**. It does not — it performs about
equally in up-trends and "chop." But the test is a **weak instrument here**:
(a) 81% of days land in "choppy," so that bucket is really "normal drift," and
(b) a *single-name, long-only* trend book profits from individual leaders
trending even when the *index* chops (cross-sectional dispersion). The one clean
signal — **flat in down-trends (Sharpe 0.01)** — shows the stops + regime
governor are de-risking as intended. A proper negative control for this sleeve
needs a per-name trend/chop split or a buy-and-hold benchmark; **flagged as a
gap, not a pass.**

---

## 4. Walk-forward ✅ (holdout touched once)

| Segment | Sharpe | Monthly skew | Net ann | MaxDD |
|---|---|---|---|---|
| Train (2016–19) | +0.58 | +0.16 | +5.7% | −13.9% |
| Validation (2020–21) | +0.28 | −0.56 | +4.0% | −15.3% |
| Holdout (2022–26) | +0.36 | +0.29 | +4.1% | −15.3% |

Sharpe positive in all three; monthly skew positive in two of three (negative
only in 2020–21, dominated by the COVID crash+rebound). Consistent OOS.

---

## 5. Multiple testing

- **PBO (CSCV, 12 configs): 0.10** — well below 0.5. Selection is **not
  overfit.** ✅
- **Deflated Sharpe: 0.873** (best config annual SR 0.61 vs deflated benchmark
  SR0 0.25, n_trials ≈ 40). **Improved from v1's 0.65** but still **< 0.95.** The
  Sharpe is borderline-not-significant after honest correction. ⚠️

---

## 6. Overall assessment & recommended config

| Test | v1 (rejected) | **trend-v2** |
|---|---|---|
| Positive skew (trade-R / monthly) | ✗ (neg everywhere) | **✅ +3.0 / +0.08–0.29** |
| Universal-principle | mixed | **✅ 100% positive** |
| Walk-forward OOS | blend failed | **✅ positive all segments** |
| PBO | 0.00 | **✅ 0.10** |
| Deflated Sharpe | 0.65 | **0.87 (still <0.95)** |
| Negative control | ✗ (backwards) | **inconclusive (weak instrument)** |

**Recommended default (skew-honoring):** chandelier **4×ATR**, RS top **~0.3**,
donchian 100–150, risk_fraction 0.0015–0.002. That sits on the **positive-skew**
side of the tradeoff (monthly skew ≈ +0.28) at a modest Sharpe (~0.31), which is
the intended prioritization.

**Bottom line:** the redesign is **validated on robustness and its stated
objective (positive skew), with an honestly modest and borderline-significant
Sharpe.** Cleared to proceed to Phase 3 evaluation. Remaining gaps unchanged:
survivorship-free/2008-inclusive data, a proper single-name negative control,
and updating the LEAN algorithm to trend-v2.
