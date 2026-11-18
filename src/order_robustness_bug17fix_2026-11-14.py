"""
order_robustness_bug17fix_2026-11-14.py -- signal-order robustness check on the
Bug 17 engine, TRAINING PERIOD ONLY, descriptive. Dated copy of
order_robustness.py (19 Oct 2026), which is left as it is and is not run.

For every strategy and scorer of the October check (A, B t+5, B t+15, C; fixed
and Kelly; keyword and Llama) and for keyword D: the deterministic result and
20 random orderings of same-day signals (`tie_rank`, seed 20261019 + k as in
October). The standard deviation of the training Sharpe ratio over the
orderings is the order noise of a row.

Differences to the October script, and nothing else:
  * Strategy A scales: outputs/summary/risk_calibration_<rung>_bug17fix_2026-11-14.csv
    (the scales of the Bug 17 correction run).
  * Strategies B, C, D: the 18 October scale files the October check read
    (outputs/risk_calibration_{keyword,llm}.csv; SHA-256 pinned below), so
    that these rows are comparable with the October file. B and C here are the
    engines as they stand today (B with the Bug 14 fill rule of 24 Oct; C is
    the daily-bar engine that Bug 13 invalidated, kept for comparison only).
  * Output: outputs/summary/order_robustness_bug17fix_2026-11-14.csv, never
    overwritten; one added column, `risk_scale`.

USAGE (from the project root):  python3 src/order_robustness_bug17fix_2026-11-14.py
"""
from __future__ import annotations

import argparse
import hashlib
from argparse import Namespace
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from paths import ROOT, PRICES, NEWS_CLEAN, BARS, OUTPUTS, DATA
from run_both_strategies import load_inputs, load_bars, market_hours_events, load_risk_scales
from newsdrift import (NewsDriftBacktest, build_signal_table, build_event_table,
                       performance_metrics, slice_period, replay)
from newsdrift.intraday import IntradayBacktest, IntradayConfig
from newsdrift.strategy_c import StrategyCBacktest, StrategyCConfig
from newsdrift.open_close import OpenCloseBacktest, OpenCloseConfig

N_ORDERS = 20
SEED = 20261019                                   # as in October
TAG = "bug17fix_2026-11-14"
SUMMARY_DIR = ROOT / "outputs" / "summary"
LLM_TRAIN = DATA / "news_scored_llm_ollama_anon.csv"
OUT = SUMMARY_DIR / f"order_robustness_{TAG}.csv"
STRATEGY_A = "A_daily_1-3d"
OCTOBER_SCALES_SHA256 = {                         # the files the check of 19 Oct read (B, C here)
    "keyword": "da42a1ff2a05e6ff1c6ba0f87d97762e7525a385a0330992441b8631daf5db5b",
    "llm": "131665fe5794ba209e986d4cc64dbf495bb7c673539fa942ae8b2ed35b02e285"}


def metrics(eq, tr) -> tuple[float, float, int]:
    m = performance_metrics(eq, tr)
    return m["sharpe"], m["ann_return"], int(m.get("n_trades", 0))


def ranks(n: int, k: int) -> np.ndarray:
    return np.random.default_rng(SEED + k).permutation(n)


def scales_for(rung: str) -> dict:
    """{(strategy, sizer): scale}: A from the Bug 17 run (outputs/summary/), B and C from the 18 Oct files."""
    october_file = OUTPUTS / f"risk_calibration_{rung}.csv"
    digest = hashlib.sha256(october_file.read_bytes()).hexdigest()
    assert digest == OCTOBER_SCALES_SHA256[rung], f"{october_file.name} is not the file of 18 Oct ({digest[:8]}...)"
    october = {k: v for k, v in load_risk_scales(str(october_file)).items() if k[0] != STRATEGY_A}
    bug17 = load_risk_scales(str(SUMMARY_DIR / f"risk_calibration_{rung}_{TAG}.csv"))
    assert set(bug17) == {(STRATEGY_A, "fixed"), (STRATEGY_A, "kelly")}, f"unexpected rows in the Bug 17 scale file of {rung}"
    return {**october, **bug17}


def summary(label: str, scorer: str, det: tuple, rand: list, scale: float) -> dict:
    s = np.array([r[0] for r in rand]); ret = np.array([r[1] for r in rand])
    row = {"strategy": label, "scorer": scorer, "sharpe_deterministic": det[0],
           "sharpe_mean": s.mean(), "sharpe_sd": s.std(ddof=1), "sharpe_min": s.min(),
           "sharpe_max": s.max(), "return_deterministic": det[1], "return_min": ret.min(),
           "return_max": ret.max(), "trades_deterministic": det[2],
           "trades_min": min(r[2] for r in rand), "trades_max": max(r[2] for r in rand),
           "risk_scale": scale}
    print(f"  {label:<26}{scorer:<9} scale {scale:<7g} det {det[0]:+.4f} | 20 orders: mean {s.mean():+.4f} "
          f"sd {s.std(ddof=1):.4f} range [{s.min():+.4f}, {s.max():+.4f}] | "
          f"trades {row['trades_min']}-{row['trades_max']}", flush=True)
    return row


def strategy_a(px_is, sig_is, cfg, scale_for, scorer) -> list:
    rows = []
    for sizer in ("fixed", "kelly"):
        scale = scale_for(STRATEGY_A, sizer)
        c = replace(cfg, risk=replace(cfg.risk, risk_scale=scale))
        det = metrics(*NewsDriftBacktest(px_is, sig_is, c, sizer_kind=sizer).run())
        rand = [metrics(*NewsDriftBacktest(px_is, sig_is.assign(tie_rank=ranks(len(sig_is), k)),
                                           c, sizer_kind=sizer).run()) for k in range(N_ORDERS)]
        rows.append(summary(f"{STRATEGY_A}_{sizer}", scorer, det, rand, scale))
    return rows


def strategies_bc(px_is, bars_is, ev_is, cfg, scale_for, scorer) -> list:
    engines = [(f"B_intraday_t+{lat}min", IntradayBacktest(bars_is, ev_is, IntradayConfig(
                   entry_latency_min=lat, cost_base_bps=cfg.cost.per_side_bps)))
               for lat in (5, 15)]
    engines.append(("C_intraday_multiday", StrategyCBacktest(
        px_is, bars_is, ev_is, StrategyCConfig(exit_cost_bps=cfg.cost.per_side_bps))))
    rows = []
    for name, bt in engines:
        cand = bt.candidate_table()
        for sizer in ("fixed", "kelly"):
            scale = scale_for(name, sizer)
            rc = replace(bt.replay_config(), sizer=sizer, risk_scale=scale)
            eq, tr, _ = replay(cand, rc)
            det = metrics(eq, tr)
            rand = []
            for k in range(N_ORDERS):
                eq, tr, _ = replay(cand.assign(tie_rank=ranks(len(cand), k)), rc)
                rand.append(metrics(eq, tr))
            rows.append(summary(f"{name}_{sizer}", scorer, det, rand, scale))
    return rows


def pre_bug11_table(nw, scorer, td, scfg) -> pd.DataFrame:
    """build_signal_table WITHOUT the gate on the netted value (pre-18 Oct)."""
    t = pd.DatetimeIndex(sorted(td.unique()))
    rows = []
    for r in nw.itertuples(index=False):
        s, d = scorer.score(r.headline, r.ticker)
        if abs(s) < scfg.min_abs_strength:
            continue
        nd = pd.Timestamp(r.timestamp).normalize()
        pos = t.searchsorted(nd + pd.Timedelta(days=1)) + scfg.signal_lag_days - 1
        if pos < len(t):
            rows.append({"news_date": nd, "effective_date": t[pos], "ticker": r.ticker,
                         "strength": s, "duration": d})
    return (pd.DataFrame(rows).groupby(["effective_date", "ticker"], as_index=False)
            .agg(news_date=("news_date", "min"), strength=("strength", "mean"),
                 duration=("duration", "max")))


def keyword_d(px_is, sig_is, sig_old_is, cfg) -> list:
    oc = OpenCloseConfig(sizer="fixed", cost_bps=cfg.cost.per_side_bps)
    det = metrics(*OpenCloseBacktest(px_is, sig_is, oc).run())
    old = metrics(*OpenCloseBacktest(px_is, sig_old_is, oc).run())
    rand = [metrics(*OpenCloseBacktest(px_is, sig_is.assign(tie_rank=ranks(len(sig_is), k)), oc).run())
            for k in range(N_ORDERS)]
    row = summary("D_open_to_close_fixed", "keyword", det, rand, 1.0)
    row.update(return_pre_bug11_table=old[1], trades_pre_bug11_table=old[2])
    return [row]


def run_scorer(name: str, llm_file: str | None, bars) -> list:
    print(f"\n=== {name} ===", flush=True)
    cfg, px, nw, scorer, td, P = load_inputs(Namespace(
        prices=str(PRICES), news=str(NEWS_CLEAN), start="2016-01-01", end="2026-06-01",
        train_frac=0.80, llm_scores=llm_file, tier0=False))
    lo, hi = P["IS"]
    px_is = slice_period(px, P["IS"])
    nwn = nw.assign(timestamp=nw.timestamp.dt.tz_localize(None))
    sig = build_signal_table(nwn, scorer, td, cfg.signal)
    sig_is = sig[(sig.effective_date >= lo) & (sig.effective_date <= hi)]
    assert px_is.date.max() <= hi and sig_is.effective_date.max() <= hi, "test-period data in the robustness check"
    scales = scales_for("llm" if llm_file else "keyword")
    scale_for = lambda strat, sizer: scales.get((strat, sizer), 1.0)
    rows = strategy_a(px_is, sig_is, cfg, scale_for, name)
    lo_utc, hi_utc = pd.Timestamp(lo, tz="UTC"), pd.Timestamp(hi, tz="UTC") + pd.Timedelta(days=1)
    bars_is = bars[(bars.ts >= lo_utc) & (bars.ts <= hi_utc)]
    ev = market_hours_events(build_event_table(nw, scorer, cfg.signal), bars)
    ev_is = ev[(ev.news_ts >= lo_utc) & (ev.news_ts <= hi_utc)]
    rows += strategies_bc(px_is, bars_is, ev_is, cfg, scale_for, name)
    if llm_file is None:
        old = pre_bug11_table(nwn, scorer, td, cfg.signal)
        rows += keyword_d(px_is, sig_is, old[(old.effective_date >= lo) & (old.effective_date <= hi)], cfg)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT), help="output CSV; an existing file is never overwritten")
    out = Path(ap.parse_args().out)
    if out.exists():
        raise SystemExit(f"{out} exists -- not rerun")
    bars = load_bars(str(BARS))
    rows = run_scorer("keyword", None, bars) + run_scorer("llm", str(LLM_TRAIN), bars)
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"\nsaved {out}")


if __name__ == "__main__":
    main()
