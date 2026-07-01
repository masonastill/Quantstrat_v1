# Phase 1.5 — Trend Sleeve Redesign for Positive Skew

**Phase:** 1.5 — targeted redesign after the Phase 2 verdict (Option A: drop MR,
rebuild trend to preserve positive skew).
**Status:** Complete on the sandbox. **Awaiting your review.**
**Date:** 2026-07-01
**Reproduce:** `cd research && python3 run_phase15.py` (writes `_phase15_results.json`).

---

## 1. What changed and why

Phase 2 root-caused the negative skew: the weight-target engine **trimmed
winners** (vol-target sizing shrank a position as it ran and its vol rose),
**capped** large positions at 5%, and **re-traded daily**. That truncates the
right tail trend-following depends on.

`phase15_trend.py` replaces that with a **position-based, fixed-shares** engine:

| Skew-killer (old) | Redesign (new) |
|---|---|
| Vol-target trims winners daily | **Size once at entry; hold shares fixed** — winners' weight is allowed to grow |
| 5% name cap clips winners | **Winner cap 20%** (entry sized ~1.5–3%); winners may run up ~10× before any trim |
| Tight 3×ATR stop | **Wide 5×ATR chandelier** — give winners room |
| Daily rebalance churn | **Trade only on entries + stop-exits** → turnover 83×→**7.5×/yr** |
| MR sleeve (convergent, neg-skew) | **Dropped** (Phase 2: net drag, failed OOS + negative control) |
| Regime governor trims book | Governor **halts new entries** in stress; never force-trims winners |

Fixed small downside (stop) + open-ended upside (let winners run) = the positive
skew the project is built around.

---

## 2. Did it achieve positive skew? — measure at the RIGHT frequency

**Daily skew of *any* long-equity book is negative** (crashes gap down intraday,
rallies grind). The philosophy's positive skew lives at **trade level** and at
**monthly+ horizons**, and that is exactly where it now shows up:

| Return frequency | Skew |
|---|---|
| Daily | −0.97 |
| Weekly | −1.08 |
| **Monthly** | **+0.08** |
| **Quarterly** | **+0.62** |

**Trade-level R-multiples (2,049 closed round-trips) — the definitive test:**

| Metric | Value |
|---|---|
| Win rate | 40.3% |
| Avg win / avg loss | **+1.35R / −0.70R** (payoff 1.93) |
| Expectancy | **+0.125 R / trade** |
| Best / worst | **+17.4R** / −3.7R |
| **Skew of R-multiples** | **+3.00** |
| % trades > +3R / % < −1R | 4.4% / 13.2% |

The R-multiple distribution is the textbook let-winners-run shape: **lose small
and often, win big occasionally.** Positive skew objective: **ACHIEVED** (monthly
+0.08, quarterly +0.62, trade-R +3.0).

> Honest note: my first pass flagged skew "still negative" off the *daily*
> number. That was a measurement-frequency error on my part — corrected here.
> Daily/weekly skew remaining negative is normal and not a defect.

---

## 3. Performance (net of costs, sandbox)

| Metric | Value |
|---|---|
| CAGR | +4.1% |
| Ann. vol | 11.4% |
| Sharpe | **0.41** |
| Sortino | 0.44 |
| Max drawdown | **−16.0%** |
| Calmar | 0.26 |
| Turnover | **7.5×/yr** (was 83×) |

Costs are no longer the story (turnover cut ~11×). Drawdown improved
(−16% vs −28% for the Phase-1 blend). **Sharpe is modest (~0.4)** — this is a
positive-expectancy, positive-skew trend book, not a high-Sharpe machine (and
that is the intended trade-off: positive skew usually *costs* Sharpe).

---

## 4. Robustness

**Walk-forward (holdout touched once):** positive Sharpe in all three segments —
train +0.58, validation +0.28, holdout +0.36 — with holdout monthly-ish skew
improving (daily-segment skew −1.52 / −1.39 / −0.16). The edge and the skew
character both survive out-of-sample.

**Skew/Sharpe across the two skew knobs** (chandelier ATR × winner cap):
daily skew −0.90…−0.97 (winner cap barely binds), Sharpe rises with wider stops
(4×→0.31, 5×→0.41, 6×→0.57). Consistent with Phase 2 (wider stops better); no
knife-edge, but note Sharpe is **monotone in stop width**, so I deliberately did
NOT chase it — 5×ATR is a sensible mid, not the max.

---

## 5. What is NOT yet done (honest gaps)

- **Full Phase 2 battery not re-run on the redesign** — Deflated Sharpe / PBO /
  negative-control should be repeated for trend-v2 before calling it robust.
  (Given Sharpe ~0.4 and ~50 configs searched, DSR may again be sub-threshold —
  the *skew*, not the Sharpe, is this design's justification.)
- **Survivorship-free, 2008-inclusive data still pending.** Everything here is
  the biased sandbox; the −16% max drawdown especially would look worse with
  2008/2020-with-delistings included.
- **Single sleeve now** — dropping MR means the "two structurally negatively-
  correlated streams" thesis is not realized. This is an honest scope change:
  we have a positive-skew trend sleeve, not yet a diversified two-sleeve
  ensemble. A genuine diversifier (managed futures / a real reversion book in
  the right universe) is a separate future workstream.

---

## 6. Verdict & gate

**The redesign met its stated objective:** positive skew (trade-R +3.0, monthly
+0.08, quarterly +0.62), positive per-trade expectancy (+0.125R), controlled
drawdown (−16%), and turnover cut ~11×. The cost is a modest Sharpe (~0.4) and
the loss of the second sleeve.

**STOP — awaiting review.** Options:
- **(A)** Re-run the full Phase 2 robustness battery (DSR/PBO/negative-control)
  on trend-v2 to formally validate before Phase 3 *(recommended — cheap, closes
  the gap in §5)*.
- **(B)** Proceed to Phase 3 evaluation (full skew-aware metrics + stress
  windows) on trend-v2 as the deliverable.
- **(C)** Re-introduce a *genuine* diversifier sleeve (managed-futures-style
  trend on liquid futures, or reversion in a small-cap universe) to rebuild the
  two-sleeve thesis — needs additional data.

My recommendation: **(A) then (B)** — formally validate the redesign, then
evaluate it, before deciding whether to invest in a second sleeve (C).
