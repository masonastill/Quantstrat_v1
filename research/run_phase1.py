"""
Phase 1 baseline run: two sleeves + regime governor + realistic costs.

Run:  python3 research/run_phase1.py

Loads the sandbox universe (adjusted close + volume), builds the combined
portfolio, simulates with costs, and prints a baseline performance summary and
a cost breakdown. Writes research/_phase1_results.json.

CAVEAT: survivor-biased, ~2016-start, large-cap-only data; absolute results are
PROVISIONAL and optimistic. This validates the mechanics and the cost drag, not
a live edge.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
from scipy import stats

from data_stockanalysis import EXTENDED_UNIVERSE, SECTOR_MAP, load_price_panel
import phase1_backtest as bt

OUT = os.path.join(os.path.dirname(__file__), "_phase1_results.json")


def perf_stats(net: pd.Series, gross: pd.Series) -> dict:
    r = net.dropna()
    ann = np.sqrt(252)
    curve = (1 + r).cumprod()
    dd = curve / curve.cummax() - 1.0
    downside = r[r < 0].std()
    neg = r[r < 0]
    return {
        "years": len(r) / 252,
        "cagr": curve.iloc[-1] ** (252 / len(r)) - 1,
        "ann_vol": r.std() * ann,
        "sharpe": r.mean() / r.std() * ann if r.std() else np.nan,
        "sortino": r.mean() / downside * ann if downside else np.nan,
        "max_drawdown": dd.min(),
        "calmar": (curve.iloc[-1] ** (252 / len(r)) - 1) / abs(dd.min())
        if dd.min() else np.nan,
        "skew": stats.skew(r),
        "excess_kurtosis": stats.kurtosis(r),
        "tail_ratio": abs(np.quantile(r, 0.95)) / abs(np.quantile(r, 0.05)),
        "gross_ann_return": gross.mean() * 252,
        "net_ann_return": r.mean() * 252,
    }


def main():
    print("Loading sandbox data (adj close + volume)...")
    prices = load_price_panel(EXTENDED_UNIVERSE, rng="10Y", field="adj_close",
                              verbose=False)
    volume = load_price_panel(EXTENDED_UNIVERSE, rng="10Y", field="volume",
                              verbose=False)
    keep = prices.columns[prices.notna().mean() > 0.6]
    prices, volume = prices[keep].dropna(how="all"), volume.reindex(
        columns=keep).reindex(prices.index)
    volume = volume.loc[prices.index]
    print(f"universe: {prices.shape[1]} names x {prices.shape[0]} days "
          f"({prices.index.min().date()} -> {prices.index.max().date()})")

    cfg = bt.Config()
    W, comp = bt.build_portfolio(prices, volume, SECTOR_MAP, cfg)
    sim = bt.simulate(prices, volume, W, cfg.cost)

    # exposure diagnostics
    gross_exp = W.abs().sum(axis=1)
    net_exp = W.sum(axis=1)
    frac_stressed = float(comp["stressed"].mean())

    print("\n" + "=" * 66 + "\nBASELINE PERFORMANCE (net of costs)\n" + "=" * 66)
    ps = perf_stats(sim["net_ret"], sim["gross_ret"])
    for k, v in ps.items():
        print(f"  {k:20s} {v:>10.4f}")

    print("\n" + "=" * 66 + "\nCOST BREAKDOWN (annualized drag, fraction of NAV)\n"
          + "=" * 66)
    cost_cols = ["cost_spread_slip", "cost_commission", "cost_impact", "cost_borrow"]
    drags = {c: sim[c].mean() * 252 for c in cost_cols}
    total_drag = sum(drags.values())
    for c in cost_cols:
        print(f"  {c:20s} {drags[c]*1e4:8.1f} bps/yr")
    print(f"  {'TOTAL':20s} {total_drag*1e4:8.1f} bps/yr")
    print(f"  gross->net gap:  {(ps['gross_ann_return']-ps['net_ann_return'])*1e4:8.1f} bps/yr")
    print(f"  avg daily turnover (1-way): {sim['turnover'].mean():.3f} "
          f"(~{sim['turnover'].mean()*252:.1f}x/yr)")

    print("\n" + "=" * 66 + "\nEXPOSURE / REGIME\n" + "=" * 66)
    print(f"  avg gross leverage: {gross_exp.mean():.2f}  (cap {cfg.risk.gross_cap})")
    print(f"  avg net leverage:   {net_exp.mean():.2f}  (cap {cfg.risk.net_cap})")
    print(f"  time in defensive regime: {frac_stressed:.1%}")
    print(f"  sleeve A (trend) avg gross: {comp['w_a'].abs().sum(axis=1).mean():.2f}")
    print(f"  sleeve B (MR) avg gross:    {comp['w_b'].abs().sum(axis=1).mean():.2f}")

    results = {
        "meta": {"n_names": int(prices.shape[1]),
                 "start": str(prices.index.min().date()),
                 "end": str(prices.index.max().date()),
                 "source": "stockanalysis.com (survivor-biased sandbox)"},
        "performance": {k: (None if isinstance(v, float) and np.isnan(v) else v)
                        for k, v in ps.items()},
        "cost_drag_bps_per_yr": {c: drags[c] * 1e4 for c in cost_cols},
        "total_cost_drag_bps_per_yr": total_drag * 1e4,
        "avg_gross_leverage": float(gross_exp.mean()),
        "avg_net_leverage": float(net_exp.mean()),
        "time_in_defensive_regime": frac_stressed,
        "avg_daily_turnover_1way": float(sim["turnover"].mean()),
    }
    with open(OUT, "w") as f:
        json.dump(results, f, indent=2, default=float)
    print(f"\nwrote {OUT}")
    print("\nCAVEAT: survivor-biased sandbox, ~2016 start, no 2008. Provisional.")


if __name__ == "__main__":
    main()
