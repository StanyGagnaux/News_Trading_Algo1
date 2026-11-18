"""
Regression test for Bug 13 (24 Oct 2026): Strategy C must enter and exit on
the SAME price basis. Synthetic: minute bars sit 5% above the adjusted daily
bars (unadjusted for dividends); prices never move. Fixed engine: a trade
loses only its costs in either direction. Old engine: a short would gain ~1R.
Run (from the project root):  python3 tests/test_bug13_basis.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from newsdrift.strategy_c import StrategyCBacktest, StrategyCConfig

PASS = []


def check(name, cond, detail=""):
    assert cond, f"FAIL: {name} {detail}"
    PASS.append(name)
    print(f"  ok  {name} {detail}")


days = pd.bdate_range("2023-01-02", periods=40)
daily = pd.DataFrame({"date": days, "ticker": "AAA", "open": 100.0, "high": 101.0,
                      "low": 99.0, "close": 100.0})                       # adjusted basis
entry_day = days[30]
ts = pd.date_range(f"{entry_day.date()} 14:30", f"{entry_day.date()} 20:59", freq="1min", tz="UTC")
minute = pd.DataFrame({"ticker": "AAA", "ts": ts, "open": 105.0, "high": 105.0,
                       "low": 105.0, "close": 105.0})                     # 5% above: unadjusted
cfg = StrategyCConfig(exit_cost_bps=2.43)


def trades(strength, minute_bars=minute):
    ev = pd.DataFrame({"ticker": ["AAA"], "news_ts": [pd.Timestamp(f"{entry_day.date()} 15:00", tz="UTC")],
                       "strength": [strength], "duration": [2]})
    bt = StrategyCBacktest(daily, minute_bars, ev, cfg)
    return bt.candidate_table(), bt


long_tr, _ = trades(+0.8)
short_tr, _ = trades(-0.8)
check("a long and a short are both simulated", len(long_tr) == 1 and len(short_tr) == 1)
for name, tr in (("long", long_tr), ("short", short_tr)):
    r = tr.r_multiple.iloc[0]
    check(f"{name}: no price move -> loses only costs (|R| < 0.05, R < 0)", -0.05 < r < 0, f"R {r:+.4f}")
check("long and short lose the same amount (symmetric)",
      abs(long_tr.r_multiple.iloc[0] - short_tr.r_multiple.iloc[0]) < 1e-3)
late_gap = minute[minute.ts < pd.Timestamp(f"{entry_day.date()} 19:30", tz="UTC")]   # no bar near 16:00 NY
dropped, bt = trades(+0.8, late_gap)
check("no minute bar in the last 10 minutes -> trade dropped and counted", len(dropped) == 0 and bt.basis_dropped == 1)

print(f"\nALL {len(PASS)} CHECKS PASSED")
