"""
cost_ladder.py -- Phase 4: the cost ladder (ladder note of 24 Oct 2026,
section d; rung-3 notes of 25 Oct 2026). One row per rung: 0 keyword,
1 Llama 3.2 3B, 1b MiniLM embeddings, 2 Claude Haiku 5.5, 3 Claude Sonnet 5.5.
Assembled from existing outputs (no strategy is rerun); keyword compute time
and latency are measured here (free, local).

Also the DESCRIPTIVE rung comparisons (added after the results, not
pre-registered): Sharpe difference of strategy A Kelly between adjacent rungs
(Jobson-Korkie-Memmel, test period) and the difference in the test-period
news-day event-study mean between adjacent rungs (stacked regression, SE
clustered by entry date; per-rung means checked against the official files).

USAGE (from the project root):  python3 src/cost_ladder.py
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from paths import DATA, OUTPUTS, NEWS_CLEAN
from newsdrift import Config, KeywordScorer, PrecomputedScorer
from newsdrift.stats import sharpe_diff_test
from run_both_strategies import _naive_returns
from momentum_continuous import read_curve
from calibrate_scorer import build_features, TRAIN_END, DATA_END
import event_study as es

TAG = "2026-10-25"
OUT = OUTPUTS / f"cost_ladder_{TAG}.csv"
OUT_CMP = OUTPUTS / f"rung_comparisons_{TAG}.csv"
GATE = 0.20
O = OUTPUTS
RUNGS = [  # rung, label, score file (incl. test), event-study files (train, test), speed-bound file
    ("0", "keyword", None, ("event_study_train_keyword+llm_anon_2026-10-18_bug11fix.csv", "event_study_test_keyword+llm_anon_2026-10-18.csv"), "speed_bound_test_2026-10-24.csv"),
    ("1", "llm_anon", "news_scored_llm_ollama_anon_incl_test.csv", ("event_study_train_keyword+llm_anon_2026-10-18_bug11fix.csv", "event_study_test_keyword+llm_anon_2026-10-18.csv"), "speed_bound_test_2026-10-24.csv"),
    ("1b", "embed_minilm", "news_scored_embed_minilm_incl_test.csv", ("event_study_train_embed_minilm_2026-10-24.csv", "event_study_test_embed_minilm_2026-10-24.csv"), "speed_bound_test_2026-10-24.csv"),
    ("2", "haiku", "news_scored_haiku_anon_incl_test.csv", ("event_study_train_haiku_2026-10-25.csv", "event_study_test_haiku_2026-10-25.csv"), "speed_bound_test_2026-10-25.csv"),
    ("3", "sonnet", "news_scored_sonnet_anon_incl_test.csv", ("event_study_train_sonnet_2026-10-25.csv", "event_study_test_sonnet_2026-10-25.csv"), "speed_bound_test_2026-10-25_sonnet.csv"),
]
LOOKAHEAD = {"keyword": "none (dictionary)",
             "llm_anon": "test clean (Llama 3.2 cutoff Dec 2023); training exposed",
             "embed_minilm": "test clean (MiniLM pre-2022); ridge fitted on 2016-2021 returns (training in-sample)",
             "haiku": "EXPOSED TO LOOK-AHEAD (whole sample)", "sonnet": "EXPOSED TO LOOK-AHEAD (whole sample)"}
N_TRIALS = {"keyword": 139, "llm_anon": 139, "embed_minilm": 155, "haiku": 155, "sonnet": "161 (A/B), 163 (C)"}
A_KELLY_OOS = {"keyword": "correction_bug14fix_2026-10-24/keyword/equity_A_daily_1-3d_kelly_OOS.csv",
               "llm_anon": "correction_bug14fix_2026-10-24/llm/equity_A_daily_1-3d_kelly_llm_OOS.csv",
               "embed_minilm": "correction_bug14fix_2026-10-24/embed_minilm/equity_A_daily_1-3d_kelly_llm_OOS.csv",
               "haiku": "rung2_2026-10-25/equity_A_daily_1-3d_kelly_llm_OOS.csv",
               "sonnet": "rung3_2026-10-25/equity_A_daily_1-3d_kelly_llm_OOS.csv"}
KW: tuple = ()


def keyword_timing() -> tuple[float, float, float]:
    """(seconds per 1,000 headlines, median latency ms, gate share over all clean rows)."""
    nw = pd.read_csv(NEWS_CLEAN, usecols=["ticker", "headline"])
    kw = KeywordScorer(Config().signal)
    t0 = time.perf_counter()
    s = np.array([kw.score(h, t)[0] for h, t in zip(nw.headline.astype(str), nw.ticker)])
    per_1000 = (time.perf_counter() - t0) / len(nw) * 1000
    lat = []
    for h, t in zip(nw.headline.astype(str).head(200), nw.ticker.head(200)):
        t1 = time.perf_counter()
        kw.score(h, t)
        lat.append((time.perf_counter() - t1) * 1000)
    return per_1000, float(np.median(lat)), float((np.abs(s) >= GATE).mean())


def event_cells(files, label: str) -> dict:
    out = {}
    for period, f in zip(("train", "test"), files):
        e = pd.read_csv(O / f)
        e = e[(e.scorer == label) & (e.split == "all events") & (e.adj == "mkt")].set_index("day")
        out[f"events_{period}"] = int(e.N.max())
        if period == "test":
            for d in (0, 1, 3, 5):
                out[f"test_day{d}_bps"], out[f"test_day{d}_t"] = e.loc[d, "mean_bps"], e.loc[d, "t_clustered"]
    return out


def speed_cell(f, label: str) -> dict:
    s = pd.read_csv(O / f)
    s = s[s.rung == label]
    b = s.loc[s.mean_bps.idxmax()]
    return {"speed_bound_best_bps": b.mean_bps, "speed_bound_best_t": b.t_clustered, "speed_bound_horizon": b.horizon,
            "speed_bound_period": "test"}


def strategy_candidates(label: str) -> pd.DataFrame:
    """Test-period rows (A, B, C; fixed and Kelly) with continuous-momentum comparisons."""
    tag = {"llm_anon": "llm"}.get(label, label)
    if label in ("keyword", "llm_anon", "embed_minilm"):
        res = pd.read_csv(O / f"results_both_strategies_{tag}_calibrated_bug14fix_2026-10-24.csv", index_col=0)
        cmp = pd.read_csv(O / "comparison_vs_continuous_momentum_2026-10-24.csv")
        cmp = cmp[(cmp.rung == tag) & (cmp.period == "OOS")].set_index("strategy")
        ab = pd.DataFrame({"strategy": cmp.index, "return_pa": res.loc[cmp.index, "OOS_return_pa"].to_numpy(),
                           "sharpe": res.loc[cmp.index, "OOS_sharpe"].to_numpy(), "DSR": res.loc[cmp.index, "OOS_DSR"].to_numpy(),
                           "sr_diff_vs_momentum": cmp.sr_diff.to_numpy(), "p_vs_momentum": cmp.p.to_numpy()})
        c = pd.read_csv(O / "c_minute_summary_2026-10-24.csv")
        c = c[(c.rung == tag) & (c.period == "OOS") & c.return_pa.notna()]
    else:
        s = pd.read_csv(O / f"{'rung2' if label == 'haiku' else 'rung3'}_summary_{TAG}.csv")
        ab = s[(s.period == "OOS") & s.return_pa.notna()]
        c = pd.read_csv(O / f"c_minute_rungs2_3_summary_{TAG}.csv")
        c = c[(c.rung == label) & (c.period == "OOS") & c.return_pa.notna()]
    cols = ["strategy", "return_pa", "sharpe", "DSR", "sr_diff_vs_momentum", "p_vs_momentum"]
    return pd.concat([ab[cols], c[cols]], ignore_index=True)


def gate_share(score_file: str) -> float:
    s = pd.read_csv(DATA / score_file, usecols=["strength"]).strength
    return float((s.abs() >= GATE).mean())


def running_costs(label: str) -> dict:
    if label in ("haiku", "sonnet"):
        u = json.load(open(O / f"{'rung2_haiku' if label == 'haiku' else 'rung3_sonnet'}_usage_{TAG}.json"))
        x = json.load(open(O / f"{'rung2' if label == 'haiku' else 'rung3'}_extras_{TAG}.json"))
        wall = (pd.Timestamp(u["finished"]) - pd.Timestamp(u["started"])).total_seconds()
        mem = x["memorisation"]
        return {"compute_s_per_1000": wall / u["requests"] * 1000, "compute_note": "batch wall clock incl. queue",
                "api_usd_per_1000": u["cost_usd"] / u["requests"] * 1000,
                "api_usd_total": u["cost_usd"] + x["extras_cost_usd"], "median_latency_ms": x["latency"]["median_latency_ms"],
                "memorisation": f"corr {mem['strength_corr']:.2f}, sign agreement {mem['sign_agreement']:.0%}, "
                                f"mean |change| {mem['mean_abs_change']:.3f}"}
    if label == "embed_minilm":
        m = json.load(open(O / "rung1b_model_2026-10-24.json"))
        return {"compute_s_per_1000": m["compute_s_per_1000_headlines"], "compute_note": "local CPU",
                "api_usd_per_1000": 0.0, "api_usd_total": 0.0, "median_latency_ms": m["median_latency_ms_single_headline"],
                "memorisation": "n/a"}
    if label == "llm_anon":
        lat = json.load(open(O / "rung1_llama_latency_2026-10-25.json"))   # 200 real-time calls, 25 Oct
        return {"compute_s_per_1000": lat["seconds_per_1000_sequential"],
                "compute_note": "measured: mean latency x 1,000 (sequential, local Ollama); Aug 2026 full run ~42 h incl. outages",
                "api_usd_per_1000": 0.0, "api_usd_total": 0.0, "median_latency_ms": lat["median_latency_ms"],
                "memorisation": "reference (not paid): named vs anonymised corr 0.71, 13.3% sign flips (training)"}
    per_1000, lat, _ = KW
    return {"compute_s_per_1000": per_1000, "compute_note": "local CPU", "api_usd_per_1000": 0.0, "api_usd_total": 0.0,
            "median_latency_ms": lat, "memorisation": "n/a"}


def ladder() -> pd.DataFrame:
    rows = []
    for rung, label, score, es_files, sb_file in RUNGS:
        cand = strategy_candidates(label)
        best = cand.loc[cand.sharpe.idxmax()]
        rows.append({"rung": rung, "scorer": label, "data_cost_usd": 0.0, **running_costs(label),
                     "latency_note": "",
                     "gate_share": KW[2] if label == "keyword" else gate_share(score),
                     "gate_share_basis": "all clean news rows" if label == "keyword" else "rows in the rung's score file (Tier-0 set)",
                     **event_cells(es_files, label), **speed_cell(sb_file, label),
                     "best_strategy_test": best.strategy, "best_return_pa": best.return_pa, "best_sharpe": best.sharpe,
                     "best_sr_diff_vs_cont_momentum": best.sr_diff_vs_momentum, "best_p_vs_momentum": best.p_vs_momentum,
                     "best_DSR": best.DSR, "dsr_trials_N": N_TRIALS[label],
                     "best_selection_note": "highest test Sharpe among A/B/C x fixed/Kelly (chosen ex post)",
                     "look_ahead": LOOKAHEAD[label]})
    return pd.DataFrame(rows)


def test_events(score_file: str | None) -> pd.DataFrame:
    px, nw, first = es.load_test()
    cfg = Config()
    scorer = KeywordScorer(cfg.signal) if score_file is None else PrecomputedScorer(str(DATA / score_file))
    td = pd.DatetimeIndex(sorted(px.date.unique()))
    sig = build_features(nw, scorer, cfg, td, None)
    ndx = es.load_ndx(TRAIN_END - es.PRE_TEST_PRICE_DAYS, DATA_END)
    return es.event_returns(px, ndx, sig[sig.effective_date >= first])


def clustered_diff(a: pd.DataFrame, b: pd.DataFrame) -> dict:
    """mean(b) - mean(a) of news-day returns, CR1 SE clustered by entry date."""
    d = pd.concat([a.assign(x=0.0), b.assign(x=1.0)]).dropna(subset=["mkt_0"]).reset_index(drop=True)
    X = np.column_stack([np.ones(len(d)), d.x.to_numpy()])
    y = d.mkt_0.to_numpy()
    bread = np.linalg.inv(X.T @ X)
    beta = bread @ X.T @ y
    u = y - X @ beta
    score = pd.DataFrame(X * u[:, None]).groupby(d.effective_date.to_numpy()).sum().to_numpy()
    G, n = len(score), len(d)
    V = bread @ (score.T @ score) @ bread * G / (G - 1) * (n - 1) / (n - 2)
    se = float(np.sqrt(V[1, 1]))
    return {"diff_bps": float(beta[1]), "se_bps": se, "t": float(beta[1] / se), "clusters": G}


def comparisons(lad: pd.DataFrame) -> pd.DataFrame:
    rows, events = [], {}
    for rung, label, score, *_ in RUNGS:
        ev = test_events(score)
        ref = lad.set_index("scorer").loc[label]
        assert np.isclose(ev.mkt_0.mean(), ref.test_day0_bps, atol=1e-6), f"{label}: news-day mean differs from the official file"
        events[label] = ev
        print(f"  {label}: test news-day mean reproduces the official event study ({ev.mkt_0.mean():+.1f} bps)")
    for (r0, a, *_), (r1, b, *_) in zip(RUNGS[:-1], RUNGS[1:]):
        jk = sharpe_diff_test(_naive_returns(read_curve(O / A_KELLY_OOS[b])), _naive_returns(read_curve(O / A_KELLY_OOS[a])))
        nd = clustered_diff(events[a], events[b])
        rows.append({"comparison": f"rung {r1} ({b}) minus rung {r0} ({a})", "kind": "DESCRIPTIVE, not pre-registered",
                     "A_kelly_test_sr_diff": jk["sr_diff"], "A_kelly_test_se": jk["se"], "A_kelly_test_p": jk["p"],
                     "news_day_test_diff_bps": nd["diff_bps"], "news_day_test_se_bps": nd["se_bps"],
                     "news_day_test_t": nd["t"], "news_day_clusters": nd["clusters"]})
    return pd.DataFrame(rows)


def main():
    global KW
    KW = keyword_timing()
    lad = ladder()
    lad.to_csv(OUT, index=False)
    print(lad.T.to_string())
    cmp = comparisons(lad)
    cmp.to_csv(OUT_CMP, index=False)
    print(cmp.to_string(index=False, float_format=lambda v: f"{v:.3f}"))


if __name__ == "__main__":
    main()
