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
| **0** | Research notebook: confirm momentum & reversal, distribution shape, sleeve anti-correlation, residual stationarity | **✅ code complete; awaiting real-data run + review** |
| 1 | Minimal LEAN backtest, ≤5–6 params/sleeve, realistic costs | not started |
| 2 | Robustness (param plateaus, walk-forward, Deflated Sharpe, PBO) | not started |
| 3 | Skew-aware evaluation + historical stress windows | not started |
| 4 | Paper/live staging, monitoring, kill-switch, pre-live checklist | not started |

> No phase begins until the previous gate is approved with **"proceed"**.

## Repo layout

```
research/
  sleeve_research.py      Pure analysis primitives (shared by notebook + harness)
  phase0_research.ipynb   QuantBook notebook -> produces the REAL Phase 0 findings
  synthetic_data.py       Synthetic price generator (code validation ONLY)
  run_synthetic_demo.py   Local driver; runs Phase 0 analysis on synthetic data
  _build_notebook.py      Regenerates the notebook from source (reproducible)
docs/
  PHASE0_FINDINGS.md      Findings summary + the data-constraint note
  ASSUMPTIONS.md          Running assumptions & [CHOICE] log
requirements.txt
```

## Running

**Real findings (recommended):** open `research/phase0_research.ipynb` in
QuantConnect Research, add `sleeve_research.py` to the project, run top-to-bottom
with the Option-A point-in-time universe.

**Local code validation (synthetic, no market data needed):**
```bash
pip install -r requirements.txt
cd research && python3 run_synthetic_demo.py
```

## Important constraint

This build environment **cannot reach external market-data vendors** (network
policy blocks them). Real Phase 0 numbers must be generated in QuantBook. The
synthetic harness validates the *code*, not any market claim. See
`docs/PHASE0_FINDINGS.md §0`.
