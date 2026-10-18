"""
fetch_historical_news.py -- bulk-download the Benzinga news archive (2015+)
via Alpaca's historical news REST API, into the newsdrift canonical schema.

WHY THIS SOURCE:
  - Same wire (Benzinga) as the live realtime watcher -> the backtest and the
    live deployment use ONE consistent news source. Methodologically clean.
  - Timestamped to the second, ticker-tagged by the wire, back to ~2015.
  - Free with the same Alpaca paper-account keys. No scraping, no ToS issues.

USAGE:
  export ALPACA_KEY=... ALPACA_SECRET=...
  python fetch_historical_news.py --start 2016-01-01 --end 2025-12-31 \
      --tickers-file nasdaq100.txt --out news_history.csv

  nasdaq100.txt = one ticker per line. The script downloads in monthly
  chunks per batch of symbols, paginates, respects rate limits, and can be
  interrupted and re-run: it resumes from the last completed month.

OUTPUT CSV COLUMNS (drop-in for newsdrift.load_news_csv):
  timestamp, ticker, headline, source
  One row per (news item x matched universe ticker).
"""
from __future__ import annotations
import argparse
import csv
import os
import time
from datetime import datetime

import requests

from paths import ROOT, LOGS, TICKERS, NEWS_RAW

API_URL = "https://data.alpaca.markets/v1beta1/news"
BATCH_SYMBOLS = 40          # symbols per request batch
PAGE_LIMIT = 50             # max items per page (API max)
SLEEP_BETWEEN_CALLS = 0.35  # ~170 req/min, under the free rate limit
PROGRESS_FILE = str(LOGS / "fetch_progress.txt")
ENV_FILE = str(ROOT / ".env")


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


def month_ranges(start: str, end: str):
    """Yield (iso_start, iso_end) pairs, one per calendar month."""
    s = datetime.fromisoformat(start)
    e = datetime.fromisoformat(end)
    cur = s.replace(day=1)
    while cur <= e:
        nxt = (cur.replace(year=cur.year + 1, month=1)
               if cur.month == 12 else cur.replace(month=cur.month + 1))
        lo = max(cur, s)
        hi = min(nxt, e.replace(hour=23, minute=59, second=59))
        yield lo.strftime("%Y-%m-%dT00:00:00Z"), hi.strftime("%Y-%m-%dT23:59:59Z")
        cur = nxt


def fetch_month(session, key, secret, symbols, start_iso, end_iso):
    """Paginate through one month for one symbol batch."""
    items, token = [], None
    while True:
        params = {"symbols": ",".join(symbols), "start": start_iso,
                  "end": end_iso, "limit": PAGE_LIMIT,
                  "include_content": "false", "sort": "asc"}
        if token:
            params["page_token"] = token
        r = session.get(API_URL, params=params, headers={
            "APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}, timeout=30)
        if r.status_code == 429:              # rate limited: back off
            time.sleep(5)
            continue
        r.raise_for_status()
        data = r.json()
        items.extend(data.get("news", []))
        token = data.get("next_page_token")
        time.sleep(SLEEP_BETWEEN_CALLS)
        if not token:
            return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--end", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--tickers-file", default=str(TICKERS))
    ap.add_argument("--out", default=str(NEWS_RAW))
    ap.add_argument("--progress", default=PROGRESS_FILE,
                    help="resume file; use a separate one per download (the "
                         "default one lists already-fetched months, which a "
                         "new download would silently skip)")
    args = ap.parse_args()

    load_env_file()
    key = os.environ.get("ALPACA_KEY", "")
    secret = os.environ.get("ALPACA_SECRET", "")
    if not key or not secret:
        raise SystemExit("Set ALPACA_KEY and ALPACA_SECRET env vars first.")

    universe = [t.strip().upper() for t in open(args.tickers_file)
                if t.strip() and not t.startswith("#")]
    uset = set(universe)
    print(f"universe: {len(universe)} tickers | {args.start} -> {args.end}")

    done = set()
    if os.path.exists(args.progress):
        done = set(x.strip() for x in open(args.progress))
        print(f"resuming: {len(done)} month-batches already completed")

    out_exists = os.path.exists(args.out)
    fout = open(args.out, "a", newline="", encoding="utf-8")
    writer = csv.writer(fout)
    if not out_exists:
        writer.writerow(["timestamp", "ticker", "headline", "source"])

    session = requests.Session()
    batches = [universe[i:i + BATCH_SYMBOLS]
               for i in range(0, len(universe), BATCH_SYMBOLS)]
    total_rows = 0
    for lo, hi in month_ranges(args.start, args.end):
        for bi, batch in enumerate(batches):
            tag = f"{lo[:7]}|batch{bi}"
            if tag in done:
                continue
            try:
                items = fetch_month(session, key, secret, batch, lo, hi)
            except Exception as e:
                print(f"[error] {tag}: {e} -- will retry on next run")
                continue
            n = 0
            for it in items:
                headline = (it.get("headline") or "").strip()
                ts = it.get("created_at", "")
                src = it.get("source", "benzinga")
                if not headline or not ts:
                    continue
                # one row per matched universe ticker
                for sym in (it.get("symbols") or []):
                    if sym in uset:
                        writer.writerow([ts, sym, headline, src])
                        n += 1
            fout.flush()
            with open(args.progress, "a") as pf:
                pf.write(tag + "\n")
            total_rows += n
            print(f"[{tag}] {len(items)} items -> {n} rows (total {total_rows})")
    fout.close()
    print(f"\ndone. wrote {total_rows} rows to {args.out}")
    print("next: python audit_news_data.py --news", args.out)


if __name__ == "__main__":
    main()
