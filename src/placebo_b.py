"""
placebo_b.py -- Strategy B placebo (note `…note_placebo_b_2026-10-25.md`),
TRAINING PERIOD ONLY. Keyword B events with RANDOMLY assigned directions
(numpy.random.default_rng(20261024) on the sign; |strength| unchanged), Bug 14
engine, fixed sizer, designed governor, the keyword B-fixed scale of the Bug 14
correction, for both variants (entry t+5 and t+15 min). PASS per variant if
the mean R-multiple lies within 2 plain SE of minus the expected cost in R,
per trade -(latency-decayed entry cost + exit cost) / stop distance. B passes
only if both variants pass. Long-minus-short reported as descriptive.

USAGE (from the project root):  python3 src/placebo_b.py
"""
from __future__ import annotations

from argparse import Namespace

import numpy as np
import pandas as pd

from paths import PRICES, NEWS_CLEAN, BARS, OUTPUTS
from run_both_strategies import load_inputs, load_bars, market_hours_events
from newsdrift import build_event_table
from newsdrift.intraday import IntradayBacktest, IntradayConfig, latency_cost_bps

SEED = 20261024
SCALES = OUTPUTS / "risk_calibration_keyword_bug14fix_2026-10-24.csv"
OUT = OUTPUTS / "placebo_b_2026-10-25.csv"
GOVERNOR = dict(use_dd_governor=True, dd_probe_floor=0.05, dd_peak_halflife_days=60.0,
                one_position_per_ticker=True)                 # the runner's "designed" settings


def main():
    cfg, px, nw, scorer, td, P = load_inputs(Namespace(
        prices=str(PRICES), news=str(NEWS_CLEAN), start="2016-01-01", end="2026-06-01",
        train_frac=0.80, llm_scores=None, tier0=False))
    scales = pd.read_csv(SCALES).set_index(["strategy", "sizer"]).risk_scale
    lo, hi = pd.Timestamp(P["IS"][0], tz="UTC"), pd.Timestamp(P["IS"][1], tz="UTC") + pd.Timedelta(days=1)
    bars = load_bars(str(BARS))
    bars_is = bars[(bars.ts >= lo) & (bars.ts <= hi)]
    ev = market_hours_events(build_event_table(nw, scorer, cfg.signal), bars)
    ev = ev[(ev.news_ts >= lo) & (ev.news_ts <= hi)].copy()
    ev["strength"] = ev.strength.abs() * np.random.default_rng(SEED).choice([-1.0, 1.0], len(ev))
    rows = []
    for lat in (5, 15):
        icfg = IntradayConfig(entry_latency_min=lat, sizer="fixed", cost_base_bps=cfg.cost.per_side_bps,
                              dd_cap=cfg.risk.dd_cap, dd_throttle_start=cfg.risk.dd_throttle_start,
                              risk_scale=float(scales[(f"B_intraday_t+{lat}min", "fixed")]), **GOVERNOR)
        _, tr = IntradayBacktest(bars_is, ev, icfg).run()
        entry_bps = latency_cost_bps(lat, icfg.cost_base_bps, icfg.cost_spike_bps, icfg.cost_tau_min)
        cost_r = -(entry_bps + icfg.cost_base_bps) / tr.stop_dist_bps
        r = tr.r_multiple
        se = r.std(ddof=1) / np.sqrt(len(r))
        gap = r.mean() - cost_r.mean()
        longs, shorts = r[tr.direction > 0], r[tr.direction < 0]
        t_diff = (longs.mean() - shorts.mean()) / np.sqrt(longs.var(ddof=1) / len(longs) + shorts.var(ddof=1) / len(shorts))
        rows.append({"variant": f"B t+{lat}min", "seed": SEED, "events": len(ev), "trades": len(tr),
                     "risk_scale": icfg.risk_scale, "mean_R": r.mean(), "se": se, "expected_cost_R": cost_r.mean(),
                     "gap_in_se": gap / se, "mean_R_long": longs.mean(), "mean_R_short": shorts.mean(),
                     "t_long_minus_short": t_diff, "PASS": abs(gap) < 2 * se})
    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    print(out.T.to_string())
    print(f"\nB PLACEBO {'PASSED (both variants)' if out.PASS.all() else 'FAILED -- B not validated by placebo'}")


if __name__ == "__main__":
    main()
