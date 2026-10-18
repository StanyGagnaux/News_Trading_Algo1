"""
fetch_intraday_bars.py -- download minute bars AROUND NEWS EVENTS from Alpaca
(free IEX feed, same keys as the news archive -> one consistent clock).

WHY WINDOWS, NOT FULL HISTORY: minute bars for 100 tickers x 10 years is
~100M rows and mostly irrelevant. The spike/continuation study only needs
bars near news timestamps. Default window: 30 minutes before the news to
6.5 hours after (rest of the session), merged when events overlap.

USAGE:
  export ALPACA_KEY=... ALPACA_SECRET=...
  python fetch_intraday_bars.py --news news_history_clean.csv \
      --out bars_intraday.csv --pre-min 30 --post-min 390
  (--news defaults to news_history_clean.csv if omitted)

OUTPUT: [ticker, ts, open, high, low, close, volume, vwap, trades]
  one row per minute bar, UTC timestamps, only within event windows.
  Feeds the intraday engine's entry-latency sweep:
  entries at news_ts + {1, 5, 15, 60} min and next-day open.

NOTES:
- IEX feed = free tier. It covers a subset of consolidated volume; prices are
  representative but volume understates the tape. Fine for a latency-decay
  study; document it in the thesis data section.
- Resumable: progress tracked per (ticker, date-window) chunk.
- Rate limit respected (~200 req/min).
"""
from __future__ import annotations
import argparse
import csv
import os
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

from paths import LOGS, NEWS_CLEAN, BARS

BARS_URL = "https://data.alpaca.markets/v2/stocks/{sym}/bars"
PROGRESS_FILE = str(LOGS / "intraday_progress.txt")
SLEEP = 0.32
ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

# Confirmed empirically against this account: the IEX feed returns 0 bars
# for anything before ~2020-07-27 (rolling ~6-year window from "now", not a
# fixed date -- see MIN_DATA_DATE usage below). News events before this are
# skipped up front instead of burning API calls that will always return
# nothing.
MIN_DATA_DATE = "2020-07-27"


def load_env_file(path=ENV_FILE):
    """Populate os.environ from a KEY=VALUE .env file, if present.

    Needed because launching this script from an editor's Run button
    starts a fresh process that never sees vars exported in a terminal.
    """
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def build_windows(news: pd.DataFrame, pre_min: int, post_min: int) -> pd.DataFrame:
    """One row per (ticker, window_start, window_end); overlaps merged."""
    n = news.copy()
    n["timestamp"] = pd.to_datetime(n["timestamp"], utc=True)
    n["w_start"] = n["timestamp"] - pd.Timedelta(minutes=pre_min)
    n["w_end"] = n["timestamp"] + pd.Timedelta(minutes=post_min)
    rows = []
    for tkr, g in n.sort_values("w_start").groupby("ticker"):
        cur_s, cur_e = None, None
        for r in g.itertuples(index=False):
            if cur_s is None:
                cur_s, cur_e = r.w_start, r.w_end
            elif r.w_start <= cur_e:            # overlap -> merge
                cur_e = max(cur_e, r.w_end)
            else:
                rows.append({"ticker": tkr, "start": cur_s, "end": cur_e})
                cur_s, cur_e = r.w_start, r.w_end
        if cur_s is not None:
            rows.append({"ticker": tkr, "start": cur_s, "end": cur_e})
    return pd.DataFrame(rows)


def fetch_window(session, key, secret, sym, start_iso, end_iso):
    items, token = [], None
    while True:
        params = {"timeframe": "1Min", "start": start_iso, "end": end_iso,
                  "limit": 10000, "feed": "iex", "adjustment": "split"}
        if token:
            params["page_token"] = token
        r = session.get(BARS_URL.format(sym=sym), params=params, headers={
            "APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}, timeout=30)
        if r.status_code == 429:
            time.sleep(5)
            continue
        r.raise_for_status()
        data = r.json()
        items.extend(data.get("bars") or [])
        token = data.get("next_page_token")
        time.sleep(SLEEP)
        if not token:
            return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--news", default=str(NEWS_CLEAN))
    ap.add_argument("--out", default=str(BARS))
    ap.add_argument("--pre-min", type=int, default=30)
    ap.add_argument("--post-min", type=int, default=390)   # rest of session
    ap.add_argument("--min-date", default=MIN_DATA_DATE,
                    help="skip news events before this date (no bar data "
                         "exists that far back on this account/feed)")
    args = ap.parse_args()

    load_env_file()
    key = os.environ.get("ALPACA_KEY", "")
    secret = os.environ.get("ALPACA_SECRET", "")
    if not key or not secret:
        raise SystemExit("Set ALPACA_KEY and ALPACA_SECRET first.")

    news = pd.read_csv(args.news)
    news["timestamp"] = pd.to_datetime(news["timestamp"], utc=True)
    min_date = pd.Timestamp(args.min_date, tz="utc")
    before = len(news)
    news = news[news["timestamp"] >= min_date]
    skipped = before - len(news)
    if skipped:
        print(f"skipping {skipped} news rows before {args.min_date} "
              f"(no bar data available that far back)")

    win = build_windows(news, args.pre_min, args.post_min)
    print(f"{len(news)} news rows -> {len(win)} merged fetch windows "
          f"across {win.ticker.nunique()} tickers")

    done = set()
    if os.path.exists(PROGRESS_FILE):
        done = set(x.strip() for x in open(PROGRESS_FILE))
        print(f"resuming: {len(done)} windows already fetched")

    exists = os.path.exists(args.out)
    fout = open(args.out, "a", newline="", encoding="utf-8")
    w = csv.writer(fout)
    if not exists:
        w.writerow(["ticker", "ts", "open", "high", "low", "close",
                    "volume", "vwap", "trades"])

    session = requests.Session()
    total = 0
    for r in win.itertuples(index=False):
        tag = f"{r.ticker}|{r.start.isoformat()}"
        if tag in done:
            continue
        try:
            bars = fetch_window(session, key, secret, r.ticker,
                                r.start.isoformat().replace("+00:00", "Z"),
                                r.end.isoformat().replace("+00:00", "Z"))
        except Exception as e:
            print(f"[error] {tag}: {e} -- retry on next run")
            continue
        for b in bars:
            w.writerow([r.ticker, b["t"], b["o"], b["h"], b["l"], b["c"],
                        b["v"], b.get("vw", ""), b.get("n", "")])
        fout.flush()
        with open(PROGRESS_FILE, "a") as pf:
            pf.write(tag + "\n")
        total += len(bars)
        print(f"[{r.ticker}] {r.start.date()} {len(bars)} bars (total {total})")
    fout.close()
    print(f"\ndone. {total} minute bars -> {args.out}")


if __name__ == "__main__":
    main()
