# Quantstrat_v1 — Two-Sleeve Absolute-Return Equity Ensemble

A diversified, absolute-return trading philosophy on liquid US equities that
combines two **structurally negatively-correlated** return streams plus a
regime governor. Design intent: **positive portfolio-level skew, small
per-trade risk, survival in all regimes** — *not* maximum backtest return.

- **Sleeve A** — medium/long-term **trend + cross-sectional momentum**
  (divergent, positive skew). Let winners run, cut losers fast (ATR chandelier).
- **Sleeve B** — short-term **mean reversion** on a *stationary residual*
  z-score (convergent, fat left tail), trend-gated and tightly risk-capped.
- **Regime governor** — simple, few-parameter exposure throttle that goes
  defensive in sustained high-vol / down-trend regimes.

Target runtime: **QuantConnect / LEAN** (Algorithm Framework).

## Phase tracker (gated — STOP for review at each gate)

| Phase | What | Status |
|---|---|---|
| **0** | Research notebook: confirm momentum & reversal, distribution shape, sleeve anti-correlation, residual stationarity | **✅ done (real 10y sandbox).** Premises only *partially* supported — `docs/PHASE0_FINDINGS.md` |
| **1** | Minimal backtest, ≤5–6 params/sleeve, realistic costs | **✅ done.** Net **−1.2%/yr** — costs (MR turnover ~77%/day) dominate; skew negative. `docs/PHASE1_FINDINGS.md` |
| **2** | Robustness (param plateaus, walk-forward, Deflated Sharpe, PBO) | **✅ done.** MR sleeve **rejected** (fails OOS + negative control); trend-only robust but **DSR 0.65<0.95** and daily-skew negative. `docs/PHASE2_FINDINGS.md` |
| **1.5** | Redesign trend sleeve for positive skew (drop MR) | **✅ done.** Positive skew **achieved** (trade-R +3.0, monthly +0.08). `docs/PHASE15_FINDINGS.md` |
| **2-v2** | Re-run robustness battery on trend-v2 | **✅ done.** PBO 0.10, DSR **0.87** (↑ from 0.65), 100% subset-positive; neg-control inconclusive. `docs/PHASE2_V2_FINDINGS.md` |
| **3** | Skew-aware evaluation + historical stress windows | **✅ done.** Sandbox: skew +0.28, maxDD −16%. `docs/PHASE3_FINDINGS.md` |
| **3-deep** | Re-eval on 2005–2026 incl. 2008/2010 (survivor-only) | **✅ done; awaiting review.** **2008 GFC −0.3% vs mkt −31%** (governor works); full-cycle monthly-skew ≈0, **~6y underwater**. `docs/PHASE3_DEEP_FINDINGS.md` |
| 4 | Paper/live staging, monitoring, kill-switch, pre-live checklist | not started |

> No phase begins until the previous gate is approved with **"proceed"**.

## Repo layout

```
algorithm/
  main.py                   LEAN Algorithm Framework (production artifact; untested draft)
research/
  sleeve_research.py        Pure analysis primitives (shared everywhere)
  phase1_backtest.py        Phase 1 engine: sleeves + governor + costs + simulator
  run_phase1.py             Phase 1 baseline driver -> performance + cost breakdown
  phase2_robustness.py      Deflated Sharpe, PBO/CSCV, walk-forward, regime tools
  run_phase2.py             Phase 2 robustness battery
  phase15_trend.py          Redesigned fixed-shares, let-winners-run trend sleeve
  run_phase15.py            Phase 1.5 driver: skew-by-frequency + trade R-multiples
  run_phase2_v2.py          Phase 2 battery re-run on trend-v2
  run_phase3.py             Phase 3 skew-aware metrics + stress windows
  data_yahoo.py             Deep-history loader (2005+, survivor-biased)
  run_phase3_deep.py        Phase 3 re-eval on 2005-2026 incl. 2008/2010
  data_stockanalysis.py     Real daily-price loader (cached) + universes
  run_real_phase0.py        Driver: Phase 0 on REAL data -> findings
  _phase0_real_results.json Raw results from the real run
  phase0_research.ipynb     QuantBook notebook (survivorship-free re-run)
  synthetic_data.py         Synthetic price generator (code validation ONLY)
  run_synthetic_demo.py     Local driver on synthetic data
  _build_notebook.py        Regenerates the notebook from source
  _data_cache/              Cached per-symbol CSVs (gitignored)
docs/
  PHASE0_FINDINGS.md        Findings summary + data-provenance caveats
  ASSUMPTIONS.md            Running assumptions & [CHOICE] log
requirements.txt
```

## Running

**Real Phase 0 (10y daily data, no API key):**
```bash
pip install -r requirements.txt
cd research && python3 run_real_phase0.py      # caches data under _data_cache/
```

**Survivorship-free re-run (recommended once data is available):** open
`research/phase0_research.ipynb` in QuantConnect Research (needs a funded org),
add `sleeve_research.py` to the project, run top-to-bottom with the Option-A
point-in-time universe.

**Local code validation (synthetic):** `cd research && python3 run_synthetic_demo.py`

## Data caveat

The free `stockanalysis.com` source is **survivor-biased** and starts ~2016 (no
2008). It's fine as a development sandbox but absolute returns/tails are
optimistic; re-confirm on survivorship-free, point-in-time data before trusting
them. See `docs/PHASE0_FINDINGS.md §0`.
