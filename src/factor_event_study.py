"""
factor_event_study.py -- factor robustness of the frozen event study (ladder
note of 24 Oct 2026, item a). Reported BESIDE the NDX-adjusted results.

Abnormal return per event and window = ticker return - sum over the window's
trading days of (rf + beta'f), f = Fama-French five factors + momentum (daily,
Kenneth French library, data_sources/factors/). Betas: OLS of the ticker's
daily excess return (close-to-close) on the six factors over the ticker's 250
trading days ending 10 trading days before day 0 (bars -259 .. -10, day 0 =
the last trading day before entry, as in the frozen event study); events with
fewer than 200 valid returns are dropped and counted. Day 0 is exact
(close-to-close); windows starting at the entry open use the first day's
close-to-close factor return (stated approximation). Same events, windows,
signing, clustering and splits as event_study.py (whose functions are reused).

USAGE (from the project root):
  python3 src/factor_event_study.py --period train
  python3 src/factor_event_study.py --period test     # logged test-period run
"""
from __future__ import annotations

import argparse
from datetime import datetime

import numpy as np
import pandas as pd

from paths import DATA, OUTPUTS, PRICES
from newsdrift import Config, KeywordScorer, PrecomputedScorer
import event_study as es
from calibrate_scorer import load_training, build_features, INDEX_TICKERS

FACTOR_DIR = DATA / "factors"
FACTORS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]
EST_LEN, EST_GAP, MIN_OBS = 250, 10, 200
WINDOWS = [0] + es.HORIZONS
STAMP = "2026-10-24"


def read_french(name: str) -> pd.DataFrame:
    lines = (FACTOR_DIR / name).read_text().splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith(","))
    rows = []
    for l in lines[start + 1:]:
        if not l.strip() or not l.strip()[0].isdigit():
            break
        rows.append([x.strip() for x in l.split(",")])
    cols = ["date"] + [c.strip() for c in lines[start].split(",")[1:]]
    df = pd.DataFrame(rows, columns=cols)
    df["date"] = pd.to_datetime(df.date, format="%Y%m%d")
    vals = df.drop(columns="date").astype(float).where(lambda v: v > -99) / 100.0
    return vals.set_index(df.date)


def load_factors() -> pd.DataFrame:
    f = read_french("F-F_Research_Data_5_Factors_2x3_daily.csv").join(
        read_french("F-F_Momentum_Factor_daily.csv"), how="inner")
    f.columns = [c.strip() for c in f.columns]
    return f[FACTORS + ["RF"]]


def history(end: pd.Timestamp) -> dict:
    """Close prices per ticker from the start of prices.csv to `end` (betas only)."""
    parts = [c[(c.date <= end) & ~c.ticker.isin(INDEX_TICKERS)][["date", "ticker", "close"]]
             for c in pd.read_csv(PRICES, parse_dates=["date"], chunksize=es.CHUNK)]
    px = pd.concat(parts).sort_values(["ticker", "date"])
    return {t: g.set_index("date").close for t, g in px.groupby("ticker")}


def factor_abnormal(px: pd.DataFrame, sig: pd.DataFrame, hist: dict, fac: pd.DataFrame) -> pd.DataFrame:
    """ff_k columns (signed bps) for the frozen windows; NaN if betas unavailable."""
    out = []
    for t, g in px.sort_values("date").groupby("ticker"):
        ev = sig[sig.ticker == t]
        h = hist.get(t)
        if ev.empty or h is None:
            continue
        d, o, c = g.date.to_numpy(), g.open.to_numpy(float), g.close.to_numpy(float)
        hd = h.index.to_numpy()
        ret = h.pct_change()
        fx = fac.reindex(h.index)
        for r in ev.itertuples(index=False):
            out.append(_one_event(r, d, o, c, hd, ret, fx))
    res = pd.DataFrame(out)
    cols = [f"ff_{k}" for k in WINDOWS]
    res[cols] = res[cols].mul(np.sign(res.strength), axis=0) * 1e4
    return res


def _one_event(r, d, o, c, hd, ret, fx) -> dict:
    row = {"effective_date": r.effective_date, "ticker": r.ticker, "strength": r.strength,
           **{f"ff_{k}": np.nan for k in WINDOWS}, "beta_obs": 0}
    e = pd.Timestamp(r.effective_date).to_datetime64()
    pos = np.searchsorted(d, e)
    if pos >= len(d) or d[pos] != e or pos < 2:
        return row
    hp = np.searchsorted(hd, d[pos - 1])                     # day 0 in the long history
    if hp >= len(hd) or hd[hp] != d[pos - 1]:
        return row
    lo, hi = hp - (EST_LEN - 1) - EST_GAP, hp - EST_GAP
    if lo < 1:
        return row
    y = (ret.iloc[lo:hi + 1] - fx.RF.iloc[lo:hi + 1]).to_numpy()
    X = fx[FACTORS].iloc[lo:hi + 1].to_numpy()
    ok = np.isfinite(y) & np.isfinite(X).all(axis=1)
    row["beta_obs"] = int(ok.sum())
    if ok.sum() < MIN_OBS:
        return row
    beta = np.linalg.lstsq(np.column_stack([np.ones(ok.sum()), X[ok]]), y[ok], rcond=None)[0][1:]
    expected = (fx.RF + fx[FACTORS] @ beta)                  # daily rf + beta'f, by history date
    row["ff_0"] = ret.iloc[hp] - expected.iloc[hp]
    for k in es.HORIZONS:
        j = pos + k - 1
        if j >= len(d):
            continue
        days = expected.reindex(pd.DatetimeIndex(d[pos:j + 1]))
        row[f"ff_{k}"] = c[j] / o[pos] - 1 - days.sum(min_count=len(days))
    return row


def period_inputs(period: str):
    if period == "train":
        px, nw, cfg = load_training()
        return px, nw, cfg, es.DATA_START, es.TRAIN_END, es.LLM_ANON, "training"
    px, nw, first = es.load_test()
    return px, nw, Config(), first, es.DATA_END, es.LLM_ANON_INCL_TEST, "TEST"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", choices=["train", "test"], required=True)
    period = ap.parse_args().period
    px, nw, cfg, first, end, llm_file, label = period_inputs(period)
    fac = load_factors()
    hist = history(end)
    ndx = es.load_ndx(es.DATA_START if period == "train" else es.TRAIN_END - es.PRE_TEST_PRICE_DAYS, end)
    td = pd.DatetimeIndex(sorted(px.date.unique()))
    llm = pd.read_csv(llm_file)
    imp = dict(zip(zip(llm.headline, llm.ticker), llm.importance))
    rows = []
    for name, scorer, importance in (("keyword", KeywordScorer(cfg.signal), None),
                                     ("llm_anon", PrecomputedScorer(str(llm_file)), imp)):
        sig = build_features(nw, scorer, cfg, td, importance)
        sig = sig[sig.effective_date >= first]
        ev = es.add_split_columns(es.event_returns(px, ndx, sig), name != "keyword")
        ff = factor_abnormal(px, sig, hist, fac)
        ev = ev.merge(ff.drop(columns="strength"), on=["effective_date", "ticker"], how="left")
        dropped = int(ev.ff_0.isna().sum())
        print(f"  {name}: {len(ev):,} events; {dropped:,} without factor betas "
              f"(< {MIN_OBS} returns in the window or no history)")
        splits = [("all events", None), ("|strength| tercile", "abs_s_tercile"),
                  ("market-cap tercile (prior day)", "mktcap_tercile"), ("news category", "category")]
        if name != "keyword":
            splits += [("importance", "importance_grp"), ("duration", "duration_grp")]
        ndx_rows = [r for split, col in splits for r in es.summarise(ev, name, split, col)]
        swapped = ev.assign(**{f"mkt_{k}": ev[f"ff_{k}"] for k in WINDOWS})
        ff_rows = [dict(r, adj="ff6") for split, col in splits
                   for r in es.summarise(swapped, name, split, col) if r["adj"] == "mkt"]
        rows += ndx_rows + ff_rows
    tab = pd.DataFrame(rows)
    out = OUTPUTS / f"event_study_ff6_{period}_{STAMP}.csv"
    tab.to_csv(out, index=False)
    allv = tab[(tab.split == "all events") & (tab.adj.isin(["mkt", "ff6"]))]
    print(f"\n{label}: all events, signed bps (t clustered by entry date)")
    print(allv.pivot_table(index=["scorer", "adj"], columns="day",
                           values=["mean_bps", "t_clustered"]).round(2).to_string())
    print(f"saved {out.name}")
    if period == "test":
        pd.DataFrame([{"timestamp": datetime.now().isoformat(timespec="seconds"),
                       "script": "src/factor_event_study.py --period test",
                       "scorers": "keyword+llm_anon", "period": "2024-04-30 .. 2026-06-01",
                       "what": "factor robustness (FF5+Mom) of the frozen event study; ladder note item a",
                       "output": out.name}]).to_csv(OUTPUTS / "test_period_runs.csv", mode="a",
                                                    index=False, header=False)


if __name__ == "__main__":
    main()
