"""Builds research/phase0_research.ipynb (QuantBook / QuantConnect Research).

Run once: python3 research/_build_notebook.py
Kept in the repo so the notebook is reproducible from source.
"""
import nbformat as nbf

nb = nbf.v4.new_notebook()
c = []
md = lambda s: c.append(nbf.v4.new_markdown_cell(s))
co = lambda s: c.append(nbf.v4.new_code_cell(s))

md(r"""# Phase 0 — Research Notebook (no trading yet)
**Two-sleeve absolute-return ensemble on liquid US equities**

Goal of this notebook (per the project brief), run on **real,
survivorship-bias-free, point-in-time QuantConnect data**:

1. **Q1** — Confirm intermediate-horizon **momentum** exists in the
   cross-section (12-1m total return predicts the next month).
2. **Q2** — Confirm short-horizon **reversal** exists (recent 5d losers
   tend to bounce).
3. **Q3** — Characterize the **cross-sectional return distribution**
   (skew / fat tails).
4. **Q4** — Establish that the two sleeves are **negatively correlated**
   as return streams.
5. **Q5** — Verify the Sleeve B residual is **stationary** (ADF / Hurst)
   before trusting a z-score on it.

All analysis math lives in `sleeve_research.py` (add that file to this QC
research project) so the notebook and the local synthetic harness run the
**identical** code path.

> **Data-integrity rules enforced here**
> * Adjusted prices only; signals use **backward** windows, forward returns
>   use `shift(-h)` and are labelled `fwd_*`. No same-bar lookahead.
> * Universe must be built **point-in-time** to avoid survivorship bias — see
>   the universe cell. The quick hard-coded list is for a first look only and
>   is explicitly biased; do **not** trust numbers from it before redoing it
>   survivorship-free.
""")

co(r"""# QuantConnect Research environment
from QuantConnect.Research import QuantBook
from QuantConnect import Resolution, Market
import numpy as np
import pandas as pd

# Same analysis primitives used by the local synthetic harness.
# Add sleeve_research.py to this research project so this import resolves.
import sleeve_research as sr

qb = QuantBook()
START = "2008-01-01"   # include 2008 so the left tail is visible (Phase 3 too)
END   = "2023-12-31"
print("QuantBook ready:", START, "->", END)
""")

md(r"""## Universe construction

Two options. **Option A** (point-in-time, survivorship-free) is the one whose
numbers you can trust. **Option B** is a fast, *survivorship-biased* sanity
look only.
""")

co(r"""# ---- Option A: point-in-time liquid universe (survivorship-free) --------
# Select, as-of each date, US primary-listed common stocks with price > $10 and
# the highest dollar volume. Using Fundamental universe history keeps it
# point-in-time (no restatement / no membership leakage).
def coarse_filter(fundamental):
    liquid = [f for f in fundamental
              if f.has_fundamental_data
              and f.price > 10
              and f.dollar_volume > 5e6]
    liquid = sorted(liquid, key=lambda f: f.dollar_volume, reverse=True)
    return [f.symbol for f in liquid[:200]]   # top-200 by ADV, as-of date

universe = qb.add_universe(coarse_filter)
# universe_history returns the as-of membership for each date (point-in-time).
members = qb.universe_history(universe, START, END)
# Build the union of symbols that were EVER members (we still only USE each
# name on dates it was actually a member -> no survivorship bias in signals).
all_symbols = sorted({s for day in members for s in day}, key=str)
print("distinct names ever in universe:", len(all_symbols))
""")

co(r"""# ---- Option B: quick biased look (DELETE before trusting results) -------
# A small hard-coded liquid list. This IS survivorship-biased (today's known
# liquid names) and is only for smoke-testing the pipeline.
QUICK = ["AAPL","MSFT","JPM","XOM","JNJ","PG","KO","WMT","HD","UNH",
         "CAT","BA","CVX","MRK","PFE","CSCO","INTC","T","VZ","DIS",
         "MCD","NKE","IBM","GE","MMM","HON","LOW","TXN","ORCL","QCOM"]
USE_QUICK = False  # set True only for a smoke test
if USE_QUICK:
    syms = [qb.add_equity(t, Resolution.DAILY).symbol for t in QUICK]
else:
    syms = [qb.add_equity(str(s).split()[0], Resolution.DAILY).symbol
            for s in all_symbols]
print("symbols attached:", len(syms))
""")

co(r"""# ---- Pull adjusted daily history -> price panel (dates x symbols) -------
hist = qb.history(syms, START, END, Resolution.DAILY)
# QC returns a multi-index (symbol, time) frame; pivot close to a wide panel.
prices = (hist["close"].unstack(level=0)
          if isinstance(hist.index, pd.MultiIndex) else hist)
prices.index = pd.to_datetime(prices.index)
prices = prices.sort_index()
print("price panel:", prices.shape, prices.index.min().date(),
      "->", prices.index.max().date())
prices.iloc[:3, :5]
""")

md(r"""## Q1 — Intermediate-horizon momentum (12-1m) predicts the cross-section
Positive mean rank-IC ⇒ momentum ranks future winners above losers.""")
co(r"""mom = sr.momentum_signal(prices, lookback=252, skip=21)
fwd_1m = sr.forward_return(prices, 21)
ic_mom = sr.rank_ic(mom, fwd_1m)
print(pd.Series(sr.ic_summary(ic_mom)))
ic_mom.rolling(63).mean().plot(title="Momentum rank-IC (63d rolling mean)");
""")

md(r"""## Q2 — Short-horizon reversal (5d) predicts the cross-section
Signal is the **negative** of recent 5d return; positive mean IC ⇒ recent
losers bounce.""")
co(r"""rev = sr.reversal_signal(prices, window=5)
fwd_1w = sr.forward_return(prices, 5)
ic_rev = sr.rank_ic(rev, fwd_1w)
print(pd.Series(sr.ic_summary(ic_rev)))
ic_rev.rolling(63).mean().plot(title="Reversal rank-IC (63d rolling mean)");
""")

md(r"""## Q3 — Cross-sectional return distribution (skew / fat tails)
We need to know the *shape* of returns — positive skew and where the left tail
lives — to size for survival later.""")
co(r"""dist = sr.cross_sectional_distribution(prices, horizon=21)
print(pd.Series(dist))
fwd = sr.forward_return(prices, 21).iloc[::21].stack().dropna()
fwd.plot(kind="hist", bins=80, title="Pooled cross-sectional 21d returns");
""")

md(r"""## Q4 — The two sleeves as return streams, and their correlation
Build each sleeve as a dollar-neutral, equal-weight tercile long/short **daily
return stream** (lagged 1 bar, no costs yet — costs arrive in Phase 1). The
core thesis is that these two streams are **negatively correlated**, so the
blend has higher risk-adjusted return and better skew than either alone.""")
co(r"""sleeve_a = sr.long_short_returns(prices, mom, rebalance_every=21, n_groups=3, lag=1)
sleeve_b = sr.long_short_returns(prices, rev, rebalance_every=5,  n_groups=3, lag=1)
a, b = sleeve_a.align(sleeve_b, join="inner")
print("Sleeve A (momentum):"); print(pd.Series(sr.distribution_stats(a)))
print("\nSleeve B (reversal):"); print(pd.Series(sr.distribution_stats(b)))
print(f"\nCROSS-SLEEVE CORRELATION: {a.corr(b):+.3f}")
blend = 0.5 * a + 0.5 * b
print("\n50/50 blend:"); print(pd.Series(sr.distribution_stats(blend)))
(1 + pd.DataFrame({"A_momentum": a, "B_reversal": b, "blend": blend})
 ).cumprod().plot(title="Gross-of-cost cumulative return (Phase 0, no frictions)");
""")

md(r"""## Q5 — Is the Sleeve B residual stationary?
The mean-reversion sleeve trades the z-score of a residual (price / MA − 1).
That is only valid if the residual is **stationary**. ADF p<0.05 ⇒ reject unit
root; Hurst<0.5 ⇒ mean-reverting.""")
co(r"""stat = sr.residual_stationarity_panel(prices, ma_window=20, max_names=150)
print(stat.describe().loc[["mean", "min", "max"]])
print("\nFraction ADF p<0.05 (stationary):",
      f"{(stat['adf_p'] < 0.05).mean():.0%}")
print("Mean Hurst:", f"{stat['hurst'].mean():.3f}  (<0.5 => mean-reverting)")
""")

md(r"""## Findings summary (fill in from the REAL QuantBook run above)

| Question | Metric | Result | Verdict |
|---|---|---|---|
| Q1 momentum | mean rank-IC, t-stat | … | exists? |
| Q2 reversal | mean rank-IC, t-stat | … | exists? |
| Q3 distribution | skew, excess kurtosis, tail ratio | … | fat-tailed / skew? |
| Q4 sleeves | cross-sleeve corr; blend vs sleeve Sharpe & skew | … | negatively correlated? |
| Q5 stationarity | % ADF<0.05; mean Hurst | … | residual stationary? |

**Honesty checklist before declaring Phase 0 done**
- [ ] Universe built with Option A (point-in-time), not the biased quick list.
- [ ] ICs reported with t-stats; weak/insignificant results stated as such.
- [ ] Distribution shape characterized (don't assume normality downstream).
- [ ] Negative cross-sleeve correlation is *measured*, not assumed.
- [ ] Any sub-period where an effect disappears is noted (regime dependence).

See `docs/PHASE0_FINDINGS.md` for the write-up template and
`docs/ASSUMPTIONS.md` for the running assumptions log.
""")

nb["cells"] = c
nb["metadata"] = {"language_info": {"name": "python"},
                  "kernelspec": {"name": "python3",
                                 "display_name": "Python 3",
                                 "language": "python"}}
with open("phase0_research.ipynb", "w") as f:
    nbf.write(nb, f)
print("wrote phase0_research.ipynb with", len(c), "cells")
