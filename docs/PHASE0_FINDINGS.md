# Phase 0 — Findings Summary

**Project:** Two-sleeve absolute-return ensemble on liquid US equities
**Phase:** 0 — Research notebook (no trading yet)
**Status:** **Complete on real data** (with the data caveats below). Awaiting
your review before Phase 1.
**Date:** 2026-06-30
**Reproduce:** `cd research && python3 run_real_phase0.py` (raw results cached in
`research/_phase0_real_results.json`).

---

## 0. Data provenance and its limits (read first — no spin)

The original build environment blocked all market-data hosts. After the network
policy was widened, **QuantConnect's API turned out to require a paid org**, so
that route is closed for this account. The working data source is
**`stockanalysis.com`** (open JSON endpoint, no key): **~10 years of daily
split/dividend-adjusted prices**, 2016‑06 → 2026‑06, for **296 liquid US
large/mid-caps**.

Three limitations that bound every conclusion here:

1. **Survivorship bias.** Only currently-listed names exist in this source.
   Delisted blowups (Lehman, Bear, WorldCom, 2008‑09 and 2000‑02 failures) are
   absent. This **inflates absolute long-side returns and hides part of the left
   tail.** Cross-sectional rank-ICs and the cross-sleeve correlation are fairly
   robust to it; **absolute performance and tail metrics are OPTIMISTIC.**
2. **Short history (~2016→).** Covers 2018‑Q4, 2020‑COVID and 2022, but **not
   2008 or the 2010 flash crash** — the worst left-tail regimes are missing.
3. **Large/mid-cap only, ~300 names.** Momentum and (especially) short-term
   reversal are known to be weakest in mega-caps; this universe is a hard test
   for them and an easy one for survivorship inflation.

**Bottom line on data:** good enough to *characterize* the premises and reject
or support them directionally; **not** good enough to trust absolute returns,
tails, or capacity. Those require survivorship-free, point-in-time data (CRSP,
or QC with a funded org) and a longer history. The QuantBook notebook
(`research/phase0_research.ipynb`) is retained for exactly that re-run.

---

## 1. Results (real data, 296 names, 2016–2026)

| # | Question | Result | Honest verdict |
|---|---|---|---|
| Q1 | Intermediate **momentum** (12-1m → 21d) | mean rank-IC **+0.006**; naive t=1.2, **non-overlapping t=0.27** | **Not significant.** Weak/absent in this universe & period. |
| Q2 | Short-horizon **reversal** (5d → 5d) | mean rank-IC **+0.013**; naive t=3.7, **non-overlapping t=1.40** | **Not significant**, but the stronger of the two and right-signed. |
| Q3 | Cross-sectional return **distribution** | skew **+0.13**, excess kurtosis **+6.3**, tail ratio **1.29** | **Fat-tailed, mild positive skew** — supports skew-harvesting premise. |
| Q4 | Cross-sectional momentum vs reversal **correlation** | **+0.044** | **NOT negatively correlated** — roughly uncorrelated. Thesis fails at the raw cross-sectional-factor level. |
| Q5 | Sleeve B **residual stationarity** | **100%** of names ADF p<0.05; mean Hurst **0.48** | **Confirmed** — the MR z-score rests on a genuinely stationary residual. |
| Q6 | **Time-series trend** vs reversal (faithful thesis test) | dollar-neutral trend vs reversal corr **−0.30**; long-biased trend vs reversal **+0.13**, and **+0.29 in the worst 5% of market days** | **Thesis holds only for market-NEUTRAL constructions.** A long-biased trend sleeve co-crashes with reversal. |

### The two findings that matter most

**(a) The raw factor edges are weak and not statistically significant here.**
The naive t-stats (momentum 1.2, reversal 3.7) are inflated by overlapping
forward returns. Sampled non-overlapping, momentum t=0.27 and reversal t=1.40 —
neither clears significance. Broadening 104→296 names did **not** help momentum
(it got weaker). This does *not* prove the effects are absent in general
(literature finds them mainly in broader, smaller, longer cross-sections and
they had a poor 2016–2026 run), but **we cannot claim an edge from this data.**

**(b) "Structurally negatively correlated" is conditional, not free.**
- Cross-sectional **momentum L/S** vs reversal: **+0.04** (≈ uncorrelated).
- Dollar-neutral **time-series trend** vs reversal: **−0.30** ✅ (thesis works).
- **Long-biased** trend vs reversal: **+0.13**, rising to **+0.29 on the worst
  market days** ❌ — they bleed together exactly when you need the hedge.

So the diversification the strategy depends on **requires both sleeves to be
market-neutral** (or the trend sleeve to be genuinely positive-skew via its
exits so it *pays off* in the crashes where reversal bleeds). A naively
long-biased trend book does not hedge the reversal sleeve in stress.

### A premise that did NOT survive contact with data
The brief labels Sleeve A (trend/momentum) as **positive skew**. In this data:
- Cross-sectional momentum L/S skew = **−1.41** (classic *momentum crashes*).
- A crude 200-day-MA trend filter skew = **−0.84** (whipsaw), and it **added
  nothing over just holding the equal-weight market** (Sharpe 0.89 vs 1.04) in
  this bull decade.

**Positive skew is not a property of "trend" per se — it must be *engineered*
by the asymmetric exit (chandelier trailing stop: cut losers fast, let winners
run).** That construction is exactly what Phase 0 did *not* build, so its skew
is unmeasured. **This is the single most important thing to prove in Phase 1**;
if the exit logic doesn't deliver positive skew, the whole "positive portfolio
skew" thesis is in doubt.

---

## 2. What this means for Phase 1 (recommended adjustments)

1. **Don't lean on raw cross-sectional factors for the edge.** They're weak
   here. The value, if any, must come from construction: asymmetric trailing-stop
   exits (skew), volatility targeting, the regime governor, and trend-gating the
   mean-reversion sleeve.
2. **Keep both sleeves market-neutral, or make the trend sleeve genuinely
   positive-skew**, so the −0.30 (not +0.13) correlation regime is the one we
   actually run in. Verify the correlation *and the tail co-movement* of the
   real sleeves, not just the all-period correlation.
3. **Phase 1's first deliverable should test skew of the chandelier-exit trend
   sleeve directly** — that's the load-bearing assumption.
4. **Treat all absolute numbers as provisional** until re-run on
   survivorship-free, 2008-inclusive data.

---

## 3. Sanity check — synthetic harness (code validation only)

`python3 research/run_synthetic_demo.py` runs the identical primitives on
synthetic data with momentum + reversal embedded by construction; it correctly
recovers both (IC +0.38 / +0.18), a negative cross-sleeve correlation, and 100%
stationary residuals. This only proves the measurement code is correct — it is not
market evidence. (The real data above is the evidence.)

---

## 4. Honesty / risk flags

- **Survivorship + short history + large-cap-only** all bias *toward* looking
  better than reality on absolute terms while *understating* the factor edges.
- **Multiple testing:** two horizons (12-1m, 5d) and two universes (104, 296)
  were tried. Small search, but it still counts toward the Phase 2 Deflated-
  Sharpe / PBO budget. No parameter was tuned to maximize anything.
- **Costs excluded** (Phase 0 streams are gross). The reversal sleeve is
  high-turnover; its thin gross edge (IC 0.013) may not survive costs — a real
  risk Phase 1 must settle before any verdict.
- **Lookahead:** signals use backward windows only; forward returns use
  `shift(-h)`; portfolio weights lagged ≥1 bar. Verified in code.

---

## 5. Deliverables

| File | What it is |
|---|---|
| `research/sleeve_research.py` | Pure, lookahead-safe analysis primitives (shared code path) |
| `research/data_stockanalysis.py` | Real daily-price loader (cached) + universes; survivorship warning in-module |
| `research/run_real_phase0.py` | Driver that produced Section 1 |
| `research/_phase0_real_results.json` | Raw machine-readable results |
| `research/phase0_research.ipynb` | QuantBook notebook for the survivorship-free re-run |
| `research/synthetic_data.py`, `run_synthetic_demo.py` | Code-validation harness |
| `docs/PHASE0_FINDINGS.md`, `docs/ASSUMPTIONS.md` | This summary + assumptions log |

---

## 6. Gate

**STOP — awaiting your review.** My honest read: the project's *premises are
only partially supported*. Positive skew + fat tails + a stationary MR residual
are real; **a reliable raw factor edge and an automatic negative sleeve
correlation are not.** The thesis can still work, but only if Phase 1 *earns*
the positive skew through the exit construction and keeps both sleeves neutral.

Two decisions for you before I proceed to Phase 1:
1. **Data:** proceed on this survivor-biased 10y set as a development sandbox
   (fast, free) and defer the survivorship-free re-run to a Phase 2 gate — or
   block until we secure better data (funded QC org / CRSP)?
2. **Scope:** want me to start Phase 1 by building the chandelier-exit trend
   sleeve and *measuring its skew first* (my recommendation), before any blend?

Say **"proceed"** (with your answers to 1–2) and I'll start Phase 1.
