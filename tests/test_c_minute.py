"""
Regression test for the minute-bar-only Strategy C (note `…note_c_minute_2026-10-24.md`).
Synthetic data (January -> New York = UTC-5): entry-bar stop, overnight gap
through stop and target, stop and target in one bar, time exit at the last
regular-session bar, pre/post-market bars ignored, stale exit, stop distance
as a ratio of the daily range BEFORE the entry day, entry not before
news + latency.
Run (from the project root):  python3 tests/test_c_minute.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from newsdrift.intraday import latency_cost_bps
from newsdrift.strategy_c import StrategyCConfig
from newsdrift.strategy_c_minute import StrategyCMinuteBacktest

PASS = []
CFG = StrategyCConfig(exit_cost_bps=2.43)
EXIT_COST = CFG.exit_cost_bps / 1e4
ENTRY = 100.0 * (1 + latency_cost_bps(CFG.entry_latency_min, CFG.entry_cost_base_bps,
                                      CFG.entry_cost_spike_bps, CFG.entry_cost_tau_min) / 1e4)
STOP_DIST = ENTRY * 2 * 0.02                             # 2 x mean (high - low) / close
days = pd.bdate_range("2023-01-02", periods=40)
D = 30                                                   # news / entry day


def check(name, cond, detail=""):
    assert cond, f"FAIL: {name} {detail}"
    PASS.append(name)
    print(f"  ok  {name} {detail}")


def daily(overrides=None) -> pd.DataFrame:
    df = pd.DataFrame({"date": days, "ticker": "AAA", "open": 100.0, "high": 101.0,
                       "low": 99.0, "close": 100.0})     # (high - low) / close = 2%
    for i, vals in (overrides or {}).items():
        for k, v in vals.items():
            df.loc[i, k] = v
    return df


def minute(overrides=None, sessions=(D, D + 1, D + 2), extra=()) -> pd.DataFrame:
    parts = []
    for i in sessions:
        ts = pd.date_range(f"{days[i].date()} 14:30", f"{days[i].date()} 20:59", freq="1min", tz="UTC")
        parts.append(pd.DataFrame({"ticker": "AAA", "ts": ts, "open": 100.0, "high": 100.01,
                                   "low": 99.99, "close": 100.0}))
    df = pd.concat(parts + [pd.DataFrame(list(extra))], ignore_index=True)
    for (i, hhmm), vals in (overrides or {}).items():
        idx = df.index[df.ts == pd.Timestamp(f"{days[i].date()} {hhmm}", tz="UTC")][0]
        for k, v in vals.items():
            df.loc[idx, k] = v
    return df


def run(m, d=None, strength=1.0, duration=2):
    ev = pd.DataFrame({"ticker": ["AAA"], "news_ts": [pd.Timestamp(f"{days[D].date()} 15:00", tz="UTC")],
                       "strength": [strength], "duration": [duration]})
    bt = StrategyCMinuteBacktest(d if d is not None else daily(), m, ev, CFG)
    tr = bt.candidate_table()
    assert len(tr) == 1, tr
    return tr.iloc[0], bt


t, _ = run(minute())
check("stop distance = entry x 2 x mean daily (high-low)/close (ratio)", np.isclose(t.stop_dist_bps, 400.0),
      f"{t.stop_dist_bps:.1f} bps")
check("entry at the first bar at or after news + 15 min",
      t.entry_ts == pd.Timestamp(f"{days[D].date()} 15:15", tz="UTC"))

t, _ = run(minute(), d=daily({D: {"high": 150.0, "low": 50.0}}))
check("stop distance ignores the entry day's own daily bar (no look-ahead)", np.isclose(t.stop_dist_bps, 400.0))

t, _ = run(minute({(D, "15:15"): {"low": 95.0}}))
check("stop on the entry bar exits on that bar", t.reason == "stop" and t.exit_bar_ts == t.entry_ts
      and -1.02 < t.r_multiple < -1.0, f"R {t.r_multiple:+.4f}")

t, _ = run(minute({(D + 1, "14:30"): {"open": 90.0, "high": 90.0, "low": 89.9, "close": 90.0}}))
check("overnight gap through the stop fills at the next open",
      t.reason == "stop" and np.isclose(t.r_multiple, (90 * (1 - EXIT_COST) - ENTRY) / STOP_DIST),
      f"R {t.r_multiple:+.4f}")

t, _ = run(minute({(D + 1, "14:30"): {"open": 112.0, "high": 112.0, "low": 111.9, "close": 112.0}}))
check("overnight gap through the target fills at the open",
      t.reason == "target" and np.isclose(t.r_multiple, (112 * (1 - EXIT_COST) - ENTRY) / STOP_DIST),
      f"R {t.r_multiple:+.4f}")

t, _ = run(minute({(D + 1, "15:00"): {"low": 95.0, "high": 112.0}}))
check("stop and target in the same bar -> stop", t.reason == "stop" and -1.02 < t.r_multiple < -1.0)

post = {"ticker": "AAA", "ts": pd.Timestamp(f"{days[D + 2].date()} 21:30", tz="UTC"),
        "open": 150.0, "high": 150.0, "low": 150.0, "close": 150.0}
pre = {"ticker": "AAA", "ts": pd.Timestamp(f"{days[D + 1].date()} 13:00", tz="UTC"),
       "open": 50.0, "high": 50.0, "low": 50.0, "close": 50.0}
t, _ = run(minute({(D + 2, "20:59"): {"close": 101.0}}, extra=[post, pre]))
check("time exit at the last regular-session bar of the exit day; pre/post-market ignored",
      t.reason == "time_exit" and t.exit_date == days[D + 2]
      and t.exit_bar_ts == pd.Timestamp(f"{days[D + 2].date()} 20:59", tz="UTC")
      and np.isclose(t.r_multiple, (101 * (1 - EXIT_COST) - ENTRY) / STOP_DIST), f"reason {t.reason}")

t, bt = run(minute(sessions=(D, D + 1)))
check("exit day without bars -> last earlier bar, counted as stale",
      t.reason == "time_exit" and t.exit_date == days[D + 1] and bt.stale_exits == 1)

t, _ = run(minute({(D, "15:10"): {"open": 50.0}}))
check("a bar before news + latency is never the entry",
      t.entry_ts == pd.Timestamp(f"{days[D].date()} 15:15", tz="UTC"))

t, _ = run(minute({(D + 1, "14:30"): {"open": 110.0, "high": 110.0, "low": 109.9, "close": 110.0}}), strength=-1.0)
check("short: overnight gap up through the stop fills at the open", t.reason == "stop" and t.r_multiple < -2.0,
      f"R {t.r_multiple:+.4f}")

print(f"\nALL {len(PASS)} CHECKS PASSED")
