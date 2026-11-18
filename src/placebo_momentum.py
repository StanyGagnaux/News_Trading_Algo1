"""
placebo_momentum.py -- random-direction placebo for the momentum benchmark
(requested 24 Oct 2026), TRAINING PERIOD ONLY, descriptive. The momentum
engine unchanged except that each ticker's sign on each day is drawn at random
(numpy.random.default_rng(20261024), +1/-1) wherever a momentum signal exists;
weights, vol scaling, weekly rebalance, one-day lag and turnover costs as in
baseline.momentum_backtest. Random weekly positions should lose about their
costs. Reports the mean daily net return vs minus the mean daily cost (plain
SE over days), and the long-leg minus short-leg gross return.

Also checks that baseline.momentum_backtest (refactored to share
momentum_weights) reproduces the archived engine exactly on both periods.

USAGE (from the project root):  python3 src/placebo_momentum.py
"""
from __future__ import annotations

import importlib.util
from argparse import Namespace

import numpy as np
import pandas as pd

from paths import PRICES, NEWS_CLEAN, OUTPUTS, ROOT
from run_both_strategies import load_inputs
from newsdrift import momentum_backtest, slice_period
from newsdrift.baseline import momentum_weights

SEED = 20261024
OUT = OUTPUTS / "placebo_momentum_2026-10-24.csv"
ARCHIVED = ROOT / "_archive" / "_backup_2026-10-24_before_momentum_placebo" / "baseline.py"


def archived_engine():
    spec = importlib.util.spec_from_file_location("newsdrift._baseline_archived", ARCHIVED,
                                                  submodule_search_locations=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "newsdrift"
    spec.loader.exec_module(mod)
    return mod.momentum_backtest


def main():
    cfg, px, *_rest, P = load_inputs(Namespace(
        prices=str(PRICES), news=str(NEWS_CLEAN), start="2016-01-01", end="2026-06-01",
        train_frac=0.80, llm_scores=None, tier0=False))
    old = archived_engine()
    for tag, period in P.items():
        a = momentum_backtest(slice_period(px, period), cfg.momentum, cfg.cost, cfg.initial_equity)
        b = old(slice_period(px, period), cfg.momentum, cfg.cost, cfg.initial_equity)
        assert a.index.equals(b.index) and np.array_equal(a.to_numpy(), b.to_numpy()), f"{tag}: engine changed"
    print("  refactored momentum engine reproduces the archived one exactly (IS and OOS)")

    close = slice_period(px, P["IS"]).pivot_table(index="date", columns="ticker", values="close",
                                                  aggfunc="last").sort_index()
    rng = np.random.default_rng(SEED)
    direction = pd.DataFrame(rng.choice([-1.0, 1.0], close.shape), index=close.index, columns=close.columns)
    w, rets = momentum_weights(close, cfg.momentum, direction)
    gross = (w * rets).sum(axis=1)
    cost = w.diff().abs().sum(axis=1).fillna(0.0) * cfg.cost.per_side_bps / 1e4
    net = gross - cost
    live = w.abs().sum(axis=1) > 0                       # days with positions (after warm-up)
    net, gross, cost = net[live], gross[live], cost[live]
    long_leg = (w.clip(lower=0) * rets).sum(axis=1)[live]
    short_leg = (w.clip(upper=0) * rets).sum(axis=1)[live]   # short weights negative: P&L of shorts
    se = net.std(ddof=1) / np.sqrt(len(net))
    gap = net.mean() + cost.mean()
    # per unit of gross exposure: long-minus-short in return of the held names
    lw, sw = w.clip(lower=0).sum(axis=1)[live], -w.clip(upper=0).sum(axis=1)[live]
    long_ret = (w.clip(lower=0) * rets).sum(axis=1)[live] / lw.replace(0, np.nan)
    short_ret = (-w.clip(upper=0) * rets).sum(axis=1)[live] / sw.replace(0, np.nan)
    d = (long_ret - short_ret).dropna()
    summary = pd.DataFrame([{
        "seed": SEED, "period": "training", "days": len(net),
        "mean_net_bps_per_day": net.mean() * 1e4, "se_bps": se * 1e4,
        "expected_cost_bps_per_day": -cost.mean() * 1e4, "gap_in_se": gap / se,
        "mean_gross_bps_per_day": gross.mean() * 1e4,
        "long_leg_pnl_bps_per_day": long_leg.mean() * 1e4, "short_leg_pnl_bps_per_day": short_leg.mean() * 1e4,
        "long_minus_short_held_return_bps_per_day": d.mean() * 1e4,
        "t_long_minus_short": d.mean() / (d.std(ddof=1) / np.sqrt(len(d))),
        "gross_exposure_mean": (lw + sw).mean(), "realised_vol_ann": net.std() * np.sqrt(252)}])
    summary.to_csv(OUT, index=False)
    print(summary.T.to_string())


if __name__ == "__main__":
    main()
