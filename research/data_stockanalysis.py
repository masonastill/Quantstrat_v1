"""
Real daily-price loader for Phase 0, backed by stockanalysis.com's open JSON
endpoint (no API key required).

>>> SURVIVORSHIP-BIAS WARNING <<<
This source only covers CURRENTLY-LISTED tickers. Names that were delisted,
acquired, or went to zero (Lehman, Bear Stearns, WorldCom, many 2000-02 and
2008-09 blowups) are simply absent. That biases the long/winner side UPWARD
and removes part of the left tail. It is acceptable for a Phase 0 *existence*
check (cross-sectional rank-IC and the cross-sleeve correlation are fairly
robust to survivorship), but ABSOLUTE performance and tail metrics MUST be
re-confirmed later on survivorship-bias-free, point-in-time data (e.g. QC
QuantBook or CRSP) before any of it is trusted. See docs/PHASE0_FINDINGS.md.

History depth: the endpoint serves up to ~10 years of daily bars (range=10Y),
so the panel typically starts ~2016. That covers the 2018-Q4, 2020-COVID and
2022 stress windows but NOT 2008/2010 — noted as a limitation.
"""
from __future__ import annotations

import io
import os
import time

import pandas as pd
import requests

CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE", "/root/.ccr/ca-bundle.crt")
_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_BASE = "https://stockanalysis.com/api/symbol/s/{sym}/history"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "_data_cache")


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": _UA})
    s.verify = CA_BUNDLE if os.path.exists(CA_BUNDLE) else True
    return s


def fetch_symbol(sym: str, rng: str = "10Y", sess: requests.Session | None = None,
                 retries: int = 3) -> pd.DataFrame | None:
    """Fetch one symbol's daily history -> DataFrame[date, close, adj_close, volume].

    `adj_close` (field 'a') is split/dividend adjusted and is what we use for
    return calculations. Returns None on persistent failure (caller skips it).
    """
    sess = sess or _session()
    url = _BASE.format(sym=sym.lower())
    for attempt in range(retries):
        try:
            r = sess.get(url, params={"range": rng, "period": "Daily"}, timeout=25)
            if r.status_code == 200:
                data = r.json().get("data", [])
                if not data:
                    return None
                df = pd.DataFrame(data)
                df["date"] = pd.to_datetime(df["t"])
                out = (df[["date", "c", "a", "v"]]
                       .rename(columns={"c": "close", "a": "adj_close", "v": "volume"})
                       .set_index("date").sort_index())
                return out
            if r.status_code in (429, 503):
                time.sleep(2 * (attempt + 1))
                continue
            return None
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return None


def load_price_panel(symbols: list[str], rng: str = "10Y", pause: float = 0.4,
                     use_cache: bool = True, field: str = "adj_close",
                     verbose: bool = True) -> pd.DataFrame:
    """Build a (dates x symbols) panel of `field` for the given symbols.

    Caches each symbol's raw history as CSV under research/_data_cache/ so reruns
    are instant and reproducible. Symbols that fail to load are skipped (and
    reported), never silently filled.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    sess = _session()
    series, missing = {}, []
    for i, sym in enumerate(symbols):
        cache_fp = os.path.join(CACHE_DIR, f"{sym.upper()}_{rng}.csv")
        df = None
        if use_cache and os.path.exists(cache_fp):
            df = pd.read_csv(cache_fp, index_col=0, parse_dates=True)
        else:
            df = fetch_symbol(sym, rng, sess)
            if df is not None:
                df.to_csv(cache_fp)
            time.sleep(pause)
        if df is None or field not in df.columns or df[field].dropna().empty:
            missing.append(sym)
            continue
        series[sym.upper()] = df[field]
        if verbose and (i + 1) % 25 == 0:
            print(f"  ...loaded {i + 1}/{len(symbols)}")
    panel = pd.DataFrame(series).sort_index()
    if verbose:
        print(f"panel: {panel.shape[0]} dates x {panel.shape[1]} symbols "
              f"({panel.index.min().date()} -> {panel.index.max().date()})")
        if missing:
            print(f"skipped {len(missing)} symbols (no data): {missing}")
    return panel


# A broad, liquid, multi-sector US large-cap universe (survivor-biased; see the
# module docstring). ~100 names across all GICS sectors so the cross-sectional
# tests have real dispersion and sector breadth, not a handful of correlated
# tech names.
DEFAULT_UNIVERSE = [
    # Tech / comms
    "AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CSCO", "ADBE", "CRM", "ACN", "TXN",
    "QCOM", "INTC", "AMD", "IBM", "INTU", "NOW", "AMAT", "MU", "GOOGL", "META",
    "NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS",
    # Consumer disc / staples
    "AMZN", "TSLA", "HD", "LOW", "NKE", "MCD", "SBUX", "BKNG", "TJX", "F", "GM",
    "PG", "KO", "PEP", "WMT", "COST", "TGT", "MDLZ", "CL", "MO", "PM", "KMB",
    # Health care
    "UNH", "JNJ", "LLY", "PFE", "MRK", "ABBV", "TMO", "ABT", "DHR", "BMY",
    "AMGN", "GILD", "CVS", "MDT", "ISRG",
    # Financials
    "BRK.B", "JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "SPGI", "AXP", "SCHW",
    "USB", "PNC", "CB", "MMC",
    # Industrials / materials / energy
    "CAT", "DE", "BA", "HON", "GE", "MMM", "UPS", "RTX", "LMT", "UNP", "EMR",
    "XOM", "CVX", "COP", "SLB", "EOG", "LIN", "APD", "FCX", "NEM",
    # Utilities / real estate
    "NEE", "DUK", "SO", "D", "AMT", "PLD", "SPG",
]

# A broader ~300-name liquid universe (still survivor-biased) used to test
# whether the weak large-cap factor edges strengthen with more cross-sectional
# breadth and mid-caps. Same caveats as DEFAULT_UNIVERSE.
_EXTRA_UNIVERSE = [
    "PANW", "SNPS", "CDNS", "KLAC", "LRCX", "ADI", "MCHP", "FTNT", "ANET", "ROP",
    "MSI", "ADSK", "WDAY", "TEAM", "DDOG", "ZS", "CRWD", "NET", "SNOW", "PLTR",
    "UBER", "ABNB", "SHOP", "PYPL", "MRVL", "ON", "NXPI", "STX", "WDC", "HPQ",
    "DELL", "HPE", "CTSH", "IT", "GLW", "KEYS", "LULU", "ROST", "DG", "DLTR",
    "YUM", "CMG", "DPZ", "MAR", "HLT", "RCL", "CCL", "EXPE", "GM", "APTV", "LEN",
    "DHI", "NVR", "PHM", "WHR", "BBY", "ULTA", "TSCO", "ORLY", "AZO", "GPC",
    "KMX", "KHC", "GIS", "K", "HSY", "STZ", "KDP", "SYY", "ADM", "KR", "HRL",
    "CAG", "CPB", "VRTX", "REGN", "ZTS", "BSX", "SYK", "BDX", "EW", "HUM", "CI",
    "CNC", "ELV", "MCK", "COR", "IDXX", "IQV", "A", "DXCM", "MTD", "WST", "RMD",
    "BIIB", "MRNA", "HCA", "CAH", "ZBH", "BAX", "TFC", "COF", "STT", "TROW",
    "NTRS", "FITB", "HBAN", "RF", "CFG", "KEY", "MTB", "ICE", "CME", "MCO",
    "AON", "AJG", "TRV", "ALL", "PGR", "MET", "PRU", "AIG", "AFL", "SYF", "V",
    "MA", "GD", "NOC", "ITW", "ETN", "PH", "ROK", "DOV", "FDX", "CSX", "NSC",
    "WM", "RSG", "PCAR", "CMI", "FAST", "GWW", "URI", "CARR", "OTIS", "JCI",
    "IR", "AME", "EFX", "VRSK", "PWR", "MPC", "PSX", "VLO", "OXY", "WMB", "KMI",
    "OKE", "HAL", "BKR", "DVN", "FANG", "SHW", "ECL", "NUE", "DOW", "DD", "PPG",
    "VMC", "MLM", "CTVA", "ALB", "AEP", "EXC", "XEL", "SRE", "PEG", "ED", "WEC",
    "ES", "AEE", "DTE", "PCG", "EIX", "CEG", "O", "CCI", "EQIX", "PSA", "DLR",
    "WELL", "AVB", "EQR", "VTR", "ARE", "CBRE", "CHTR", "EA", "TTWO",
]

# De-duplicated union, order preserved.
EXTENDED_UNIVERSE = list(dict.fromkeys(DEFAULT_UNIVERSE + _EXTRA_UNIVERSE))
