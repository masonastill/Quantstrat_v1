"""
Phase 2 — robustness battery (NOT optimization).

Run:  python3 research/run_phase2.py   (a few minutes; caches data)

Produces, per the brief:
  1. Parameter robustness (plateau vs knife-edge) over key params.
  2. Universal-principle test: edge across RANDOM universe subsets.
  3. Negative control ("map to market"): trend sleeve should win in trends /
     lose in chop; MR sleeve the reverse. A sleeve that wins everywhere is
     suspected of fitting noise.
  4. Walk-forward: train / validation / holdout (holdout touched once).
  5. Multiple-testing: Deflated Sharpe Ratio + PBO (CSCV).

Writes research/_phase2_results.json. All numbers on the survivor-biased
sandbox -> PROVISIONAL.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from data_stockanalysis import EXTENDED_UNIVERSE, SECTOR_MAP, load_price_panel
import phase1_backtest as bt
import phase2_robustness as rb
from run_phase1 import perf_stats

OUT = os.path.join(os.path.dirname(__file__), "_phase2_results.json")


def sim_net(prices, volume, W, cfg, band):
    s = bt.simulate(prices, volume, W, cfg.cost, rebalance_band=band)
    return s["net_ret"], s["gross_ret"], s["turnover"].mean()


def cfg_alloc(at, am):
    c = bt.Config(); c.risk.alloc_trend = at; c.risk.alloc_mr = am
    return c


def main():
    print("Loading sandbox data...")
    prices = load_price_panel(EXTENDED_UNIVERSE, "10Y", field="adj_close", verbose=False)
    volume = load_price_panel(EXTENDED_UNIVERSE, "10Y", field="volume", verbose=False)
    keep = prices.columns[prices.notna().mean() > 0.6]
    prices = prices[keep].dropna(how="all")
    volume = volume.reindex(columns=keep).reindex(prices.index)
    rets = prices.pct_change()
    idx_px = (1 + rets.mean(axis=1)).cumprod()
    print(f"{prices.shape[1]} names x {prices.shape[0]} days")

    base = bt.Config()
    wa = bt.trend_sleeve(prices, volume, base)         # min_hold-independent
    wb = {mh: bt.mr_sleeve(prices, _mh(base, mh)) for mh in (1, 3)}
    results = {"meta": {"n_names": int(prices.shape[1]),
                        "start": str(prices.index.min().date()),
                        "end": str(prices.index.max().date()),
                        "source": "stockanalysis.com (survivor-biased sandbox)"}}

    # ---------------- 1. Parameter plateaus ------------------------------ #
    print("\n[1] PARAMETER ROBUSTNESS (plateau vs knife-edge)")
    plateau = {}
    # (a) no-trade band  (b) allocation  (c) z_entry  (d) chandelier_atr
    band_row = {}
    for band in [0.0, 0.005, 0.01, 0.02, 0.03]:
        W, _ = bt.combine_and_overlay(wa, wb[3], prices, SECTOR_MAP, cfg_alloc(0.5, 0.5))
        n, g, t = sim_net(prices, volume, W, base, band)
        band_row[band] = round(perf_stats(n, g)["sharpe"], 3)
    plateau["rebalance_band_sharpe"] = band_row
    print("  band -> net Sharpe:", band_row)

    alloc_row = {}
    for at in [1.0, 0.75, 0.5, 0.25, 0.0]:
        W, _ = bt.combine_and_overlay(wa, wb[3], prices, SECTOR_MAP, cfg_alloc(at, 1 - at))
        n, g, t = sim_net(prices, volume, W, base, 0.01)
        p = perf_stats(n, g)
        alloc_row[at] = {"sharpe": round(p["sharpe"], 3), "skew": round(p["skew"], 2)}
    plateau["alloc_trend"] = alloc_row
    print("  alloc_trend -> (Sharpe, skew):", alloc_row)

    ze_row = {}
    for ze in [1.0, 1.5, 2.0, 2.5]:
        c = _mh(base, 3); c.mr.z_entry = ze
        wb_ze = bt.mr_sleeve(prices, c)
        W, _ = bt.combine_and_overlay(wa, wb_ze, prices, SECTOR_MAP, cfg_alloc(0.5, 0.5))
        n, g, t = sim_net(prices, volume, W, base, 0.01)
        ze_row[ze] = round(perf_stats(n, g)["sharpe"], 3)
    plateau["mr_z_entry_sharpe"] = ze_row
    print("  z_entry -> net Sharpe:", ze_row)

    ch_row = {}
    for m in [2.0, 3.0, 4.0, 5.0]:
        c = bt.Config(); c.trend.chandelier_atr = m
        wa_m = bt.trend_sleeve(prices, volume, c)
        W, _ = bt.combine_and_overlay(wa_m, wb[3], prices, SECTOR_MAP, cfg_alloc(1.0, 0.0))
        n, g, t = sim_net(prices, volume, W, base, 0.01)
        ch_row[m] = round(perf_stats(n, g)["sharpe"], 3)
    plateau["trend_chandelier_atr_sharpe(trend_only)"] = ch_row
    print("  chandelier_atr (trend-only) -> net Sharpe:", ch_row)
    results["parameter_robustness"] = plateau

    # ---------------- 2. Universal-principle (random subsets) ------------ #
    print("\n[2] UNIVERSAL-PRINCIPLE (random universe halves, trend-only)")
    rng = np.random.default_rng(11)
    subset_sharpes = []
    cols = list(prices.columns)
    for _ in range(12):
        pick = rng.choice(cols, size=len(cols) // 2, replace=False)
        wa_s = wa[pick]
        W, _ = bt.combine_and_overlay(wa_s, wb[3][pick], prices[pick], SECTOR_MAP,
                                      cfg_alloc(1.0, 0.0))
        n, g, t = sim_net(prices[pick], volume[pick], W, base, 0.01)
        subset_sharpes.append(perf_stats(n, g)["sharpe"])
    ss = np.array(subset_sharpes)
    results["universal_principle"] = {
        "trend_only_subset_sharpe_mean": float(ss.mean()),
        "trend_only_subset_sharpe_std": float(ss.std()),
        "frac_positive": float((ss > 0).mean())}
    print(f"  random-half Sharpe: mean {ss.mean():.2f} +/- {ss.std():.2f}, "
          f"{(ss>0).mean():.0%} positive")

    # ---------------- 3. Negative control (map to market) --------------- #
    print("\n[3] NEGATIVE CONTROL (map to market)")
    regime = rb.classify_regimes(idx_px, trend_win=60, chop_thresh=0.10)
    trend_ret = (wa.shift(1) * rets).sum(axis=1)
    mr_ret = (wb[1].shift(1) * rets).sum(axis=1)
    cs_trend = rb.conditional_sharpe(trend_ret, regime)
    cs_mr = rb.conditional_sharpe(mr_ret, regime)
    results["negative_control"] = {"trend_sleeve": cs_trend, "mr_sleeve": cs_mr,
                                   "frac_trending": float((regime == "trending").mean())}
    print(f"  trend sleeve Sharpe  trending={cs_trend['trending']:.2f} "
          f"choppy={cs_trend['choppy']:.2f}  (want trending > choppy)")
    print(f"  MR sleeve Sharpe     trending={cs_mr['trending']:.2f} "
          f"choppy={cs_mr['choppy']:.2f}  (want choppy > trending)")

    # ---------------- 4. Walk-forward (holdout touched once) ------------ #
    print("\n[4] WALK-FORWARD (train/validation/holdout)")
    splits = {"train": ("2016-01-01", "2019-12-31"),
              "validation": ("2020-01-01", "2021-12-31"),
              "holdout": ("2022-01-01", "2026-12-31")}
    masks = rb.walk_forward_segments(prices.index, splits)
    wf = {}
    for name, cfg in [("trend_only", cfg_alloc(1.0, 0.0)), ("blend_5050", cfg_alloc(0.5, 0.5))]:
        W, _ = bt.combine_and_overlay(wa, wb[3], prices, SECTOR_MAP, cfg)
        n, g, _t = sim_net(prices, volume, W, base, 0.01)
        seg = {}
        for s, m in masks.items():
            seg_dates = prices.index[m]
            sub_n = n[n.index.isin(seg_dates)]
            sub_g = g[g.index.isin(seg_dates)]
            p = perf_stats(sub_n, sub_g)
            seg[s] = {"net_ann": round(p["net_ann_return"], 4),
                      "sharpe": round(p["sharpe"], 2), "skew": round(p["skew"], 2),
                      "maxDD": round(p["max_drawdown"], 3)}
        wf[name] = seg
        print(f"  {name}: " + " | ".join(
            f"{s}: Sh {seg[s]['sharpe']:+.2f} ret {seg[s]['net_ann']:+.1%} sk {seg[s]['skew']:+.2f}"
            for s in ["train", "validation", "holdout"]))
    results["walk_forward"] = wf

    # ---------------- 5. Multiple-testing: DSR + PBO -------------------- #
    print("\n[5] MULTIPLE TESTING (Deflated Sharpe + PBO)")
    grid_returns = {}
    for at in (1.0, 0.75, 0.5):
        for band in (0.005, 0.01, 0.02):
            for mh in (1, 3):
                W, _ = bt.combine_and_overlay(wa, wb[mh], prices, SECTOR_MAP,
                                              cfg_alloc(at, 1 - at))
                n, _g, _t = sim_net(prices, volume, W, base, band)
                grid_returns[f"a{at}_b{band}_h{mh}"] = n
    R = pd.DataFrame(grid_returns).dropna(how="any")
    daily_sr = R.mean() / R.std()
    n_trials = 50   # honest estimate of total configs searched across Phase 1-2
    best_col = daily_sr.idxmax()
    dsr = rb.deflated_sharpe_ratio(R[best_col], n_trials, float(daily_sr.var()))
    pbo = rb.pbo_cscv(R, n_splits=10)
    results["multiple_testing"] = {"best_config": best_col, "deflated_sharpe": dsr,
                                   "pbo": pbo, "n_trials_assumed": n_trials}
    print(f"  best config: {best_col}")
    print(f"  Deflated Sharpe: {dsr.get('dsr'):.3f} (annual SR {dsr.get('sharpe_annual'):.2f} "
          f"vs benchmark {dsr.get('sr0_benchmark_annual'):.2f}); passes .95 = {dsr.get('passes_0.95')}")
    print(f"  PBO: {pbo.get('pbo'):.2f} ({pbo['n_configs']} configs) "
          f"(want < 0.5)")

    with open(OUT, "w") as f:
        json.dump(results, f, indent=2, default=float)
    print(f"\nwrote {OUT}")
    print("CAVEAT: survivor-biased sandbox, ~2016 start, no 2008. Provisional.")


def _mh(cfg: bt.Config, mh: int) -> bt.Config:
    import copy
    c = copy.deepcopy(cfg); c.mr.min_hold = mh
    return c


if __name__ == "__main__":
    main()
