"""
Regression test for Bug 10 (13 Oct 2026): Strategy A's ATR landed on the wrong
rows and tickers, and used the entry day's own high/low.

Builds a price table like the real one after filtering -- gaps in the index,
first rows dropped, rows shuffled, different price levels per ticker -- and
checks 200 random rows against an ATR recomputed by a plain loop from that
ticker's rows STRICTLY BEFORE the row's date (Wilder, alpha = 1/period).
Run (from the project root):  python3 tests/test_atr_alignment.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from newsdrift.backtest import attach_atr

PERIOD = 14
N_CHECK = 200
rng = np.random.default_rng(7)


def messy_prices() -> pd.DataFrame:
    days = pd.bdate_range("2019-01-01", periods=160)
    parts = []
    for t, level in (("AAA", 10.0), ("BBB", 50.0), ("CCC", 300.0), ("DDD", 1500.0)):
        close = level * np.exp(np.cumsum(rng.normal(0, 0.02, len(days))))
        spread = close * rng.uniform(0.005, 0.04, len(days))
        parts.append(pd.DataFrame({"date": days, "ticker": t, "close": close,
                                   "high": close + spread * rng.uniform(0, 1, len(days)),
                                   "low": close - spread * rng.uniform(0, 1, len(days))}))
    px = pd.concat(parts, ignore_index=True)       # ticker-major, like prices.csv
    px = px[px.date >= days[20]]                    # date filter -> index gaps per ticker
    px = px.drop(px.sample(frac=0.10, random_state=1).index)   # missing bars
    return px.sample(frac=1.0, random_state=2)      # arbitrary row order


def reference_atr(px: pd.DataFrame, ticker: str, date: pd.Timestamp) -> float:
    prior = px[(px.ticker == ticker) & (px.date < date)].sort_values("date")
    if prior.empty:
        return np.nan
    a, prev_close = None, None
    for h, l, c in zip(prior.high, prior.low, prior.close):
        tr = h - l if prev_close is None else max(h - l, abs(h - prev_close), abs(l - prev_close))
        a = tr if a is None else (1 - 1 / PERIOD) * a + tr / PERIOD
        prev_close = c
    return a


px = messy_prices()
out = attach_atr(px, PERIOD)
assert set(out.index) == set(px.index) and len(out) == len(px), "rows lost or added"
labels = rng.choice(px.index.to_numpy(), N_CHECK, replace=False)
bad = []
for lab in labels:
    row = px.loc[lab]
    want = reference_atr(px, row.ticker, row.date)
    got = float(out.loc[lab, "atr"])
    if not (np.isclose(got, want, rtol=1e-10) or (np.isnan(got) and np.isnan(want))):
        bad.append((row.ticker, row.date.date(), got, want))

if bad:
    print(f"FAIL: {len(bad)} of {N_CHECK} rows have the wrong ATR, e.g.")
    for t, d, g, w in bad[:5]:
        print(f"   {t} {d}: engine {g:.4f}  expected {w:.4f}")
    sys.exit(1)
print(f"ALL {N_CHECK} rows: ATR equals the ticker's own Wilder ATR from strictly earlier bars")
