"""
Phase 0 analysis on REAL daily data (stockanalysis.com loader).

Run:  python3 research/run_real_phase0.py

Uses the SAME lookahead-safe primitives as the synthetic harness
(sleeve_research.py); only the data source differs. Answers Q1-Q5 and writes a
machine-readable summary to research/_phase0_real_results.json for the findings
doc.

HONESTY: the data is survivor-biased and starts ~2016 (no 2008/2010). Treat the
absolute performance and tail numbers as OPTIMISTIC; the cross-sectional
predictive signs (ICs) and the cross-sleeve correlation are the robust takeaways
at this stage. See data_stockanalysis.py and docs/PHASE0_FINDINGS.md.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

import sleeve_research as sr
from data_stockanalysis import EXTENDED_UNIVERSE, load_price_panel

pd.set_option("display.float_format", lambda x: f"{x:,.4f}")
OUT = os.path.join(os.path.dirname(__file__), "_phase0_real_results.json")


def section(t):
    print("\n" + "=" * 72 + f"\n{t}\n" + "=" * 72)


def jsonable(d):
    return {k: (None if (isinstance(v, float) and (np.isnan(v) or np.isinf(v)))
                else float(v) if isinstance(v, (np.floating, np.integer)) else v)
            for k, v in d.items()}


def nonoverlap_ic(prices, signal, horizon):
    """Honest IC significance: sample ICs every `horizon` bars so the forward
    returns don't overlap (naive daily ICs are autocorrelated and inflate t)."""
    ic = sr.rank_ic(signal, sr.forward_return(prices, horizon)).iloc[::horizon].dropna()
    n = len(ic); m = ic.mean(); s = ic.std()
    return {"mean_ic": float(m), "n_indep": int(n),
            "t_stat": float(m / s * np.sqrt(n)) if (s and n) else np.nan,
            "significant_5pct": bool(abs(m / s * np.sqrt(n)) > 1.96) if (s and n) else False}


def main():
    section("LOAD REAL DATA (survivor-biased, ~10y) ")
    prices = load_price_panel(EXTENDED_UNIVERSE, rng="10Y")
    # keep names with a reasonably complete history for fair cross-sections
    keep = prices.columns[prices.notna().mean() > 0.6]
    prices = prices[keep].dropna(how="all")
    print(f"using {prices.shape[1]} names with >60% history coverage")

    results = {"meta": {
        "n_names": int(prices.shape[1]),
        "start": str(prices.index.min().date()),
        "end": str(prices.index.max().date()),
        "n_days": int(prices.shape[0]),
        "source": "stockanalysis.com (survivor-biased)",
    }}

    section("Q1  Intermediate-horizon momentum (12-1m) -> next-21d return")
    mom = sr.momentum_signal(prices, lookback=252, skip=21)
    s_mom = sr.ic_summary(sr.rank_ic(mom, sr.forward_return(prices, 21)))
    no_mom = nonoverlap_ic(prices, mom, 21)
    print(pd.Series(s_mom)); print("  non-overlapping:", no_mom)
    results["Q1_momentum_ic"] = {"naive": jsonable(s_mom), "nonoverlap": no_mom}

    section("Q2  Short-horizon reversal (5d) -> next-5d return")
    rev = sr.reversal_signal(prices, window=5)
    s_rev = sr.ic_summary(sr.rank_ic(rev, sr.forward_return(prices, 5)))
    no_rev = nonoverlap_ic(prices, rev, 5)
    print(pd.Series(s_rev)); print("  non-overlapping:", no_rev)
    results["Q2_reversal_ic"] = {"naive": jsonable(s_rev), "nonoverlap": no_rev}

    section("Q3  Cross-sectional forward 21d return distribution")
    dist = sr.cross_sectional_distribution(prices, horizon=21)
    print(pd.Series(dist)); results["Q3_distribution"] = jsonable(dist)

    section("Q4  Sleeve return streams + cross-sleeve correlation")
    a = sr.long_short_returns(prices, mom, rebalance_every=21, n_groups=3, lag=1)
    b = sr.long_short_returns(prices, rev, rebalance_every=5, n_groups=3, lag=1)
    a, b = a.align(b, join="inner")
    corr = float(a.corr(b))
    blend = 0.5 * a + 0.5 * b
    sa, sb, sbl = (sr.distribution_stats(a), sr.distribution_stats(b),
                   sr.distribution_stats(blend))
    print("Sleeve A (momentum):"); print(pd.Series(sa))
    print("\nSleeve B (reversal):"); print(pd.Series(sb))
    print(f"\nCROSS-SLEEVE CORRELATION: {corr:+.3f}")
    print("\n50/50 blend:"); print(pd.Series(sbl))
    results["Q4_sleeves"] = {
        "cross_sleeve_corr": corr,
        "sleeve_a_momentum": jsonable(sa),
        "sleeve_b_reversal": jsonable(sb),
        "blend_50_50": jsonable(sbl),
    }

    section("Q6  Time-series TREND vs reversal correlation (the real thesis)")
    mkt = sr.simple_returns(prices).mean(axis=1).dropna()
    trend_lo = sr.timeseries_trend_returns(prices, 200, dollar_neutral=False)
    trend_dn = sr.timeseries_trend_returns(prices, 200, dollar_neutral=True)
    print("Trend long-only :", pd.Series(sr.distribution_stats(trend_lo))[
        ["ann_return", "ann_vol", "sharpe", "skew"]].to_dict())
    print("Trend dollar-neu:", pd.Series(sr.distribution_stats(trend_dn))[
        ["ann_return", "ann_vol", "sharpe", "skew"]].to_dict())
    c_lo = float(trend_lo.align(b, join="inner")[0].corr(
        trend_lo.align(b, join="inner")[1]))
    c_dn = float(trend_dn.align(b, join="inner")[0].corr(
        trend_dn.align(b, join="inner")[1]))
    tail = sr.tail_conditional_correlation(trend_lo, b, mkt, q=0.05)
    print(f"corr(trend_long_only, reversal) = {c_lo:+.3f}")
    print(f"corr(trend_dollar_neutral, reversal) = {c_dn:+.3f}   <- thesis test")
    print(f"worst-5% market-day corr(trend_LO, reversal) = {tail['tail_corr']:+.3f}")
    results["Q6_trend_vs_reversal"] = {
        "corr_trend_longonly_reversal": c_lo,
        "corr_trend_neutral_reversal": c_dn,
        "trend_longonly_skew": float(sr.distribution_stats(trend_lo)["skew"]),
        "trend_neutral_skew": float(sr.distribution_stats(trend_dn)["skew"]),
        "tail_conditional": jsonable(tail),
    }

    section("Q5  Sleeve B residual stationarity (ADF p, Hurst)")
    stat = sr.residual_stationarity_panel(prices, ma_window=20, max_names=80)
    frac = float((stat["adf_p"] < 0.05).mean())
    print(stat.describe().loc[["mean", "min", "max"]])
    print(f"\nFraction ADF p<0.05 (stationary residual): {frac:.0%}")
    print(f"Mean Hurst (raw price): {stat['hurst'].mean():.3f}")
    results["Q5_stationarity"] = {
        "frac_adf_stationary": frac,
        "mean_adf_p": float(stat["adf_p"].mean()),
        "mean_hurst_price": float(stat["hurst"].mean()),
    }

    with open(OUT, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nwrote {OUT}")
    section("CAVEAT")
    print("Survivor-biased, ~2016-start data. ICs & cross-sleeve correlation "
          "are the robust\nsignals here; absolute return / tail metrics are "
          "OPTIMISTIC and must be re-checked\non survivorship-free data.")


if __name__ == "__main__":
    main()
