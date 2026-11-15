"""
intraday_description.py -- does a headline DESCRIBE a move that already
happened, or PREDICT one? TRAINING PERIOD ONLY, regular-trading-hours news only.

For each scored headline published 09:30-16:00 New York time (DST-aware), the
signed return (sign of that headline's own score, same gate and netting as
build_event_table) over:
    -30 min -> t       (main pre-news window; the minute bars were fetched from
                        30 min before each headline, see fetch_intraday_bars.py)
    -60 min -> t       (only where earlier news extended the fetched window --
                        a selected subset, reported with its own N)
    t -> +30 min, t -> +60 min, t -> session close
Price at a moment = close of the last 1-minute bar ENDING at or before it
(bars are stamped by their start), at most 10 minutes stale, same session.
Windows must lie inside the session. No intraday NDX/QQQ in the bar file, so
returns are RAW. Mean bps, t-stat clustered by date, N; the main table uses the
common sample where -30, +30, +60 and close all exist.

USAGE (from the project root):  python3 src/intraday_description.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from paths import BARS, OUTPUTS, DATA
from newsdrift import KeywordScorer, PrecomputedScorer, build_event_table
from calibrate_scorer import load_training, headline_type, TRAIN_END
from event_study import clustered_mean

LLM_ANON = DATA / "news_scored_llm_ollama_anon.csv"
NY = "America/New_York"
MAX_STALE = pd.Timedelta(minutes=10)
BAR_LEN = pd.Timedelta(minutes=1)
OPEN_T, CLOSE_T = pd.Timedelta(hours=9, minutes=30), pd.Timedelta(hours=16)
PRE = {"pre_60": -60, "pre_30": -30}
POST = {"post_30": 30, "post_60": 60}
MAIN = ["pre_30", "post_30", "post_60", "post_close"]
CHUNK = 2_000_000
OUT = OUTPUTS / "intraday_description_2026-10-18.csv"


def load_bars_training() -> pd.DataFrame:
    last = (TRAIN_END + pd.Timedelta(days=1)).tz_localize("UTC")
    parts = []
    for c in pd.read_csv(BARS, usecols=["ticker", "ts", "close"], chunksize=CHUNK):
        c["ts"] = pd.to_datetime(c.ts, utc=True)
        parts.append(c[c.ts < last])
    bars = pd.concat(parts, ignore_index=True).sort_values(["ticker", "ts"])
    assert bars.ts.max() < last
    return bars


def headline_events(nw: pd.DataFrame, scorer, cfg) -> pd.DataFrame:
    """build_event_table's events plus the headline category (first headline at
    that timestamp). Asserted identical to build_event_table."""
    rows = []
    for r in nw.itertuples(index=False):
        s, d = scorer.score(r.headline, r.ticker)
        if abs(s) >= cfg.signal.min_abs_strength:
            rows.append({"ticker": r.ticker, "news_ts": r.timestamp, "strength": float(s),
                         "category": headline_type(r.headline)})
    df = pd.DataFrame(rows)
    ev = df.groupby(["ticker", "news_ts"], as_index=False).agg(
        strength=("strength", "mean"), category=("category", "first"))
    ev = ev[ev.strength.abs() >= cfg.signal.min_abs_strength]
    ref = build_event_table(nw, scorer, cfg.signal)
    assert len(ref) == len(ev) and np.allclose(
        ref.sort_values(["ticker", "news_ts"]).strength, ev.sort_values(["ticker", "news_ts"]).strength), \
        "events differ from build_event_table"
    return ev


def rth_only(ev: pd.DataFrame) -> pd.DataFrame:
    ts = pd.to_datetime(ev.news_ts).dt.tz_localize("UTC")
    local = ts.dt.tz_convert(NY)
    tod = local - local.dt.normalize()
    keep = (local.dt.weekday < 5) & (tod >= OPEN_T) & (tod < CLOSE_T)
    return ev[keep].assign(ts=ts[keep], day=local[keep].dt.normalize())


def _price_at(ends, close, day_of_bar, anchors, days) -> np.ndarray:
    """Close of the last bar ending <= anchor, <= MAX_STALE old, same session."""
    i = np.searchsorted(ends, anchors, side="right") - 1
    ok = i >= 0
    j = np.maximum(i, 0)
    ok &= (ends[j] >= anchors - MAX_STALE.to_timedelta64()) & (day_of_bar[j] == days)
    return np.where(ok, close[j], np.nan)


def window_returns(ev: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    out = []
    by_ticker = dict(tuple(ev.groupby("ticker")))
    for t, g in bars.groupby("ticker"):
        e = by_ticker.get(t)
        if e is None:
            continue
        ends = (g.ts + BAR_LEN).dt.tz_convert(None).to_numpy()
        day_of_bar = g.ts.dt.tz_convert(NY).dt.normalize().dt.tz_localize(None).to_numpy()
        close = g.close.to_numpy(float)
        ts = e.ts.dt.tz_convert(None).to_numpy()
        days = e.day.dt.tz_localize(None).to_numpy()
        open_utc = (e.day + OPEN_T).dt.tz_convert("UTC").dt.tz_localize(None).to_numpy()
        close_utc = (e.day + CLOSE_T).dt.tz_convert("UTC").dt.tz_localize(None).to_numpy()
        p0 = _price_at(ends, close, day_of_bar, ts, days)
        res = {}
        for name, mins in PRE.items():
            a = ts + np.timedelta64(mins, "m")
            p = _price_at(ends, close, day_of_bar, a, days)
            res[name] = np.where(a >= open_utc, p0 / p - 1, np.nan)
        for name, mins in POST.items():
            a = ts + np.timedelta64(mins, "m")
            p = _price_at(ends, close, day_of_bar, a, days)
            res[name] = np.where(a <= close_utc, p / p0 - 1, np.nan)
        pc = _price_at(ends, close, day_of_bar, close_utc, days)
        res["post_close"] = pc / p0 - 1
        out.append(e.assign(**res))
    ev = pd.concat(out, ignore_index=True)
    cols = list(PRE) + list(POST) + ["post_close"]
    ev[cols] = ev[cols].mul(np.sign(ev.strength), axis=0) * 1e4
    return ev


def summarise(ev: pd.DataFrame, scorer: str) -> list[dict]:
    rows = []
    common = ev.dropna(subset=MAIN)
    for cat, g in [("all", common)] + sorted(common.groupby("category")):
        for w in MAIN:
            m, t, n = clustered_mean(g[w], g.day)
            rows.append({"scorer": scorer, "sample": "common", "category": cat, "window": w,
                         "mean_bps": m, "t_clustered": t, "N": n})
    for cat, g in [("all", ev)] + sorted(ev.groupby("category")):
        sub = g.dropna(subset=["pre_60", "post_60"])
        for w in ("pre_60", "post_60"):
            m, t, n = clustered_mean(sub[w], sub.day)
            rows.append({"scorer": scorer, "sample": "pre_60 subset", "category": cat, "window": w,
                         "mean_bps": m, "t_clustered": t, "N": n})
    return rows


def print_tables(tab: pd.DataFrame) -> None:
    for (scorer, sample), part in tab.groupby(["scorer", "sample"], sort=False):
        windows = part.window.unique()
        print(f"\n  [{scorer}] {sample} sample   cells: mean bps (t clustered by date)")
        print(f"    {'category':<18}{'N':>8}" + "".join(f"{w:>18}" for w in windows))
        for cat, r in part.groupby("category", sort=False):
            r = r.set_index("window").loc[windows]
            print(f"    {cat:<18}{int(r.N.iloc[0]):>8,}" + "".join(
                f"{x.mean_bps:>+10.1f} ({x.t_clustered:>+5.2f})" for x in r.itertuples()))


def main():
    px, nw, cfg = load_training()
    del px
    bars = load_bars_training()
    print(f"training only | minute bars {bars.ts.min().date()} -> {bars.ts.max().date()} "
          f"({len(bars):,} rows, {bars.ticker.nunique()} tickers) | raw returns (no intraday index)")
    nw = nw[nw.timestamp >= bars.ts.min().tz_convert(None).normalize()]
    rows = []
    for name, scorer in (("keyword", KeywordScorer(cfg.signal)),
                         ("llm_anon", PrecomputedScorer(str(LLM_ANON)))):
        ev = rth_only(headline_events(nw, scorer, cfg))
        ev = window_returns(ev, bars)
        cover = ev[MAIN].notna().all(axis=1).mean()
        print(f"  {name}: {len(ev):,} RTH headline events with bars; {cover:.0%} have all main windows")
        rows += summarise(ev, name)
    tab = pd.DataFrame(rows)
    tab.to_csv(OUT, index=False)
    print_tables(tab)
    print(f"\n  saved {OUT.name} in outputs/")


if __name__ == "__main__":
    main()
