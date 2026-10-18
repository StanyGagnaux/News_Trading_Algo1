"""
order_robustness.py -- Bug 12 robustness check, TRAINING PERIOD ONLY.

For every strategy and scorer of the frozen test run (A, B t+5, B t+15, C;
fixed and Kelly) and for keyword D: the deterministic result (19 Oct
tie-break) and 20 random orderings of tied signals (`tie_rank`), at the
18 October risk scales. The spread of Sharpe across orderings is the noise
floor of the official 18 October test results, which were produced with an
arbitrary (input) order.

Keyword D discrepancy (same 8,040 trades, different return before/after the
Bug 11 fix): D is run with the deterministic engine on the pre-Bug-11 signal
table (no gate on the netted value) and on the current table. Equal results
mean the removed rows did not matter and the old discrepancy was ordering.

USAGE (from the project root):  python3 src/order_robustness.py
"""
from __future__ import annotations

from argparse import Namespace
from dataclasses import replace

import numpy as np
import pandas as pd

from paths import PRICES, NEWS_CLEAN, BARS, OUTPUTS, DATA
from run_both_strategies import load_inputs, load_bars, market_hours_events, load_risk_scales
from newsdrift import (NewsDriftBacktest, build_signal_table, build_event_table,
                       performance_metrics, slice_period, replay)
from newsdrift.intraday import IntradayBacktest, IntradayConfig
from newsdrift.strategy_c import StrategyCBacktest, StrategyCConfig
from newsdrift.open_close import OpenCloseBacktest, OpenCloseConfig

N_ORDERS = 20
SEED = 20261019
LLM_TRAIN = DATA / "news_scored_llm_ollama_anon.csv"
OUT = OUTPUTS / "order_robustness_2026-10-19.csv"


def metrics(eq, tr) -> tuple[float, float, int]:
    m = performance_metrics(eq, tr)
    return m["sharpe"], m["ann_return"], int(m.get("n_trades", 0))


def ranks(n: int, k: int) -> np.ndarray:
    return np.random.default_rng(SEED + k).permutation(n)


def summary(label: str, scorer: str, det: tuple, rand: list) -> dict:
    s = np.array([r[0] for r in rand]); ret = np.array([r[1] for r in rand])
    row = {"strategy": label, "scorer": scorer, "sharpe_deterministic": det[0],
           "sharpe_mean": s.mean(), "sharpe_sd": s.std(ddof=1), "sharpe_min": s.min(),
           "sharpe_max": s.max(), "return_deterministic": det[1], "return_min": ret.min(),
           "return_max": ret.max(), "trades_deterministic": det[2],
           "trades_min": min(r[2] for r in rand), "trades_max": max(r[2] for r in rand)}
    print(f"  {label:<26}{scorer:<9} det {det[0]:+.2f} | 20 orders: mean {s.mean():+.2f} "
          f"sd {s.std(ddof=1):.3f} range [{s.min():+.2f}, {s.max():+.2f}] | "
          f"trades {row['trades_min']}-{row['trades_max']}", flush=True)
    return row


def strategy_a(px_is, sig_is, cfg, scale_for, scorer) -> list:
    rows = []
    for sizer in ("fixed", "kelly"):
        c = replace(cfg, risk=replace(cfg.risk, risk_scale=scale_for("A_daily_1-3d", sizer)))
        det = metrics(*NewsDriftBacktest(px_is, sig_is, c, sizer_kind=sizer).run())
        rand = [metrics(*NewsDriftBacktest(px_is, sig_is.assign(tie_rank=ranks(len(sig_is), k)),
                                           c, sizer_kind=sizer).run()) for k in range(N_ORDERS)]
        rows.append(summary(f"A_daily_1-3d_{sizer}", scorer, det, rand))
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
            rc = replace(bt.replay_config(), sizer=sizer, risk_scale=scale_for(name, sizer))
            eq, tr, _ = replay(cand, rc)
            det = metrics(eq, tr)
            rand = []
            for k in range(N_ORDERS):
                eq, tr, _ = replay(cand.assign(tie_rank=ranks(len(cand), k)), rc)
                rand.append(metrics(eq, tr))
            rows.append(summary(f"{name}_{sizer}", scorer, det, rand))
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
    print(f"  keyword D, deterministic engine: current table {det[1]:+.2%} ({det[2]} trades) | "
          f"pre-Bug-11 table {old[1]:+.2%} ({old[2]} trades)", flush=True)
    row = summary("D_open_to_close_fixed", "keyword", det, rand)
    row.update(return_pre_bug11_table=old[1], trades_pre_bug11_table=old[2])
    return [row]


def run_scorer(name: str, llm_file: str | None, bars) -> list:
    print(f"\n=== {name} ===", flush=True)
    cfg, px, nw, scorer, td, P = load_inputs(Namespace(
        prices=str(PRICES), news=str(NEWS_CLEAN), start="2016-01-01", end="2026-06-01",
        train_frac=0.80, llm_scores=llm_file, tier0=False))
    lo, hi = P["IS"]
    px_is = slice_period(px, P["IS"])
    assert px_is.date.max() <= hi, "test-period prices in the robustness check"
    nwn = nw.assign(timestamp=nw.timestamp.dt.tz_localize(None))
    sig = build_signal_table(nwn, scorer, td, cfg.signal)
    sig_is = sig[(sig.effective_date >= lo) & (sig.effective_date <= hi)]
    scales = load_risk_scales(str(OUTPUTS / f"risk_calibration_{'llm' if llm_file else 'keyword'}.csv"))
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
    bars = load_bars(str(BARS))
    rows = run_scorer("keyword", None, bars) + run_scorer("llm", str(LLM_TRAIN), bars)
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"\nsaved {OUT.name}")


if __name__ == "__main__":
    main()
