"""
event_study.py -- diagnostics on the anonymised LLM scores vs the keyword
scorer. TRAINING PERIOD ONLY (rows after 2024-04-29 dropped while reading, via
calibrate_scorer.load_training). No variants, no tuning, no re-scoring.

1. Score distributions (anonymised LLM): strength, importance, duration.
2. Anonymisation effect: same (headline, ticker), named vs anonymised scores.
3. Event study on the daily signal table Strategy A trades (one event per
   ticker-day, direction = sign of the netted strength). Zero-netting days
   (net strength exactly 0) produce no event (the open engine issue in
   context/bugs.md, applied here only). Signed returns, in bps:
     day 0  = close-to-close return of the last trading day BEFORE entry
              (the news day; never traded)
     day k  = entry open (effective_date) -> close of the k-th trading day,
              k = 1, 2, 3, 5 (day 1 = same-day close)
   raw and market-adjusted (minus NDX over the same window); mean, t-stat
   clustered by entry date, N. The overnight gap close(E-1) -> open(E) is in
   neither window. Costs are NOT deducted; the reference is one round trip.

USAGE (from the project root):
  python3 src/event_study.py                                  # training, both scorers
  python3 src/event_study.py --period test --scorers keyword  # TEST period (logged)
Every test-period run is appended to outputs/test_period_runs.csv.
"""
from __future__ import annotations
import argparse
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from paths import PRICES, NEWS_CLEAN, LLM_SCORES, OUTPUTS, DATA
from newsdrift import Config, KeywordScorer, PrecomputedScorer
from calibrate_scorer import (load_training, build_features, TRAIN_END, DATA_START,
                              DATA_END, INDEX_TICKERS)

LLM_ANON = DATA / "news_scored_llm_ollama_anon.csv"                 # training only
LLM_ANON_INCL_TEST = DATA / "news_scored_llm_ollama_anon_incl_test.csv"  # --include-test-period run
KEYWORD_STD_REF = 0.238
ROUND_TRIP_BPS = 2 * 2.43
HORIZONS = [1, 2, 3, 5]
CHART_DAYS = [1, 2, 3, 4, 5]
TEST_RUN_LOG = OUTPUTS / "test_period_runs.csv"
PRE_TEST_PRICE_DAYS = pd.Timedelta(days=30)    # prior bars for the day-0 return only
PRE_TEST_NEWS_DAYS = pd.Timedelta(days=10)     # news whose signal lands in the test period
CHUNK = 200_000


# --------------------------------------------------------------- 1 and 2
def text_hist(s: pd.Series, bins) -> str:
    counts = pd.cut(s, bins, include_lowest=True).value_counts(sort=False)
    top = counts.max()
    return "\n".join(f"    {str(k):>16} {v:>7,} {v / len(s):6.1%} {'#' * int(40 * v / top)}"
                     for k, v in counts.items())


def distributions(llm: pd.DataFrame, nw: pd.DataFrame, kw: KeywordScorer) -> None:
    s = llm.strength
    print(f"\n{'=' * 70}\n1. SCORE DISTRIBUTIONS (anonymised LLM, {len(llm):,} scored rows)\n{'=' * 70}")
    print("  strength histogram:")
    print(text_hist(s, np.linspace(-1, 1, 11)))
    kw_same = pd.Series([kw.score(h, t)[0] for h, t in zip(llm.headline, llm.ticker)])
    kw_all = pd.Series([kw.score(h, t)[0] for h, t in zip(nw.headline, nw.ticker)])
    print(f"  std {s.std():.3f}  (keyword reference {KEYWORD_STD_REF}; keyword on the same "
          f"headlines {kw_same.std():.3f}, on all {len(nw):,} training headlines {kw_all.std():.3f})")
    print(f"  distinct values {s.nunique()}  | most common: "
          + ", ".join(f"{v:+.2f} ({c:.1%})" for v, c in s.value_counts(normalize=True).head(6).items()))
    for th in (0.2, 0.5, 0.8):
        print(f"  |s| >= {th}: {(s.abs() >= th).mean():.1%}")
    print(f"  exactly 0: {(s == 0).mean():.2%}  | positive {(s > 0).mean():.1%}  negative {(s < 0).mean():.1%}")
    print("  importance (share per value 1-10):")
    imp = llm.importance.round().astype(int).value_counts(normalize=True).reindex(range(1, 11), fill_value=0)
    print("    " + "  ".join(f"{k}:{v:.1%}" for k, v in imp.items()))
    dur = llm.duration.value_counts(normalize=True).reindex([1, 2, 3], fill_value=0)
    print("  duration: " + "  ".join(f"{k}: {v:.1%}" for k, v in dur.items()))


def anonymisation_effect(llm: pd.DataFrame) -> None:
    named = pd.read_csv(LLM_SCORES)
    keys = ["headline", "ticker"]
    m = named.drop_duplicates(keys).merge(llm.drop_duplicates(keys), on=keys, suffixes=("_named", "_anon"))
    a, b = m.strength_named, m.strength_anon
    print(f"\n{'=' * 70}\n2. ANONYMISATION EFFECT ({len(m):,} identical (headline, ticker) pairs)\n{'=' * 70}")
    print(f"  strength correlation named vs anonymised: {np.corrcoef(a, b)[0, 1]:+.3f}")
    print(f"  sign flipped (+ <-> -): {(np.sign(a) * np.sign(b) < 0).mean():.1%}  | "
          f"sign differs incl. zero: {(np.sign(a) != np.sign(b)).mean():.1%}")
    print(f"  mean |change| in strength: {(a - b).abs().mean():.3f}  (median {(a - b).abs().median():.3f})")
    print(f"  mean strength named {a.mean():+.3f} -> anonymised {b.mean():+.3f}")
    print(f"  importance: corr {np.corrcoef(m.importance_named, m.importance_anon)[0, 1]:+.3f}, "
          f"mean {m.importance_named.mean():.2f} -> {m.importance_anon.mean():.2f}")
    print(f"  duration identical: {(m.duration_named == m.duration_anon).mean():.1%}")


# --------------------------------------------------------------- 3. event study
def load_ndx(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    parts = [c[(c.ticker == "NDX") & (c.date >= start) & (c.date <= end)]
             for c in pd.read_csv(PRICES, parse_dates=["date"], chunksize=CHUNK)]
    ndx = pd.concat(parts).set_index("date").sort_index()
    assert ndx.index.max() <= end
    return ndx[["open", "close"]]


def load_window(news_path, price_start, price_end, news_start, news_end
                ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Prices from prices.csv in [price_start, price_end] and news from
    news_path with timestamp >= news_start and UTC date <= news_end; common
    tickers only. The single loader for the test period and the holdout."""
    px = pd.concat(c[(c.date >= price_start) & (c.date <= price_end)
                     & ~c.ticker.isin(INDEX_TICKERS)]
                   for c in pd.read_csv(PRICES, parse_dates=["date"], chunksize=CHUNK))
    parts = []
    for c in pd.read_csv(news_path, chunksize=CHUNK, low_memory=False):
        ts = pd.to_datetime(c.timestamp, utc=True).dt.tz_localize(None)
        keep = (ts >= news_start) & (ts.dt.normalize() <= news_end)
        parts.append(c.loc[keep].assign(timestamp=ts[keep]))
    nw = pd.concat(parts, ignore_index=True)
    common = set(px.ticker) & set(nw.ticker)
    return (px[px.ticker.isin(common)].reset_index(drop=True),
            nw[nw.ticker.isin(common)].reset_index(drop=True))


def load_test() -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]:
    """TEST period: events with effective_date in (TRAIN_END, DATA_END]. Prices
    from 30 days earlier are loaded only for the day-0 return."""
    px, nw = load_window(NEWS_CLEAN, TRAIN_END - PRE_TEST_PRICE_DAYS, DATA_END,
                         TRAIN_END - PRE_TEST_NEWS_DAYS, DATA_END)
    test_start = px.date[px.date > TRAIN_END].min()
    return px, nw, test_start


def _ticker_returns(g: pd.DataFrame, ev: pd.DataFrame, ndx: pd.DataFrame) -> pd.DataFrame:
    d = g.date.to_numpy()
    o, c, cap = g.open.to_numpy(float), g.close.to_numpy(float), g.mktcap.to_numpy(float)
    eff = ev.effective_date.to_numpy()
    pos = np.searchsorted(d, eff)
    hit = (pos < len(d)) & (d[np.minimum(pos, len(d) - 1)] == eff)
    ev, pos = ev[hit], pos[hit]
    n_o, n_c = ndx.open.reindex(d).to_numpy(float), ndx.close.reindex(d).to_numpy(float)
    p1, p2 = np.maximum(pos - 1, 0), np.maximum(pos - 2, 0)
    res = {"mktcap": np.where(pos >= 1, cap[p1], np.nan)}       # prior day: known at entry
    res["raw_0"] = np.where(pos >= 2, c[p1] / c[p2] - 1, np.nan)
    res["mkt_0"] = res["raw_0"] - np.where(pos >= 2, n_c[p1] / n_c[p2] - 1, np.nan)
    for k in sorted(set(HORIZONS) | set(CHART_DAYS)):
        j = pos + k - 1
        ok, jj = j < len(d), np.minimum(j, len(d) - 1)
        res[f"raw_{k}"] = np.where(ok, c[jj] / o[pos] - 1, np.nan)
        res[f"mkt_{k}"] = res[f"raw_{k}"] - np.where(ok, n_c[jj] / n_o[pos] - 1, np.nan)
    return ev.assign(**res)


def event_returns(px: pd.DataFrame, ndx: pd.DataFrame, sig: pd.DataFrame) -> pd.DataFrame:
    """One row per signal with signed raw / market-adjusted returns in bps."""
    by_ticker = dict(tuple(sig.groupby("ticker")))
    ev = pd.concat([_ticker_returns(g, by_ticker[t], ndx)
                    for t, g in px.sort_values("date").groupby("ticker") if t in by_ticker],
                   ignore_index=True)
    cols = [c for c in ev.columns if c.startswith(("raw_", "mkt_"))]
    signed = ev[cols].mul(np.sign(ev.strength), axis=0) * 1e4
    return ev.drop(columns=cols).join(signed)


def clustered_mean(y: pd.Series, cluster: pd.Series) -> tuple[float, float, int]:
    ok = y.notna()
    yv, cl = y[ok].to_numpy(float), cluster[ok].to_numpy()
    n = len(yv)
    if n < 2:
        return np.nan, np.nan, n
    m = yv.mean()
    sums = pd.Series(yv - m).groupby(cl).sum().to_numpy()
    g = len(sums)
    var = g / (g - 1) * (sums ** 2).sum() / n ** 2 if g > 1 else np.nan
    return m, (m / np.sqrt(var) if var > 0 else np.nan), n


def summarise(ev: pd.DataFrame, scorer: str, split: str, group_col: str | None) -> list[dict]:
    groups = [("all", ev)] if group_col is None else \
        [(str(k), g) for k, g in ev.groupby(group_col, observed=True, sort=True)]
    rows = []
    for name, g in groups:
        for adj in ("raw", "mkt"):
            for k in [0] + HORIZONS:
                m, t, n = clustered_mean(g[f"{adj}_{k}"], g.effective_date)
                rows.append({"scorer": scorer, "split": split, "group": name, "adj": adj,
                             "day": k, "mean_bps": m, "t_clustered": t, "N": n})
    return rows


def add_split_columns(ev: pd.DataFrame, is_llm: bool) -> pd.DataFrame:
    ev = ev.assign(
        abs_s_tercile=pd.qcut(ev.strength.abs().rank(method="first"), 3, labels=["low", "mid", "high"]),
        mktcap_tercile=pd.qcut(ev.mktcap, 3, labels=["small", "mid", "large"]))
    if is_llm:
        ev = ev.assign(importance_grp=pd.cut(ev.importance, [0, 3, 6, 10], labels=["1-3", "4-6", "7-10"]),
                       duration_grp=np.where(ev.duration == 2, "2", "not 2"))
    return ev


def print_table(tab: pd.DataFrame) -> None:
    for (scorer, split), part in tab.groupby(["scorer", "split"], sort=False):
        print(f"\n  [{scorer}] {split}")
        print(f"    {'group':<18}{'adj':<5}" + "".join(f"{'day ' + str(k):>24}" for k in [0] + HORIZONS))
        for (grp, adj), r in part.groupby(["group", "adj"], sort=False):
            cells = "".join(f"{row.mean_bps:>+8.1f} ({row.t_clustered:>+5.2f}) {row.N:>7,}"
                            for row in r.sort_values("day").itertuples())
            print(f"    {grp:<18}{adj:<5}{cells}")
    print(f"\n    cells: mean bps (t clustered by entry date) N | round-trip cost "
          f"reference {ROUND_TRIP_BPS:.2f} bps (gross returns, costs not deducted)")


def chart(evs: dict, out_png, period_label: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for (name, ev), colour in zip(evs.items(), ("tab:blue", "tab:orange")):
        ax.plot([0], [ev.mkt_0.mean()], "o", color=colour)
        ax.plot([0.6] + CHART_DAYS, [0] + [ev[f"mkt_{k}"].mean() for k in CHART_DAYS],
                "-o", color=colour, label=f"{name} (N={len(ev):,})")
    ax.axhline(ROUND_TRIP_BPS, ls="--", color="grey", lw=1, label=f"round-trip cost {ROUND_TRIP_BPS:.2f} bps")
    ax.axhline(0, color="black", lw=0.5)
    ax.axvline(0.6, color="grey", lw=0.5, ls=":")
    ax.set_xticks([0, 0.6] + CHART_DAYS, ["day 0\n(news)", "entry\nopen"] + [f"day {k}" for k in CHART_DAYS])
    ax.set_ylabel("signed market-adjusted return (bps)")
    ax.set_title(f"Signed return vs NDX, {period_label}\n"
                 "(dot: day 0 = news day, not traded; line: entry open -> close of day k)", fontsize=10)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)


def event_study(px, nw, cfg, scorers: list, ndx, first_event, out_stem: str,
                period_label: str) -> None:
    print(f"\n{'=' * 70}\n3. EVENT STUDY ({period_label}, daily signals as Strategy A trades them)\n{'=' * 70}")
    td = pd.DatetimeIndex(sorted(px.date.unique()))
    rows, evs = [], {}
    for name, scorer, importance in scorers:
        sig = build_features(nw, scorer, cfg, td, importance)    # Bug 11 gate inside
        sig = sig[sig.effective_date >= first_event]
        print(f"  {name}: {len(sig):,} events (zero-netting and |net strength| < 0.20 "
              f"days excluded), {sig.effective_date.min().date()} -> {sig.effective_date.max().date()}")
        ev = add_split_columns(event_returns(px, ndx, sig), name != "keyword")
        evs[name] = ev
        splits = [("all events", None), ("|strength| tercile", "abs_s_tercile"),
                  ("market-cap tercile (prior day)", "mktcap_tercile"), ("news category", "category")]
        if name != "keyword":
            splits += [("importance", "importance_grp"), ("duration", "duration_grp")]
        for split, col in splits:
            rows += summarise(ev, name, split, col)
    tab = pd.DataFrame(rows)
    out_csv, out_png = OUTPUTS / f"{out_stem}.csv", OUTPUTS / f"{out_stem}.png"
    tab.to_csv(out_csv, index=False)
    print_table(tab)
    chart(evs, out_png, period_label)
    print(f"\n  saved {out_csv.name} and {out_png.name} in outputs/")
    return out_csv


def log_test_run(scorers: list, out_csv) -> None:
    row = {"timestamp": datetime.now().isoformat(timespec="seconds"),
           "script": "src/event_study.py --period test",
           "scorers": "+".join(scorers), "period": f"> {TRAIN_END.date()} .. {DATA_END.date()}",
           "what": "event study (diagnostic, no trading rule, no tuning)",
           "output": out_csv.name}
    pd.DataFrame([row]).to_csv(TEST_RUN_LOG, mode="a", index=False, header=not TEST_RUN_LOG.exists())
    print(f"  logged as a TEST-PERIOD run in {TEST_RUN_LOG.name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", choices=["train", "test"], default="train")
    ap.add_argument("--scorers", nargs="+", choices=["keyword", "llm_anon"],
                    default=["keyword", "llm_anon"])
    ap.add_argument("--tag", default=datetime.now().strftime("%Y-%m-%d"))
    args = ap.parse_args()
    llm_file = LLM_ANON if args.period == "train" else LLM_ANON_INCL_TEST
    if "llm_anon" in args.scorers and not llm_file.exists():
        raise SystemExit(f"no LLM scores for this period: {llm_file.name} missing")

    if args.period == "train":
        px, nw, cfg = load_training()
        first_event, ndx_start, label = DATA_START, DATA_START, "training period 2016 - 2024-04-29"
        print(f"training only: {px.date.min().date()} -> {px.date.max().date()} | {len(nw):,} headlines")
    else:
        px, nw, first_event = load_test()
        cfg = Config()                     # signal config only; costs are not used here
        ndx_start, label = TRAIN_END - PRE_TEST_PRICE_DAYS, f"TEST period {first_event.date()} - {DATA_END.date()}"
        print(f"TEST PERIOD: events {first_event.date()} -> {DATA_END.date()} | {len(nw):,} headlines")
    end = TRAIN_END if args.period == "train" else DATA_END
    ndx = load_ndx(ndx_start, end)

    llm = pd.read_csv(llm_file if llm_file.exists() else LLM_ANON)
    if args.period == "train":
        ts = pd.to_datetime(llm.timestamp, utc=True).dt.tz_localize(None)
        assert ts.max().normalize() <= TRAIN_END, "anonymised score file has test-period rows"
        distributions(llm, nw, KeywordScorer(cfg.signal))
        anonymisation_effect(llm)
    imp = dict(zip(zip(llm.headline, llm.ticker), llm.importance))
    available = {"keyword": (KeywordScorer(cfg.signal), None),
                 "llm_anon": (PrecomputedScorer(str(llm_file if llm_file.exists() else LLM_ANON)), imp)}
    scorers = [(n, *available[n]) for n in args.scorers]
    out_csv = event_study(px, nw, cfg, scorers, ndx, first_event,
                          f"event_study_{args.period}_{'+'.join(args.scorers)}_{args.tag}", label)
    if args.period == "test":
        log_test_run(args.scorers, out_csv)


if __name__ == "__main__":
    main()
