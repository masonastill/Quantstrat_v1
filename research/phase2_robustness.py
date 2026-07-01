"""
Phase 2 — robustness statistics (NOT optimization tools).

Implements the multiple-testing / overfitting diagnostics the brief requires:
  * Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014)
  * Probability of Backtest Overfitting via CSCV (Bailey et al., 2017)
  * Walk-forward segmentation helper
  * Regime classification (trending vs choppy) for the "map to market" test

These operate on return series / a matrix of candidate-config returns; they do
not touch the strategy logic. Kept pure and testable.
"""
from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd
from scipy import stats

GAMMA = 0.5772156649015329  # Euler-Mascheroni


# --------------------------------------------------------------------------- #
# Deflated Sharpe Ratio
# --------------------------------------------------------------------------- #
def expected_max_sharpe(sharpe_variance: float, n_trials: int) -> float:
    """E[max SR] under the null of zero true skill, given the variance of the
    trial Sharpes and the number of independent trials (per-observation SR)."""
    if n_trials < 2 or sharpe_variance <= 0:
        return 0.0
    z1 = stats.norm.ppf(1 - 1.0 / n_trials)
    z2 = stats.norm.ppf(1 - 1.0 / (n_trials * math.e))
    return math.sqrt(sharpe_variance) * ((1 - GAMMA) * z1 + GAMMA * z2)


def deflated_sharpe_ratio(returns: pd.Series, n_trials: int,
                          sharpe_variance: float) -> dict:
    """DSR: probability the observed (per-period) Sharpe is real after adjusting
    for non-normality AND for having searched `n_trials` configurations.

    Returns the observed annualized Sharpe, the benchmark SR0 it must beat, and
    the DSR probability (want > 0.95).
    """
    r = returns.dropna()
    T = len(r)
    if T < 30:
        return {"dsr": np.nan}
    sr = r.mean() / r.std()                      # per-period Sharpe
    skew = stats.skew(r)
    kurt = stats.kurtosis(r, fisher=False)       # non-excess kurtosis
    sr0 = expected_max_sharpe(sharpe_variance, n_trials)
    denom = math.sqrt(max(1 - skew * sr + (kurt - 1) / 4.0 * sr**2, 1e-9))
    dsr = stats.norm.cdf((sr - sr0) * math.sqrt(T - 1) / denom)
    return {
        "sharpe_annual": sr * math.sqrt(252),
        "sr0_benchmark_annual": sr0 * math.sqrt(252),
        "n_trials": n_trials,
        "dsr": float(dsr),
        "passes_0.95": bool(dsr > 0.95),
    }


# --------------------------------------------------------------------------- #
# Probability of Backtest Overfitting (CSCV)
# --------------------------------------------------------------------------- #
def pbo_cscv(returns_matrix: pd.DataFrame, n_splits: int = 10) -> dict:
    """CSCV PBO. `returns_matrix`: index=time, columns=candidate configs, values
    =per-period returns. Splits time into `n_splits` blocks; for every way to
    pick half as IS, selects the best IS config and measures its OOS rank.

    PBO = P(the IS-best config lands below the OOS median) — high PBO (>0.5)
    means the selection procedure is overfitting.
    """
    R = returns_matrix.dropna(how="any")
    T, N = R.shape
    if N < 2 or T < n_splits * 4:
        return {"pbo": np.nan, "n_configs": N}
    if n_splits % 2:
        n_splits += 1
    blocks = np.array_split(np.arange(T), n_splits)
    logits = []
    for is_idx in itertools.combinations(range(n_splits), n_splits // 2):
        is_rows = np.concatenate([blocks[i] for i in is_idx])
        oos_rows = np.concatenate([blocks[i] for i in range(n_splits)
                                   if i not in is_idx])
        Ris, Roos = R.iloc[is_rows], R.iloc[oos_rows]
        sr_is = Ris.mean() / Ris.std().replace(0, np.nan)
        sr_oos = Roos.mean() / Roos.std().replace(0, np.nan)
        best = sr_is.idxmax()
        # OOS relative rank of the IS-best config
        rank = sr_oos.rank(ascending=True)[best] / (N + 1)
        rank = min(max(rank, 1e-6), 1 - 1e-6)
        logits.append(math.log(rank / (1 - rank)))
    logits = np.array(logits)
    return {
        "pbo": float((logits <= 0).mean()),   # P(best-IS underperforms OOS median)
        "n_configs": N,
        "n_splits": n_splits,
        "median_logit": float(np.median(logits)),
    }


# --------------------------------------------------------------------------- #
# Walk-forward segmentation
# --------------------------------------------------------------------------- #
def walk_forward_segments(index: pd.DatetimeIndex, splits: dict) -> dict:
    """Return boolean masks for named date ranges, e.g.
    {'train': ('2016-01-01','2019-12-31'), ...}. The 'holdout' should be touched
    exactly once."""
    return {name: (index >= pd.Timestamp(a)) & (index <= pd.Timestamp(b))
            for name, (a, b) in splits.items()}


# --------------------------------------------------------------------------- #
# Regime classification for the "map to market" negative control
# --------------------------------------------------------------------------- #
def classify_regimes(index_prices: pd.Series, trend_win: int = 60,
                     chop_thresh: float = 0.10) -> pd.Series:
    """Label each day 'trending' or 'choppy' from the index's own behavior.

    A period is 'trending' when the magnitude of its `trend_win` return exceeds
    `chop_thresh` (strong directional move up OR down); otherwise 'choppy'. This
    is the market map against which we check that the TREND sleeve does better in
    trends and the MR sleeve does better in chop (a model that wins in BOTH is
    suspected of fitting noise).
    """
    mom = index_prices / index_prices.shift(trend_win) - 1.0
    return pd.Series(np.where(mom.abs() > chop_thresh, "trending", "choppy"),
                     index=index_prices.index).shift(1)


def conditional_sharpe(returns: pd.Series, regime: pd.Series) -> dict:
    """Annualized Sharpe of `returns` within each regime label."""
    r, g = returns.align(regime, join="inner")
    out = {}
    for label in ["trending", "choppy"]:
        sub = r[g == label]
        out[label] = float(sub.mean() / sub.std() * np.sqrt(252)) \
            if len(sub) > 5 and sub.std() else np.nan
    return out
