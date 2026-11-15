"""
descriptive_event_study_clustering.py -- standard errors of the training event
study under wider clusters. DESCRIPTIVE, TRAINING PERIOD ONLY (rows after
2024-04-29 are dropped while reading, via calibrate_scorer.load_training).

Specification: review_2026-11-14/CLUSTERING_note_2026-11-14.md (written before
the reviewer's check; SHA-256 a595eddc...). The official event study clusters
its standard errors by entry date; the windows of days 2, 3 and 5 overlap
across neighbouring entry dates. Here the same cluster-robust variance
(event_study.clustered_mean, unchanged) is computed with the cluster defined
as (a) the entry date (official), (b) the ISO week, (c) the calendar month of
the entry date. All events, market-adjusted signed returns, days 1, 2, 3, 5.

Validity condition: mean, t-statistic and N of the eight entry-date cells must
equal outputs/event_study_train_keyword+llm_anon_2026-10-18_bug11fix.csv (mean
and t to 1e-6, N exact). If not, nothing is written. As on 18 Oct, the Llama
scores are those with a timestamp before 2024-03-26 (59,154 rows; the rows of
2024-03-26 to 04-29 were scored later).

No strategy is run, nothing is tuned, no other result changes.

USAGE (from the project root):  python3 src/descriptive_event_study_clustering.py
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd

from paths import OUTPUTS
from newsdrift import KeywordScorer, PrecomputedScorer
from calibrate_scorer import load_training, build_features, TRAIN_END, DATA_START
from event_study import LLM_ANON, ROUND_TRIP_BPS, HORIZONS, load_ndx, event_returns, clustered_mean

DATE = "2026-11-14"
OFFICIAL = OUTPUTS / "event_study_train_keyword+llm_anon_2026-10-18_bug11fix.csv"
OUT = OUTPUTS / f"descriptive_event_study_clustering_train_{DATE}.csv"
LLM_ROWS_18_OCT = 59_154
LLM_SCORED_LATER_FROM = pd.Timestamp("2024-03-26")
ONE_SIDED_95 = 1.645
TOLERANCE = 1e-6
MATERIAL_SE_RATIO = 1.25           # reading rule (ii) of the note
OFFICIAL_CLUSTER = "entry date"


def cluster_labels(entry_date: pd.Series) -> dict:
    """The three cluster definitions of the note, keyed by their name in the output."""
    d = pd.to_datetime(entry_date)
    iso = d.dt.isocalendar()
    return {OFFICIAL_CLUSTER: d,
            "ISO week": iso.year.astype(str) + "-" + iso.week.astype(str),
            "month": d.dt.to_period("M").astype(str)}


def llm_scores_as_on_18_oct(folder: Path) -> tuple[Path, dict]:
    """The Llama score file cut to the rows the official run of 18 Oct read; (path, importance lookup)."""
    llm = pd.read_csv(LLM_ANON)
    ts = pd.to_datetime(llm.timestamp, utc=True).dt.tz_localize(None)
    assert ts.max().normalize() <= TRAIN_END, "anonymised score file has test-period rows"
    llm = llm[ts < LLM_SCORED_LATER_FROM]
    assert len(llm) == LLM_ROWS_18_OCT, f"expected {LLM_ROWS_18_OCT:,} rows before {LLM_SCORED_LATER_FROM.date()}, found {len(llm):,}"
    path = folder / "llm_anon_before_2024-03-26.csv"
    llm.to_csv(path, index=False)
    return path, dict(zip(zip(llm.headline, llm.ticker), llm.importance))


def events(px, nw, cfg, ndx, scorer, importance) -> pd.DataFrame:
    """Event-level returns exactly as event_study.event_study builds them."""
    td = pd.DatetimeIndex(sorted(px.date.unique()))
    sig = build_features(nw, scorer, cfg, td, importance)
    sig = sig[sig.effective_date >= DATA_START]
    ev = event_returns(px, ndx, sig)
    assert ev.effective_date.max() <= TRAIN_END, "an event after the training period"
    return ev


def rows_for(name: str, ev: pd.DataFrame, official: pd.DataFrame) -> list[dict]:
    rows = []
    labels = cluster_labels(ev.effective_date)
    for day in HORIZONS:
        y = ev[f"mkt_{day}"]
        ref = official[(official.scorer == name) & (official.day == day)].iloc[0]
        se_official = None
        for label, cluster in labels.items():
            mean, t, n = clustered_mean(y, cluster)
            se = mean / t
            reproduces = None
            if label == OFFICIAL_CLUSTER:
                se_official = se
                reproduces = bool(abs(mean - ref.mean_bps) < TOLERANCE and abs(t - ref.t_clustered) < TOLERANCE and n == int(ref.N))
            upper = mean + ONE_SIDED_95 * se
            rows.append({"scorer": name, "day": day, "cluster": label, "clusters": int(cluster[y.notna()].nunique()), "N": n,
                         "mean_bps": mean, "se_bps": se, "t": t, "upper95_bps": upper,
                         "se_ratio_to_official": se / se_official, "reproduces_official": reproduces,
                         "bound_below_cost": bool(upper < ROUND_TRIP_BPS)})
    return rows


def reading(table: pd.DataFrame) -> dict:
    """The reading rule fixed in the note, for days 2, 3 and 5."""
    later = table[table.day > 1]
    below = later.pivot_table(index=["scorer", "day"], columns="cluster", values="bound_below_cost", aggfunc="first").astype(bool)
    crossing = below[OFFICIAL_CLUSTER] & (~below["ISO week"] | ~below["month"])
    wider = later[later.cluster != OFFICIAL_CLUSTER]
    return {"rule_i_bound_crosses_cost": bool(crossing.any()),
            "rule_ii_se_up_25pct_or_more": bool((wider.se_ratio_to_official >= MATERIAL_SE_RATIO).any()),
            "largest_se_ratio": float(wider.se_ratio_to_official.max()),
            "bounds_below_zero_by_cluster": table.assign(neg=table.upper95_bps < 0).groupby("cluster", sort=False).neg.sum().to_dict(),
            "bounds_below_cost_by_cluster": table.groupby("cluster", sort=False).bound_below_cost.sum().to_dict()}


def main():
    official = pd.read_csv(OFFICIAL)
    official = official[(official.split == "all events") & (official.adj == "mkt")]
    px, nw, cfg = load_training()
    assert px.date.max() <= TRAIN_END and nw.timestamp.max().normalize() <= TRAIN_END, "training only"
    ndx = load_ndx(DATA_START, TRAIN_END)
    print(f"training only: {px.date.min().date()} -> {px.date.max().date()} | {len(nw):,} headlines")
    with tempfile.TemporaryDirectory() as tmp:
        llm_path, importance = llm_scores_as_on_18_oct(Path(tmp))
        scorers = [("keyword", KeywordScorer(cfg.signal), None), ("llm_anon", PrecomputedScorer(str(llm_path)), importance)]
        rows = []
        for name, scorer, imp in scorers:
            ev = events(px, nw, cfg, ndx, scorer, imp)
            print(f"  {name}: {len(ev):,} events, {ev.effective_date.min().date()} -> {ev.effective_date.max().date()}")
            rows += rows_for(name, ev, official)
    table = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.float_format", lambda x: f"{x:.4f}")
    print(table.to_string(index=False))
    valid = bool(table[table.cluster == OFFICIAL_CLUSTER].reproduces_official.all())
    print(f"\nvalidity (all eight official cells reproduced): {valid}")
    if not valid:
        raise SystemExit("VOID: the official training cells are not reproduced -- nothing written")
    table.to_csv(OUT, index=False)
    print(f"saved {OUT.name} in outputs/")
    for key, value in reading(table).items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
