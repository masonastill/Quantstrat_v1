"""
Phase 0 research primitives for the two-sleeve absolute-return ensemble.

This module contains PURE analysis functions (pandas / numpy / scipy /
statsmodels only). They have NO dependency on QuantConnect, LEAN, or any
particular data source, so the exact same code path is exercised by:

  * research/phase0_research.ipynb  -> real, survivorship-free QuantBook data
  * research/run_synthetic_demo.py  -> synthetic data, for code validation

Design principles
-----------------
* No lookahead. Every signal at date t uses only information available at the
  close of t. Forward returns are computed with .shift(-h) and are clearly
  named `fwd_*`. Signals are computed with backward windows only.
* Point-in-time discipline is the caller's job for fundamentals; this module
  works on a price panel (DatetimeIndex x symbols) of split/dividend-adjusted
  prices and is careful never to peek forward.
* Everything is parameterized and small. The defaults are economically
  sensible, NOT optimized.

Conventions
-----------
prices : pd.DataFrame, index = DatetimeIndex (ascending), columns = symbols,
         values = adjusted close. NaNs allowed (e.g. before listing).
A "signal panel" has the same shape; higher signal value => more bullish in
the cross-section for that sleeve.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

try:
    from statsmodels.tsa.stattools import adfuller
    _HAS_SM = True
except Exception:  # pragma: no cover - statsmodels optional at import time
    _HAS_SM = False


# --------------------------------------------------------------------------- #
# Returns helpers
# --------------------------------------------------------------------------- #
def simple_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Daily simple returns of an adjusted-price panel."""
    return prices.pct_change()


def forward_return(prices: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Forward simple return over `horizon` bars, aligned to the FORMATION date.

    fwd[t] = price[t+horizon] / price[t] - 1.  Uses shift(-horizon): the value
    at date t describes what happens AFTER t, so pairing signal[t] with
    fwd[t] is lookahead-free for an evaluation done as-of t.
    """
    return prices.shift(-horizon) / prices - 1.0


# --------------------------------------------------------------------------- #
# Sleeve A signal: intermediate-horizon cross-sectional momentum
# --------------------------------------------------------------------------- #
def momentum_signal(prices: pd.DataFrame, lookback: int = 252,
                    skip: int = 21) -> pd.DataFrame:
    """Total-return momentum, skipping the most recent `skip` bars.

    signal[t] = price[t-skip] / price[t-lookback] - 1

    Skipping the last ~1 month removes the short-term reversal contamination
    that is well documented in the cross-section (Jegadeesh 1990). Defaults:
    lookback=252 (~12m), skip=21 (~1m) -> classic "12-1" momentum.
    """
    if skip < 0 or lookback <= skip:
        raise ValueError("require 0 <= skip < lookback")
    return prices.shift(skip) / prices.shift(lookback) - 1.0


# --------------------------------------------------------------------------- #
# Sleeve B signal: short-horizon mean reversion
# --------------------------------------------------------------------------- #
def reversal_signal(prices: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    """Short-horizon reversal signal (higher = more oversold = bullish).

    Raw short return r[t] = price[t]/price[t-window] - 1 ; the reversal bet is
    the NEGATIVE of recent performance, so signal = -r[t]. High signal => the
    name just fell and is expected to bounce.
    """
    short_ret = prices / prices.shift(window) - 1.0
    return -short_ret


def ma_residual_zscore(price: pd.Series, ma_window: int = 20,
                       z_window: int | None = None) -> pd.Series:
    """Stationary residual of price vs its own moving average, as a z-score.

    resid[t] = price[t] / MA(price, ma_window)[t] - 1     (a ratio, ~stationary)
    z[t]     = (resid[t] - mean(resid)) / std(resid)      over a trailing window

    This is the Sleeve B state variable the philosophy calls for: we trade the
    z-score of a STATIONARY residual, never the raw price level. All windows
    are backward-looking. z_window defaults to 5*ma_window.
    """
    z_window = z_window or 5 * ma_window
    ma = price.rolling(ma_window, min_periods=ma_window).mean()
    resid = price / ma - 1.0
    mu = resid.rolling(z_window, min_periods=z_window).mean()
    sd = resid.rolling(z_window, min_periods=z_window).std()
    return (resid - mu) / sd


# --------------------------------------------------------------------------- #
# Cross-sectional predictive power: rank information coefficient
# --------------------------------------------------------------------------- #
def rank_ic(signal: pd.DataFrame, fwd: pd.DataFrame,
            min_names: int = 10) -> pd.Series:
    """Per-date Spearman rank correlation between signal[t] and fwd[t].

    Returns a time series of cross-sectional rank ICs. A positive mean IC
    means the signal ranks future winners above future losers in the
    cross-section. We use rank (Spearman) IC because it is robust to the fat
    tails documented elsewhere in this notebook.
    """
    sig, fw = signal.align(fwd, join="inner")
    out = {}
    for dt in sig.index:
        s = sig.loc[dt]
        f = fw.loc[dt]
        mask = s.notna() & f.notna()
        if mask.sum() < min_names:
            continue
        out[dt] = s[mask].rank().corr(f[mask].rank())
    return pd.Series(out, name="rank_ic").sort_index()


def ic_summary(ic: pd.Series) -> dict:
    """Mean IC, IC stdev, and the IC information ratio (mean/std * sqrt(n))."""
    ic = ic.dropna()
    n = len(ic)
    mean = ic.mean()
    std = ic.std()
    return {
        "n_periods": n,
        "mean_ic": mean,
        "ic_std": std,
        "ic_ir": (mean / std) if std and not np.isnan(std) else np.nan,
        "t_stat": (mean / std * np.sqrt(n)) if (std and n) else np.nan,
    }


# --------------------------------------------------------------------------- #
# Long/short portfolio return streams (the two "sleeves" as return series)
# --------------------------------------------------------------------------- #
def _quantile_weights(sig_row: pd.Series, n_groups: int) -> pd.Series:
    """Dollar-neutral equal-weight long-top / short-bottom weights for one date."""
    s = sig_row.dropna()
    if len(s) < n_groups * 2:
        return pd.Series(dtype=float)
    ranks = s.rank(method="first")
    edge = len(s) / n_groups
    longs = ranks[ranks > len(s) - edge].index
    shorts = ranks[ranks <= edge].index
    w = pd.Series(0.0, index=s.index)
    if len(longs):
        w[longs] = 0.5 / len(longs)
    if len(shorts):
        w[shorts] = -0.5 / len(shorts)
    return w  # gross = 1.0, net ~ 0


def long_short_returns(prices: pd.DataFrame, signal: pd.DataFrame,
                       rebalance_every: int = 21, n_groups: int = 3,
                       lag: int = 1) -> pd.Series:
    """Daily return stream of a dollar-neutral cross-sectional L/S portfolio.

    At each rebalance date the signal forms long-top / short-bottom tercile
    (n_groups=3) equal-weight, dollar-neutral books; weights are held until the
    next rebalance. `lag` (>=1) means weights computed from signal[t] are not
    earned until t+lag returns -> removes same-bar lookahead.

    This produces a comparable DAILY return series for either sleeve, which is
    what we need to measure the cross-sleeve correlation honestly.
    """
    if lag < 1:
        raise ValueError("lag must be >= 1 to avoid same-bar lookahead")
    rets = simple_returns(prices)
    dates = prices.index
    rebal_idx = range(0, len(dates), rebalance_every)
    weights = pd.DataFrame(0.0, index=dates, columns=prices.columns)
    current = pd.Series(0.0, index=prices.columns)
    next_rebal = set(dates[i] for i in rebal_idx)
    for dt in dates:
        if dt in next_rebal:
            current = _quantile_weights(signal.loc[dt], n_groups).reindex(
                prices.columns).fillna(0.0)
        weights.loc[dt] = current
    # earn return at t using weights known at t-lag
    port = (weights.shift(lag) * rets).sum(axis=1)
    port.name = "ls_return"
    return port.dropna()


# --------------------------------------------------------------------------- #
# Distribution characterization (fat tails / skew)
# --------------------------------------------------------------------------- #
def tail_ratio(returns: pd.Series, q: float = 0.05) -> float:
    """Ratio of the right-tail magnitude to the left-tail magnitude.

    >1 => right tail (gains) fatter than left tail (losses) = positive-skew
    flavour; <1 => fat left tail. q is the tail probability (0.05 = 5%/95%).
    """
    r = returns.dropna()
    if r.empty:
        return np.nan
    left = abs(np.quantile(r, q))
    right = abs(np.quantile(r, 1 - q))
    return right / left if left else np.nan


def distribution_stats(returns: pd.Series) -> dict:
    """Skew-aware summary of a return series."""
    r = returns.dropna()
    if len(r) < 3:
        return {}
    from scipy import stats
    ann = np.sqrt(252)
    return {
        "n": len(r),
        "mean_daily": r.mean(),
        "std_daily": r.std(),
        "ann_return": r.mean() * 252,
        "ann_vol": r.std() * ann,
        "sharpe": (r.mean() / r.std() * ann) if r.std() else np.nan,
        "skew": stats.skew(r),
        "excess_kurtosis": stats.kurtosis(r),  # 0 == normal
        "tail_ratio_5pct": tail_ratio(r, 0.05),
        "var_95": np.quantile(r, 0.05),
        "cvar_95": r[r <= np.quantile(r, 0.05)].mean(),
    }


def cross_sectional_distribution(prices: pd.DataFrame,
                                 horizon: int = 21) -> dict:
    """Pool forward `horizon`-bar returns ACROSS names and dates, then describe
    the fat-tail / skew character of the cross-section. Uses non-overlapping
    samples (step = horizon) to keep observations roughly independent."""
    fwd = forward_return(prices, horizon)
    pooled = fwd.iloc[::horizon].stack().dropna()
    return distribution_stats(pd.Series(pooled.values))


# --------------------------------------------------------------------------- #
# Stationarity / mean-reversion diagnostics for the Sleeve B residual
# --------------------------------------------------------------------------- #
def adf_pvalue(series: pd.Series) -> float:
    """Augmented Dickey-Fuller p-value (H0 = unit root / non-stationary).

    Low p (<0.05) => reject unit root => series is mean-reverting/stationary,
    which is the precondition for trusting the Sleeve B z-score.
    """
    s = series.dropna()
    if not _HAS_SM or len(s) < 30:
        return np.nan
    try:
        return float(adfuller(s, autolag="AIC")[1])
    except Exception:
        return np.nan


def hurst_exponent(series: pd.Series, max_lag: int = 50) -> float:
    """Hurst exponent via the variance-of-lagged-differences method.

    H < 0.5 => mean-reverting (good for Sleeve B), H = 0.5 => random walk,
    H > 0.5 => trending/persistent (Sleeve A territory).
    """
    s = series.dropna().values
    if len(s) < max_lag * 2:
        return np.nan
    lags = range(2, max_lag)
    tau = []
    for lag in lags:
        diff = s[lag:] - s[:-lag]
        tau.append(np.sqrt(np.std(diff)) if len(diff) else np.nan)
    tau = np.array(tau)
    good = tau > 0
    if good.sum() < 5:
        return np.nan
    poly = np.polyfit(np.log(np.array(list(lags))[good]), np.log(tau[good]), 1)
    return poly[0] * 2.0


def residual_stationarity_panel(prices: pd.DataFrame, ma_window: int = 20,
                                max_names: int = 200) -> pd.DataFrame:
    """Run ADF + Hurst on each name's MA-residual to check that the Sleeve B
    state variable is actually stationary across the cross-section."""
    rows = []
    for sym in list(prices.columns)[:max_names]:
        resid = (prices[sym] / prices[sym].rolling(
            ma_window, min_periods=ma_window).mean() - 1.0)
        rows.append({
            "symbol": sym,
            "adf_p": adf_pvalue(resid),
            "hurst": hurst_exponent(prices[sym].dropna()),
        })
    return pd.DataFrame(rows).set_index("symbol")
