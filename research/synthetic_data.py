"""
Synthetic cross-section of equity prices for CODE VALIDATION ONLY.

>>> This is NOT real market data and proves NOTHING about real markets. <<<

Its single purpose is to exercise research/sleeve_research.py end-to-end so we
can confirm the analysis code is correct and see representative output, while
the environment cannot reach a real data vendor. The real Phase 0 findings must
be produced by running research/phase0_research.ipynb against QuantConnect's
survivorship-bias-free QuantBook data.

Generative model (per name i, daily, log space)
------------------------------------------------
  r_i,t = beta_i * m_t                # common market factor (regime / vol clustering)
        + g_i,t                       # slow persistent drift  -> intermediate MOMENTUM
        + (d_i,t - d_i,t-1)           # fast OU reversion incr. -> short-term REVERSAL
        + eps_i,t                     # idiosyncratic noise

By construction the panel contains BOTH a persistent (trend) component and a
mean-reverting component, so a correct momentum measure and a correct reversal
measure should each detect a positive edge. We then read the realised
cross-sleeve correlation off the data rather than asserting it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def make_market(n_days: int, rng: np.random.Generator) -> np.ndarray:
    """Market daily returns with GARCH-like volatility clustering."""
    w, a, b = 1e-6, 0.08, 0.90
    sig2 = w / (1 - a - b)
    out = np.empty(n_days)
    shock = 0.0
    for t in range(n_days):
        sig2 = w + a * shock**2 + b * sig2
        shock = rng.normal(0, np.sqrt(sig2))
        out[t] = 0.0002 + shock          # small positive drift
    return out


def generate_panel(n_names: int = 80, n_days: int = 252 * 8, seed: int = 7,
                   start: str = "2016-01-04") -> pd.DataFrame:
    """Return a (n_days x n_names) panel of synthetic adjusted prices."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start=start, periods=n_days)
    syms = [f"SYN{i:03d}" for i in range(n_names)]

    market = make_market(n_days, rng)
    beta = rng.uniform(0.6, 1.4, n_names)

    # slow persistent drift g (drives intermediate-horizon momentum).
    # phi_g near 1 -> long memory so 12-1m winners persist; tiny innovation so
    # g contributes little at the 5-day horizon (keeps the two effects on
    # separate timescales).
    phi_g, sd_g = 0.995, 0.00022
    g = np.zeros((n_days, n_names))
    g[0] = rng.normal(0, 0.0008, n_names)
    for t in range(1, n_days):
        g[t] = phi_g * g[t - 1] + rng.normal(0, sd_g, n_names)

    # fast OU deviation d (its increments drive short-term reversal). phi_d well
    # below 1 concentrates the negative autocorrelation at short lags, so
    # reversal shows up at ~5 days but does NOT pollute 12-1m momentum.
    phi_d, sd_d = 0.60, 0.016
    d = np.zeros((n_days, n_names))
    for t in range(1, n_days):
        d[t] = phi_d * d[t - 1] + rng.normal(0, sd_d, n_names)
    d_incr = np.vstack([np.zeros((1, n_names)), np.diff(d, axis=0)])

    eps = rng.normal(0, 0.008, (n_days, n_names))

    daily = beta[None, :] * market[:, None] + g + d_incr + eps
    log_price = np.log(rng.uniform(20, 120, n_names))[None, :] + np.cumsum(
        daily, axis=0)
    return pd.DataFrame(np.exp(log_price), index=dates, columns=syms)


if __name__ == "__main__":
    p = generate_panel()
    print(p.shape)
    print(p.iloc[:3, :4])
