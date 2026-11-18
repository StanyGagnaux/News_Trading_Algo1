"""
Regression test for Bug 14 (note of 24 Oct 2026): stop/target fills.
Gap through the stop -> fill at the open; gap through the target -> fill at
the open; stop and target in one bar -> stop; stops checked from the entry
day (A) / entry bar (B); C1 never uses its entry day's range (entry at the
close). Synthetic data only.
Run (from the project root):  python3 tests/test_bug14_fills.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from newsdrift import Config, NewsDriftBacktest
from newsdrift.risk import barrier_exit
from newsdrift.intraday import IntradayBacktest, IntradayConfig
from newsdrift.strategy_c import StrategyCBacktest, StrategyCConfig

PASS = []
COST = 2.43 / 1e4


def check(name, cond, detail=""):
    assert cond, f"FAIL: {name} {detail}"
    PASS.append(name)
    print(f"  ok  {name} {detail}")


print("helper")
check("long gap below stop fills at the open", barrier_exit(1, 90, 91, 89, 96, 110) == (90, "stop"))
check("long gap above target fills at the open", barrier_exit(1, 112, 113, 111, 96, 110) == (112, "target"))
check("long both touched, no gap -> stop", barrier_exit(1, 100, 112, 95, 96, 110) == (96, "stop"))
check("short gap above stop fills at the open", barrier_exit(-1, 110, 111, 109, 104, 90) == (110, "stop"))
check("short gap below target fills at the open", barrier_exit(-1, 88, 89, 87, 104, 90) == (88, "target"))
check("no touch -> no exit", barrier_exit(1, 100, 101, 99, 96, 110) == (None, None))

# ---------------------------------------------------------------- A (daily)
days = pd.bdate_range("2023-01-02", periods=40)
D = 30                                                  # entry day index


def daily(overrides: dict) -> pd.DataFrame:
    df = pd.DataFrame({"date": days, "ticker": "AAA", "open": 100.0, "high": 101.0,
                       "low": 99.0, "close": 100.0})    # TR 2 -> ATR 2
    for i, vals in overrides.items():
        for k, v in vals.items():
            df.loc[i, k] = v
    return df


def run_a(overrides, duration=2):
    sig = pd.DataFrame({"effective_date": [days[D]], "ticker": ["AAA"],
                        "strength": [1.0], "duration": [duration]})
    _, tr = NewsDriftBacktest(daily(overrides), sig, Config(), sizer_kind="fixed").run()
    assert len(tr) == 1, tr
    return tr.iloc[0]


print("Strategy A")
COST_A = Config().cost.per_side_bps / 1e4          # engine default cost
t = run_a({D: {"low": 95.0}})
check("A: stop on the entry day exits that day at the stop",
      t.reason == "stop" and t.exit_date == t.entry_date and -1.01 < t.r_multiple < -1.0, f"R {t.r_multiple:+.4f}")
t = run_a({D + 1: {"open": 90.0, "high": 91.0, "low": 89.0, "close": 90.0}})
sd = t.stop_dist_bps / 1e4 * t.entry
expect = (90 * (1 - COST_A) - t.entry) / sd
check("A: gap through the stop fills at the open (loss > 1R)",
      t.reason == "stop" and np.isclose(t.r_multiple, expect) and t.r_multiple < -2, f"R {t.r_multiple:+.4f}")
t = run_a({D + 1: {"open": 112.0, "high": 113.0, "low": 111.0, "close": 112.0}})
check("A: gap through the target fills at the open",
      t.reason == "target" and np.isclose(t.exit, 112 * (1 - COST_A)), f"exit {t.exit:.4f}")
t = run_a({D + 1: {"low": 95.0, "high": 112.0}})
check("A: stop and target in the same bar -> stop", t.reason == "stop" and -1.01 < t.r_multiple < -1.0)
t = run_a({})
check("A: untouched trade still time-exits after `duration` days",
      t.reason == "time" and t.exit_date == days[D + 2])

# ---------------------------------------------------------------- B (minute)
DAY = "2023-03-01"


def minute(overrides: dict) -> pd.DataFrame:
    ts = pd.date_range(f"{DAY} 14:30", f"{DAY} 19:59", freq="1min", tz="UTC")
    close = np.where(np.arange(len(ts)) % 2 == 0, 100.0, 100.2)   # vol from pre-entry bars
    df = pd.DataFrame({"ticker": "AAA", "ts": ts, "open": close, "high": close + 0.01,
                       "low": close - 0.01, "close": close})
    for hhmm, vals in overrides.items():
        i = df.index[df.ts == pd.Timestamp(f"{DAY} {hhmm}", tz="UTC")][0]
        for k, v in vals.items():
            df.loc[i, k] = v
    return df


def run_b(overrides):
    ev = pd.DataFrame({"ticker": ["AAA"], "news_ts": [pd.Timestamp(f"{DAY} 15:00", tz="UTC")],
                       "strength": [1.0], "duration": [1]})
    bt = IntradayBacktest(minute(overrides), ev, IntradayConfig(entry_latency_min=5, cost_base_bps=2.43))
    out = bt._simulate_trade(next(ev.itertuples(index=False)))
    assert out is not None
    return out


print("Strategy B")
o = run_b({"15:05": {"open": 100.0, "low": 99.0}})
check("B: stop on the entry bar exits on that bar",
      o["reason"] == "stop" and o["exit_ts"] == o["entry_ts"], f"R {o['r_multiple']:+.4f}")
o = run_b({"15:05": {"open": 100.0}, "15:06": {"open": 98.0, "high": 98.0, "low": 97.9, "close": 98.0}})
check("B: gap through the stop fills at the open (loss > 1R)", o["reason"] == "stop" and o["r_multiple"] < -1.5,
      f"R {o['r_multiple']:+.4f}")

# ---------------------------------------------------------------- C1 (close entry)
print("Strategy C1")


def run_c1(overrides):
    ev = pd.DataFrame({"ticker": ["AAA"], "news_ts": [pd.Timestamp(f"{days[D].date()} 15:00", tz="UTC")],
                       "strength": [0.8], "duration": [2]})
    no_minutes = pd.DataFrame({"ticker": ["ZZZ"], "ts": [pd.Timestamp("2020-01-02 15:00", tz="UTC")],
                               "open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0]})
    tr = StrategyCBacktest(daily(overrides), no_minutes, ev,
                           StrategyCConfig(exit_cost_bps=2.43, entry_mode="close")).candidate_table()
    assert len(tr) == 1
    return tr.iloc[0]


t = run_c1({D: {"low": 50.0}, D + 1: {"open": 90.0, "high": 91.0, "low": 89.0, "close": 90.0}})
entry = 100 * (1 + COST)
sd = t.stop_dist_bps / 1e4 * entry
check("C1: overnight gap through the stop fills at the next open",
      t.reason == "stop" and np.isclose(t.r_multiple, (90 * (1 - COST) - entry) / sd), f"R {t.r_multiple:+.4f}")
t = run_c1({D: {"low": 50.0}})
check("C1: the entry day's range (before the close entry) is never used",
      t.reason == "time_exit", f"reason {t.reason}")

print(f"\nALL {len(PASS)} CHECKS PASSED")
