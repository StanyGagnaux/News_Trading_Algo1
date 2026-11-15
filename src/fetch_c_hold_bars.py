"""
fetch_c_hold_bars.py -- full-session IEX minute bars for Strategy C's hold
days (note `…note_c_minute_2026-10-24.md`, section 2). Strategy C only.

  --plan   build the day list: for every C event of any rung (keyword, LLM
           anonymised, rung 1b), training and test, the news day (New York)
           and the next 4 trading days of the ticker; merge into date ranges.
  (fetch)  one request per range, 09:30 New York of the first day to 16:00 of
           the last, feed=iex, adjustment="split"; keep bars stamped
           09:30-15:59 New York. Throttled (>= 1 s between requests), paused
           Mon 26 / Tue 27 Oct 14:00-21:30 Europe/Zurich (shadow run), stops
           at the note's deadline (Wed 28 Oct 23:59 Europe/Zurich). Resumable.

Output: data_sources/bars_c_hold.csv (the existing bars file is untouched).

USAGE (from the project root):
  python3 src/fetch_c_hold_bars.py --plan
  python3 src/fetch_c_hold_bars.py
"""
from __future__ import annotations

import argparse
import csv
import os
import time
from argparse import Namespace
from datetime import datetime

import pandas as pd
import requests

from paths import PRICES, NEWS_CLEAN, BARS, DATA, LOGS, ROOT
from fetch_intraday_bars import fetch_window, load_env_file, MIN_DATA_DATE

NY, ZRH = "America/New_York", "Europe/Zurich"
DAYS_AFTER = 4                                   # entry may roll + 3-day hold
MERGE_GAP_DAYS = 4                               # weekends / holidays inside a range
REQUEST_PAUSE_S = 1.0
PAUSES = [(pd.Timestamp("2026-10-26 14:00", tz=ZRH), pd.Timestamp("2026-10-26 21:30", tz=ZRH)),
          (pd.Timestamp("2026-10-27 14:00", tz=ZRH), pd.Timestamp("2026-10-27 21:30", tz=ZRH))]
DEADLINE = pd.Timestamp("2026-10-28 23:59", tz=ZRH)
DAY_LIST = DATA / "c_hold_days.csv"
RANGES = DATA / "c_hold_ranges.csv"
DAY_LIST_DELTA = DATA / "c_hold_days_delta_rungs2_3.csv"     # note …note_c_minute_rungs2_3_2026-10-25.md
RANGES_DELTA = DATA / "c_hold_ranges_delta_rungs2_3.csv"
OUT = DATA / "bars_c_hold.csv"
PROGRESS = LOGS / "c_hold_progress.txt"
FIELDS = ["ticker", "ts", "open", "high", "low", "close", "volume", "vwap", "trades"]
RUNG_SCORES = {"keyword": None,
               "llm_anon": DATA / "news_scored_llm_ollama_anon_incl_test.csv",
               "embed_minilm": DATA / "news_scored_embed_minilm_incl_test.csv",
               "haiku": DATA / "news_scored_haiku_anon_incl_test.csv",
               "sonnet": DATA / "news_scored_sonnet_anon_incl_test.csv"}
ORIGINAL_RUNGS = ["keyword", "llm_anon", "embed_minilm"]


def c_event_days(rungs=ORIGINAL_RUNGS) -> pd.DataFrame:
    """(ticker, New York news date) of every C event, union of the given rungs."""
    from run_both_strategies import load_inputs, load_bars, market_hours_events
    from newsdrift import build_event_table
    bars = load_bars(str(BARS))
    out = []
    for rung in rungs:
        scores = RUNG_SCORES[rung]
        cfg, _, nw, scorer, _, _ = load_inputs(Namespace(
            prices=str(PRICES), news=str(NEWS_CLEAN), start="2016-01-01", end="2026-06-01",
            train_frac=0.80, llm_scores=str(scores) if scores else None, tier0=False))
        ev = market_hours_events(build_event_table(nw, scorer, cfg.signal), bars)
        day = pd.to_datetime(ev.news_ts, utc=True).dt.tz_convert(NY).dt.tz_localize(None).dt.normalize()
        out.append(pd.DataFrame({"ticker": ev.ticker.to_numpy(), "news_day": day.to_numpy()}))
        print(f"  {rung}: {len(ev):,} C events")
    return pd.concat(out).drop_duplicates()


def plan() -> None:
    days = hold_days(c_event_days())
    days.to_csv(DAY_LIST, index=False)
    write_ranges(days, RANGES)


def plan_delta(rungs) -> None:
    """Hold days of the given rungs' C events not already in DAY_LIST."""
    days = hold_days(c_event_days(rungs))
    old = pd.read_csv(DAY_LIST, parse_dates=["date"])
    new = days.merge(old, on=["ticker", "date"], how="left", indicator=True)
    new = new[new._merge == "left_only"].drop(columns="_merge")
    new.to_csv(DAY_LIST_DELTA, index=False)
    print(f"  {len(days):,} hold days for {rungs}; {len(new):,} not yet fetched")
    write_ranges(new, RANGES_DELTA)


def hold_days(ev: pd.DataFrame) -> pd.DataFrame:
    px = pd.read_csv(PRICES, usecols=["date", "ticker"], parse_dates=["date"])
    cal = {t: pd.DatetimeIndex(sorted(g.date)) for t, g in px.groupby("ticker")}
    rows = []
    for t, g in ev.groupby("ticker"):
        c = cal.get(t)
        if c is None:
            continue
        for d in g.news_day:
            i = c.searchsorted(d)
            rows += [(t, x) for x in c[i:i + DAYS_AFTER + 1]]
    return pd.DataFrame(rows, columns=["ticker", "date"]).drop_duplicates().sort_values(["ticker", "date"])


def write_ranges(days: pd.DataFrame, path) -> None:
    ranges = []
    for t, g in days.groupby("ticker"):
        ds = list(g.date)
        start = prev = ds[0]
        for d in ds[1:]:
            if (d - prev).days > MERGE_GAP_DAYS:
                ranges.append((t, start, prev))
                start = d
            prev = d
        ranges.append((t, start, prev))
    r = pd.DataFrame(ranges, columns=["ticker", "first_day", "last_day"])
    r["start"] = [(d + pd.Timedelta(hours=9, minutes=30)).tz_localize(NY).tz_convert("UTC") for d in r.first_day]
    r["end"] = [(d + pd.Timedelta(hours=16)).tz_localize(NY).tz_convert("UTC") for d in r.last_day]
    r[["ticker", "start", "end"]].to_csv(path, index=False)
    print(f"  {len(days):,} ticker-days in {len(r):,} ranges ({days.ticker.nunique()} tickers); "
          f"{days.date.min().date()} -> {days.date.max().date()}")


def wait_if_paused() -> None:
    now = pd.Timestamp.now(tz=ZRH)
    if now > DEADLINE:
        raise SystemExit(f"{now}: past the note's deadline -- stopped")
    for lo, hi in PAUSES:
        if lo <= now < hi:
            print(f"{now}: paused for the shadow run until {hi}", flush=True)
            time.sleep((hi - now).total_seconds() + 5)


def regular_session(bars: list[dict]) -> list[dict]:
    keep = []
    for b in bars:
        ny = pd.Timestamp(b["t"]).tz_convert(NY)
        m = ny.hour * 60 + ny.minute
        if 570 <= m < 960 and ny.weekday() < 5:
            keep.append(b)
    return keep


def fetch(ranges_path=RANGES) -> None:
    load_env_file(str(ROOT / ".env"))
    key, secret = os.environ.get("ALPACA_KEY", ""), os.environ.get("ALPACA_SECRET", "")
    if not key or not secret:
        raise SystemExit("ALPACA_KEY / ALPACA_SECRET not found in .env")
    ranges = pd.read_csv(ranges_path)
    ranges = ranges[pd.to_datetime(ranges.end, utc=True) >= pd.Timestamp(MIN_DATA_DATE, tz="UTC")]  # feed has nothing earlier
    done = set(PROGRESS.read_text().split()) if PROGRESS.exists() else set()
    new_file = not OUT.exists()
    session = requests.Session()
    with OUT.open("a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(FIELDS)
        for n, r in enumerate(ranges.itertuples(index=False), 1):
            tag = f"{r.ticker}|{r.start}"
            if tag in done:
                continue
            wait_if_paused()
            for attempt in range(5):
                try:
                    bars = fetch_window(session, key, secret, r.ticker,
                                        pd.Timestamp(r.start).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                        pd.Timestamp(r.end).strftime("%Y-%m-%dT%H:%M:%SZ"))
                    break
                except requests.RequestException as e:          # network: back off and retry
                    print(f"  {tag}: {type(e).__name__}, retry {attempt + 1}", flush=True)
                    time.sleep(30 * (attempt + 1))
            else:
                raise SystemExit(f"{tag}: failed 5 times -- stopped (resumable)")
            for b in regular_session(bars):
                w.writerow([r.ticker, b["t"], b["o"], b["h"], b["l"], b["c"], b.get("v"), b.get("vw"), b.get("n")])
            f.flush()
            with PROGRESS.open("a") as p:
                p.write(tag + "\n")
            if n % 100 == 0:
                print(f"{datetime.now():%Y-%m-%d %H:%M} {n:,}/{len(ranges):,} ranges", flush=True)
            time.sleep(REQUEST_PAUSE_S)
    print(f"{datetime.now():%Y-%m-%d %H:%M} fetch complete: {len(ranges):,} ranges", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--plan-delta", nargs="+", choices=["haiku", "sonnet"])
    ap.add_argument("--ranges", default=str(RANGES), help="range list to fetch (default: the original plan)")
    a = ap.parse_args()
    if a.plan:
        plan()
    elif a.plan_delta:
        plan_delta(a.plan_delta)
    else:
        fetch(a.ranges)
