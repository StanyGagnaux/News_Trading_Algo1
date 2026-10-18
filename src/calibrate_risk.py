"""
calibrate_risk.py -- find the position scale that puts each strategy's
IN-SAMPLE max drawdown near the 5% target (CLAUDE.md section 7 DECISION).

Drawdown scales roughly with position size while Sharpe barely moves, so the
target is reached by sizing, with the "designed" throttle kept as a second
line of defence. Calibration uses the training period only; freeze the
resulting scale, then the test period shows whether 5% holds out of sample.

Strategy B is calibrated for completeness, but with negative expectancy smaller
positions only lose more slowly -- report it as an edge that does not exist,
not as a risk-control failure.

USAGE (from the project root):
  python3 src/calibrate_risk.py
  python3 src/calibrate_risk.py --llm-scores data_sources/news_scored_llm_ollama.csv
  python3 src/run_both_strategies.py --risk-scales outputs/frozen_risk_scales_<date>_keyword.csv
"""
from __future__ import annotations
import argparse
from dataclasses import replace

import pandas as pd

from paths import PRICES, NEWS_CLEAN, BARS, OUTPUTS
from newsdrift import (build_event_table, build_signal_table, slice_period,
                       NewsDriftBacktest, performance_metrics, replay)
from newsdrift.intraday import IntradayBacktest, IntradayConfig
from newsdrift.strategy_c import StrategyCBacktest, StrategyCConfig
from run_both_strategies import load_inputs, load_bars, market_hours_events

TARGET_DD = 0.05
TOLERANCE = 0.0025
MAX_ITER = 6
MAX_SCALE = 2.0


def calibrate(label: str, metrics_at) -> dict:
    """Proportional search: drawdown ~ scale, so rescale by target/actual."""
    base = metrics_at(1.0)
    scale, tried = 1.0, [(1.0, base)]
    for _ in range(MAX_ITER):
        m = tried[-1][1]
        print(f"  {label:<18} scale {scale:6.3f} -> maxDD {m['max_drawdown']:6.2%}  "
              f"return {m['ann_return']:+6.2%}  Sharpe {m['sharpe']:+.2f}")
        if m["max_drawdown"] <= 0 or abs(m["max_drawdown"] - TARGET_DD) <= TOLERANCE:
            break
        scale = min(MAX_SCALE, scale * TARGET_DD / m["max_drawdown"])
        tried.append((scale, metrics_at(scale)))
    within = [t for t in tried if t[1]["max_drawdown"] <= TARGET_DD + TOLERANCE]
    best_scale, best = max(within, key=lambda t: t[0]) if within else min(tried, key=lambda t: t[0])
    return {"risk_scale": round(best_scale, 4), "IS_maxDD": best["max_drawdown"],
            "IS_return_pa": best["ann_return"], "IS_sharpe": best["sharpe"],
            "maxDD_at_scale1": base["max_drawdown"],
            "return_at_scale1": base["ann_return"], "sharpe_at_scale1": base["sharpe"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices", default=str(PRICES))
    ap.add_argument("--news", default=str(NEWS_CLEAN))
    ap.add_argument("--bars", default=str(BARS))
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--end", default="2026-06-01")
    ap.add_argument("--train-frac", type=float, default=0.80)
    ap.add_argument("--llm-scores", default=None)
    args = ap.parse_args()

    cfg, px, nw, scorer, trading_days, P = load_inputs(args)
    px_is = slice_period(px, P["IS"])
    assert px_is.date.max() <= P["IS"][1], "OOS prices leaked into calibration"
    nw_naive = nw.assign(timestamp=nw.timestamp.dt.tz_localize(None))
    sig = build_signal_table(nw_naive, scorer, trading_days, cfg.signal)
    sig_is = sig[(sig.effective_date >= P["IS"][0]) & (sig.effective_date <= P["IS"][1])]
    print(f"\nCALIBRATING ON IN-SAMPLE ONLY {P['IS'][0].date()} -> {P['IS'][1].date()} "
          f"| target maxDD {TARGET_DD:.0%} | designed throttle on\n")

    rows = []
    for sizer in ("fixed", "kelly"):
        def a_metrics(scale, sizer=sizer):
            c = replace(cfg, risk=replace(cfg.risk, risk_scale=scale))
            eq, tr = NewsDriftBacktest(px_is, sig_is, c, sizer_kind=sizer).run()
            return performance_metrics(eq, tr)
        rows.append({"strategy": "A_daily_1-3d", "sizer": sizer,
                     **calibrate(f"A {sizer}", a_metrics)})

    bars = load_bars(args.bars)
    lo = pd.Timestamp(P["IS"][0], tz="UTC")
    hi = pd.Timestamp(P["IS"][1], tz="UTC") + pd.Timedelta(days=1)
    bars_is = bars[(bars.ts >= lo) & (bars.ts <= hi)]
    ev = market_hours_events(build_event_table(nw, scorer, cfg.signal), bars)
    ev_is = ev[(ev.news_ts >= lo) & (ev.news_ts <= hi)]
    engines = [(f"B_intraday_t+{lat}min",
                IntradayBacktest(bars_is, ev_is, IntradayConfig(
                    entry_latency_min=lat, cost_base_bps=cfg.cost.per_side_bps)))
               for lat in (5, 15)]
    engines.append(("C_intraday_multiday", StrategyCBacktest(
        px_is, bars_is, ev_is, StrategyCConfig(exit_cost_bps=cfg.cost.per_side_bps))))
    for strategy, bt in engines:
        cand = bt.candidate_table()        # simulate once; only sizing varies
        for sizer in ("fixed", "kelly"):
            rc = replace(bt.replay_config(), sizer=sizer)

            def metrics(scale, rc=rc, cand=cand):
                eq, tr, _ = replay(cand, replace(rc, risk_scale=scale))
                return performance_metrics(eq, tr)
            rows.append({"strategy": strategy, "sizer": sizer,
                         **calibrate(f"{strategy[:11]} {sizer}", metrics)})

    df = pd.DataFrame(rows)
    out = OUTPUTS / f"risk_calibration_{'llm' if args.llm_scores else 'keyword'}.csv"
    df.to_csv(out, index=False)
    print("\n" + df.to_string(index=False, formatters={
        c: "{:.2%}".format for c in df.columns if "DD" in c or "return" in c}))
    print(f"\nsaved {out}  -- freeze one scale, then: "
          f"python3 run_both_strategies.py --risk-scale <value>")


if __name__ == "__main__":
    main()
