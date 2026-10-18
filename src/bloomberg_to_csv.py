"""
bloomberg_to_csv.py -- convert a Bloomberg Excel price export into the
newsdrift canonical prices CSV, plus a data-audit mode for the full dataset.

================================ HOW TO EXPORT FROM THE TERMINAL =============
On the Bloomberg terminal PC, open Excel (Bloomberg add-in loaded) and create
ONE SHEET PER TICKER, sheet name = ticker (e.g. "AAPL"). In cell A1 of each
sheet, enter:

  =BDH("AAPL US Equity", "PX_OPEN,PX_HIGH,PX_LOW,PX_LAST,PX_VOLUME",
       "1/1/2016", "", "Dir=V", "Dts=S", "Sort=A")

This fills columns: Date | Open | High | Low | Close | Volume.
Tip: build the formula once, then use a helper sheet listing all tickers and
copy the formula across sheets (or ask the terminal助 desk for the
"spreadsheet builder" template -- Nasdaq-100 takes ~15 minutes).

For POINT-IN-TIME index membership (survivorship-bias control), also export:
  =BDS("NDX Index", "INDX_MWEIGHT_HIST", "END_DATE_OVERRIDE=20160101")
one call per year-end, into a sheet named MEMBERS_YYYY. This script will pick
those up automatically if present.

Save as prices_export.xlsx, copy it off the terminal PC, then run:

  python bloomberg_to_csv.py convert --xlsx prices_export.xlsx --out prices.csv
  python bloomberg_to_csv.py audit   --prices prices.csv --news news_history.csv
==============================================================================
"""
from __future__ import annotations
import argparse
import sys

import numpy as np
import pandas as pd

from paths import PRICES

CANON = ["date", "ticker", "open", "high", "low", "close", "volume"]


# ------------------------------- CONVERT ------------------------------------
SKIP_SHEETS = {"INSTRUCTIONS", "ADD_TICKERS", "PROBLEMS"}


def convert(xlsx_paths, out_path: str):
    if isinstance(xlsx_paths, str):
        xlsx_paths = [xlsx_paths]
    frames, members = [], {}
    for xlsx_path in xlsx_paths:
        print(f"--- {xlsx_path} ---")
        _convert_one(xlsx_path, frames, members)
    _finish(frames, members, out_path)


def _convert_one(xlsx_path, frames, members):
    xl = pd.ExcelFile(xlsx_path)
    for sheet in xl.sheet_names:
        if sheet.upper() in SKIP_SHEETS:
            continue
        if sheet.upper().startswith("MEMBERS"):
            m = xl.parse(sheet)
            members[sheet] = m
            continue
        df = xl.parse(sheet, header=None)
        # locate the header row BDH writes (first row whose col0 parses as date
        # OR a row containing 'Date'); handle both layouts
        start = 0
        for i in range(min(10, len(df))):
            v = str(df.iloc[i, 0]).strip().lower()
            if v == "date":
                start = i + 1
                break
            try:
                pd.Timestamp(df.iloc[i, 0])
                start = i
                break
            except Exception:
                continue
        # accept 2-col (date+PX_LAST, e.g. RF), 6-col (OHLCV) or 9-col layouts
        # (OHLCV + PX_BID + PX_ASK + CUR_MKT_CAP)
        ncols = df.iloc[start:, :9].dropna(axis=1, how="all").shape[1]
        if ncols >= 9:
            cols = ["date", "open", "high", "low", "close", "volume",
                    "bid", "ask", "mktcap"]
        elif ncols >= 6:
            cols = ["date", "open", "high", "low", "close", "volume"]
        elif ncols >= 5:
            cols = ["date", "open", "high", "low", "close"]
        else:
            cols = ["date", "close"]
        block = df.iloc[start:, :len(cols)].copy()
        block.columns = cols
        block = block.dropna(subset=["date", "close"])
        block["date"] = pd.to_datetime(block["date"], errors="coerce")
        block = block.dropna(subset=["date"])
        for c in cols[1:]:
            block[c] = pd.to_numeric(block[c], errors="coerce")
        block["ticker"] = sheet.strip().upper()
        for c in ("open", "high", "low"):
            if c not in block:
                block[c] = block["close"]
        if "volume" not in block:
            block["volume"] = pd.NA
        keep = CANON + [c for c in ("bid", "ask", "mktcap") if c in block]
        frames.append(block[keep])
        print(f"  {sheet}: {len(block)} rows "
              f"({block.date.min().date()} -> {block.date.max().date()})")
    print(f"  ok")


def _finish(frames, members, out_path):
    if not frames:
        sys.exit("no ticker sheets found")
    out = pd.concat(frames, ignore_index=True).sort_values(["ticker", "date"])
    out.to_csv(out_path, index=False)
    print(f"\nwrote {len(out)} rows, {out.ticker.nunique()} tickers -> {out_path}")
    if members:
        print(f"found {len(members)} MEMBERS_* sheets (point-in-time index "
              f"membership) -- keep them for the survivorship-bias appendix")


# -------------------------------- AUDIT -------------------------------------
def audit(prices_path: str, news_path: str | None):
    px = pd.read_csv(prices_path, parse_dates=["date"])
    print("=== PRICES AUDIT ===")
    print(f"tickers: {px.ticker.nunique()} | rows: {len(px)} | "
          f"range: {px.date.min().date()} -> {px.date.max().date()}")
    # gaps: tickers with materially fewer observations than the median
    counts = px.groupby("ticker").size()
    med = counts.median()
    short = counts[counts < 0.9 * med]
    if len(short):
        print(f"tickers with >10% missing days vs median ({int(med)}):")
        print(short.to_string())
        print("  (late IPOs / delistings -- decide inclusion window per name)")
    # sanity: non-positive prices, high<low
    bad = px[(px.close <= 0) | (px.high < px.low)]
    print(f"corrupt rows (close<=0 or high<low): {len(bad)}")
    if "bid" in px.columns and "ask" in px.columns:
        hs = ((px.ask - px.bid) / (2 * px.close) * 1e4).replace(
            [float("inf"), float("-inf")], pd.NA).dropna()
        hs = hs[(hs > 0) & (hs < 100)]
        print(f"empirical half-spread (bps): median {hs.median():.1f}, "
              f"p75 {hs.quantile(.75):.1f}, p95 {hs.quantile(.95):.1f}"
              f"  -> calibrates the cost model per ticker")

    if news_path:
        nw = pd.read_csv(news_path, parse_dates=["timestamp"])
        print("\n=== NEWS AUDIT ===")
        print(f"rows: {len(nw)} | tickers: {nw.ticker.nunique()} | "
              f"range: {nw.timestamp.min()} -> {nw.timestamp.max()}")
        per_year = nw.groupby(nw.timestamp.dt.year).size()
        print("headlines per year:")
        print(per_year.to_string())
        cover = nw.groupby("ticker").size().sort_values()
        print(f"\nthinnest coverage (bottom 10):\n{cover.head(10).to_string()}")
        print(f"\ndensest coverage (top 10):\n{cover.tail(10).to_string()}")
        # overlap check
        both = set(px.ticker.unique()) & set(nw.ticker.unique())
        only_px = set(px.ticker.unique()) - both
        print(f"\ntickers with prices AND news: {len(both)} | "
              f"prices but no news: {sorted(only_px) if only_px else 'none'}")
        # timestamp-of-day distribution: needed for the lag rule discussion
        hrs = nw.timestamp.dt.hour.value_counts().sort_index()
        print("\nnews by UTC hour (check pre/post-market share):")
        print(hrs.to_string())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("convert")
    c.add_argument("--xlsx", required=True, nargs="+")
    c.add_argument("--out", default=str(PRICES))
    a = sub.add_parser("audit")
    a.add_argument("--prices", required=True)
    a.add_argument("--news", default=None)
    args = ap.parse_args()
    if args.cmd == "convert":
        convert(args.xlsx, args.out)
    else:
        audit(args.prices, args.news)
