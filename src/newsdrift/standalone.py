"""
newsdrift/standalone.py -- per-signal outcomes with Strategy A's EXACT rules,
one signal at a time, ignoring portfolio caps, open-position conflicts and the
drawdown governor. Used as the training target for score calibration, so the
target is not shaped by which signals the portfolio had room for.

Mirrors NewsDriftBacktest.run():
  * entry at the open of effective_date, cost-adjusted;
  * ATR from backtest.attach_atr (the ticker's Wilder ATR up to the previous
    bar -- the engine's own function), stops/targets from
    risk.compute_stop_targets (2xATR stop, 2R target, 2.5R if |strength|>0.7);
  * exits checked from the NEXT bar of that ticker (the engine never checks
    the entry day), stop before target, time exit at the close after
    `duration` bars; exit cost applied;
  * r_multiple = direction * (exit_net - entry) / stop_dist.
A signal whose walk runs out of bars before exiting gets no outcome, so the
result never depends on prices beyond the data passed in.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from .config import Config
from .risk import compute_stop_targets
from .backtest import attach_atr


def _ticker_arrays(px: pd.DataFrame, period: int) -> dict:
    out = {}
    for t, g in attach_atr(px, period).groupby("ticker"):
        g = g.reset_index(drop=True)
        out[t] = {
            "pos": {d: i for i, d in enumerate(g["date"])},
            "date": g["date"].to_numpy(), "open": g["open"].to_numpy(float),
            "high": g["high"].to_numpy(float), "low": g["low"].to_numpy(float),
            "close": g["close"].to_numpy(float),
            "atr": g["atr"].to_numpy(float),
        }
    return out


def _walk(a: dict, i: int, direction: int, stop: float, target: float,
          duration: int):
    """(exit_index, exit_price, reason) or None if bars run out."""
    bars_left = duration
    for j in range(i + 1, len(a["date"])):
        if direction == 1:
            if a["low"][j] <= stop:
                return j, stop, "stop"
            if a["high"][j] >= target:
                return j, target, "target"
        else:
            if a["high"][j] >= stop:
                return j, stop, "stop"
            if a["low"][j] <= target:
                return j, target, "target"
        bars_left -= 1
        if bars_left <= 0:
            return j, a["close"][j], "time"
    return None


def simulate_standalone(px: pd.DataFrame, signals: pd.DataFrame,
                        cfg: Config) -> pd.DataFrame:
    """One row per signal that entered and exited within `px`."""
    cost = cfg.cost.per_side_bps / 1e4
    arrays = _ticker_arrays(px, cfg.risk.atr_period)
    rows = []
    for s in signals.itertuples(index=False):
        a = arrays.get(s.ticker)
        i = a["pos"].get(s.effective_date) if a else None
        if i is None or s.strength == 0:
            continue
        bar_atr = a["atr"][i]
        if np.isnan(bar_atr) or bar_atr <= 0:
            continue
        direction = 1 if s.strength > 0 else -1
        entry = a["open"][i] * (1 + direction * cost)
        stop, target, stop_dist = compute_stop_targets(
            entry, direction, bar_atr, s.strength, cfg.risk)
        if stop_dist <= 0:
            continue
        hit = _walk(a, i, direction, stop, target, int(s.duration))
        if hit is None:
            continue
        j, exit_px, reason = hit
        exit_net = exit_px * (1 - direction * cost)
        rows.append({"effective_date": s.effective_date, "ticker": s.ticker,
                     "exit_date": a["date"][j], "reason": reason,
                     "r_multiple": direction * (exit_net - entry) / stop_dist})
    return pd.DataFrame(rows, columns=["effective_date", "ticker", "exit_date",
                                       "reason", "r_multiple"])
