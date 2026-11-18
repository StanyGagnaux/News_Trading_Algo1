"""
Pillar 3 -- Momentum baseline (the benchmark the news strategy must beat)
and locked walk-forward data splits (overfitting control).

Momentum: time-series momentum in the Jegadeesh-Titman lineage.
  Signal_i = sign( return over [t - lookback, t - skip] )
  Weights vol-targeted (10% annualized default), rebalanced weekly, costs
  charged on turnover. Fully vectorized.

Walk-forward: split fractions are fixed in config BEFORE any tuning.
  train      -> parameter search allowed
  validation -> model/parameter selection
  test       -> touched exactly once, after everything is frozen
Any result quoted in the thesis from `test` must come from a single run.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from .config import MomentumConfig, WalkForwardConfig, CostConfig


def momentum_weights(close: pd.DataFrame, mcfg: MomentumConfig,
                     direction: pd.DataFrame | None = None
                     ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(weights applied to each day's return, daily returns). `direction`
    (+1/-1, same shape as `close`) replaces the momentum sign where a momentum
    signal exists -- the random-direction placebo; None = momentum."""
    rets = close.pct_change()

    mom = close.shift(mcfg.skip_days).pct_change(
        mcfg.lookback_days - mcfg.skip_days)
    raw_sig = np.sign(mom) if direction is None else direction.where(mom.notna())

    vol = rets.rolling(mcfg.vol_lookback).std() * np.sqrt(252)
    n = close.shape[1]
    w = raw_sig * (mcfg.vol_target_annual / vol.replace(0, np.nan)) / n
    w = w.clip(-1.0 / n * 3, 1.0 / n * 3)          # per-name cap
    # weekly rebalance: hold weights between rebalance dates
    rebal_mask = np.arange(len(w)) % mcfg.rebalance_days == 0
    w = w.where(pd.Series(rebal_mask, index=w.index), np.nan).ffill().fillna(0.0)
    # signals computed on info through t -> applied to return t+1 (no look-ahead)
    w = w.shift(1).fillna(0.0)
    return w, rets


def momentum_backtest(prices: pd.DataFrame, mcfg: MomentumConfig,
                      ccfg: CostConfig, initial_equity: float = 100_000.0,
                      risk_scale: float = 1.0) -> pd.Series:
    """Vectorized TS-momentum equity curve on the same universe.
    risk_scale multiplies every position (and so turnover and costs); the
    default 1.0 is the frozen benchmark (momentum note of 24 Oct 2026)."""
    close = prices.pivot_table(index="date", columns="ticker",
                               values="close", aggfunc="last").sort_index()
    w, rets = momentum_weights(close, mcfg)
    if risk_scale != 1.0:
        w = w * risk_scale

    gross_ret = (w * rets).sum(axis=1)
    turnover = w.diff().abs().sum(axis=1).fillna(0.0)
    cost = turnover * (ccfg.per_side_bps / 1e4)
    net_ret = gross_ret - cost
    equity = initial_equity * (1 + net_ret.fillna(0)).cumprod()
    return equity


def walk_forward_dates(dates: pd.DatetimeIndex, wcfg: WalkForwardConfig
                       ) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    """Two-way chronological split: earliest train_frac of dates = train
    (in-sample), the rest = test (out-of-sample)."""
    dates = pd.DatetimeIndex(sorted(pd.Index(dates).unique()))
    n = len(dates)
    i1 = int(n * wcfg.train_frac)
    return {
        "train": (dates[0], dates[i1 - 1]),
        "test": (dates[i1], dates[-1]),
    }


def slice_period(df: pd.DataFrame, period: tuple, date_col: str = "date"
                 ) -> pd.DataFrame:
    lo, hi = period
    return df[(df[date_col] >= lo) & (df[date_col] <= hi)].copy()
