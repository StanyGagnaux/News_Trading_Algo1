"""
splits.py -- the backtest's chronological train/test split, in one place.

Same rule as run_both_strategies.load_inputs: trading calendar = price dates
in [start, end] for non-index tickers that also have news in [start, end];
training ends at calendar[int(n * train_frac)] (inclusive) = 2024-04-29 with
the defaults. Reads only the date/ticker columns (no prices or news text).

Used by score_news_llm.py (which used to cut on the full, unfiltered price
calendar -> 2024-03-26, leaving the last month of training unscored) and by
calibrate_scorer.verify_train_end.
"""
from __future__ import annotations

import pandas as pd

INDEX_TICKERS = {"NDX", "SPX", "VIX", "RF"}
DEFAULT_START, DEFAULT_END, DEFAULT_TRAIN_FRAC = "2016-01-01", "2026-06-01", 0.80


def backtest_train_end(prices_path, news_path, start: str = DEFAULT_START,
                       end: str = DEFAULT_END, train_frac: float = DEFAULT_TRAIN_FRAC
                       ) -> pd.Timestamp:
    cal = pd.read_csv(prices_path, usecols=["date", "ticker"], parse_dates=["date"])
    cal = cal[~cal.ticker.isin(INDEX_TICKERS) & (cal.date >= start) & (cal.date <= end)]
    nt = pd.read_csv(news_path, usecols=["timestamp", "ticker"])
    ts = pd.to_datetime(nt.timestamp, utc=True).dt.tz_localize(None)
    news_tickers = set(nt.ticker[(ts >= start) & (ts <= end)])
    days = pd.DatetimeIndex(sorted(cal[cal.ticker.isin(news_tickers)].date.unique()))
    return days[int(len(days) * train_frac)]
