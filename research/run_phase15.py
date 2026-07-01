"""
Phase 1.5 driver: does the redesigned trend sleeve achieve POSITIVE SKEW?

Run:  python3 research/run_phase15.py

Reports skew-aware metrics, turnover, walk-forward per segment, and a small
robustness sweep over the two skew-relevant knobs (chandelier width, winner cap)
to check that positive skew is ROBUST, not a single lucky setting.

Survivor-biased sandbox -> PROVISIONAL.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
from scipy import stats

from data_stockanalysis import EXTENDED_UNIVERSE, load_price_panel
from run_phase1 import perf_stats
import phase15_trend as p15

OUT = os.path.join(os.path.dirname(__file__), "_phase15_results.json")


def load():
    prices = load_price_panel(EXTENDED_UNIVERSE, "10Y", field="adj_close", verbose=False)
    volume = load_price_panel(EXTENDED_UNIVERSE, "10Y", field="volume", verbose=False)
    keep = prices.columns[prices.notna().mean() > 0.6]
    prices = prices[keep].dropna(how="all")
    volume = volume.reindex(columns=keep).reindex(prices.index)
    return prices, volume


def main():
    prices, volume = load()
    print(f"{prices.shape[1]} names x {prices.shape[0]} days "
          f"({prices.index.min().date()} -> {prices.index.max().date()})")

    res = p15.backtest(prices, volume)
    net, gross = res["net_ret"], res["net_ret"]
    ps = perf_stats(net, gross)
    print("\n" + "=" * 60 + "\nREDESIGNED TREND SLEEVE (net of costs)\n" + "=" * 60)
    for k in ["cagr", "ann_vol", "sharpe", "sortino", "max_drawdown", "calmar",
              "skew", "excess_kurtosis", "tail_ratio", "net_ann_return"]:
        print(f"  {k:16s} {ps[k]:>9.4f}")
    print(f"  avg daily turnover  {res['turnover'].mean():>9.4f} "
          f"(~{res['turnover'].mean()*252:.1f}x/yr, {res['n_trades']} trades)")

    # ---- SKEW AT THE RIGHT FREQUENCY --------------------------------------
    # Daily skew of ANY long equity book is negative (crashes gap down). The
    # philosophy's positive skew lives at trade level and at monthly+ horizons.
    print("\n  Skew by frequency (daily skew is negative for ALL long equity):")
    skew_freq = {}
    for lbl, rule in [("daily", None), ("weekly", "W"), ("monthly", "ME"),
                      ("quarterly", "QE")]:
        r = net if rule is None else (1 + net).resample(rule).prod() - 1
        r = r.dropna()
        skew_freq[lbl] = float(stats.skew(r))
        print(f"    {lbl:10s} skew {skew_freq[lbl]:+.2f}")

    R = res["trade_R"]; R = R[np.isfinite(R)]
    wins, losses = R[R > 0], R[R < 0]
    trade_stats = {
        "n_trades": int(len(R)), "win_rate": float(len(wins) / len(R)),
        "avg_win_R": float(wins.mean()), "avg_loss_R": float(losses.mean()),
        "expectancy_R": float(R.mean()), "skew_R": float(stats.skew(R)),
        "payoff_ratio": float(wins.mean() / abs(losses.mean())),
        "best_R": float(R.max()), "worst_R": float(R.min())}
    print(f"\n  Trade R-multiples ({trade_stats['n_trades']} trades): "
          f"win {trade_stats['win_rate']:.0%}, avg win {trade_stats['avg_win_R']:+.2f}R, "
          f"avg loss {trade_stats['avg_loss_R']:+.2f}R,")
    print(f"    expectancy {trade_stats['expectancy_R']:+.3f}R, "
          f"payoff {trade_stats['payoff_ratio']:.2f}, "
          f"R-skew {trade_stats['skew_R']:+.2f} (best {trade_stats['best_R']:+.1f}R)")

    pos = skew_freq["monthly"] > 0 and trade_stats["skew_R"] > 0
    print(f"\n  >>> SKEW OBJECTIVE (monthly {skew_freq['monthly']:+.2f}, "
          f"trade-R {trade_stats['skew_R']:+.2f}): "
          f"{'ACHIEVED ✓' if pos else 'NOT MET ✗'}")

    # walk-forward per segment (holdout touched once)
    print("\nWALK-FORWARD (skew + Sharpe per segment):")
    splits = {"train": ("2016-01-01", "2019-12-31"),
              "validation": ("2020-01-01", "2021-12-31"),
              "holdout": ("2022-01-01", "2026-12-31")}
    wf = {}
    for s, (a, b) in splits.items():
        m = (net.index >= a) & (net.index <= b)
        p = perf_stats(net[m], gross[m])
        wf[s] = {"sharpe": round(p["sharpe"], 2), "skew": round(p["skew"], 2),
                 "net_ann": round(p["net_ann_return"], 4),
                 "maxDD": round(p["max_drawdown"], 3)}
        print(f"  {s:11s} Sharpe {wf[s]['sharpe']:+.2f}  skew {wf[s]['skew']:+.2f}  "
              f"ret {wf[s]['net_ann']:+.1%}  maxDD {wf[s]['maxDD']:.1%}")

    # robustness: is positive skew stable across the two skew knobs?
    print("\nROBUSTNESS — skew across (chandelier_atr, winner_cap):")
    grid = {}
    for ch in [4.0, 5.0, 6.0]:
        row = {}
        for wc in [0.15, 0.20, 0.25]:
            pr = p15.TrendV2Params(chandelier_atr=ch, winner_cap=wc)
            r = p15.backtest(prices, volume, pr)
            pp = perf_stats(r["net_ret"], r["net_ret"])
            row[wc] = {"skew": round(pp["skew"], 2), "sharpe": round(pp["sharpe"], 2)}
        grid[ch] = row
        print(f"  chandelier={ch}: " + "  ".join(
            f"wc{wc}->sk{row[wc]['skew']:+.2f}/sh{row[wc]['sharpe']:+.2f}" for wc in row))

    results = {
        "meta": {"n_names": int(prices.shape[1]),
                 "start": str(prices.index.min().date()),
                 "end": str(prices.index.max().date()),
                 "source": "stockanalysis.com (survivor-biased sandbox)"},
        "performance": {k: (None if isinstance(v, float) and np.isnan(v) else v)
                        for k, v in ps.items()},
        "skew_by_frequency": skew_freq,
        "trade_R_stats": trade_stats,
        "avg_daily_turnover": float(res["turnover"].mean()),
        "n_trades": res["n_trades"],
        "walk_forward": wf,
        "skew_robustness_grid": grid,
    }
    with open(OUT, "w") as f:
        json.dump(results, f, indent=2, default=float)
    print(f"\nwrote {OUT}")
    print("CAVEAT: survivor-biased sandbox, ~2016 start, no 2008. Provisional.")


if __name__ == "__main__":
    main()
