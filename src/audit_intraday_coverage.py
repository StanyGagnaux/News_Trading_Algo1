"""
audit_intraday_coverage.py -- answer the ONLY question that matters about
IEX bar gaps: are bars present in the minutes right after news events?

Sparse bars in random quiet minutes are irrelevant. Missing bars at
t+2..t+15min after a headline would break the entry logic. This measures
exactly that, split by ticker liquidity and by year.

USAGE:
  python audit_intraday_coverage.py --news news_history_clean.csv \
      --bars bars_intraday.csv [--prices prices.csv]

OUTPUT:
  1. Overall bar coverage per session (sanity)
  2. ENTRY-WINDOW coverage: for each news event, is there a bar available
     at t+2, t+5, t+15, t+60 minutes? (the latency sweep entry points)
  3. Same, split by year and by ticker, to find where the data is unusable
  4. A verdict per latency: what % of events are actually tradable
"""
from __future__ import annotations
import argparse
import numpy as np
import pandas as pd

from paths import NEWS_CLEAN, BARS

LATENCIES = [2, 5, 15, 60]
SEARCH_TOLERANCE_MIN = 5   # accept a bar within N min after the target time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--news", default=str(NEWS_CLEAN))
    ap.add_argument("--bars", default=str(BARS))
    ap.add_argument("--prices", default=None)
    ap.add_argument("--max-events", type=int, default=20000,
                    help="sample size for speed; 0 = all")
    args = ap.parse_args()

    print("loading...")
    bars = pd.read_csv(args.bars, parse_dates=["ts"])
    bars["ts"] = pd.to_datetime(bars["ts"], utc=True)
    news = pd.read_csv(args.news, parse_dates=["timestamp"], low_memory=False)
    news["timestamp"] = pd.to_datetime(news["timestamp"], utc=True)

    print(f"bars: {len(bars):,} rows | {bars.ticker.nunique()} tickers | "
          f"{bars.ts.min()} -> {bars.ts.max()}")

    # restrict news to the period actually covered by bars
    lo, hi = bars.ts.min(), bars.ts.max()
    news = news[(news.timestamp >= lo) & (news.timestamp <= hi)]
    news = news[news.ticker.isin(bars.ticker.unique())]
    print(f"news events in bar-covered period: {len(news):,}")

    if args.max_events and len(news) > args.max_events:
        news = news.sample(args.max_events, random_state=42)
        print(f"sampling {len(news):,} events for speed")

    # ---------- 1. session-level coverage ----------
    bars["date"] = bars.ts.dt.date
    per_session = bars.groupby(["ticker", "date"]).size()
    print(f"\n=== SESSION COVERAGE ===")
    print(f"median bars per ticker-session: {per_session.median():.0f} "
          f"(a full 09:30-16:00 session = 390)")
    print(f"p25: {per_session.quantile(.25):.0f} | "
          f"p75: {per_session.quantile(.75):.0f}")
    thin = (per_session < 100).mean()
    print(f"ticker-sessions with <100 bars: {thin:.1%}")

    # ---------- 2. entry-window coverage (THE key metric) ----------
    print(f"\n=== ENTRY-WINDOW COVERAGE (does a bar exist to enter on?) ===")
    bars_sorted = bars.sort_values(["ticker", "ts"])
    # strip tz for numpy comparison (both sides are UTC)
    by_ticker = {t: g.ts.dt.tz_localize(None).values
                 for t, g in bars_sorted.groupby("ticker")}

    results = {lat: [] for lat in LATENCIES}
    for r in news.itertuples(index=False):
        arr = by_ticker.get(r.ticker)
        if arr is None or len(arr) == 0:
            for lat in LATENCIES:
                results[lat].append(False)
            continue
        base = pd.Timestamp(r.timestamp).tz_localize(None)
        for lat in LATENCIES:
            target = np.datetime64(base + pd.Timedelta(minutes=lat))
            idx = np.searchsorted(arr, target)
            if idx >= len(arr):
                results[lat].append(False)
                continue
            gap_min = (arr[idx] - target) / np.timedelta64(1, "m")
            results[lat].append(bool(gap_min <= SEARCH_TOLERANCE_MIN))

    print(f"(a bar counts as available if one exists within "
          f"{SEARCH_TOLERANCE_MIN} min of the target entry time)\n")

    # split by whether the news landed during regular trading hours.
    # Outside RTH no bar CAN exist -- those events are not a data-quality
    # failure, they are premarket/afterhours news needing a different rule.
    hh = news.timestamp.dt.hour + news.timestamp.dt.minute / 60
    # NYSE RTH in UTC: 13:30-20:00 (EDT) / 14:30-21:00 (EST). Use the
    # conservative intersection for "definitely open": 14:30-20:00.
    rth = ((hh >= 14.5) & (hh <= 20.0)).values

    verdict = {}
    print(f"{'latency':>10} | {'ALL events':>11} | {'during RTH':>11} | "
          f"{'outside RTH':>11}")
    print("-" * 52)
    for lat in LATENCIES:
        arr = np.array(results[lat])
        cov_all = arr.mean()
        cov_rth = arr[rth].mean() if rth.sum() else float("nan")
        cov_off = arr[~rth].mean() if (~rth).sum() else float("nan")
        verdict[lat] = cov_rth          # RTH is the meaningful number
        print(f"  t+{lat:>3}min | {cov_all:10.1%} | {cov_rth:10.1%} | "
              f"{cov_off:10.1%}")
    print(f"\nevents during RTH: {rth.mean():.1%} | outside RTH: "
          f"{(~rth).mean():.1%} (premarket/afterhours -- no bar can exist)")
    print("NOTE: the RTH column is the real coverage metric. Outside-RTH")
    print("events need a next-open entry rule, not an intraday one.")

    # ---------- 3. by year ----------
    print(f"\n=== COVERAGE BY YEAR (t+5min entry) ===")
    news = news.reset_index(drop=True)
    yr_cov = pd.DataFrame({"year": news.timestamp.dt.year,
                           "ok": results[5]})
    print(yr_cov.groupby("year").agg(
        events=("ok", "size"), coverage=("ok", "mean")).to_string(
        float_format=lambda x: f"{x:.1%}" if x <= 1 else f"{x:.0f}"))

    # ---------- 4. worst tickers ----------
    print(f"\n=== WORST-COVERED TICKERS (t+5min, min 50 events) ===")
    tk = pd.DataFrame({"ticker": news.ticker.values, "ok": results[5]})
    agg = tk.groupby("ticker").agg(events=("ok", "size"),
                                   coverage=("ok", "mean"))
    agg = agg[agg.events >= 50].sort_values("coverage")
    print(agg.head(15).to_string(float_format=lambda x: f"{x:.1%}"
                                 if x <= 1 else f"{x:.0f}"))
    print(f"\n=== BEST-COVERED TICKERS ===")
    print(agg.tail(10).to_string(float_format=lambda x: f"{x:.1%}"
                                 if x <= 1 else f"{x:.0f}"))

    # ---------- verdict ----------
    print(f"\n{'='*60}\nVERDICT")
    c5 = verdict[5]   # now RTH-only coverage
    print("(judged on DURING-MARKET-HOURS events only)")
    if c5 >= 0.85:
        print(f"USABLE. {c5:.0%} of events have a bar at t+5min. Gaps are in")
        print("quiet minutes, not at entry points. Proceed with the sweep;")
        print("drop unfilled events and disclose the rate in the data chapter.")
    elif c5 >= 0.60:
        print(f"USABLE WITH CARE. {c5:.0%} coverage at t+5min. Restrict the")
        print("universe to well-covered tickers (see table above) and")
        print("disclose the exclusion rule explicitly.")
    else:
        print(f"PROBLEMATIC. Only {c5:.0%} coverage at t+5min. The intraday")
        print("arm is not viable on this data. Options: paid SIP feed, a")
        print("university data source, or restrict to the daily drift arm.")
    print("="*60)


if __name__ == "__main__":
    main()
