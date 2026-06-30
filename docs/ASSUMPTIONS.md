# Assumptions & Choices Log

A single running list of every assumption and `[CHOICE]` made, so nothing is
hidden. Each entry: what, the value picked, why, and the risk it carries.
Updated every phase.

## Phase 0

### Data
- **Source ACTUALLY USED for Phase 0:** `stockanalysis.com` open JSON endpoint
  (no key), ~10y daily split/dividend-adjusted prices, 296 liquid US large/mid
  caps, 2016→2026. *Why:* QuantConnect's API requires a paid org (free account
  can't get a token); free vendors (Yahoo/Stooq) were IP-blocked or behind a
  bot wall. *Risk:* **survivor-biased, ~2016-start, large-cap-only** — inflates
  absolute returns, hides left tail, understates factor edges. Cross-sectional
  ICs and the cross-sleeve correlation are the robust takeaways; absolute/tail
  metrics are provisional. **Must be re-confirmed on survivorship-free,
  point-in-time data.**
- **Survivorship-free re-run path:** QuantConnect `QuantBook` notebook is kept
  for when a funded QC org (or CRSP) is available.
- **History window (real run):** 2016-06 → 2026-06. *Limitation:* omits 2008 and
  the 2010 flash crash — the worst left-tail regimes. Phase 3 stress testing
  needs a longer, survivorship-free history.
- **Prices:** split/dividend-adjusted close. *Risk:* adjusted prices can leak
  if mishandled; mitigated by using backward-only signal windows and never
  trading on the adjustment itself.

### Universe (Phase 0 research)
- **Filter:** US primary-listed, `price > $10`, `dollar_volume > $5M`,
  top-200 by ADV, selected **as-of each date** (point-in-time).
  *Why:* liquid, tradable, avoids penny-stock noise; point-in-time avoids
  survivorship bias. *Risk:* top-200 is a `[CHOICE]`; revisit breadth in
  Phase 2 universal-principle test.
- **Quick list (Option B):** explicitly survivorship-biased, smoke-test only,
  `USE_QUICK=False` by default.

### Signals (conventional defaults — NOT optimized)
- **Momentum (Sleeve A):** 12-1m = `lookback=252`, `skip=21`. *Why:* classic
  Jegadeesh–Titman / skip-a-month to dodge short-term reversal. *Risk:* one of
  several reasonable windows; robustness tested in Phase 2.
- **Reversal (Sleeve B):** `window=5` trading days; signal = −(5d return).
  *Why:* short-horizon reversal is a ~1-week effect. *Risk:* horizon `[CHOICE]`.
- **MR residual:** `price / MA(20) − 1`, z-scored over `5×20=100` days.
  *Why:* a stationary, dimensionless state variable; never trade raw price.
- **Time-series trend proxy (Q6):** name in uptrend if `price > MA(200)`.
  *Why:* a crude faithful-er proxy for Sleeve A than cross-sectional momentum,
  to test trend-vs-reversal correlation. *Risk:* an on/off MA filter is NOT the
  chandelier-exit strategy and does not capture its skew — used only for the
  correlation study, not as a performance claim.
- **Universe breadth test:** ran both a 104-name and a 296-name list to check
  whether weak edges were a mega-cap artifact (they were not).

### Portfolio-stream construction (for the correlation test only)
- **Books:** dollar-neutral, equal-weight **terciles** (`n_groups=3`), long top
  / short bottom. *Why:* simplest robust cross-sectional spread.
- **Rebalance:** momentum every 21d, reversal every 5d; weights held between.
- **Lag:** ≥1 bar between signal and earned return (no same-bar lookahead).
- **Costs:** **excluded in Phase 0 by design.** Frictions (commission,
  slippage, spread, borrow, impact) are introduced in Phase 1 before any
  performance verdict.

### Statistics
- **Predictive power:** Spearman **rank**-IC (robust to fat tails) with a naive
  t-stat (`mean/std·√n`). *Risk:* overlapping/​autocorrelated IC inflates the
  t-stat; treat magnitudes, not the headline t, as the signal. Proper
  multiple-testing correction (Deflated Sharpe, PBO) is a Phase 2 deliverable.
- **Stationarity:** ADF (`autolag=AIC`) p<0.05 to reject unit root; Hurst via
  variance-of-lagged-differences, <0.5 ⇒ mean-reverting.

### Synthetic data (validation only)
- 80 names × ~8y, seed=7. Persistent AR(1) drift ⇒ momentum; fast OU deviation
  (`phi=0.60`) ⇒ reversal; GARCH-like market factor ⇒ regime/vol clustering.
  *Purpose:* exercise the code; **not** evidence about real markets.

## Open `[CHOICE]`s deferred to later phases
- `risk_fraction` per trade (0.10%–0.25%) — Phase 1 sizing.
- Portfolio vol target (8%–12% annualized) — Phase 1.
- Gross/net leverage caps (e.g. gross ≤ 1.5×), sector/sub-sector caps — Phase 1.
- Short leg on/off (borrow & liquidity gated) — Phase 1.
- Regime-governor thresholds (index MA length, realized-vol cutoff) — Phase 1.
- Extension to liquid futures for true diversification — post-Phase 3.
