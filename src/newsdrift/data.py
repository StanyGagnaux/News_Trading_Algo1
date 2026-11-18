"""
Data layer (Pillar 3).

Design principle: SOURCE-AGNOSTIC. The rest of the system only ever sees two
canonical DataFrames, regardless of where the data came from:

  prices : MultiIndex-free long table
           [date, ticker, open, high, low, close, volume]

  news   : [timestamp, ticker, headline, (optional) body, source]
           Schema chosen to be a strict subset of RavenPack fields so that a
           WRDS/RavenPack export drops in without code changes. Fallback
           sources (Benzinga, FNSPID, GDELT, scraped headlines) just need to
           map onto these five columns.

Loaders provided:
  - load_prices_csv / load_news_csv      (primary path: exported files)
  - load_prices_yfinance                 (fallback, requires `yfinance` locally)
  - load_prices_stooq                    (fallback, requires `pandas-datareader`)
  - make_synthetic                       (controlled experiments / pipeline tests)

The synthetic generator injects a KNOWN post-news drift so the pipeline can be
validated against ground truth (a form of unit test for the whole system:
if the backtest cannot recover an edge we planted, the plumbing is broken).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

PRICE_COLS = ["date", "ticker", "open", "high", "low", "close", "volume"]
NEWS_COLS = ["timestamp", "ticker", "headline"]


# ----------------------------------------------------------------------------
# CSV loaders (primary path)
# ----------------------------------------------------------------------------
def load_prices_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    missing = set(PRICE_COLS) - set(df.columns)
    if missing:
        raise ValueError(f"prices file missing columns: {missing}")
    return df[PRICE_COLS].sort_values(["ticker", "date"]).reset_index(drop=True)


def load_news_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["timestamp"])
    missing = set(NEWS_COLS) - set(df.columns)
    if missing:
        raise ValueError(f"news file missing columns: {missing}")
    return df.sort_values("timestamp").reset_index(drop=True)


# ----------------------------------------------------------------------------
# Remote fallbacks (run locally; network-dependent, hence import inside)
# ----------------------------------------------------------------------------
def load_prices_yfinance(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    import yfinance as yf  # pip install yfinance
    frames = []
    for t in tickers:
        raw = yf.download(t, start=start, end=end, auto_adjust=True, progress=False)
        raw = raw.reset_index()
        raw.columns = [c[0].lower() if isinstance(c, tuple) else str(c).lower()
                       for c in raw.columns]
        raw["ticker"] = t
        raw = raw.rename(columns={"index": "date"})
        frames.append(raw[PRICE_COLS])
    return pd.concat(frames, ignore_index=True).sort_values(["ticker", "date"])


def load_prices_stooq(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    from pandas_datareader import data as pdr  # pip install pandas-datareader
    frames = []
    for t in tickers:
        raw = pdr.DataReader(t, "stooq", start, end).sort_index().reset_index()
        raw.columns = [c.lower() for c in raw.columns]
        raw["ticker"] = t
        frames.append(raw[PRICE_COLS])
    return pd.concat(frames, ignore_index=True).sort_values(["ticker", "date"])


# ----------------------------------------------------------------------------
# Synthetic ground-truth generator
# ----------------------------------------------------------------------------
def make_synthetic(
    n_tickers: int = 8,
    n_days: int = 1500,
    news_per_ticker_per_year: int = 24,
    drift_per_day: float = 0.004,      # planted post-news edge (40 bps/day)
    drift_days: int = 2,               # consistent with Lopez-Lira & Tang decay
    noise_vol_daily: float = 0.015,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Returns (prices, news, truth) where `truth` records the sign/duration of
    each planted event, for validating signal extraction downstream.

    News on day t moves prices on days t+1 .. t+drift_days -- i.e. the initial
    spike is NOT tradable (it happens in the day-t bar), only the drift is.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2018-01-02", periods=n_days)
    tickers = [f"SYN{i:02d}" for i in range(n_tickers)]

    pos_templates = [
        "{t} beats quarterly earnings estimates, raises full-year guidance",
        "{t} wins major contract, analysts upgrade to buy",
        "{t} reports record revenue growth, announces buyback",
    ]
    neg_templates = [
        "{t} misses earnings expectations, cuts outlook",
        "{t} faces regulatory probe, shares under pressure",
        "{t} warns of weak demand, announces layoffs",
    ]

    price_frames, news_rows, truth_rows = [], [], []
    for t in tickers:
        rets = rng.normal(0.0002, noise_vol_daily, n_days)

        n_events = int(news_per_ticker_per_year * n_days / 252)
        event_idx = np.sort(rng.choice(np.arange(30, n_days - 10),
                                       size=n_events, replace=False))
        for idx in event_idx:
            sign = 1 if rng.random() < 0.5 else -1
            dur = int(rng.integers(1, drift_days + 1))
            # day-t spike (non-tradable): 3x the drift, embedded in the news bar
            rets[idx] += sign * drift_per_day * 3
            # drift on t+1..t+dur (tradable edge)
            rets[idx + 1: idx + 1 + dur] += sign * drift_per_day
            tmpl = rng.choice(pos_templates if sign > 0 else neg_templates)
            # news released INTRADAY on day idx (10:00). The day-idx bar is the
            # (non-tradable) reaction bar; with lag=1 the signal becomes
            # effective at the open of day idx+1, capturing only the drift.
            ts = dates[idx] + pd.Timedelta(hours=10)
            news_rows.append({"timestamp": ts, "ticker": t,
                              "headline": tmpl.format(t=t)})
            truth_rows.append({"date": dates[idx], "ticker": t,
                               "sign": sign, "duration": dur})

        close = 100 * np.exp(np.cumsum(rets))
        intraday = np.abs(rng.normal(0, noise_vol_daily / 2, n_days))
        # open derives from the PREVIOUS close + overnight noise only --
        # same-day information can never leak into an open-price entry
        prev_close = np.concatenate([[100.0], close[:-1]])
        opn = prev_close * np.exp(rng.normal(0, noise_vol_daily / 3, n_days))
        high = np.maximum(opn, close) * (1 + intraday)
        low = np.minimum(opn, close) * (1 - intraday)
        vol = rng.integers(1e5, 5e6, n_days).astype(float)
        price_frames.append(pd.DataFrame({
            "date": dates, "ticker": t, "open": opn, "high": high,
            "low": low, "close": close, "volume": vol,
        }))

    prices = pd.concat(price_frames, ignore_index=True)
    news = pd.DataFrame(news_rows).sort_values("timestamp").reset_index(drop=True)
    truth = pd.DataFrame(truth_rows)
    return prices, news, truth
