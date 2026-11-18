"""
newsdrift/exposure.py -- average gross exposure of a strategy, recovered from
its trade log and equity curve (the engines enforce exposure caps internally
but do not record exposure).

Position notional:
  * Strategy A (NewsDriftBacktest trades): pnl = direction * (exit - entry) * shares
    exactly, so shares = pnl / (direction * (exit - entry)); notional =
    shares * entry. Trades with exit == entry (no recoverable size) are skipped.
  * Strategies B / C (portfolio.replay trades): risk_amount = shares * stop
    distance, so notional = risk_amount / (stop_dist_bps / 1e4).

Daily gross exposure = sum of the notionals of positions alive on that day
(entry day through exit day, inclusive) / equity that day. The average is over
every day of the equity curve, days without positions counting as 0.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _notional_and_days(trades: pd.DataFrame) -> pd.DataFrame:
    if {"risk_amount", "stop_dist_bps"} <= set(trades.columns):
        notional = trades.risk_amount / (trades.stop_dist_bps / 1e4)
        start = pd.to_datetime(trades.entry_ts, utc=True).dt.tz_convert(None).dt.normalize()
        end = pd.to_datetime(trades.exit_ts, utc=True).dt.tz_convert(None).dt.normalize()
    else:
        move = trades.direction * (trades["exit"] - trades.entry)
        shares = (trades.pnl / move).where(move != 0)
        notional = shares.abs() * trades.entry
        start = pd.to_datetime(trades.entry_date).dt.normalize()
        end = pd.to_datetime(trades.exit_date).dt.normalize()
    return pd.DataFrame({"notional": notional, "start": start, "end": end}).dropna()


def average_gross_exposure(trades: pd.DataFrame | None, equity: pd.Series | None) -> float:
    """Mean over the equity curve's days of sum(open notional) / equity."""
    if trades is None or equity is None or len(trades) == 0 or len(equity) == 0:
        return np.nan
    pos = _notional_and_days(trades)
    days = pd.DatetimeIndex(pd.to_datetime(equity.index)).tz_localize(None).normalize()
    eq = pd.Series(equity.to_numpy(float), index=days).groupby(level=0).last()
    idx = eq.index
    acc = np.zeros(len(idx) + 1)
    lo = idx.searchsorted(pos.start.to_numpy(), side="left")
    hi = idx.searchsorted(pos.end.to_numpy(), side="right")
    np.add.at(acc, lo, pos.notional.to_numpy())
    np.add.at(acc, hi, -pos.notional.to_numpy())
    gross = np.cumsum(acc[:-1])
    return float(np.mean(gross / eq.to_numpy()))
