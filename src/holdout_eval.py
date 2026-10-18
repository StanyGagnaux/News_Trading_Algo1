"""
holdout_eval.py -- the single holdout evaluation of H1, H2 and H3
(FROZEN_CONFIG_2026-10-18 + dated notes; Bloomberg-prices note of 18 Oct 2026).

Prices: Bloomberg prices.csv (ends 2026-07-14) through event_study.load_window,
the same loader and event-study code as the official test-period run. Only
the date window differs. Yahoo is not used.

Event set: daily gated signals (frozen event-study spec) from holdout news
dated 2026-06-02 .. LAST_NEWS_DATE, the last news date whose full day-5
window (entry open -> close of day 5) ends on or before 2026-07-14 on the
prices.csv trading calendar. Complete cases only: an event enters every
horizon (day 0, 1, 2, 3, 5) or none, so all horizons share one event set.

  H1 (Holm, 8 cells = keyword/LLM x day 1,2,3,5): p = Phi((mean - 4.86)/se),
     date-clustered se; a cell "holds" (no tradable drift) if its Holm-adjusted
     p <= 0.05; otherwise it is inconclusive.
  H2: keyword corporate_event, day 3: t = mean/se < -1.645 (one-sided 5%).
  H3: LLM, slope of day-3 return on |strength|, CR1 date-clustered, t > 1.645.

USAGE (from the project root):
  python3 src/holdout_eval.py --counts     # Phase 1: counts + power, no returns
  python3 src/holdout_eval.py --validate   # code check on a TRAINING window
  python3 src/holdout_eval.py --run        # Phase 2: THE single holdout run
"""
from __future__ import annotations

import argparse
import math
from datetime import datetime
from statistics import NormalDist

import numpy as np
import pandas as pd

from paths import DATA, NEWS_CLEAN, OUTPUTS
from newsdrift import Config, KeywordScorer, PrecomputedScorer
from calibrate_scorer import build_features
import event_study as es
from h3 import h3_decision, Z_95

COST_BPS = es.ROUND_TRIP_BPS                       # 4.86
HORIZONS = [1, 2, 3, 5]
CASE_COLS = [f"{a}_{k}" for a in ("raw", "mkt") for k in [0] + HORIZONS]
H1_ALPHA = 0.05
HOLDOUT_NEWS = DATA / "holdout" / "news_holdout_clean.csv"
HOLDOUT_LLM = DATA / "holdout" / "news_scored_llm_ollama_anon_holdout.csv"
HOLDOUT = {"news": HOLDOUT_NEWS, "llm": HOLDOUT_LLM,
           "news_start": pd.Timestamp("2026-06-02"), "price_end": pd.Timestamp("2026-07-14")}
TRAIN_CHECK = {"news": NEWS_CLEAN, "llm": DATA / "news_scored_llm_ollama_anon.csv",
               "news_start": pd.Timestamp("2023-06-02"), "price_end": pd.Timestamp("2023-07-14")}
PRICE_LEAD = pd.Timedelta(days=30)                 # prior bars for the day-0 return


def last_news_date(td: pd.DatetimeIndex, price_end: pd.Timestamp, last_day: int = 5) -> pd.Timestamp:
    """Latest news date whose entry day + (last_day - 1) trading days <= price_end.
    Entry = first trading day strictly after the news date (frozen spec)."""
    td = pd.DatetimeIndex(sorted(td.unique()))
    assert price_end in td, "price_end must be a trading day of the calendar"
    last_entry = td[td.get_loc(price_end) - (last_day - 1)]
    return last_entry - pd.Timedelta(days=1)


def cluster_mean_se(y: pd.Series, g: pd.Series) -> tuple[float, float, int]:
    """Mean and date-clustered SE (same formula as event_study.clustered_mean)."""
    ok = y.notna()
    yv, gv = y[ok].to_numpy(float), g[ok].to_numpy()
    n = len(yv)
    m = yv.mean()
    sums = pd.Series(yv - m).groupby(gv).sum().to_numpy()
    k = len(sums)
    return m, math.sqrt(k / (k - 1) * (sums ** 2).sum() / n ** 2), n


def load(window: dict):
    px, _ = es.load_window(window["news"], window["news_start"] - PRICE_LEAD, window["price_end"],
                           window["news_start"], window["price_end"])
    td = pd.DatetimeIndex(sorted(px.date.unique()))
    end = last_news_date(td, window["price_end"])
    px, nw = es.load_window(window["news"], window["news_start"] - PRICE_LEAD, window["price_end"],
                            window["news_start"], end)
    return px, nw, td, end


def signals(nw, td, window: dict) -> dict:
    cfg = Config()
    llm = pd.read_csv(window["llm"])
    imp = dict(zip(zip(llm.headline, llm.ticker), llm.importance))
    return {"keyword": build_features(nw, KeywordScorer(cfg.signal), cfg, td, None),
            "llm_anon": build_features(nw, PrecomputedScorer(str(window["llm"])), cfg, td, imp)}


def complete_by_dates(px, sig) -> pd.Series:
    """Phase 1 availability (dates only, no prices): bars exist for day 0 and day 5."""
    pos = {t: pd.DatetimeIndex(g.date.sort_values()) for t, g in px.groupby("ticker")}
    ok = []
    for r in sig.itertuples(index=False):
        d = pos.get(r.ticker)
        i = d.get_indexer([r.effective_date])[0] if d is not None else -1
        ok.append(bool(d is not None and i >= 2 and i + 4 < len(d)))
    return pd.Series(ok, index=sig.index)


def holm(p: np.ndarray) -> np.ndarray:
    order, m, run = np.argsort(p), len(p), 0.0
    adj = np.empty(m)
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (m - rank) * p[i]))
        adj[i] = run
    return adj


def evaluate(window: dict) -> pd.DataFrame:
    px, nw, td, end = load(window)
    ndx = es.load_ndx(window["news_start"] - PRICE_LEAD, window["price_end"])
    ev = {k: es.event_returns(px, ndx, s).dropna(subset=CASE_COLS)
          for k, s in signals(nw, td, window).items()}
    rows = []
    for scorer, e in ev.items():
        for k in HORIZONS:
            m, se, n = cluster_mean_se(e[f"mkt_{k}"], e.effective_date)
            m_ref, t_ref, _ = es.clustered_mean(e[f"mkt_{k}"], e.effective_date)
            assert np.isclose(m, m_ref) and np.isclose(m / se, t_ref), "SE helper disagrees with event_study"
            rows.append({"test": "H1", "scorer": scorer, "day": k, "mean_bps": m, "se": se, "n": n,
                         "upper_95": m + Z_95 * se, "p": NormalDist().cdf((m - COST_BPS) / se)})
    h1 = pd.DataFrame(rows)
    h1["p_holm"] = holm(h1.p.to_numpy())
    h1["result"] = np.where(h1.p_holm <= H1_ALPHA, "holds: no tradable drift", "inconclusive")
    corp = ev["keyword"][ev["keyword"].category == "corporate_event"]
    m, se, n = cluster_mean_se(corp.mkt_3, corp.effective_date)
    h2 = {"test": "H2", "scorer": "keyword", "day": 3, "mean_bps": m, "se": se, "n": n, "t": m / se,
          "result": "supported" if m / se < -Z_95 else "not supported"}
    d3 = h3_decision(ev["llm_anon"])
    h3 = {"test": "H3", "scorer": "llm_anon", "day": 3, "slope_bps": d3["slope"], "se": d3["se"],
          "t": d3["t"], "n": d3["n"], "result": "supported" if d3["reject_H0_one_sided_5pct"] else "not supported"}
    out = pd.concat([h1, pd.DataFrame([h2, h3])], ignore_index=True).assign(
        window=f"news {window['news_start'].date()}..{end.date()}, prices to {window['price_end'].date()}")
    print(out.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    return out


def power_rows(label, eff_se, n_test, g_test, n_h, g_h, direction, threshold, alpha, truths):
    """direction=-1: reject if estimate < threshold; +1: reject if > threshold."""
    z = NormalDist().inv_cdf(1 - alpha)
    out = []
    for basis, k in (("events", math.sqrt(n_test / n_h)), ("entry dates", math.sqrt(g_test / g_h))):
        se_h = eff_se * k
        for assume, mu in truths:
            gap = (threshold - mu) if direction < 0 else (mu - threshold)
            out.append({"test": label, "se_basis": basis, "assumed_true": assume, "assumed_value": mu,
                        "alpha": alpha, "expected_se": se_h, "power": NormalDist().cdf(gap / se_h - z)})
    return out


def test_entry_dates() -> dict:
    """Entry dates of the TEST-period event sets (signal tables only, no returns)."""
    px, nw, first = es.load_test()
    td = pd.DatetimeIndex(sorted(px.date.unique()))
    s = {k: v[v.effective_date >= first] for k, v in signals(nw, td, {"llm": es.LLM_ANON_INCL_TEST}).items()}
    corp = s["keyword"][s["keyword"].category == "corporate_event"]
    return {"keyword": s["keyword"].effective_date.nunique(), "llm_anon": s["llm_anon"].effective_date.nunique(),
            "corp": corp.effective_date.nunique()}


def test_power(counts: dict) -> pd.DataFrame:
    tab = pd.read_csv(OUTPUTS / "event_study_test_keyword+llm_anon_2026-10-18.csv")
    g_test = test_entry_dates()
    rows = []
    for scorer in ("keyword", "llm_anon"):
        for k in HORIZONS:
            r = tab[(tab.scorer == scorer) & (tab.split == "all events") & (tab.adj == "mkt") & (tab.day == k)].iloc[0]
            for a in (H1_ALPHA / 8, H1_ALPHA):
                rows += power_rows(f"H1 {scorer} day {k}", r.mean_bps / r.t_clustered, r.N, g_test[scorer],
                                   *counts[scorer], -1, COST_BPS, a,
                                   [("test-period mean", r.mean_bps), ("true mean 0", 0.0)])
    c = tab[(tab.scorer == "keyword") & (tab.split == "news category") & (tab.group == "corporate_event")
            & (tab.adj == "mkt") & (tab.day == 3)].iloc[0]
    rows += power_rows("H2 keyword corporate_event day 3", c.mean_bps / c.t_clustered, c.N, g_test["corp"],
                       *counts["corp"], -1, 0.0, 0.05,
                       [("test-period mean", c.mean_bps), ("half of it", c.mean_bps / 2)])
    rows += power_rows("H3 LLM slope day 3", 67.55, 10_139, g_test["llm_anon"], *counts["llm_anon"],
                       +1, 0.0, 0.05, [("test-period slope", 120.96), ("half of it", 60.48)])
    df = pd.DataFrame(rows)
    df.to_csv(OUTPUTS / "holdout_power_2026-10-18.csv", index=False)
    print("test-period entry dates:", g_test)
    print(df[df.se_basis == "entry dates"].to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    return df


def counts_and_power() -> None:
    px, nw, td, end = load(HOLDOUT)
    sig = signals(nw, td, HOLDOUT)
    d = pd.to_datetime(pd.read_csv(HOLDOUT_NEWS, usecols=["timestamp"]).timestamp, utc=True)
    d = d.dt.tz_localize(None).dt.normalize()
    entry = td[td.searchsorted(end + pd.Timedelta(days=1))]
    print(f"LAST NEWS DATE {end.date()} -> entry {entry.date()} -> day-5 close {HOLDOUT['price_end'].date()}")
    print(f"holdout news rows {len(d):,}: in window {((d >= HOLDOUT['news_start']) & (d <= end)).sum():,}; "
          f"EXCLUDED after {end.date()}: {(d > end).sum():,}; before {HOLDOUT['news_start'].date()}: "
          f"{(d < HOLDOUT['news_start']).sum():,}")
    counts = {}
    for k, s in sig.items():
        ok = complete_by_dates(px, s)
        counts[k] = (int(ok.sum()), int(s.effective_date[ok].nunique()))
        print(f"  {k}: {len(s):,} events, {ok.sum():,} complete (bars for day 0..5), {counts[k][1]} entry dates")
        if k == "keyword":
            c = s[ok & (s.category == "corporate_event")]
            counts["corp"] = (len(c), int(c.effective_date.nunique()))
            print(f"  keyword corporate_event: {len(c):,} complete events on {counts['corp'][1]} entry dates")
    test_power(counts)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--counts", action="store_true")
    g.add_argument("--validate", action="store_true")
    g.add_argument("--run", action="store_true")
    a = ap.parse_args()
    if a.counts:
        counts_and_power()
    elif a.validate:
        out = evaluate(TRAIN_CHECK)
        (OUTPUTS / "validation_2026-10-18").mkdir(exist_ok=True)
        out.to_csv(OUTPUTS / "validation_2026-10-18" / "holdout_eval_on_training_window.csv", index=False)
    else:
        stamp = datetime.now().strftime("%Y-%m-%d")
        out = evaluate(HOLDOUT)
        out.to_csv(OUTPUTS / f"holdout_results_{stamp}.csv", index=False)
        pd.DataFrame([{"timestamp": datetime.now().isoformat(timespec="seconds"),
                       "script": "src/holdout_eval.py --run (Bloomberg-prices note, 18 Oct 2026)",
                       "what": "THE single holdout evaluation: H1, H2, H3",
                       "output": f"holdout_results_{stamp}.csv"}]).to_csv(
            OUTPUTS / "holdout_runs.csv", mode="a", index=False, header=False)


if __name__ == "__main__":
    main()
