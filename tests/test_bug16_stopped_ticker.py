"""
Regression test for Bug 16 (note of 10 Nov 2026): a Strategy A position in a ticker that stops trading must
be closed. Rule: positions are marked at their last available close; the holding period is counted on the
trading calendar; a time exit that falls on a day without a bar fills at the last available close (reason
"stale") and is booked like any other trade. Synthetic data only.

Run (from the project root):  python3 tests/test_bug16_stopped_ticker.py
The code before the fix must FAIL it:
  BUG16_SRC=_archive/_backup_2026-11-10_before_bug16_fix/src BUG16_COLLECT=1 python3 tests/test_bug16_stopped_ticker.py
"""
import os
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get("BUG16_SRC") or os.path.join(HERE, "..", "src"))
from newsdrift import Config, NewsDriftBacktest

COLLECT = os.environ.get("BUG16_COLLECT") == "1"
PASS, FAIL = [], []
ENTRY, DURATION, N_DAYS = 30, 2, 60                  # entry at the open of day 30, time exit at the close of day 32
days = pd.bdate_range("2023-01-02", periods=N_DAYS)
cfg = replace(Config(), risk=replace(Config().risk, use_dd_governor=False, risk_scale=0.1))
COST = cfg.cost.per_side_bps / 1e4


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print(f"  ok    {name} {detail}")
        return
    if not COLLECT:
        raise AssertionError(f"FAIL: {name} {detail}")
    FAIL.append(name)
    print(f"  FAIL  {name} {detail}")


def bars(ticker, keep=None, drift=0.0):
    """Quiet bars (range 2 around 100: ATR 2, stop distance 4, no stop or target is reached)."""
    close = 100.0 + drift * np.arange(N_DAYS)
    df = pd.DataFrame({"date": days, "ticker": ticker, "open": close, "high": close + 1.0, "low": close - 1.0, "close": close})
    return df if keep is None else df[keep(np.arange(N_DAYS))]


def run(frames, ticker):
    sig = pd.DataFrame({"effective_date": [days[ENTRY]], "ticker": [ticker], "strength": [0.6], "duration": [DURATION]})
    return NewsDriftBacktest(pd.concat(frames, ignore_index=True), sig, cfg, sizer_kind="fixed").run()


print("a ticker stops trading while a position is open (last bar on day 31, time exit due on day 32)")
eq, tr = run([bars("STOP", keep=lambda i: i <= ENTRY + 1, drift=0.1), bars("LIVE")], "STOP")
check("the position is closed and booked", len(tr) == 1, f"{len(tr)} trades")
if len(tr) == 1:
    t = tr.iloc[0]
    last_close = 100.0 + 0.1 * (ENTRY + 1)
    check("it exits on its time-exit day of the trading calendar, reason 'stale'", t.exit_date == days[ENTRY + 2] and t.reason == "stale",
          f"exit {pd.Timestamp(t.exit_date).date()}, reason {t.reason}")
    check("the fill is the last available close, exit cost applied", abs(t.exit - last_close * (1 - COST)) < 1e-9, f"{t.exit:.6f}")
    check("equity changes by the trade result only", abs(eq.iloc[-1] - cfg.initial_equity - t.pnl) < 1e-6,
          f"equity change {eq.iloc[-1] - cfg.initial_equity:+.4f}, trade result {t.pnl:+.4f}")
check("the position's value never drops out of equity", eq.min() > cfg.initial_equity - 50,
      f"lowest equity {eq.min():.2f}")
check("equity equals the sum of booked results at the end (nothing left open)", abs(eq.iloc[-1] - cfg.initial_equity - (tr.pnl.sum() if len(tr) else 0.0)) < 1e-6)

print("a one-day gap in the ticker's bars inside the holding period (no bar on day 31)")
eq, tr = run([bars("GAP", keep=lambda i: i != ENTRY + 1), bars("LIVE")], "GAP")
check("holding days are counted on the trading calendar: exit at the close of day 32, reason 'time'",
      len(tr) == 1 and tr.exit_date.iloc[0] == days[ENTRY + 2] and tr.reason.iloc[0] == "time",
      f"exit {pd.Timestamp(tr.exit_date.iloc[0]).date() if len(tr) else None}")
check("on the day without a bar the position is marked at its last close (equity has no hole)",
      abs(eq[days[ENTRY + 1]] - eq[days[ENTRY]]) < 1e-9 or abs(eq[days[ENTRY + 1]] - cfg.initial_equity) < 5,
      f"equity {eq[days[ENTRY + 1]]:.2f}")

print("a ticker with all its bars is unaffected")
eq, tr = run([bars("FULL"), bars("LIVE")], "FULL")
check("normal time exit at the close of day 32", len(tr) == 1 and tr.exit_date.iloc[0] == days[ENTRY + 2] and tr.reason.iloc[0] == "time")

if FAIL:
    print(f"\n{len(FAIL)} OF {len(PASS) + len(FAIL)} CHECKS FAILED: " + "; ".join(FAIL))
    sys.exit(1)
print(f"\nALL {len(PASS)} CHECKS PASSED")
