"""
sweep_strategy_b.py -- compare Strategy B entry/exit variants IN-SAMPLE ONLY.

The out-of-sample period is never touched here (CLAUDE.md hard rule 3).
Pick a configuration from these numbers, write it down, and only then run
run_both_strategies.py with it once to see out-of-sample.

Sizer is fixed-fractional throughout so the comparison isolates the
entry/exit logic (Kelly vs fixed is a separate experiment).

USAGE (from the project root):
  python3 src/sweep_strategy_b.py
  python3 src/sweep_strategy_b.py --llm-scores data_sources/news_scored_llm_ollama.csv
"""
from __future__ import annotations
import argparse

import pandas as pd

from paths import PRICES, NEWS_CLEAN, BARS, OUTPUTS
from newsdrift import build_event_table, performance_metrics
from newsdrift.intraday import IntradayBacktest, IntradayConfig
from run_both_strategies import load_inputs, load_bars, market_hours_events

HALF_AT_1R = dict(partial_exit_r=1.0, partial_exit_frac=0.5)
TRAIL_1R = dict(HALF_AT_1R, trail_r=1.0)
WIDE_STOP = dict(TRAIL_1R, stop_vol_mult=5.0)

VARIANTS = {
    "t+5  2R target (current)": dict(entry_latency_min=5),
    "t+15 2R target (current)": dict(entry_latency_min=15),
    "t+30 2R target": dict(entry_latency_min=30),
    "t+60 2R target": dict(entry_latency_min=60),
    "t+15 half@1R, runner to close": dict(entry_latency_min=15, **HALF_AT_1R),
    "t+30 half@1R, runner to close": dict(entry_latency_min=30, **HALF_AT_1R),
    "t+60 half@1R, runner to close": dict(entry_latency_min=60, **HALF_AT_1R),
    "t+15 half@1R, trail 1R": dict(entry_latency_min=15, **TRAIL_1R),
    "t+30 half@1R, trail 1R": dict(entry_latency_min=30, **TRAIL_1R),
    "t+60 half@1R, trail 1R": dict(entry_latency_min=60, **TRAIL_1R),
    "t+15 stop 5x, half@1R, trail 1R": dict(entry_latency_min=15, **WIDE_STOP),
    "t+30 stop 5x, half@1R, trail 1R": dict(entry_latency_min=30, **WIDE_STOP),
    "t+60 stop 5x, half@1R, trail 1R": dict(entry_latency_min=60, **WIDE_STOP),
}


def summarize_variant(name: str, eq: pd.Series, tr: pd.DataFrame) -> dict:
    m = performance_metrics(eq, tr)
    return {"variant": name, "return_pa": m["ann_return"], "sharpe": m["sharpe"],
            "maxDD": m["max_drawdown"], "trades": len(tr),
            "hit_rate": m["hit_rate"], "mean_R": tr.r_multiple.mean(),
            "stop_outs": (tr["reason"] == "stop").mean() if "reason" in tr else float("nan"),
            "partials": tr["partial_hit"].mean() if "partial_hit" in tr else float("nan")}


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

    cfg, _, nw, scorer, _, P = load_inputs(args)
    bars = load_bars(args.bars)
    ev = market_hours_events(build_event_table(nw, scorer, cfg.signal), bars)

    lo = pd.Timestamp(P["IS"][0], tz="UTC")
    hi = pd.Timestamp(P["IS"][1], tz="UTC") + pd.Timedelta(days=1)
    ev_is = ev[(ev.news_ts >= lo) & (ev.news_ts <= hi)]
    bars_is = bars[(bars.ts >= lo) & (bars.ts <= hi)]
    assert bars_is.ts.max() <= hi, "OOS bars leaked into the in-sample sweep"
    print(f"\nIN-SAMPLE ONLY {P['IS'][0].date()} -> {P['IS'][1].date()} | "
          f"{len(ev_is):,} events | {len(VARIANTS)} variants\n")

    rows = []
    for name, overrides in VARIANTS.items():
        icfg = IntradayConfig(sizer="fixed", cost_base_bps=cfg.cost.per_side_bps,
                              **overrides)
        eq, tr = IntradayBacktest(bars_is, ev_is, icfg).run()
        if tr.empty:
            print(f"  {name:<34} no trades")
            continue
        rows.append(summarize_variant(name, eq, tr))
        r = rows[-1]
        print(f"  {name:<34} {r['return_pa']:+7.1%}  Sharpe {r['sharpe']:+.2f}  "
              f"maxDD {r['maxDD']:5.1%}  trades {r['trades']:>5,}  "
              f"mean R {r['mean_R']:+.3f}")

    df = pd.DataFrame(rows).set_index("variant")
    scorer_name = "llm" if args.llm_scores else "keyword"
    out = OUTPUTS / f"sweep_strategy_b_{scorer_name}.csv"
    df.to_csv(out)
    print(f"\nsaved {out}  ({len(df)} variants tried -- report this count)")


if __name__ == "__main__":
    main()
