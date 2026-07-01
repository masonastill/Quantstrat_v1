"""
Phase 2 (re-run) — robustness battery on the REDESIGNED trend sleeve (v2).

Run:  python3 research/run_phase2_v2.py   (a few minutes)

Repeats the Phase 2 battery for phase15_trend (fixed-shares, let-winners-run),
which Phase 1.5 introduced. Answers whether the redesign is robust, not just
prettier: parameter plateaus, universal-principle, negative control (map to
market), walk-forward, Deflated Sharpe + PBO.

Survivor-biased sandbox -> PROVISIONAL.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
from scipy import stats

from data_stockanalysis import EXTENDED_UNIVERSE, load_price_panel
import phase15_trend as p15
import phase2_robustness as rb
from run_phase1 import perf_stats

OUT = os.path.join(os.path.dirname(__file__), "_phase2_v2_results.json")


def monthly_skew(net: pd.Series) -> float:
    m = (1 + net).resample("ME").prod() - 1
    return float(stats.skew(m.dropna()))


def run(prices, volume, **kw):
    p = p15.TrendV2Params(**kw)
    r = p15.backtest(prices, volume, p)
    return r["net_ret"]


def main():
    prices = load_price_panel(EXTENDED_UNIVERSE, "10Y", field="adj_close", verbose=False)
    volume = load_price_panel(EXTENDED_UNIVERSE, "10Y", field="volume", verbose=False)
    keep = prices.columns[prices.notna().mean() > 0.6]
    prices = prices[keep].dropna(how="all")
    volume = volume.reindex(columns=keep).reindex(prices.index)
    idx_px = (1 + prices.pct_change().mean(axis=1)).cumprod()
    print(f"{prices.shape[1]} names x {prices.shape[0]} days")
    results = {"meta": {"n_names": int(prices.shape[1]),
                        "start": str(prices.index.min().date()),
                        "end": str(prices.index.max().date()),
                        "source": "stockanalysis.com (survivor-biased sandbox)"}}

    # ---- 1. Parameter plateaus (Sharpe / monthly skew) ----------------- #
    print("\n[1] PARAMETER ROBUSTNESS (Sharpe, monthly-skew)")
    plateau = {}
    sweeps = {
        "chandelier_atr": [3.0, 4.0, 5.0, 6.0, 7.0],
        "donchian": [50, 100, 150, 200],
        "rs_top_pct": [0.2, 0.4, 0.6, 1.0],
        "risk_fraction": [0.001, 0.0015, 0.002, 0.003],
    }
    for param, vals in sweeps.items():
        row = {}
        for v in vals:
            net = run(prices, volume, **{param: v})
            p = perf_stats(net, net)
            row[v] = {"sharpe": round(p["sharpe"], 2), "mskew": round(monthly_skew(net), 2)}
        plateau[param] = row
        print(f"  {param}: " + "  ".join(
            f"{v}->Sh{row[v]['sharpe']:+.2f}/msk{row[v]['mskew']:+.2f}" for v in vals))
    results["parameter_robustness"] = plateau

    # ---- 2. Universal-principle (random universe halves) --------------- #
    print("\n[2] UNIVERSAL-PRINCIPLE (12 random universe halves)")
    rng = np.random.default_rng(23)
    cols = list(prices.columns)
    shs, msk = [], []
    for _ in range(12):
        pick = list(rng.choice(cols, len(cols) // 2, replace=False))
        net = p15.backtest(prices[pick], volume[pick])["net_ret"]
        shs.append(perf_stats(net, net)["sharpe"]); msk.append(monthly_skew(net))
    shs, msk = np.array(shs), np.array(msk)
    results["universal_principle"] = {
        "sharpe_mean": float(shs.mean()), "sharpe_std": float(shs.std()),
        "frac_sharpe_positive": float((shs > 0).mean()),
        "frac_mskew_positive": float((msk > 0).mean())}
    print(f"  Sharpe {shs.mean():.2f}+/-{shs.std():.2f} ({(shs>0).mean():.0%} +); "
          f"monthly-skew positive in {(msk>0).mean():.0%}")

    # ---- 3. Negative control (map to market): 3 regime buckets --------- #
    print("\n[3] NEGATIVE CONTROL (trend should win in up-trends, lag in chop)")
    net = run(prices, volume)                       # base trend-v2
    mom60 = (idx_px / idx_px.shift(60) - 1.0).shift(1)
    regime = pd.Series(np.where(mom60 > 0.10, "uptrend",
                       np.where(mom60 < -0.10, "downtrend", "choppy")),
                       index=idx_px.index)
    cond = {}
    r, g = net.align(regime, join="inner")
    for lab in ["uptrend", "choppy", "downtrend"]:
        sub = r[g == lab]
        cond[lab] = {"sharpe": round(float(sub.mean() / sub.std() * np.sqrt(252)), 2)
                     if sub.std() else None, "ann_ret": round(float(sub.mean() * 252), 3),
                     "frac_days": round(float((g == lab).mean()), 2)}
    results["negative_control"] = cond
    for lab in ["uptrend", "choppy", "downtrend"]:
        print(f"  {lab:9s} Sharpe {cond[lab]['sharpe']}  ann {cond[lab]['ann_ret']:+.1%} "
              f"({cond[lab]['frac_days']:.0%} of days)")
    ok = (cond["uptrend"]["sharpe"] or 0) > (cond["choppy"]["sharpe"] or 0)
    print(f"  -> trend wins in up-trends vs chop: {'YES (expected)' if ok else 'NO (suspect)'}")

    # ---- 4. Walk-forward (monthly skew per segment) -------------------- #
    print("\n[4] WALK-FORWARD (holdout touched once)")
    splits = {"train": ("2016-01-01", "2019-12-31"),
              "validation": ("2020-01-01", "2021-12-31"),
              "holdout": ("2022-01-01", "2026-12-31")}
    wf = {}
    for s, (a, b) in splits.items():
        m = (net.index >= a) & (net.index <= b)
        p = perf_stats(net[m], net[m])
        wf[s] = {"sharpe": round(p["sharpe"], 2), "mskew": round(monthly_skew(net[m]), 2),
                 "net_ann": round(p["net_ann_return"], 4), "maxDD": round(p["max_drawdown"], 3)}
        print(f"  {s:11s} Sharpe {wf[s]['sharpe']:+.2f}  mskew {wf[s]['mskew']:+.2f}  "
              f"ret {wf[s]['net_ann']:+.1%}  DD {wf[s]['maxDD']:.1%}")
    results["walk_forward"] = wf

    # ---- 5. Deflated Sharpe + PBO on a config grid --------------------- #
    print("\n[5] MULTIPLE TESTING (Deflated Sharpe + PBO)")
    grid = {}
    for ch in (4.0, 5.0, 6.0):
        for dn in (100, 150):
            for rf in (0.0015, 0.002):
                net_i = run(prices, volume, chandelier_atr=ch, donchian=dn, risk_fraction=rf)
                grid[f"ch{ch}_dn{dn}_rf{rf}"] = net_i
    R = pd.DataFrame(grid).dropna(how="any")
    daily_sr = R.mean() / R.std()
    n_trials = 40
    best = daily_sr.idxmax()
    dsr = rb.deflated_sharpe_ratio(R[best], n_trials, float(daily_sr.var()))
    pbo = rb.pbo_cscv(R, n_splits=10)
    results["multiple_testing"] = {"best_config": best, "deflated_sharpe": dsr,
                                   "pbo": pbo, "n_trials_assumed": n_trials}
    print(f"  best: {best}")
    print(f"  Deflated Sharpe {dsr.get('dsr'):.3f} (SR {dsr.get('sharpe_annual'):.2f} "
          f"vs SR0 {dsr.get('sr0_benchmark_annual'):.2f}); passes .95 = {dsr.get('passes_0.95')}")
    print(f"  PBO {pbo.get('pbo'):.2f} ({pbo['n_configs']} configs; want < 0.5)")

    with open(OUT, "w") as f:
        json.dump(results, f, indent=2, default=float)
    print(f"\nwrote {OUT}")
    print("CAVEAT: survivor-biased sandbox, ~2016 start, no 2008. Provisional.")


if __name__ == "__main__":
    main()
