"""
Regression test for Bug 17 (note of 14 Nov 2026): the entry step of Strategy A must admit positions on the
book as it stood at the close of d-1, not on the book after day d's exits. Rule: a ticker held at the previous
close is not entered at the open of d, whatever happens to that position during d; the gross figure of the
cap test is the notional of the positions held at the previous close plus the notional of the entries already
admitted at this open, whether or not they are still open at the close of d. Synthetic data only.

Run (from the project root):  python3 tests/test_bug17_admission_snapshot.py
The code before the fix must FAIL each of the three cases:
  BUG17_SRC=_archive/_backup_2026-11-14_before_bug17_fix/src BUG17_COLLECT=1 python3 tests/test_bug17_admission_snapshot.py
"""
import os
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get("BUG17_SRC") or os.path.join(HERE, "..", "src"))
from newsdrift import Config, NewsDriftBacktest

COLLECT = os.environ.get("BUG17_COLLECT") == "1"
PASS, FAIL = [], []
N_DAYS, ENTRY = 60, 30                      # first entries at the open of day 30
STRENGTH = 0.6                              # fixed sizer: 2% risk; target at 2R
POSITION_FRAC = 0.20                        # every position is cut to the 20% position cap
days = pd.bdate_range("2023-01-02", periods=N_DAYS)


def config(max_gross: float) -> Config:
    """No governor, scale 1: risk 2,000 on a stop distance of 4 asks for 50,000 notional, so the 20% position
    cap binds and every position posts exactly 20% of the sizing equity."""
    base = Config()
    return replace(base, risk=replace(base.risk, use_dd_governor=False, risk_scale=1.0,
                                      max_position_frac=POSITION_FRAC, max_gross_exposure=max_gross))


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print(f"  ok    {name} {detail}")
        return
    if not COLLECT:
        raise AssertionError(f"FAIL: {name} {detail}")
    FAIL.append(name)
    print(f"  FAIL  {name} {detail}")


def bars(ticker, high=None, low=None):
    """Quiet bars (open = close = 100, range 2: ATR 2, stop distance 4, target distance 8); `high` / `low`
    replace the high / low of single days, {day index: price}."""
    df = pd.DataFrame({"date": days, "ticker": ticker, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0})
    for column, changes in (("high", high), ("low", low)):
        for i, price in (changes or {}).items():
            df.loc[i, column] = price
    return df


def run(frames, signals, max_gross=1.0):
    """signals: list of (day index, ticker, duration). Returns (equity, trades, sizing log)."""
    sig = pd.DataFrame({"effective_date": [days[i] for i, _, _ in signals], "ticker": [t for _, t, _ in signals],
                        "strength": STRENGTH, "duration": [n for _, _, n in signals]})
    bt = NewsDriftBacktest(pd.concat(frames, ignore_index=True), sig, config(max_gross), sizer_kind="fixed")
    eq, tr = bt.run()
    log = pd.DataFrame(bt.sizing_log, columns=bt.SIZING_LOG_COLUMNS)
    return eq, tr, log


def entries(tr, ticker, day_index):
    return int(((tr.ticker == ticker) & (tr.entry_date == days[day_index])).sum()) if len(tr) else 0


def opened(log, ticker, day_index):
    """Positions opened according to the engine's own record (also those still open at the end)."""
    return int(((log.ticker == ticker) & (log.date == days[day_index]) & log.opened).sum()) if len(log) else 0


def reentries_on_exit_day(tr) -> int:
    """Trades whose entry date equals the exit date of the previous trade in the same ticker."""
    t = tr.sort_values(["ticker", "entry_date", "exit_date"])
    return int((t.entry_date == t.groupby("ticker").exit_date.shift(1)).sum())


D = ENTRY + 1                               # the day whose exits must not change that day's admissions

# ------------------------------------------------- 1. eligibility
print("1. A held ticker whose target is hit on day d is not entered again at the open of d")
held = [bars("HLD", high={D: 110.0}), bars("LIVE")]            # long from day 30; target (entry + 8) hit on day 31
eq, tr, log = run(held, [(ENTRY, "HLD", 3), (D, "HLD", 3)])
first = tr[(tr.ticker == "HLD") & (tr.entry_date == days[ENTRY])]
check("set-up: the position of day 30 leaves by its target on day d",
      len(first) == 1 and first.reason.iloc[0] == "target" and first.exit_date.iloc[0] == days[D])
check("no entry in that ticker at the open of d", entries(tr, "HLD", D) == 0 and opened(log, "HLD", D) == 0,
      f"{opened(log, 'HLD', D)} opened on d")
check("no trade is entered on the exit day of an earlier trade in its ticker", reentries_on_exit_day(tr) == 0,
      f"{reentries_on_exit_day(tr)} such trades")
eq, tr, log = run(held, [(ENTRY, "HLD", 3), (D, "HLD", 3), (D + 1, "HLD", 2)])
check("with a further signal effective d+1: still no entry at d", opened(log, "HLD", D) == 0)
check("with a further signal effective d+1: the ticker is entered at d+1", opened(log, "HLD", D + 1) == 1,
      f"{opened(log, 'HLD', D + 1)} opened on d+1")

# ------------------------------------------------- 2. gross cap on the book of the previous close
print("2. Capacity freed during day d does not admit an entry at the open of d")
GROSS = 0.5                                 # two positions of 20% fill the book: a third (60%) is refused
book = [bars("AAA", high={D: 110.0}), bars("BBB"), bars("CCC"), bars("LIVE")]   # AAA leaves by its target on d
eq, tr, log = run(book, [(ENTRY, "AAA", 3), (ENTRY, "BBB", 3), (D, "CCC", 2)], max_gross=GROSS)
check("set-up: two positions are held at the close of d-1 and one of them is closed during d",
      opened(log, "AAA", ENTRY) == 1 and opened(log, "BBB", ENTRY) == 1
      and len(tr[tr.ticker == "AAA"]) == 1 and (tr[tr.ticker == "AAA"].exit_date == days[D]).all())
check("the signal in another ticker effective d is refused", opened(log, "CCC", D) == 0, f"{opened(log, 'CCC', D)} opened on d")
eq, tr, log = run(book, [(ENTRY, "AAA", 3), (ENTRY, "BBB", 3), (D + 1, "CCC", 2)], max_gross=GROSS)
check("the freed capacity is available from d+1", opened(log, "CCC", D + 1) == 1)

# ------------------------------------------------- 3. entries of the same open count, open or not
print("3. An entry that stops out on its entry day still counts for the later tickers of the same open")
GROSS = 0.3                                 # one position of 20% leaves no room for a second
same_open = [bars("AAA", low={ENTRY: 90.0}), bars("BBB"), bars("LIVE")]         # AAA: stop (entry - 4) hit on its entry day
eq, tr, log = run(same_open, [(ENTRY, "AAA", 3), (ENTRY, "BBB", 3)], max_gross=GROSS)
aaa = tr[tr.ticker == "AAA"] if len(tr) else tr
check("set-up: the first ticker is admitted and stops out on its entry day",
      len(aaa) == 1 and aaa.reason.iloc[0] == "stop" and aaa.exit_date.iloc[0] == days[ENTRY] == aaa.entry_date.iloc[0])
check("the second ticker of the same open is refused", opened(log, "BBB", ENTRY) == 0, f"{opened(log, 'BBB', ENTRY)} opened")
eq, tr, log = run(same_open, [(ENTRY, "AAA", 3), (ENTRY + 1, "BBB", 3)], max_gross=GROSS)
check("one day later the second ticker is admitted", opened(log, "BBB", ENTRY + 1) == 1)

# ------------------------------------------------- 4. the engine's own record
print("4. Sizing log: the gross figure of every admission test (new engine only)")
eq, tr, log = run(same_open, [(ENTRY, "AAA", 3), (ENTRY, "BBB", 3)], max_gross=GROSS)
has_column = "gross_at_decision" in log.columns
check("the sizing log has the column gross_at_decision", has_column)
if has_column:
    gross = log.set_index("ticker").gross_at_decision
    notional = POSITION_FRAC * Config().initial_equity
    check("first call of the open: gross 0; second call: the notional admitted before it",
          abs(gross["AAA"]) < 1e-9 and abs(gross["BBB"] - notional) < 1e-6, f"{gross['AAA']:.2f}, {gross['BBB']:.2f}")

if FAIL:
    print(f"\n{len(FAIL)} OF {len(PASS) + len(FAIL)} CHECKS FAILED: " + "; ".join(FAIL))
    sys.exit(1)
print(f"\nALL {len(PASS)} CHECKS PASSED")
