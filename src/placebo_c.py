"""
placebo_c.py -- Bug 13 placebo (note of 24 Oct 2026), TRAINING PERIOD ONLY.
Strategy C on the keyword C event set with RANDOMLY assigned directions
(numpy.random.default_rng(20261024)); |strength| unchanged. Every candidate
trade (no portfolio, so nothing depends on admission order).

PASS if (1) the mean R-multiple is within 2 standard errors of minus the
expected cost in R, -(entry cost + exit cost) / stop distance per trade, and
(2) the long-minus-short difference in mean R has |t| < 2. Otherwise stop.

USAGE (from the project root):  python3 src/placebo_c.py
"""
from __future__ import annotations

import argparse
from argparse import Namespace

import numpy as np
import pandas as pd

from paths import PRICES, NEWS_CLEAN, BARS, OUTPUTS, DATA
from run_both_strategies import load_inputs, load_bars, market_hours_events
from newsdrift import build_event_table, slice_period
from newsdrift.intraday import latency_cost_bps
from newsdrift.strategy_c import StrategyCBacktest, StrategyCConfig
from newsdrift.strategy_c_minute import StrategyCMinuteBacktest

SEED = 20261024
OUT = OUTPUTS / "placebo_c_2026-10-24.csv"
OUT_C1 = OUTPUTS / "placebo_c1_2026-10-24.csv"
OUT_CMIN = OUTPUTS / "placebo_cmin_2026-10-24.csv"
HOLD_BARS = DATA / "bars_c_hold.csv"      # full-session bars (note …note_c_minute_2026-10-24.md)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["C", "C1", "Cmin"], default="C",
                    help="C1 = entry at the news-day daily close (daily bars only); "
                         "Cmin = minute-bar-only C on full-session bars (mean criterion only)")
    ap.add_argument("--tag", default="2026-10-24", help="output file tag")
    a = ap.parse_args()
    variant = a.variant
    cfg, px, nw, scorer, td, P = load_inputs(Namespace(
        prices=str(PRICES), news=str(NEWS_CLEAN), start="2016-01-01", end="2026-06-01",
        train_frac=0.80, llm_scores=None, tier0=False))
    lo, hi = pd.Timestamp(P["IS"][0], tz="UTC"), pd.Timestamp(P["IS"][1], tz="UTC") + pd.Timedelta(days=1)
    bars = load_bars(str(BARS))
    bars_is = bars[(bars.ts >= lo) & (bars.ts <= hi)]
    ev = market_hours_events(build_event_table(nw, scorer, cfg.signal), bars)
    ev = ev[(ev.news_ts >= lo) & (ev.news_ts <= hi)].copy()
    rng = np.random.default_rng(SEED)
    ev["strength"] = ev.strength.abs() * rng.choice([-1.0, 1.0], len(ev))
    ccfg = StrategyCConfig(exit_cost_bps=cfg.cost.per_side_bps,
                           **({"entry_mode": "close"} if variant == "C1" else {}))
    if variant == "Cmin":                       # events as C; prices from the full-session file
        hold = load_bars(str(HOLD_BARS))
        bt = StrategyCMinuteBacktest(slice_period(px, P["IS"]), hold[(hold.ts >= lo) & (hold.ts <= hi + pd.Timedelta(days=7))],
                                     ev, ccfg)
    else:
        bt = StrategyCBacktest(slice_period(px, P["IS"]), bars_is, ev, ccfg)
    tr = bt.candidate_table()
    entry_bps = (ccfg.exit_cost_bps if variant == "C1" else      # C1 entry cost = per-side cost
                 latency_cost_bps(ccfg.entry_latency_min, ccfg.entry_cost_base_bps,
                                  ccfg.entry_cost_spike_bps, ccfg.entry_cost_tau_min))
    tr["cost_R"] = -(entry_bps + ccfg.exit_cost_bps) / tr.stop_dist_bps
    r = tr.r_multiple
    se = r.std(ddof=1) / np.sqrt(len(r))
    gap = r.mean() - tr.cost_R.mean()
    longs, shorts = r[tr.direction > 0], r[tr.direction < 0]
    diff = longs.mean() - shorts.mean()
    t_diff = diff / np.sqrt(longs.var(ddof=1) / len(longs) + shorts.var(ddof=1) / len(shorts))
    # Cmin: one criterion for all engines (note …note_c_minute_2026-10-24.md): mean only
    passed = abs(gap) < 2 * se if variant == "Cmin" else (abs(gap) < 2 * se and abs(t_diff) < 2)
    by_year = tr.assign(year=pd.to_datetime(tr.entry_ts).dt.year).groupby(["year", "direction"]).r_multiple.mean().unstack()
    summary = pd.DataFrame([{"variant": variant, "seed": SEED, "trades": len(tr), "dropped_no_basis_ratio": bt.basis_dropped,
                             "mean_R": r.mean(), "se": se, "expected_cost_R": tr.cost_R.mean(),
                             "gap_in_se": gap / se, "mean_R_long": longs.mean(), "mean_R_short": shorts.mean(),
                             "t_long_minus_short": t_diff, "PASS": passed}])
    if variant == "Cmin":
        div = bt.implied_dividend(tr)
        effect = -tr.direction * div / (tr.stop_dist_bps / 1e4)          # R lost (long) / gained (short)
        summary = summary.assign(
            events=len(ev), stale_exits=bt.stale_exits, share_div_over_5bps=float((div > 5e-4).mean()),
            div_effect_R_mean=float(effect.mean()), div_effect_R_long=float(effect[tr.direction > 0].mean()),
            div_effect_R_short=float(effect[tr.direction < 0].mean()))
    out = {"C1": OUT_C1, "Cmin": OUT_CMIN}.get(variant, OUT)
    summary.to_csv(out.with_name(out.name.replace("2026-10-24", a.tag)), index=False)
    print(summary.T.to_string())
    print("\nmean R by year and direction (placebo):")
    print(by_year.round(3).to_string())
    print(f"\nPLACEBO {'PASSED' if passed else 'FAILED -- stop and report'}")


if __name__ == "__main__":
    main()
