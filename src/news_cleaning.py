"""
news_cleaning.py -- the shared news-row logic of the historical pipeline,
imported by the historical fetcher (fetch_historical_news.py), the live
pipeline (live_pipeline.py) and the parity test, so all three apply the SAME
rules:

  universe_rows(item, universe): one row (created_at, ticker, headline,
      source) per newswire symbol tag that is in the universe; items without
      a headline or created_at give no rows.
  clean_news(df): drop exact duplicates on (timestamp, ticker, headline) and
      fill a missing source with "benzinga".
"""
from __future__ import annotations

import pandas as pd

ROW_COLUMNS = ["timestamp", "ticker", "headline", "source"]


def universe_rows(item: dict, universe: set) -> list[tuple]:
    headline = (item.get("headline") or "").strip()
    ts = item.get("created_at", "")
    src = item.get("source", "benzinga")
    if not headline or not ts:
        return []
    return [(ts, sym, headline, src) for sym in (item.get("symbols") or []) if sym in universe]


def clean_news(df: pd.DataFrame) -> pd.DataFrame:
    out = df.drop_duplicates(subset=["timestamp", "ticker", "headline"])
    blank = out.source.isna() | (out.source.astype(str).str.strip() == "")
    return out.assign(source=out.source.where(~blank, "benzinga")).reset_index(drop=True)
