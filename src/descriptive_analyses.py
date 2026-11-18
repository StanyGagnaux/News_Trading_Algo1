"""
descriptive_analyses.py -- DESCRIPTIVE runs requested 24 Oct 2026 (items 1a,
1c, 3, 4). Not new tests: no new rule, no parameter, no tuning; every number
re-slices the frozen specification. Each run is logged in
outputs/descriptive_runs.csv.

  yearly    1(a) frozen event study by calendar year (training + test), both
            scorers, raw and NDX-adjusted, days 0-3 and 5, t clustered by
            entry date; chart of the news-day reaction by year.
            + 3 news-sample statistics (same pass: shares the signal tables).
  subgroups 4 tidy subgroup table from the official training event study.
  strength  1(c) per-year |strength| vs trade R-multiple for A and B, from the
            trade logs of the reproduced 18 Oct frozen runs (--trades DIR).

USAGE (from the project root):
  python3 src/descriptive_analyses.py yearly
  python3 src/descriptive_analyses.py subgroups
  python3 src/descriptive_analyses.py strength --trades <dir with trades_* folders>
"""
from __future__ import annotations

import argparse
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from paths import NEWS_RAW, NEWS_CLEAN, OUTPUTS
from newsdrift import Config, KeywordScorer, PrecomputedScorer
from newsdrift.stats import correlation_t
from calibrate_scorer import load_training, build_features, headline_type, TRAIN_END, DATA_START, DATA_END
import event_study as es

TAG = "2026-10-24"
RUN_LOG = OUTPUTS / "descriptive_runs.csv"
OUT_YEARLY = OUTPUTS / f"descriptive_event_study_by_year_{TAG}.csv"
OUT_YEARLY_PNG = OUTPUTS / f"descriptive_event_study_by_year_{TAG}.png"
OUT_SAMPLE = OUTPUTS / f"descriptive_news_sample_{TAG}.csv"
OUT_SUBGROUPS = OUTPUTS / f"descriptive_subgroups_train_{TAG}.csv"
OUT_STRENGTH = OUTPUTS / f"descriptive_strength_vs_outcome_by_year_{TAG}.csv"
OFFICIAL_ES = {"train": OUTPUTS / "event_study_train_keyword+llm_anon_2026-10-18_bug11fix.csv",
               "test": OUTPUTS / "event_study_test_keyword+llm_anon_2026-10-18.csv"}
DAYS = [0, 1, 2, 3, 5]
RTH_OPEN, RTH_CLOSE = 9.5, 16.0                       # New York hours
# The official training event study (18 Oct 07:35) ran before the 1,098 rows of
# 2024-03-26..04-29 were scored (08:00). To reproduce it, training uses the LLM
# rows up to this date; those gap rows are in no official event study.
OFFICIAL_TRAIN_LLM_LAST_DAY = pd.Timestamp("2024-03-25")


def official_train_llm_file() -> str:
    llm = pd.read_csv(es.LLM_ANON)
    day = pd.to_datetime(llm.timestamp, utc=True).dt.tz_localize(None).dt.normalize()
    path = Path(tempfile.mkdtemp()) / "llm_anon_train_as_of_official_run.csv"
    llm[day <= OFFICIAL_TRAIN_LLM_LAST_DAY].to_csv(path, index=False)
    print(f"  training LLM rows as of the official run: {(day <= OFFICIAL_TRAIN_LLM_LAST_DAY).sum():,} "
          f"of {len(llm):,} (excluded gap rows: {(day > OFFICIAL_TRAIN_LLM_LAST_DAY).sum():,})")
    return str(path)


def log_run(item: str, what: str, outputs: list[Path]) -> None:
    row = {"timestamp": datetime.now().isoformat(timespec="seconds"), "item": item,
           "script": "src/descriptive_analyses.py", "what": what,
           "kind": "descriptive (no new test, no tuning)", "outputs": " ".join(p.name for p in outputs)}
    pd.DataFrame([row]).to_csv(RUN_LOG, mode="a", index=False, header=not RUN_LOG.exists())


# ------------------------------------------------------------ 1(a) yearly
def period_events(period: str) -> dict:
    """Frozen event-study events per scorer for one period (as event_study.main)."""
    if period == "train":
        px, nw, cfg = load_training()
        first, ndx, llm_file = DATA_START, es.load_ndx(DATA_START, TRAIN_END), official_train_llm_file()
    else:
        px, nw, first = es.load_test()
        cfg, llm_file = Config(), es.LLM_ANON_INCL_TEST
        ndx = es.load_ndx(TRAIN_END - es.PRE_TEST_PRICE_DAYS, DATA_END)
    llm = pd.read_csv(llm_file)
    imp = dict(zip(zip(llm.headline, llm.ticker), llm.importance))
    td = pd.DatetimeIndex(sorted(px.date.unique()))
    out = {}
    for name, scorer, importance in (("keyword", KeywordScorer(cfg.signal), None),
                                     ("llm_anon", PrecomputedScorer(str(llm_file)), imp)):
        sig = build_features(nw, scorer, cfg, td, importance)
        sig = sig[sig.effective_date >= first]
        out[name] = es.event_returns(px, ndx, sig)
    return out


def verify_against_official(ev: pd.DataFrame, period: str, scorer: str) -> None:
    off = pd.read_csv(OFFICIAL_ES[period])
    off = off[(off.scorer == scorer) & (off.split == "all events")]
    mine = pd.DataFrame(es.summarise(ev, scorer, "all events", None))
    m = off.merge(mine, on=["adj", "day"], suffixes=("_off", "_new"))
    assert len(m) == len(off) and (m.N_off == m.N_new).all() \
        and np.allclose(m.mean_bps_off, m.mean_bps_new, atol=1e-9), f"{period} {scorer}: differs from official"
    print(f"  {period} {scorer}: reproduces the official 'all events' rows exactly ({len(m)} cells)")


def yearly_table(evs: dict) -> pd.DataFrame:
    rows = []
    for period, by_scorer in evs.items():
        for scorer, ev in by_scorer.items():
            verify_against_official(ev, period, scorer)
            ev = ev.assign(year=ev.effective_date.dt.year)
            for r in es.summarise(ev, scorer, "year", "year"):
                rows.append({"period": period, **r})
    tab = pd.DataFrame(rows).rename(columns={"group": "year"})
    return tab[tab.day.isin(DAYS)]


def yearly_chart(tab: pd.DataFrame) -> None:
    t = tab[tab.adj == "mkt"].assign(label=lambda d: np.where(
        d.year == "2024", "2024 " + d.period, d.year))
    labels = sorted(t.label.unique(), key=lambda s: (s[:4], s.endswith("test")))   # train half first
    x = {lab: i for i, lab in enumerate(labels)}
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    for ax, day, title in ((axes[0], 0, "day 0: news-day close-to-close (not traded)"),
                           (axes[1], 3, "entry open -> close of day 3 (what A holds)")):
        for (scorer, g), off, colour in zip(t[t.day == day].groupby("scorer"), (-0.12, 0.12),
                                            ("tab:blue", "tab:orange")):
            g = g.set_index("label").reindex(labels).dropna(subset=["mean_bps"])
            se = (g.mean_bps / g.t_clustered).abs()
            ax.errorbar([x[l] + off for l in g.index], g.mean_bps, yerr=1.96 * se, fmt="o",
                        color=colour, capsize=3, label=scorer)
        if day:
            ax.axhline(es.ROUND_TRIP_BPS, ls="--", color="grey", lw=1, label="round-trip cost 4.86 bps")
        ax.axhline(0, color="black", lw=0.5)
        ax.set_title(title, fontsize=10)
        ax.set_ylabel("signed NDX-adj. bps")
        ax.legend(fontsize=8)
    axes[1].set_xticks(range(len(labels)), labels, rotation=45)
    fig.suptitle("Frozen event study by year (descriptive), mean ± 1.96 SE clustered by date", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT_YEARLY_PNG, dpi=150)


# ------------------------------------------------------------ 3 news sample
def load_news(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, usecols=["timestamp", "ticker", "headline"], low_memory=False)
    df["ts"] = pd.to_datetime(df.timestamp, utc=True, format="mixed")
    day = df.ts.dt.tz_localize(None).dt.normalize()
    return df[(day >= DATA_START) & (day <= DATA_END)]


def stat_rows(table: str, key, values: dict) -> list[dict]:
    return [{"table": table, "key": str(key), "metric": k, "value": v} for k, v in values.items()]


def headline_counts(news: dict) -> list[dict]:
    rows = []
    for stage, df in news.items():
        uniq = df.drop_duplicates(["ts", "headline"])
        for yr, n_rows in df.groupby(df.ts.dt.year).size().items():
            rows += stat_rows("headlines_per_year", yr, {f"{stage}_rows": n_rows,
                              f"{stage}_unique_headlines": int((uniq.ts.dt.year == yr).sum())})
        multi = df.groupby(["ts", "headline"]).ticker.nunique()
        rows += stat_rows("multi_ticker", stage, {"unique_headlines": len(multi),
                          "share_with_2plus_tickers": float((multi > 1).mean())})
    return rows


def timing_and_categories(clean: pd.DataFrame) -> list[dict]:
    uniq = clean.drop_duplicates(["ts", "headline"])
    ny = uniq.ts.dt.tz_convert("America/New_York")
    hour = ny.dt.hour + ny.dt.minute / 60
    rth = (ny.dt.weekday < 5) & (hour >= RTH_OPEN) & (hour < RTH_CLOSE)
    rows = stat_rows("rth_share", "all", {"share_rth": float(rth.mean()), "n": len(uniq)})
    for yr, s in rth.groupby(ny.dt.year):
        rows += stat_rows("rth_share", yr, {"share_rth": float(s.mean()), "n": len(s)})
    period = np.where(uniq.ts.dt.tz_localize(None).dt.normalize() <= TRAIN_END, "train", "test")
    cat = uniq.headline.map(headline_type)
    for p in ("train", "test"):
        rows += stat_rows("category_share_headlines", p, cat[period == p].value_counts(normalize=True).to_dict())
    per_ticker = clean.groupby("ticker").size()
    q = per_ticker.quantile([0.25, 0.5, 0.75])
    rows += stat_rows("rows_per_ticker", "all", {"tickers": len(per_ticker), "q1": q[0.25], "median": q[0.5],
                                                 "q3": q[0.75], "min": per_ticker.min(), "max": per_ticker.max()})
    rows += stat_rows("rows_per_ticker_top10", "all", per_ticker.nlargest(10).to_dict())
    return rows


def signal_rows(evs: dict) -> list[dict]:
    rows = []
    for period, by_scorer in evs.items():
        for scorer, ev in by_scorer.items():
            yr = ev.effective_date.dt.year
            for y, g in ev.groupby(yr):
                rows += stat_rows("signal_days", f"{period}|{scorer}|{y}",
                                  {"ticker_days": len(g), "dates": g.effective_date.nunique()})
            rows += stat_rows("category_share_events", f"{period}|{scorer}",
                              ev.category.value_counts(normalize=True).to_dict())
    return rows


def sample_stats(evs: dict) -> pd.DataFrame:
    news = {"raw": load_news(NEWS_RAW), "clean": load_news(NEWS_CLEAN),
            "tier0_llm_scored": load_news(es.LLM_ANON_INCL_TEST)}
    return pd.DataFrame(headline_counts(news) + timing_and_categories(news["clean"]) + signal_rows(evs))


# ------------------------------------------------------------ 4 subgroups
def subgroup_table() -> pd.DataFrame:
    tab = pd.read_csv(OFFICIAL_ES["train"])
    tab = tab[tab.day.isin(DAYS)]
    tab = tab.assign(cell=[f"{m:+.1f} ({t:+.2f}) N={n:,}" for m, t, n in zip(tab.mean_bps, tab.t_clustered, tab.N)])
    wide = tab.pivot_table(index=["scorer", "adj", "split", "group"], columns="day", values="cell", aggfunc="first")
    wide.columns = [f"day_{d}" for d in wide.columns]
    order = {"all events": 0, "|strength| tercile": 1, "importance": 2,
             "market-cap tercile (prior day)": 3, "news category": 4, "duration": 5}
    return (wide.reset_index().sort_values(["scorer", "adj", "split", "group"],
                                           key=lambda s: s.map(order) if s.name == "split" else s))


# ------------------------------------------------------------ 1(c) strength
def strength_by_year(trades_dir: Path) -> pd.DataFrame:
    rows = []
    for f in sorted(trades_dir.glob("trades_*/[AB]_*.csv")):
        name, tag = f.stem.rsplit("_", 1)
        tr = pd.read_csv(f)
        when = pd.to_datetime(tr["entry_date"] if "entry_date" in tr else tr["entry_ts"], utc=True)
        groups = [("all", tr)] + list(tr.groupby(when.dt.year))
        for yr, g in groups:
            st = correlation_t(g.strength.abs(), g.r_multiple)
            rows.append({"strategy": name, "period": tag, "year": str(yr), "N": len(g),
                         "share_abs_strength_eq_1": float((g.strength.abs() == 1).mean()),
                         "corr": st["corr"], "r2": st["r2"], "t": st["t"]})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["yearly", "subgroups", "strength"])
    ap.add_argument("--trades", type=Path)
    a = ap.parse_args()
    if a.what == "yearly":
        evs = {p: period_events(p) for p in ("train", "test")}
        tab = yearly_table(evs)
        tab.to_csv(OUT_YEARLY, index=False)
        yearly_chart(tab)
        sample_stats(evs).to_csv(OUT_SAMPLE, index=False)
        log_run("1a", "frozen event study by year, training + test, both scorers", [OUT_YEARLY, OUT_YEARLY_PNG])
        log_run("3", "news-sample descriptive statistics", [OUT_SAMPLE])
        print(f"saved {OUT_YEARLY.name}, {OUT_YEARLY_PNG.name}, {OUT_SAMPLE.name}")
    elif a.what == "subgroups":
        subgroup_table().to_csv(OUT_SUBGROUPS, index=False)
        log_run("4", "subgroup table from the official training event study (reshape only)", [OUT_SUBGROUPS])
        print(f"saved {OUT_SUBGROUPS.name}")
    else:
        if a.trades is None:
            raise SystemExit("--trades DIR required")
        strength_by_year(a.trades).to_csv(OUT_STRENGTH, index=False)
        log_run("1c", "per-year |strength| vs R-multiple, A and B, reproduced 18 Oct runs", [OUT_STRENGTH])
        print(f"saved {OUT_STRENGTH.name}")


if __name__ == "__main__":
    main()
