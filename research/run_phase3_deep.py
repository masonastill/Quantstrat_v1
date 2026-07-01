"""
Phase 3 (deep) — re-evaluate trend-v2 on 2005-2026 Yahoo data, including the
2008 GFC and 2010 flash crash that the sandbox lacked.

Run:  python3 research/run_phase3_deep.py   (first run fetches ~300 names ~6min)

SURVIVOR-BIASED still (Yahoo has no delisted names) -> the 2008 tail here is a
LOWER BOUND on pain; real 2008 with delistings was worse. But this finally shows
whether the strategy's stops + regime governor behave sanely through a GFC-scale
shock. Writes _phase3_deep_results.json.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from data_stockanalysis import EXTENDED_UNIVERSE
from data_yahoo import load_price_panel
import phase15_trend as p15
from run_phase3 import full_metrics, capacity_estimate, FINAL

OUT = os.path.join(os.path.dirname(__file__), "_phase3_deep_results.json")

STRESS = {
    "2008_GFC": ("2008-09-01", "2009-03-31"),
    "2010_flash_crash": ("2010-05-01", "2010-06-30"),
    "2011_euro_crisis": ("2011-07-01", "2011-10-31"),
    "2015-16_selloff": ("2015-08-01", "2016-02-29"),
    "2018Q4_selloff": ("2018-10-01", "2018-12-31"),
    "2020_covid_crash": ("2020-02-19", "2020-04-30"),
    "2022_bear": ("2022-01-01", "2022-12-31"),
}


def main():
    print("Fetching deep history from Yahoo (cached after first run)...")
    prices = load_price_panel(EXTENDED_UNIVERSE, field="adj_close", start="2005-01-01")
    volume = load_price_panel(EXTENDED_UNIVERSE, field="volume", start="2005-01-01",
                              verbose=False)
    keep = prices.columns[prices.notna().mean() > 0.5]
    prices = prices[keep].dropna(how="all")
    volume = volume.reindex(columns=keep).reindex(prices.index)
    print(f"USABLE: {prices.shape[1]} names x {prices.shape[0]} days "
          f"({prices.index.min().date()} -> {prices.index.max().date()})")

    res = p15.backtest(prices, volume, FINAL)
    net = res["net_ret"]
    m = full_metrics(net, res["trade_R"])
    m["avg_annual_turnover_x"] = float(res["turnover"].mean() * 252)
    cap = capacity_estimate(prices, volume)

    print("\n" + "=" * 62 + "\nFULL METRICS (net, 2005-2026, survivor-biased)\n" + "=" * 62)
    for k in ["cagr", "ann_vol", "sharpe", "sortino", "calmar_mar", "max_drawdown",
              "recovery_days", "longest_underwater_days", "skew_monthly",
              "tail_ratio", "win_rate", "expectancy_R", "payoff_ratio", "best_R",
              "worst_R", "n_trades", "avg_annual_turnover_x"]:
        v = m[k]
        print(f"  {k:26s} {v if v is None else round(v,4)}")

    print("\n" + "=" * 62 + "\nSTRESS WINDOWS incl. 2008/2010 (as-is)\n" + "=" * 62)
    mkt = prices.pct_change().mean(axis=1)
    stress = {}
    for name, (a, b) in STRESS.items():
        seg = net[(net.index >= a) & (net.index <= b)]
        if seg.empty:
            print(f"  {name:18s} (no data)")
            continue
        cum = (1 + seg).prod() - 1
        curve = (1 + seg).cumprod()
        dd = (curve / curve.cummax() - 1).min()
        mseg = mkt[(mkt.index >= a) & (mkt.index <= b)]
        stress[name] = {"strategy_return": float(cum), "strategy_maxDD": float(dd),
                        "worst_day": float(seg.min()),
                        "market_return": float((1 + mseg).prod() - 1)}
        print(f"  {name:18s} strat {cum:+.1%} (maxDD {dd:5.1%}, worst {seg.min():+.1%}) "
              f"| eq-wt mkt {stress[name]['market_return']:+.1%}")

    results = {"meta": {"config": "trend-v2 chandelier=4xATR",
                        "n_names": int(prices.shape[1]),
                        "start": str(prices.index.min().date()),
                        "end": str(prices.index.max().date()),
                        "source": "Yahoo (survivor-biased, deep history)"},
               "metrics": m, "capacity": cap, "stress_windows": stress}
    with open(OUT, "w") as f:
        json.dump(results, f, indent=2, default=float)
    print(f"\nwrote {OUT}")
    print("CAVEAT: survivor-biased (no delisted 2008 blowups) -> 2008 tail is a "
          "LOWER BOUND on true pain.")


if __name__ == "__main__":
    main()
