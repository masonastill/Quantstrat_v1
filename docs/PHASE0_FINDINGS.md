# Phase 0 — Findings Summary

**Project:** Two-sleeve absolute-return ensemble on liquid US equities
**Phase:** 0 — Research notebook (no trading yet)
**Status:** Code complete and validated; **real-market findings pending** a
QuantBook run (see the data constraint below).
**Date:** 2026-06-30

---

## 0. Read this first — the data constraint (no spin)

The build environment's network policy **blocks every external market-data
host** (Yahoo, Stooq, AlphaVantage, Nasdaq Data Link, Tiingo all return HTTP
403 at the proxy). Only package registries (PyPI) are reachable. Therefore I
**could not pull real price data here** to confirm the hypotheses empirically.

This is handled honestly, not papered over:

1. The real deliverable is **`research/phase0_research.ipynb`**, which runs in
   **QuantConnect Research (`QuantBook`)** — the correct source anyway, because
   it is survivorship-bias-free, point-in-time, and corporate-action adjusted,
   and it is native to the LEAN target. **You run it there to get the real
   numbers.**
2. All analysis math is in **`research/sleeve_research.py`** — pure
   pandas/numpy/scipy/statsmodels, no QC dependency — so the notebook and the
   local harness exercise the *identical* code.
3. **`research/run_synthetic_demo.py`** runs *here* on synthetic data to prove
   the code is correct and show representative output. **Those numbers are from
   synthetic data and are evidence about the code only — not about markets.**

> Until the notebook is run on QuantBook, treat every market claim below as
> **UNCONFIRMED**. The synthetic results only demonstrate the measurement
> apparatus works and has the right sign behaviour.

---

## 1. What Phase 0 set out to test

| # | Hypothesis | How it is tested |
|---|---|---|
| Q1 | Intermediate-horizon **momentum** exists cross-sectionally | Mean Spearman rank-IC between 12-1m total return and next-21d return, with t-stat |
| Q2 | Short-horizon **reversal** exists cross-sectionally | Mean rank-IC between −(5d return) and next-5d return, with t-stat |
| Q3 | Cross-sectional returns are **fat-tailed / skewed** | Skew, excess kurtosis, 5% tail ratio, VaR/CVaR on pooled forward returns |
| Q4 | The two sleeves are **negatively correlated** return streams | Build each as a dollar-neutral tercile L/S daily stream; correlate; compare blend vs sleeves |
| Q5 | The Sleeve B **residual is stationary** | ADF p-value and Hurst exponent on each name's (price/MA−1) residual |

---

## 2. Synthetic-data validation results (CODE CHECK ONLY — not market evidence)

From `python3 research/run_synthetic_demo.py`, seed=7, 80 names × ~8y. The
synthetic generator embeds a persistent drift (momentum) and a fast OU
deviation (reversal) by construction, so a *correct* measurement should detect
both with the right sign:

| Question | Synthetic result | Interpretation (of the **code**) |
|---|---|---|
| Q1 momentum | mean IC **+0.376**, t≈156 | Code detects embedded momentum (sign +, as built) |
| Q2 reversal | mean IC **+0.182**, t≈73 | Code detects embedded reversal (sign +, as built) |
| Q3 distribution | skew **+0.29**, excess kurt **+0.23**, tail ratio **1.16** | Code measures skew/fat tails correctly |
| Q4 sleeves | corr **−0.116**; blend Sharpe **10.6** vs A **7.0**, B **7.2**; blend vol *below* either sleeve | Code measures negative correlation and the diversification/skew benefit |
| Q5 stationarity | **100%** of names ADF p<0.05; mean Hurst 0.61* | ADF/Hurst wired correctly |

\* The Hurst on the *raw price* reads >0.5 (prices trend); the ADF on the
*residual* reads stationary — exactly the split the philosophy relies on. The
Sharpe values are absurdly high because synthetic data has clean embedded
structure and **zero trading costs**; real-market ICs are an order of magnitude
smaller and costs are material (both addressed in Phase 1).

**Conclusion of Section 2:** the analysis pipeline is correct and ready to run
on real data.

---

## 3. Real-market findings — TO BE COMPLETED in QuantBook

Run `research/phase0_research.ipynb` (Option A point-in-time universe) and fill:

| Question | Metric | Real result | Verdict |
|---|---|---|---|
| Q1 momentum | mean rank-IC, t-stat | _TBD_ | _exists? strength?_ |
| Q2 reversal | mean rank-IC, t-stat | _TBD_ | _exists? strength?_ |
| Q3 distribution | skew, excess kurt, tail ratio, CVaR95 | _TBD_ | _fat-tailed / skew sign?_ |
| Q4 sleeves | cross-sleeve corr; blend vs sleeve Sharpe & skew | _TBD_ | _negatively correlated?_ |
| Q5 stationarity | % ADF<0.05; mean Hurst | _TBD_ | _residual stationary enough?_ |

**Expected (from literature, to be verified not assumed):** intermediate
momentum rank-IC ~ +0.02–0.05; short-term reversal rank-IC ~ +0.02–0.05;
cross-sectional returns right-skewed at the single-name level with fat tails;
momentum L/S and short-term-reversal L/S **negatively correlated** (momentum
crashes coincide with sharp reversal rallies). If the real data contradicts any
of these, **the strategy thesis is weakened and we say so before proceeding.**

---

## 4. Honesty / risk flags raised in Phase 0

- **Survivorship bias:** Option B (hard-coded list) is biased and is for smoke
  testing only. Trustworthy numbers require Option A point-in-time membership.
- **Lookahead:** signals use backward windows only; forward returns use
  `shift(-h)`; portfolio returns are lagged ≥1 bar. Verified in code.
- **Multiple testing:** even in Phase 0 we are choosing lookbacks (252/21/5).
  These are *conventional* defaults, not optimized, but the search budget must
  still be carried into the Phase 2 Deflated-Sharpe / PBO accounting.
- **Costs excluded by design in Phase 0** — Q4 streams are gross. A
  negative-correlation, high-turnover reversal sleeve can look great gross and
  die after costs; Phase 1 introduces realistic frictions before any verdict.
- **Synthetic ≠ market:** nothing in Section 2 is evidence about real returns.

---

## 5. Deliverables (this phase)

| File | What it is |
|---|---|
| `research/sleeve_research.py` | Pure, tested analysis primitives (shared code path) |
| `research/phase0_research.ipynb` | QuantBook notebook — **produces the real findings** |
| `research/synthetic_data.py` | Synthetic generator (code validation only) |
| `research/run_synthetic_demo.py` | Local driver that ran Section 2 |
| `docs/PHASE0_FINDINGS.md` | This summary |
| `docs/ASSUMPTIONS.md` | Running assumptions log |

---

## 6. Gate

**STOP — awaiting review.** Per the workflow I will not start Phase 1 (the
minimal LEAN backtest) until you say **"proceed"**. If you have QuantBook
access, the highest-value next step is to run the notebook and paste the real
Q1–Q5 numbers so we confirm the hypotheses on real data before writing any
trading code.
