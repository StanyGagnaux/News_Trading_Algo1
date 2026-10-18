"""
sweep_new_strategies.py -- structurally different trade logic, IN-SAMPLE ONLY
(CLAUDE.md hard rule 3). Same signals as the baselines; only the way the
trade is entered/exited changes.

  A   daily 1-3d hold (reference)
  D   next-day open -> same-day close      (first trading session only)
  N   first close after news -> next open  (first overnight gap only)
  B1  confirmation entry: t+15 only if price already moved with the signal
  B2  hold to the close: no target, wide emergency stop only
  C1  enter at the news-day close, hold 1-3 days
  C2  confirmation entry for C
  C3  C with no target, wide emergency stop, time exit only

USAGE (from the project root):
  python3 src/sweep_new_strategies.py [--llm-scores data_sources/news_scored_llm_ollama.csv]
  python3 src/sweep_new_strategies.py --daily-only     # A, D, N only (no minute bars)
"""
from __future__ import annotations
import argparse

import pandas as pd

from paths import PRICES, NEWS_CLEAN, BARS, OUTPUTS
from newsdrift import (build_event_table, build_signal_table, slice_period,
                       NewsDriftBacktest)
from newsdrift.intraday import IntradayBacktest, IntradayConfig
from newsdrift.open_close import (OpenCloseBacktest, OpenCloseConfig,
                                  OvernightBacktest)
from newsdrift.strategy_c import StrategyCBacktest, StrategyCConfig
from run_both_strategies import load_inputs, load_bars, market_hours_events
from sweep_strategy_b import summarize_variant

NO_TARGET = 1e9

B_VARIANTS = {
    "B  baseline t+15 2R (current)": dict(),
    "B1 confirmation entry": dict(confirm_move_bps=0.0),
    "B2 hold to close, emergency stop": dict(stop_vol_mult=8.0, tp_r_multiple=NO_TARGET),
}
C_VARIANTS = {
    "C  baseline t+15 2R (current)": dict(),
    "C1 enter at news-day close": dict(entry_mode="close"),
    "C2 confirmation entry": dict(confirm_move_bps=0.0),
    "C3 no target, emergency stop": dict(stop_atr_mult=4.0, tp_r_multiple=NO_TARGET),
}


def daily_runs(cfg, px_is, sig_is, ev_all_is) -> list:
    oc = OpenCloseConfig(sizer="fixed", cost_bps=cfg.cost.per_side_bps)
    return [("A  daily 1-3d hold (reference)",
             NewsDriftBacktest(px_is, sig_is, cfg, sizer_kind="fixed")),
            ("D  next-day open-to-close", OpenCloseBacktest(px_is, sig_is, oc)),
            ("N  first close after news -> next open",
             OvernightBacktest(px_is, ev_all_is, oc))]


def intraday_runs(cfg, args, px_is, ev_all_is, lo, hi) -> list:
    bars = load_bars(args.bars)
    bars_is = bars[(bars.ts >= lo) & (bars.ts <= hi)]
    assert bars_is.ts.max() <= hi, "OOS bars leaked into the in-sample sweep"
    ev_is = market_hours_events(ev_all_is, bars)
    runs = [(name, IntradayBacktest(bars_is, ev_is, IntradayConfig(
                entry_latency_min=15, sizer="fixed",
                cost_base_bps=cfg.cost.per_side_bps, **kw)))
            for name, kw in B_VARIANTS.items()]
    runs += [(name, StrategyCBacktest(px_is, bars_is, ev_is, StrategyCConfig(
                 sizer="fixed", exit_cost_bps=cfg.cost.per_side_bps, **kw)))
             for name, kw in C_VARIANTS.items()]
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices", default=str(PRICES))
    ap.add_argument("--news", default=str(NEWS_CLEAN))
    ap.add_argument("--bars", default=str(BARS))
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--end", default="2026-06-01")
    ap.add_argument("--train-frac", type=float, default=0.80)
    ap.add_argument("--llm-scores", default=None)
    ap.add_argument("--daily-only", action="store_true",
                    help="run A, D and N only (skips the minute-bar strategies)")
    args = ap.parse_args()

    cfg, px, nw, scorer, trading_days, P = load_inputs(args)
    nw_naive = nw.assign(timestamp=nw.timestamp.dt.tz_localize(None))
    sig = build_signal_table(nw_naive, scorer, trading_days, cfg.signal)
    sig_is = sig[(sig.effective_date >= P["IS"][0])
                 & (sig.effective_date <= P["IS"][1])]
    lo = pd.Timestamp(P["IS"][0], tz="UTC")
    hi = pd.Timestamp(P["IS"][1], tz="UTC") + pd.Timedelta(days=1)
    ev_all = build_event_table(nw, scorer, cfg.signal)
    ev_all_is = ev_all[(ev_all.news_ts >= lo) & (ev_all.news_ts <= hi)]
    px_is = slice_period(px, P["IS"])
    assert px_is.date.max() <= P["IS"][1], "OOS prices leaked into the sweep"

    runs = daily_runs(cfg, px_is, sig_is, ev_all_is)
    if not args.daily_only:
        runs += intraday_runs(cfg, args, px_is, ev_all_is, lo, hi)
    print(f"\nIN-SAMPLE ONLY {P['IS'][0].date()} -> {P['IS'][1].date()} | "
          f"{len(runs)} variants\n")

    rows = []
    for name, bt in runs:
        eq, tr = bt.run()
        if tr.empty:
            print(f"  {name:<38} no trades")
            continue
        rows.append(summarize_variant(name, eq, tr))
        r = rows[-1]
        print(f"  {name:<38} {r['return_pa']:+7.1%}  Sharpe {r['sharpe']:+.2f}  "
              f"maxDD {r['maxDD']:5.1%}  trades {r['trades']:>6,}  "
              f"hit {r['hit_rate']:.0%}  mean R {r['mean_R']:+.3f}")

    df = pd.DataFrame(rows).set_index("variant")
    tag = ("llm" if args.llm_scores else "keyword") + ("_daily" if args.daily_only else "")
    out = OUTPUTS / f"sweep_new_strategies_{tag}.csv"
    df.to_csv(out)
    print(f"\nsaved {out}  ({len(df)} variants)")


if __name__ == "__main__":
    main()
