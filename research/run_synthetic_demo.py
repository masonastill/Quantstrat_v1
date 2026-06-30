"""
Phase 0 analysis driver, run against SYNTHETIC data for code validation.

Run:  python3 research/run_synthetic_demo.py

It executes the four Phase 0 questions using research/sleeve_research.py:
  Q1  Does intermediate-horizon momentum predict the cross-section?
  Q2  Does short-horizon reversal predict the cross-section?
  Q3  What is the shape (skew / fat tails) of the cross-sectional returns?
  Q4  Are the two sleeves' return streams negatively correlated?
  Q5  Is the Sleeve B residual actually stationary (ADF / Hurst)?

Every number printed is from SYNTHETIC data and is only evidence that the code
is correct, NOT evidence about real markets.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import sleeve_research as sr
from synthetic_data import generate_panel

pd.set_option("display.float_format", lambda x: f"{x:,.4f}")


def section(title: str) -> None:
    print("\n" + "=" * 72 + f"\n{title}\n" + "=" * 72)


def main() -> None:
    prices = generate_panel()
    print(f"Synthetic panel: {prices.shape[0]} days x {prices.shape[1]} names "
          f"({prices.index[0].date()} -> {prices.index[-1].date()})")

    # --- Q1: intermediate momentum predictive power (12-1, eval over ~1m) ----
    section("Q1  Intermediate-horizon momentum (12-1m) -> next-21d return")
    mom = sr.momentum_signal(prices, lookback=252, skip=21)
    fwd_1m = sr.forward_return(prices, 21)
    ic_mom = sr.rank_ic(mom, fwd_1m)
    print(pd.Series(sr.ic_summary(ic_mom)))

    # --- Q2: short-horizon reversal predictive power (5d, eval over 5d) ------
    section("Q2  Short-horizon reversal (5d) -> next-5d return")
    rev = sr.reversal_signal(prices, window=5)
    fwd_1w = sr.forward_return(prices, 5)
    ic_rev = sr.rank_ic(rev, fwd_1w)
    print(pd.Series(sr.ic_summary(ic_rev)))

    # --- Q3: cross-sectional return distribution shape ----------------------
    section("Q3  Cross-sectional forward 21d return distribution")
    print(pd.Series(sr.cross_sectional_distribution(prices, horizon=21)))

    # --- Q4: build both sleeves as daily L/S return streams & correlate -----
    section("Q4  Sleeve return streams + cross-sleeve correlation")
    sleeve_a = sr.long_short_returns(prices, mom, rebalance_every=21,
                                     n_groups=3, lag=1)
    sleeve_b = sr.long_short_returns(prices, rev, rebalance_every=5,
                                     n_groups=3, lag=1)
    a, b = sleeve_a.align(sleeve_b, join="inner")
    print("Sleeve A (momentum) daily L/S stats:")
    print(pd.Series(sr.distribution_stats(a)))
    print("\nSleeve B (reversal) daily L/S stats:")
    print(pd.Series(sr.distribution_stats(b)))
    print(f"\nCross-sleeve daily return correlation: {a.corr(b):+.3f}")
    print("50/50 blend stats:")
    print(pd.Series(sr.distribution_stats(0.5 * a + 0.5 * b)))

    # --- Q5: stationarity of the Sleeve B residual --------------------------
    section("Q5  Sleeve B residual stationarity (ADF p, Hurst)")
    stat = sr.residual_stationarity_panel(prices, ma_window=20, max_names=40)
    frac_stationary = (stat["adf_p"] < 0.05).mean()
    print(stat.describe().loc[["mean", "min", "max"]])
    print(f"\nFraction of names with ADF p<0.05 (stationary residual): "
          f"{frac_stationary:.0%}")
    print(f"Mean Hurst exponent: {stat['hurst'].mean():.3f} "
          f"(<0.5 => mean-reverting)")

    section("REMINDER")
    print("All figures above are from SYNTHETIC data and validate the code "
          "only.\nReal Phase 0 findings must come from phase0_research.ipynb on "
          "QuantBook data.")


if __name__ == "__main__":
    main()
