"""
placebo_a.py -- Bug 14 placebo for Strategy A (note of 24 Oct 2026), TRAINING
PERIOD ONLY. Keyword daily signals with RANDOMLY assigned directions
(numpy.random.default_rng(20261024) on the sign; |strength| unchanged), fixed
sizer, designed governor, the 18 Oct keyword A-fixed risk scale (so caps rarely
bind). PASS if the mean R-multiple lies within 2 (plain) standard errors of
minus the expected cost in R, per trade -(2 x per-side cost) / stop distance.
Long-minus-short is reported as descriptive.

Bug 15 (note of 10 Nov 2026, test D), additive options, defaults unchanged:
`--sizer kelly --scales <calibration csv>` runs the same placebo with the
Kelly sizer at the portfolio level and adds criterion (ii): the size-weighted
signed open-to-close return of the entry day must not exceed the
equal-weighted one by more than 2 (plain) standard errors. Size = the risk
amount actually taken, pnl / R-multiple, from the trade log.
`--directions long short` (addendum of 10 Nov 2026, test D2): the
common-direction placebo, every signal long / every signal short, no random
draw; the criterion is the same excess against the SE clustered by entry date
(criterion (i) is not applied: a one-sided book earns the market's drift).

USAGE (from the project root):
  python3 src/placebo_a.py
  python3 src/placebo_a.py --sizer kelly --scales outputs/risk_calibration_keyword_bug15fix_2026-11-10.csv \
      --out outputs/placebo_a_kelly_bug15fix_2026-11-10.csv
"""
from __future__ import annotations

import argparse
from argparse import Namespace
from dataclasses import replace

import numpy as np
import pandas as pd

from paths import PRICES, NEWS_CLEAN, OUTPUTS
from run_both_strategies import load_inputs
from newsdrift import build_signal_table, slice_period, NewsDriftBacktest

SEED = 20261024
SCALES = OUTPUTS / "risk_calibration_keyword.csv"      # 18 Oct, keyword
OUT = OUTPUTS / "placebo_a_bug14fix_2026-10-24.csv"
SE_LIMIT = 2.0


def clustered_se_of_mean(x: pd.Series, clusters: pd.Series) -> float:
    """Standard error of mean(x) with errors correlated inside a cluster (CR1)."""
    sums = (x - x.mean()).groupby(clusters.to_numpy()).sum()
    g = len(sums)
    return float(np.sqrt(g / (g - 1) * (sums ** 2).sum()) / len(x))


def size_weighted_entry_day(tr: pd.DataFrame, px: pd.DataFrame) -> dict:
    """Criterion (ii): size-weighted minus equal-weighted signed open-to-close
    return of the entry day, in bps, with plain and date-clustered SE."""
    t = tr[tr.r_multiple != 0].merge(px[["ticker", "date", "open", "close"]], left_on=["ticker", "entry_date"],
                                     right_on=["ticker", "date"], how="left", validate="many_to_one")
    assert t.open.notna().all(), "entry-day bar missing for a trade"
    oc = t.direction * (t.close / t.open - 1)
    size = t.pnl / t.r_multiple                         # risk amount actually taken
    w = size / size.mean()
    x = (w - 1) * oc
    se = x.std(ddof=1) / np.sqrt(len(x))
    se_cluster = clustered_se_of_mean(x, t.entry_date)
    return {"zero_R_trades_dropped": int(len(tr) - len(t)),
            "entry_day_oc_bps_equal_weight": 1e4 * oc.mean(), "entry_day_oc_bps_size_weight": 1e4 * (w * oc).mean(),
            "excess_bps": 1e4 * x.mean(), "excess_se_bps": 1e4 * se, "excess_in_se": x.mean() / se,
            "excess_se_clustered_bps": 1e4 * se_cluster, "excess_in_se_clustered": x.mean() / se_cluster,
            "PASS_ii": bool(x.mean() <= SE_LIMIT * se)}


def assign_directions(strength: pd.Series, directions: str) -> pd.Series:
    """random: the 24 Oct placebo (fair coin per signal, seed 20261024). long / short: test D2 of the
    Bug 15 addendum (common direction, every signal the same sign; no random number is drawn)."""
    if directions == "random":
        return strength.abs() * np.random.default_rng(SEED).choice([-1.0, 1.0], len(strength))
    return strength.abs() * (1.0 if directions == "long" else -1.0)


def placebo_row(sig: pd.DataFrame, px_is: pd.DataFrame, cfg, sizer: str, directions: str) -> dict:
    sig = sig.assign(strength=assign_directions(sig.strength, directions))
    _, tr = NewsDriftBacktest(px_is, sig, cfg, sizer_kind=sizer).run()
    r = tr.r_multiple
    cost_r = -2 * cfg.cost.per_side_bps / tr.stop_dist_bps
    se = r.std(ddof=1) / np.sqrt(len(r))
    gap = r.mean() - cost_r.mean()
    longs, shorts = r[tr.direction > 0], r[tr.direction < 0]
    t_diff = ((longs.mean() - shorts.mean()) / np.sqrt(longs.var(ddof=1) / len(longs)
                                                       + shorts.var(ddof=1) / len(shorts))
              if len(longs) > 1 and len(shorts) > 1 else np.nan)
    size_stats = size_weighted_entry_day(tr, px_is)
    return {"strategy": "A", "seed": SEED, "signals": len(sig), "trades": len(tr),
            "mean_R": r.mean(), "se": se, "expected_cost_R": cost_r.mean(), "gap_in_se": gap / se,
            "mean_R_long": longs.mean() if len(longs) else np.nan,
            "mean_R_short": shorts.mean() if len(shorts) else np.nan, "t_long_minus_short": t_diff,
            "share_stop": (tr.reason == "stop").mean(), "share_target": (tr.reason == "target").mean(),
            "share_exit_on_entry_day": (tr.exit_date == tr.entry_date).mean(),
            "PASS": bool(abs(gap) < SE_LIMIT * se),          # criterion (i); not applied to common directions
            "sizer": sizer, "risk_scale": cfg.risk.risk_scale, **size_stats,
            "directions": directions,
            "excess_within_2_clustered_se": bool(size_stats["excess_in_se_clustered"] <= SE_LIMIT)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizer", choices=["fixed", "kelly"], default="fixed")
    ap.add_argument("--scales", default=str(SCALES), help="calibration CSV; the A scale of --sizer is used")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--directions", nargs="+", choices=["random", "long", "short"], default=["random"],
                    help="random = the placebo of 24 Oct; long / short = common-direction placebo "
                         "(test D2, Bug 15 addendum of 10 Nov 2026); one output row per value")
    args = ap.parse_args()

    cfg, px, nw, scorer, td, P = load_inputs(Namespace(
        prices=str(PRICES), news=str(NEWS_CLEAN), start="2016-01-01", end="2026-06-01",
        train_frac=0.80, llm_scores=None, tier0=False))
    scales = pd.read_csv(args.scales).set_index(["strategy", "sizer"]).risk_scale
    scale = float(scales[("A_daily_1-3d", args.sizer)])
    cfg = replace(cfg, risk=replace(cfg.risk, use_dd_governor=True, dd_probe_floor=0.05,
                                    dd_peak_halflife_days=60.0, risk_scale=scale))
    sig = build_signal_table(nw.assign(timestamp=nw.timestamp.dt.tz_localize(None)), scorer, td, cfg.signal)
    sig = sig[(sig.effective_date >= P["IS"][0]) & (sig.effective_date <= P["IS"][1])].copy()
    px_is = slice_period(px, P["IS"])
    assert px_is.date.max() <= P["IS"][1] and sig.effective_date.max() <= P["IS"][1], "placebo is training-only"

    summary = pd.DataFrame([placebo_row(sig, px_is, cfg, args.sizer, d) for d in args.directions])
    summary.to_csv(args.out, index=False)
    print(summary.T.to_string())
    for row in summary.itertuples(index=False):
        if row.directions == "random":
            print(f"\nPLACEBO {'PASSED' if row.PASS else 'FAILED -- stop and report'}")
            if args.sizer == "kelly":
                print(f"CRITERION (ii), size-weighted entry-day return: "
                      f"{'PASSED' if row.PASS_ii else 'FAILED -- stop and report'}")
        else:
            print(f"\nD2-{row.directions}: excess {row.excess_bps:+.2f} bps = {row.excess_in_se_clustered:+.2f} clustered SE "
                  f"-> {'within' if row.excess_within_2_clustered_se else 'ABOVE'} +2 clustered SE")


if __name__ == "__main__":
    main()
