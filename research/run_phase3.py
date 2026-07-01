"""
Phase 3 — skew-aware evaluation + historical stress windows.

Run:  python3 research/run_phase3.py   (writes _phase3_results.json)

Evaluates the final trend-v2 config (skew-honoring: chandelier 4xATR) with the
full metric set the brief requires, plus conditional performance in the stress
windows AVAILABLE in the sandbox (2018-Q4, 2020-COVID, 2022). 2008 and the 2010
flash crash are NOT in this data -> the true worst-case left tail is still
untested (flagged, not hidden). No avoidance fitting was done, so the stress
numbers are the honest as-is behavior.

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

OUT = os.path.join(os.path.dirname(__file__), "_phase3_results.json")

# skew-honoring final config (Phase 2 v2 tradeoff analysis)
FINAL = p15.TrendV2Params(chandelier_atr=4.0, rs_top_pct=0.40, donchian=100,
                          risk_fraction=0.0015)

STRESS = {
    "2018Q4_selloff": ("2018-10-01", "2018-12-31"),
    "2020_covid_crash": ("2020-02-19", "2020-04-30"),
    "2022_bear": ("2022-01-01", "2022-12-31"),
}


def drawdown_stats(net: pd.Series) -> dict:
    curve = (1 + net).cumprod()
    peak = curve.cummax()
    dd = curve / peak - 1.0
    trough = dd.idxmin()
    pk = curve[:trough].idxmax()
    after = curve[trough:]
    rec = after[after >= curve[pk]]
    recovered = None if rec.empty else rec.index[0]
    underwater = (dd < -1e-9)
    # longest underwater run (in trading days)
    longest, cur = 0, 0
    for u in underwater.values:
        cur = cur + 1 if u else 0
        longest = max(longest, cur)
    return {
        "max_drawdown": float(dd.min()),
        "peak_date": str(pk.date()), "trough_date": str(trough.date()),
        "recovery_date": None if recovered is None else str(recovered.date()),
        "peak_to_trough_days": int((trough - pk).days),
        "trough_to_recovery_days": None if recovered is None else int((recovered - trough).days),
        "longest_underwater_days": int(longest),
        "still_underwater": recovered is None,
    }


def full_metrics(net: pd.Series, trade_R: np.ndarray) -> dict:
    r = net.dropna()
    ann = np.sqrt(252)
    curve = (1 + r).cumprod()
    cagr = curve.iloc[-1] ** (252 / len(r)) - 1
    downside = r[r < 0].std()
    dd = drawdown_stats(r)
    R = trade_R[np.isfinite(trade_R)]
    wins, losses = R[R > 0], R[R < 0]
    monthly = (1 + r).resample("ME").prod() - 1
    return {
        "cagr": float(cagr),
        "ann_vol": float(r.std() * ann),
        "sharpe": float(r.mean() / r.std() * ann),
        "sortino": float(r.mean() / downside * ann) if downside else None,
        "calmar_mar": float(cagr / abs(dd["max_drawdown"])) if dd["max_drawdown"] else None,
        "max_drawdown": dd["max_drawdown"],
        "recovery_days": dd["trough_to_recovery_days"],
        "longest_underwater_days": dd["longest_underwater_days"],
        "skew_daily": float(stats.skew(r)),
        "skew_monthly": float(stats.skew(monthly.dropna())),
        "excess_kurtosis_daily": float(stats.kurtosis(r)),
        "tail_ratio": float(abs(np.quantile(r, 0.95)) / abs(np.quantile(r, 0.05))),
        "win_rate": float(len(wins) / len(R)),
        "avg_win_R": float(wins.mean()), "avg_loss_R": float(losses.mean()),
        "expectancy_R": float(R.mean()),
        "payoff_ratio": float(wins.mean() / abs(losses.mean())),
        "best_R": float(R.max()), "worst_R": float(R.min()),
        "n_trades": int(len(R)),
    }


def capacity_estimate(prices, volume, entry_weight=0.02, adv_cap=0.10) -> dict:
    """Crude capacity: largest AUM at which a typical position (entry_weight of
    NAV) stays under adv_cap of the name's median dollar ADV."""
    adv = (prices * volume.rolling(20, min_periods=5).mean())
    med_adv = float(adv.stack().median())
    aum = adv_cap * med_adv / entry_weight
    return {"median_name_ADV_usd": med_adv, "assumed_entry_weight": entry_weight,
            "assumed_adv_participation_cap": adv_cap,
            "approx_capacity_usd": aum}


def main():
    prices = load_price_panel(EXTENDED_UNIVERSE, "10Y", field="adj_close", verbose=False)
    volume = load_price_panel(EXTENDED_UNIVERSE, "10Y", field="volume", verbose=False)
    keep = prices.columns[prices.notna().mean() > 0.6]
    prices = prices[keep].dropna(how="all")
    volume = volume.reindex(columns=keep).reindex(prices.index)
    print(f"{prices.shape[1]} names x {prices.shape[0]} days | config: chandelier=4xATR")

    res = p15.backtest(prices, volume, FINAL)
    net = res["net_ret"]
    m = full_metrics(net, res["trade_R"])
    m["avg_annual_turnover_x"] = float(res["turnover"].mean() * 252)
    cap = capacity_estimate(prices, volume)

    print("\n" + "=" * 62 + "\nFULL METRICS (net of costs) — trend-v2 final\n" + "=" * 62)
    order = ["cagr", "ann_vol", "sharpe", "sortino", "calmar_mar", "max_drawdown",
             "recovery_days", "longest_underwater_days", "skew_daily",
             "skew_monthly", "excess_kurtosis_daily", "tail_ratio", "win_rate",
             "avg_win_R", "avg_loss_R", "expectancy_R", "payoff_ratio", "best_R",
             "worst_R", "n_trades", "avg_annual_turnover_x"]
    for k in order:
        v = m[k]
        print(f"  {k:26s} {v if v is None else round(v,4)}")
    print(f"  approx_capacity_usd        ${cap['approx_capacity_usd']/1e9:.2f}B "
          f"(median ADV ${cap['median_name_ADV_usd']/1e6:.0f}M, 2% pos, 10% ADV)")

    print("\n" + "=" * 62 + "\nSTRESS WINDOWS (as-is; NO avoidance fitting)\n" + "=" * 62)
    stress = {}
    for name, (a, b) in STRESS.items():
        seg = net[(net.index >= a) & (net.index <= b)]
        if seg.empty:
            continue
        cum = (1 + seg).prod() - 1
        curve = (1 + seg).cumprod()
        dd = (curve / curve.cummax() - 1).min()
        # market comparison over same window
        mkt = prices.pct_change().mean(axis=1)
        mkt_seg = mkt[(mkt.index >= a) & (mkt.index <= b)]
        mkt_cum = (1 + mkt_seg).prod() - 1
        stress[name] = {"strategy_return": float(cum), "strategy_maxDD": float(dd),
                        "worst_day": float(seg.min()), "market_return": float(mkt_cum)}
        print(f"  {name:18s} strat {cum:+.1%} (maxDD {dd:.1%}, worst day {seg.min():+.1%}) "
              f"| eq-wt mkt {mkt_cum:+.1%}")
    print("  NOTE: 2008 and 2010 flash crash are NOT in this data — the true "
          "worst-case\n  left tail is UNTESTED.")

    results = {"meta": {"config": "chandelier=4xATR, rs_top=0.40, donchian=100, "
                        "risk_fraction=0.0015", "n_names": int(prices.shape[1]),
                        "start": str(prices.index.min().date()),
                        "end": str(prices.index.max().date()),
                        "source": "stockanalysis.com (survivor-biased sandbox)"},
               "metrics": m, "capacity": cap, "stress_windows": stress}
    with open(OUT, "w") as f:
        json.dump(results, f, indent=2, default=float)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
