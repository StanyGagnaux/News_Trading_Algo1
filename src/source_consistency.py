"""
source_consistency.py -- Yahoo Finance (holdout price source) vs Bloomberg
(prices.csv), and the coverage facts for the frozen-config note.

1. Consistency, 2026-01-02 -> 2026-07-14, 20 tickers drawn at random (fixed
   seed) from universe tickers with Bloomberg prices in that window, plus
   NDX vs ^NDX: correlation of daily returns, mean absolute difference (bps),
   share of days differing by more than 5 bps, for close-to-close and
   open-to-open returns (and open-to-close, the event study's day-1 window).
2. Holdout availability: which universe tickers Yahoo cannot supply for
   2026-06-02 -> 2026-10-16. Only row COUNTS are kept; no holdout prices are
   stored or used.
3. Universe tickers with no Bloomberg price data, and the headlines affected.

USAGE (from the project root):  python3 src/source_consistency.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from paths import PRICES, NEWS_CLEAN, TICKERS, OUTPUTS
from newsdrift.data import load_prices_yfinance
from splits import INDEX_TICKERS

SEED = 20261018
N_SAMPLE = 20
CHECK_START, CHECK_END = "2026-01-02", "2026-07-14"
HOLDOUT_START, HOLDOUT_END = "2026-06-02", "2026-10-16"
DIFF_BPS = 5.0
OUT = OUTPUTS / "source_consistency_2026-10-18.csv"


def yahoo(ticker: str, start: str, end_inclusive: str, symbol: str | None = None) -> pd.DataFrame:
    """Daily adjusted OHLC from Yahoo; empty frame if Yahoo has nothing."""
    end = (pd.Timestamp(end_inclusive) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")  # yf end is exclusive
    try:
        df = load_prices_yfinance([symbol or ticker], start, end)
    except Exception as e:                       # delisted / unknown symbol
        print(f"    yahoo: {symbol or ticker} unavailable ({type(e).__name__})")
        return pd.DataFrame()
    return df.dropna(subset=["open", "close"]).assign(ticker=ticker)


def returns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("date")
    return pd.DataFrame({"date": df.date.values,
                         "close_to_close": df.close.pct_change().values,
                         "open_to_open": df.open.pct_change().values,
                         "open_to_close": (df.close / df.open - 1).values})


def compare(bbg: pd.DataFrame, yf: pd.DataFrame, label: str) -> list[dict]:
    m = returns(bbg).merge(returns(yf), on="date", suffixes=("_bbg", "_yf")).dropna()
    rows = []
    for s in ("close_to_close", "open_to_open", "open_to_close"):
        a, b = m[f"{s}_bbg"], m[f"{s}_yf"]
        d = (a - b).abs() * 1e4
        rows.append({"ticker": label, "series": s, "corr": a.corr(b),
                     "mean_abs_diff_bps": d.mean(), "share_gt_5bps": (d > DIFF_BPS).mean(),
                     "N_days": len(m)})
    return rows


def pooled(raw: dict) -> pd.DataFrame:
    rows = []
    for s, parts in raw.items():
        a = pd.concat([p[0] for p in parts]); b = pd.concat([p[1] for p in parts])
        d = (a - b).abs() * 1e4
        rows.append({"series": s, "corr": a.corr(b), "mean_abs_diff_bps": d.mean(),
                     "median_abs_diff_bps": d.median(), "share_gt_5bps": (d > DIFF_BPS).mean(),
                     "N_ticker_days": len(d)})
    return pd.DataFrame(rows)


def consistency(px: pd.DataFrame, universe: list[str]) -> None:
    win = px[(px.date >= CHECK_START) & (px.date <= CHECK_END)]
    eligible = sorted(set(win.ticker) & set(universe))
    sample = sorted(np.random.default_rng(SEED).choice(eligible, N_SAMPLE, replace=False))
    print(f"\n1. CONSISTENCY {CHECK_START} -> {CHECK_END} | seed {SEED} | "
          f"{N_SAMPLE} of {len(eligible)} eligible tickers:\n   {', '.join(sample)}")
    per, raw = [], {s: [] for s in ("close_to_close", "open_to_open", "open_to_close")}
    for t in sample + ["NDX"]:
        y = yahoo(t, CHECK_START, CHECK_END, "^NDX" if t == "NDX" else None)
        if y.empty:
            continue
        b = win[win.ticker == t]
        per += compare(b, y, t)
        if t != "NDX":
            m = returns(b).merge(returns(y), on="date", suffixes=("_bbg", "_yf")).dropna()
            for s in raw:
                raw[s].append((m[f"{s}_bbg"], m[f"{s}_yf"]))
    per = pd.DataFrame(per)
    per.to_csv(OUT, index=False)
    print("\n   pooled over the 20 tickers:")
    print(pooled(raw).to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print("\n   NDX vs ^NDX:")
    print(per[per.ticker == "NDX"].to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    worst = per[(per.ticker != "NDX") & (per.series == "close_to_close")].nlargest(5, "mean_abs_diff_bps")
    print("\n   largest close-to-close differences by ticker:")
    print(worst.to_string(index=False, float_format=lambda v: f"{v:.4f}"))


def holdout_availability(universe: list[str], news: pd.DataFrame) -> None:
    print(f"\n2. YAHOO AVAILABILITY {HOLDOUT_START} -> {HOLDOUT_END} (row counts only)")
    counts = {t: len(yahoo(t, HOLDOUT_START, HOLDOUT_END)) for t in universe}
    missing = sorted(t for t, n in counts.items() if n == 0)
    recent = set(news.ticker[news.ts >= pd.Timestamp("2026-01-01", tz="UTC")])
    print(f"   universe {len(universe)} | Yahoo cannot supply {len(missing)}: {', '.join(missing)}")
    active_missing = sorted(set(missing) & recent)
    print(f"   of those, with news in 2026 (likely still active): {len(active_missing)} "
          f"{', '.join(active_missing) if active_missing else ''}")
    short = sorted(t for t, n in counts.items() if 0 < n < 0.9 * max(counts.values()))
    print(f"   partial coverage (< 90% of days): {len(short)} {', '.join(short)}")


def missing_bloomberg(px: pd.DataFrame, universe: list[str], news: pd.DataFrame) -> None:
    no_px = sorted(set(universe) - set(px.ticker))
    affected = news[news.ticker.isin(no_px)]
    d = affected.ts.dt.tz_convert(None).dt.normalize()
    print(f"\n3. UNIVERSE TICKERS WITHOUT BLOOMBERG PRICES: {len(no_px)}\n   {', '.join(no_px)}")
    print(f"   headlines affected: {len(affected):,} of {len(news):,} "
          f"({len(affected) / len(news):.1%}); training {(d <= '2024-04-29').sum():,}, "
          f"test {((d > '2024-04-29') & (d <= '2026-06-01')).sum():,}")
    print(f"   tickers with news among them: {affected.ticker.nunique()}")


def main():
    universe = sorted({t.strip().upper() for t in open(TICKERS) if t.strip()})
    px = pd.read_csv(PRICES, parse_dates=["date"])
    px = px[~px.ticker.isin(INDEX_TICKERS - {"NDX"})]
    news = pd.read_csv(NEWS_CLEAN, usecols=["timestamp", "ticker"])
    news["ts"] = pd.to_datetime(news.timestamp, utc=True)
    consistency(px, universe)
    missing_bloomberg(px[px.ticker != "NDX"], universe, news)
    holdout_availability(universe, news)
    print(f"\nsaved per-ticker table: {OUT.name}")


if __name__ == "__main__":
    main()
