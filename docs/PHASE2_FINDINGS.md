# Phase 2 — Robustness Report & Overfitting Risk Assessment

**Phase:** 2 — Robustness, NOT optimization.
**Status:** Complete on the sandbox. **Awaiting your review.**
**Date:** 2026-07-01
**Reproduce:** `cd research && python3 run_phase2.py` (writes `_phase2_results.json`).

> Bottom line up front: on honest robustness testing the strategy **does not
> meet its own design objectives.** The mean-reversion sleeve should be
> **rejected**; the trend sleeve is **stable but sub-threshold** and, more
> importantly, **fails the positive-skew objective** because the risk framework
> truncates the right tail. Details below. All numbers are on the survivor-
> biased sandbox and are provisional, but the *robustness conclusions* are
> unlikely to flatter reality.

---

## 1. Parameter robustness — plateau vs knife-edge

Net Sharpe (blend unless noted), varying one parameter:

| Parameter | Sweep → net Sharpe | Shape |
|---|---|---|
| No-trade band | 0.00→−0.07, 0.005→0.00, 0.01→0.03, 0.02→0.09, 0.03→**0.39** | rising, broad (good) |
| Alloc trend | 1.0→**0.65**, 0.75→0.51, 0.5→0.03, 0.25→−0.21, 0.0→−0.25 | monotone in trend weight |
| MR z-entry | 1.0→−0.26, 1.5→0.03, 2.0→0.25, 2.5→**0.54** | **monotone** (fewer MR trades = better) |
| Trend chandelier ATR | 2→0.46, 3→0.65, 4→0.72, 5→**0.82** | **monotone** (wider stop = better) |

**Read:** the band is a genuine plateau. But z-entry and chandelier-ATR are
**monotone, not plateaus** — "trade the MR sleeve less" and "stop the trend
sleeve out less" are *always* better in-sample. Monotone responses with no
interior optimum are a subtle overfitting trap (you'd be tempted to push the
parameter to the edge) and, here, they say the **MR machinery and the tight
trend stop are subtracting value, not adding it.**

---

## 2. Universal-principle test (trend sleeve)

Trend-only net Sharpe across **12 random halves of the universe:
mean 0.30, std 0.12, positive in 100%.** The trend edge is a **broad
cross-sectional principle**, not an artifact of a few symbols. ✅ (The full-
universe number is higher, ~0.65; halving reduces diversification.)

---

## 3. Negative control ("map to market") — BOTH sleeves fail

Annualized Sharpe by index regime (trending = |60d index return| > 10%):

| Sleeve | Trending | Choppy | Expected | Result |
|---|---|---|---|---|
| Trend | 0.29 | 0.37 | trending **>** choppy | ❌ (roughly equal / wrong way) |
| Mean-reversion | **0.98** | 0.10 | choppy **>** trending | ❌ (strongly backwards) |

**This is the most important Phase 2 finding.** The MR sleeve makes almost all
its money in **trending** markets and next to nothing in choppy ones — the exact
opposite of a mean-reversion diversifier. The trend-gate (long dips only above
the 200d MA) has quietly turned the "mean-reversion" sleeve into a **dip-buying
*momentum* overlay.** It is therefore *not* the convergent, negatively-correlated
stream the whole two-sleeve thesis rests on. The trend sleeve, meanwhile, does
not cleanly prefer trends (partly a classification artifact — "trending"
includes crashes, which hurt a long book — but it certainly does not pass).

A model that does *not* map to the market the way its economics predict is
either mis-specified or fitting noise. Here it is mis-specified: the sleeves are
not doing what they were designed to do.

---

## 4. Walk-forward (train / validation / holdout — holdout touched once)

| Config | Train (2016-19) | Validation (2020-21) | **Holdout (2022-26)** |
|---|---|---|---|
| **Trend-only** | Sh +0.64, +4.8%, skew −1.30 | Sh +0.82, +9.6%, skew −0.99 | **Sh +0.59, +6.2%, skew −0.53** |
| Blend 50/50 | Sh +0.20, +1.8%, skew −1.24 | Sh +0.33, +3.8%, skew −0.83 | **Sh −0.28, −2.6%, skew −0.60** |

- **Trend-only is consistent out-of-sample** (Sharpe 0.6–0.8 in all three,
  including the once-touched holdout). Genuinely robust in *stability* terms.
- **The blend fails out-of-sample** — the holdout is negative. The MR sleeve
  destroys OOS performance.
- **Skew is negative in every segment, every config** (−0.5 to −1.3). The
  positive-skew objective is missed throughout, though it improves over time.

---

## 5. Multiple-testing correction

- **PBO (CSCV, 18 configs, 10 splits): 0.00.** The in-sample-best config is
  essentially always the out-of-sample-best too — because trend-heavy configs
  robustly dominate. Selection is **not** overfit. ✅
- **Deflated Sharpe Ratio: 0.65** for the best config (annual Sharpe 0.82 vs a
  deflated benchmark SR0 of 0.70, n_trials ≈ 50). **Fails the 0.95 bar.** ❌
  After honestly penalizing for the ~50 configurations searched and for
  non-normal returns, the headline Sharpe is **not distinguishable from a lucky
  draw.**

The two are not contradictory: the *ranking* of configs is stable (low PBO),
but the *level* of the best Sharpe is too modest to call skill (low DSR).

---

## 6. Overfitting risk assessment

| Risk | Assessment |
|---|---|
| Selection overfitting (PBO) | **Low** — trend-heavy dominates every split. |
| Statistical significance (DSR) | **Fails** — DSR 0.65 < 0.95; edge not proven vs the search. |
| Parameter fragility | **Mixed** — band is a plateau; z-entry and chandelier are monotone (no interior optimum → temptation to push to the edge). |
| Economic mis-specification | **High** — negative control shows neither sleeve behaves as designed; MR is a disguised momentum overlay. |
| Data-driven bias | **High & unresolved** — survivor-biased, ~2016 start (no 2008), large-cap only. Inflates absolute results, hides left tail. |
| Objective failure | **Yes** — negative skew everywhere; the core "positive portfolio skew" goal is not achieved. |

---

## 7. Root cause: the risk framework destroys the intended skew

Trend-following is *supposed* to be positive-skew ("cut losers fast, let winners
run to multiples"). Ours is negative-skew. The parameter sweeps show why: **wider
stops are monotonically better and less MR is monotonically better** — i.e., the
tight chandelier stop and the convergent MR sleeve are both truncating the right
tail. On top of that, **vol-target sizing shrinks a winner exactly as it runs and
its vol rises**, and the **5% name / 1.5× gross caps** clip the large positions
that produce the fat right tail. The very machinery meant to control risk is
suppressing the open-ended upside the philosophy depends on.

---

## 8. Honest verdict & recommendation

The disciplined conclusion, taking robustness over backtest beauty:

1. **Drop the mean-reversion sleeve** in this universe. It is a net drag, fails
   the OOS holdout, and fails the negative control (it is not mean-reversion).
   The two-sleeve negative-correlation thesis **does not hold** in liquid US
   large-caps as implemented. (Phase 0 already hinted: raw reversal was weak and
   the negative correlation only appeared for *market-neutral time-series
   trend*, not this construction.)
2. **The trend sleeve is stable but not yet a keeper:** robust across subsets and
   walk-forward, but (a) Deflated Sharpe fails the significance bar, and (b) it
   is negatively skewed — it fails the project's defining objective.
3. **If we continue, the real work is redesigning the trend sleeve to preserve
   positive skew:** let winners run (remove winner-trimming from vol-targeting,
   or size at entry and don't trim), widen/trail stops, relax caps on winners,
   rebalance less. Re-test whether that produces the positive skew that is the
   entire point — and re-validate on survivorship-free, 2008-inclusive data.

This is the outcome the process is designed to produce: it stopped a
negatively-skewed, cost-fragile, mis-specified strategy from advancing on the
strength of a pretty-but-hollow backtest.

---

## 9. Deliverables

| File | What |
|---|---|
| `research/phase2_robustness.py` | Deflated Sharpe, PBO/CSCV, walk-forward, regime classification |
| `research/run_phase2.py` | Robustness battery driver |
| `research/_phase2_results.json` | Machine-readable results |
| `research/phase1_backtest.py` | +`min_hold`, `rebalance_band`, `combine_and_overlay` refactor |
| `docs/PHASE2_FINDINGS.md` | This report |

---

## 10. Gate

**STOP — awaiting your review.** My recommendation is **not** to proceed to
Phase 3 evaluation on the current design, because it fails its own objectives.
Instead, the highest-value next step is a **Phase 1.5 redesign**: drop MR, and
rebuild the trend sleeve to *keep* positive skew (let winners run), then re-run
Phase 2. Alternatively, if you want to preserve the two-sleeve thesis, we test
the MR sleeve in the universe where reversal actually lives (smaller / less
liquid names) — which needs better data.

Tell me which:
- **(A)** Redesign trend sleeve for positive skew, drop MR, re-test *(recommended)*.
- **(B)** Keep hunting for a working MR sleeve in a different universe (needs data).
- **(C)** Proceed to Phase 3 evaluation on trend-only as-is, documenting that it
  is a modest, negatively-skewed trend strategy (accepting the objective miss).
