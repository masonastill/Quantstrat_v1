"""
Deep-history daily loader (2005+) backed by Yahoo Finance's chart endpoint.

Purpose: get 2008- and 2010-inclusive history so the trend sleeve's worst-case
left tail can finally be stress-tested (Phase 3 gap). Same panel interface as
data_stockanalysis.py so the analysis code is unchanged.

>>> STILL SURVIVORSHIP-BIASED. <<<
Yahoo only serves CURRENTLY-LISTED tickers. Names that were delisted / went to
zero in 2008-09 (Lehman, Bear, Wachovia, WaMu, CIT, ...) are ABSENT. So this
tests how the strategy behaves through a 2008-magnitude shock ON THE SURVIVORS,
which UNDERSTATES the true tail (the real blowups are missing). It is a large
improvement over the 2016-start sandbox, but it is NOT survivorship-free data.
True survivorship-free history still requires a paid source (funded QC org,
CRSP, Norgate). See docs/PHASE3_FINDINGS.md.
"""
from __future__ import annotations

import os
import time

import pandas as pd
import requests

CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE", "/root/.ccr/ca-bundle.crt")
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
CACHE_DIR = os.path.join(os.path.dirname(__file__), "_data_cache_yahoo")
_HOSTS = ("query1", "query2")


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": _UA})
    s.verify = CA_BUNDLE if os.path.exists(CA_BUNDLE) else True
    return s


def _yahoo_symbol(sym: str) -> str:
    # Yahoo uses '-' for share classes (BRK.B -> BRK-B)
    return sym.upper().replace(".", "-")


def fetch_symbol(sym: str, sess: requests.Session, start_ts: int = 1104537600,
                 retries: int = 4) -> pd.DataFrame | None:
    """Fetch full daily history -> DataFrame[date, adj_close, volume]."""
    ysym = _yahoo_symbol(sym)
    for attempt in range(retries):
        host = _HOSTS[attempt % 2]
        url = (f"https://{host}.finance.yahoo.com/v8/finance/chart/{ysym}"
               f"?period1={start_ts}&period2=1790000000&interval=1d"
               f"&events=div%2Csplit")
        try:
            r = sess.get(url, timeout=25)
            if r.status_code == 200:
                res = r.json()["chart"]["result"]
                if not res:
                    return None
                d = res[0]
                ts = d.get("timestamp")
                if not ts:
                    return None
                adj = d["indicators"].get("adjclose", [{}])[0].get("adjclose")
                vol = d["indicators"]["quote"][0].get("volume")
                if adj is None:
                    return None
                df = pd.DataFrame({
                    "date": pd.to_datetime(ts, unit="s").normalize(),
                    "adj_close": adj, "volume": vol}).dropna(subset=["adj_close"])
                return df.set_index("date").sort_index()
            if r.status_code in (429, 999, 503):
                time.sleep(2 * (attempt + 1))
                continue
            return None
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return None


def load_price_panel(symbols: list[str], field: str = "adj_close",
                     start: str = "2005-01-01", pause: float = 1.1,
                     use_cache: bool = True, verbose: bool = True) -> pd.DataFrame:
    """Build a (dates x symbols) panel of `field` from Yahoo, cached per symbol."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    sess = _session()
    start_ts = int(pd.Timestamp(start).timestamp())
    series, missing = {}, []
    for i, sym in enumerate(symbols):
        fp = os.path.join(CACHE_DIR, f"{sym.upper()}.csv")
        df = None
        if use_cache and os.path.exists(fp):
            df = pd.read_csv(fp, index_col=0, parse_dates=True)
        else:
            df = fetch_symbol(sym, sess, start_ts)
            if df is not None:
                df.to_csv(fp)
            time.sleep(pause)
        if df is None or field not in df.columns or df[field].dropna().empty:
            missing.append(sym)
            continue
        series[sym.upper()] = df[field]
        if verbose and (i + 1) % 25 == 0:
            print(f"  ...loaded {i + 1}/{len(symbols)}")
    panel = pd.DataFrame(series).sort_index()
    panel = panel[panel.index >= pd.Timestamp(start)]
    if verbose:
        print(f"panel: {panel.shape[0]} dates x {panel.shape[1]} symbols "
              f"({panel.index.min().date()} -> {panel.index.max().date()})")
        if missing:
            print(f"skipped {len(missing)}: {missing}")
    return panel
