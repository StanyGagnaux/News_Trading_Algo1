"""
speed_bound.py -- ladder note of 24 Oct 2026, item e. For trading-hours news,
the signed return from the price AT the headline timestamp to +1, +5, +15,
+30 minutes and the session close, per rung and period, against the 4.86 bps
round trip. Raw minute returns (no intraday index), t clustered by date.

Reuses intraday_description.py unchanged: headline_events (own-score events,
same gate and netting as build_event_table), rth_only, _price_at (close of the
last 1-minute bar ENDING at or before the moment, <= 10 minutes stale, same
session). A horizon counts only if its moment lies inside the session; the
price at +k minutes may be the same bar as at the timestamp when no trade
printed in between (IEX bars are sparse), reported as "unchanged bar".

USAGE (from the project root):
  python3 src/speed_bound.py --period train --rungs keyword llm_anon embed_minilm
  python3 src/speed_bound.py --period test  --rungs keyword llm_anon embed_minilm   # logged
"""
from __future__ import annotations

import argparse
from datetime import datetime

import numpy as np
import pandas as pd

from paths import BARS, DATA, OUTPUTS
from newsdrift import Config, KeywordScorer, PrecomputedScorer
import intraday_description as idd
import event_study as es
from calibrate_scorer import load_training

HORIZONS_MIN = [1, 5, 15, 30]
STAMP = "2026-10-24"
FILES = {"llm_anon": ("news_scored_llm_ollama_anon.csv", "news_scored_llm_ollama_anon_incl_test.csv"),
         "embed_minilm": ("news_scored_embed_minilm.csv", "news_scored_embed_minilm_incl_test.csv"),
         "haiku": ("news_scored_haiku_anon.csv", "news_scored_haiku_anon_incl_test.csv"),
         "sonnet": ("news_scored_sonnet_anon.csv", "news_scored_sonnet_anon_incl_test.csv")}
TEST_START, TEST_END = pd.Timestamp("2024-04-30", tz="UTC"), pd.Timestamp("2026-06-02", tz="UTC")


def scorer_for(rung: str, period: str, cfg):
    if rung == "keyword":
        return KeywordScorer(cfg.signal)
    return PrecomputedScorer(str(DATA / FILES[rung][0 if period == "train" else 1]))


def load_bars(period: str) -> pd.DataFrame:
    if period == "train":
        return idd.load_bars_training()
    parts = []
    for c in pd.read_csv(BARS, usecols=["ticker", "ts", "close"], chunksize=idd.CHUNK):
        c["ts"] = pd.to_datetime(c.ts, utc=True)
        parts.append(c[(c.ts >= TEST_START) & (c.ts < TEST_END)])
    return pd.concat(parts, ignore_index=True).sort_values(["ticker", "ts"])


def horizon_returns(ev: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    out = []
    by_ticker = dict(tuple(ev.groupby("ticker")))
    for t, g in bars.groupby("ticker"):
        e = by_ticker.get(t)
        if e is None:
            continue
        ends = (g.ts + idd.BAR_LEN).dt.tz_convert(None).to_numpy()
        day_of_bar = g.ts.dt.tz_convert(idd.NY).dt.normalize().dt.tz_localize(None).to_numpy()
        close = g.close.to_numpy(float)
        ts = e.ts.dt.tz_convert(None).to_numpy()
        days = e.day.dt.tz_localize(None).to_numpy()
        close_utc = (e.day + idd.CLOSE_T).dt.tz_convert("UTC").dt.tz_localize(None).to_numpy()
        p0 = idd._price_at(ends, close, day_of_bar, ts, days)
        i0 = np.searchsorted(ends, ts, side="right") - 1
        res = {}
        for k in HORIZONS_MIN:
            a = ts + np.timedelta64(k, "m")
            p = idd._price_at(ends, close, day_of_bar, a, days)
            res[f"m{k}"] = np.where(a <= close_utc, p / p0 - 1, np.nan)
            res[f"m{k}_unchanged"] = (np.searchsorted(ends, a, side="right") - 1) == i0
        res["close"] = idd._price_at(ends, close, day_of_bar, close_utc, days) / p0 - 1
        out.append(e.assign(**res))
    ev = pd.concat(out, ignore_index=True)
    cols = [f"m{k}" for k in HORIZONS_MIN] + ["close"]
    ev[cols] = ev[cols].mul(np.sign(ev.strength), axis=0) * 1e4
    return ev


def summarise(ev: pd.DataFrame, rung: str, period: str) -> list:
    rows = []
    for h in [f"m{k}" for k in HORIZONS_MIN] + ["close"]:
        m, t, n = es.clustered_mean(ev[h], ev.day)
        rows.append({"rung": rung, "period": period, "horizon": h, "mean_bps": m, "t_clustered": t,
                     "N": n, "events": len(ev), "coverage": n / len(ev) if len(ev) else np.nan,
                     "unchanged_bar_share": float(ev.loc[ev[h].notna(), f"{h}_unchanged"].mean())
                     if h != "close" else np.nan,
                     "above_cost": m > es.ROUND_TRIP_BPS})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", choices=["train", "test"], required=True)
    ap.add_argument("--rungs", nargs="+", default=["keyword", "llm_anon", "embed_minilm"])
    a = ap.parse_args()
    cfg = Config()
    if a.period == "train":
        _, nw, cfg = load_training()
    else:
        _, nw, _ = es.load_test()
    bars = load_bars(a.period)
    nw = nw[nw.timestamp >= bars.ts.min().tz_convert(None).normalize()]
    rows = []
    for rung in a.rungs:
        ev = idd.rth_only(idd.headline_events(nw, scorer_for(rung, a.period, cfg), cfg))
        ev = horizon_returns(ev, bars)
        rows += summarise(ev, rung, a.period)
        print(f"  {rung}: {len(ev):,} trading-hours headline events", flush=True)
    tab = pd.DataFrame(rows)
    out = OUTPUTS / f"speed_bound_{a.period}_{STAMP}.csv"
    tab.to_csv(out, index=False)
    print(tab.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    if a.period == "test":
        pd.DataFrame([{"timestamp": datetime.now().isoformat(timespec="seconds"),
                       "script": f"src/speed_bound.py --period test --rungs {' '.join(a.rungs)}",
                       "scorers": "+".join(a.rungs), "period": "2024-04-30 .. 2026-06-01",
                       "what": "speed bound (ladder note item e)", "output": out.name}]).to_csv(
            OUTPUTS / "test_period_runs.csv", mode="a", index=False, header=False)


if __name__ == "__main__":
    main()
