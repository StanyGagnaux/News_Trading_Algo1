"""
h3.py -- pre-registered holdout hypothesis H3 (dated note, 19 Oct 2026):
"For LLM signals in the holdout, the market-adjusted signed return from entry
to the close of day 3 increases with |strength|."

Test: OLS slope b of y = market-adjusted signed day-3 return (bps, the frozen
event-study definition) on x = |net daily strength| across LLM holdout events;
standard error clustered by entry date (CR1: sandwich x G/(G-1)); one-sided,
reject H0 (b <= 0) if t = b / SE > 1.645. Single evaluation, outside the H1
Holm family.

This file also holds the ex-ante power analysis (run before any holdout price
exists): the test-period slope as the effect size, and the holdout's expected
sample from COUNTING holdout events (no prices, no returns).

USAGE (from the project root):  python3 src/h3.py --power
"""
from __future__ import annotations

import argparse
from datetime import datetime
from statistics import NormalDist

import numpy as np
import pandas as pd

from paths import OUTPUTS, DATA
from newsdrift import Config, PrecomputedScorer

Z_95 = NormalDist().inv_cdf(0.95)          # one-sided 5%: 1.645
WINDOW = "mkt_3"                            # event_study: entry open -> close day 3, minus NDX
HOLDOUT_START, HOLDOUT_END = pd.Timestamp("2026-06-02"), pd.Timestamp("2026-10-16")
OUT = OUTPUTS / "h3_power_2026-10-19.csv"


def clustered_slope(y, x, clusters) -> dict:
    """OLS of y on [1, x]; slope with CR1 cluster-robust SE (G/(G-1))."""
    d = pd.DataFrame({"y": y, "x": x, "g": clusters}).dropna()
    n = len(d)
    X = np.column_stack([np.ones(n), d.x.to_numpy(float)])
    yv = d.y.to_numpy(float)
    bread = np.linalg.inv(X.T @ X)
    beta = bread @ X.T @ yv
    e = yv - X @ beta
    scores = pd.DataFrame(X * e[:, None]).groupby(d.g.to_numpy()).sum().to_numpy()
    g = len(scores)
    v = g / (g - 1) * bread @ (scores.T @ scores) @ bread
    se = float(np.sqrt(v[1, 1]))
    return {"slope": float(beta[1]), "se": se, "t": float(beta[1]) / se, "n": n, "clusters": g}


def h3_decision(ev: pd.DataFrame) -> dict:
    """The single holdout evaluation: ev = LLM holdout events from event_study."""
    r = clustered_slope(ev[WINDOW], ev.strength.abs(), ev.effective_date)
    return {**r, "reject_H0_one_sided_5pct": r["t"] > Z_95}


def power(slope: float, se: float) -> float:
    return NormalDist().cdf(slope / se - Z_95)


def test_period_effect() -> dict:
    """Effect size on the TEST period (logged as a diagnostic test-period run)."""
    import event_study as es
    px, nw, first = es.load_test()
    cfg = Config()
    llm = pd.read_csv(es.LLM_ANON_INCL_TEST)
    imp = dict(zip(zip(llm.headline, llm.ticker), llm.importance))
    td = pd.DatetimeIndex(sorted(px.date.unique()))
    sig = es.build_features(nw, PrecomputedScorer(str(es.LLM_ANON_INCL_TEST)), cfg, td, imp)
    sig = sig[sig.effective_date >= first]
    ev = es.event_returns(px, es.load_ndx(es.TRAIN_END - es.PRE_TEST_PRICE_DAYS, es.DATA_END), sig)
    return clustered_slope(ev[WINDOW], ev.strength.abs(), ev.effective_date)


def holdout_count() -> dict:
    """COUNT of LLM holdout events (gated daily signals); no prices, no returns.
    Calendar: business days (US market holidays not removed -- a slight
    overcount of entry dates)."""
    from calibrate_scorer import build_features
    nw = pd.read_csv(DATA / "holdout" / "news_holdout_clean.csv")
    nw["timestamp"] = pd.to_datetime(nw.timestamp, utc=True).dt.tz_localize(None)
    td = pd.bdate_range(HOLDOUT_START - pd.Timedelta(days=10), HOLDOUT_END + pd.Timedelta(days=10))
    scorer = PrecomputedScorer(str(DATA / "holdout" / "news_scored_llm_ollama_anon_holdout.csv"))
    sig = build_features(nw, scorer, Config(), pd.Series(td), None)
    sig = sig[(sig.effective_date >= HOLDOUT_START) & (sig.effective_date <= HOLDOUT_END)]
    return {"events": len(sig), "entry_dates": int(sig.effective_date.nunique())}


def power_analysis() -> None:
    eff = test_period_effect()
    hold = holdout_count()
    scale_dates = np.sqrt(eff["clusters"] / hold["entry_dates"])
    scale_events = np.sqrt(eff["n"] / hold["events"])
    rows = []
    for basis, k in (("entry dates (clusters)", scale_dates), ("events", scale_events)):
        se_h = eff["se"] * k
        for label, b in (("test-period slope", eff["slope"]), ("half the test-period slope", eff["slope"] / 2)):
            rows.append({"se_scaling": basis, "assumed_slope": label, "slope_bps": b,
                         "expected_se_bps": se_h, "power": power(b, se_h)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False)
    print(f"test period: slope {eff['slope']:+.2f} bps per unit |strength|, SE {eff['se']:.2f}, "
          f"t {eff['t']:+.2f}, N {eff['n']:,}, entry dates {eff['clusters']}")
    print(f"holdout (count only): {hold['events']:,} LLM events on {hold['entry_dates']} entry dates")
    print(df.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    log = OUTPUTS / "test_period_runs.csv"
    pd.DataFrame([{"timestamp": datetime.now().isoformat(timespec="seconds"),
                   "script": "src/h3.py --power", "scorers": "llm_anon",
                   "period": "2024-04-30 .. 2026-06-01",
                   "what": "H3 power planning: slope of day-3 mkt-adj return on |strength| (diagnostic, no decision)",
                   "output": OUT.name}]).to_csv(log, mode="a", index=False, header=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--power", action="store_true")
    if ap.parse_args().power:
        power_analysis()
