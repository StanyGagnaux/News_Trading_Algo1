"""
Regression test for Bug 15 (note of 10 Nov 2026): every input to the size of a
Strategy A position opened at the open of day d is fixed at the close of day
d-1 -- the Kelly window (trades with exit date strictly before d), the sizing
equity and the governor throttle. Results of day d reach the sizer after the
day's last entry and act from day d+1. Synthetic data only.

Run (from the project root):  python3 tests/test_bug15_sizing_lag.py
The code of 10 Nov 2026 must FAIL it:
  BUG15_SRC=_archive/_backup_2026-11-10_before_bug15_fix/src BUG15_COLLECT=1 \
      python3 tests/test_bug15_sizing_lag.py
(BUG15_SRC: engine under test; BUG15_COLLECT=1: list every failing check
instead of stopping at the first.)
"""
import os
import sys
from dataclasses import replace

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get("BUG15_SRC") or os.path.join(HERE, "..", "src"))
from newsdrift import Config, NewsDriftBacktest
from newsdrift.risk import DrawdownGovernor, KellySizer

COLLECT = os.environ.get("BUG15_COLLECT") == "1"
PASS, FAIL = [], []
REL_TOL = 1e-9
N_DAYS = 60
HISTORY_START = 20            # first day with a history trade (ATR is defined from day 1)
D = 45                        # the entry day under test
WIN_HIGH, LOSS_LOW = 112.0, 95.0      # beyond the 2.5R target / the 1R stop of a 100 open, ATR 2
days = pd.bdate_range("2023-01-02", periods=N_DAYS)


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print(f"  ok    {name} {detail}")
        return
    if not COLLECT:
        raise AssertionError(f"FAIL: {name} {detail}")
    FAIL.append(name)
    print(f"  FAIL  {name} {detail}")


def same(a, b):
    return abs(a - b) <= REL_TOL * max(abs(a), abs(b))


def bars(ticker, outcome_by_day=None):
    """Flat 100 / 101 / 99 / 100 bars (true range 2 -> ATR 2 -> stop distance 4);
    {day index: "win" | "loss"} makes that day's range cross the target or the stop."""
    df = pd.DataFrame({"date": days, "ticker": ticker, "open": 100.0, "high": 101.0,
                       "low": 99.0, "close": 100.0})
    for i, outcome in (outcome_by_day or {}).items():
        column, level = ("high", WIN_HIGH) if outcome == "win" else ("low", LOSS_LOW)
        df.loc[i, column] = level
    return df


def signal(day_index, ticker, duration=1):
    return {"effective_date": days[day_index], "ticker": ticker, "strength": 1.0, "duration": duration}


def history(n_trades):
    """n one-day trades on separate tickers, alternating target and stop on the entry day."""
    frames, rows = [], []
    for k in range(n_trades):
        ticker = f"H{k:02d}"
        frames.append(bars(ticker, {HISTORY_START + k: "win" if k % 2 == 0 else "loss"}))
        rows.append(signal(HISTORY_START + k, ticker))
    return frames, rows


def run(frames, rows, sizer, risk_scale, **risk_overrides):
    cfg = Config()
    cfg = replace(cfg, risk=replace(cfg.risk, risk_scale=risk_scale, **risk_overrides))
    bt = NewsDriftBacktest(pd.concat(frames, ignore_index=True), pd.DataFrame(rows), cfg, sizer_kind=sizer)
    equity, trades = bt.run()
    trades = trades.assign(risk=trades.pnl / trades.r_multiple)        # risk amount actually taken
    return equity, trades, cfg, bt


def risk_of(trades, ticker):
    row = trades[trades.ticker == ticker]
    assert len(row) == 1, f"{ticker}: {len(row)} trades"
    return float(row.risk.iloc[0])


def kelly_base(trades, cfg, before):
    """Kelly fraction from the trades with exit date strictly before `before`, in log order."""
    sizer = KellySizer(cfg.risk)
    for r in trades.loc[trades.exit_date < before, "r_multiple"]:
        sizer.record_trade(r)
    return sizer.risk_fraction(1.0)


def throttle_at_close(equity, cfg, day):
    """The governor's value at the close of `day`: the engine's governor replayed on the equity curve."""
    governor = DrawdownGovernor(cfg.risk, cfg.initial_equity, probe_floor=cfg.risk.dd_probe_floor,
                                peak_halflife_days=cfg.risk.dd_peak_halflife_days)
    value = 1.0
    for level in equity[:day]:
        value = governor.update(level)
    return value


# ------------------------------------------------- 1. Kelly window: a position closing on day d
print("1. Kelly sizer: another position closes on day d at its target or at its stop")
KELLY_SCALE = 0.05                                   # keeps every notional under the 20% cap


def kelly_case(outcome):
    frames, rows = history(20)
    frames += [bars("XXX", {D: outcome}), bars("YYY"), bars("ZZZ")]
    rows += [signal(D - 1, "XXX", duration=2), signal(D, "YYY"), signal(D + 1, "ZZZ")]
    return run(frames, rows, "kelly", KELLY_SCALE)


eq_w, tr_w, cfg_k, bt_w = kelly_case("win")
eq_l, tr_l, _, bt_l = kelly_case("loss")
x_w, x_l = tr_w[tr_w.ticker == "XXX"].iloc[0], tr_l[tr_l.ticker == "XXX"].iloc[0]
check("set-up: X exits on day d, at the target in one world and at the stop in the other",
      x_w.exit_date == days[D] and x_l.exit_date == days[D] and x_w.reason == "target" and x_l.reason == "stop")
check("set-up: no exposure cap bound", not bt_w.cap_days and not bt_l.cap_days)
check("size of Y (opened at the open of d) does not depend on X's result of day d",
      same(risk_of(tr_w, "YYY"), risk_of(tr_l, "YYY")),
      f"win {risk_of(tr_w, 'YYY'):.6f} vs loss {risk_of(tr_l, 'YYY'):.6f}")
for label, eq, tr in (("win", eq_w, tr_w), ("loss", eq_l, tr_l)):
    expected = eq[days[D - 1]] * kelly_base(tr, cfg_k, days[D]) * KELLY_SCALE
    check(f"[{label}] size of Y = equity at the close of d-1 x Kelly(trades closed before d) x scale",
          same(risk_of(tr, "YYY"), expected), f"{risk_of(tr, 'YYY'):.6f} vs {expected:.6f}")
    expected_next = eq[days[D]] * kelly_base(tr, cfg_k, days[D + 1]) * KELLY_SCALE
    check(f"[{label}] size of Z (day d+1) = equity at the close of d x Kelly(trades closed through d) x scale",
          same(risk_of(tr, "ZZZ"), expected_next), f"{risk_of(tr, 'ZZZ'):.6f} vs {expected_next:.6f}")
check("the result of day d DOES change the size on day d+1 (information arrives one day later, not never)",
      not same(risk_of(tr_w, "ZZZ"), risk_of(tr_l, "ZZZ")),
      f"win {risk_of(tr_w, 'ZZZ'):.6f} vs loss {risk_of(tr_l, 'ZZZ'):.6f}")

# ------------------------------------------------- 2. equity and throttle: fixed sizer
print("2. Fixed sizer: equity and governor at the close of day d higher or lower")
FIXED_SCALE = 0.35                                   # five 0.7% risks: a day-d loss of ~3.5% moves the throttle
LOSERS = [f"X{i}" for i in range(5)]


def fixed_case(outcome):
    frames = [bars(t, {D: outcome}) for t in LOSERS] + [bars("YYY"), bars("ZZZ")]
    rows = [signal(D - 1, t, duration=2) for t in LOSERS] + [signal(D, "YYY"), signal(D + 1, "ZZZ")]
    return run(frames, rows, "fixed", FIXED_SCALE, max_gross_exposure=2.0)


eq_w, tr_w, cfg_f, _ = fixed_case("win")
eq_l, tr_l, _, _ = fixed_case("loss")
fixed_frac = cfg_f.risk.fixed_fraction * FIXED_SCALE
throttle_d = throttle_at_close(eq_l, cfg_f, days[D])
check("set-up: the losing world is in the governor's taper at the close of d, not before",
      cfg_f.risk.dd_probe_floor < throttle_d < 1.0 and throttle_at_close(eq_l, cfg_f, days[D - 1]) == 1.0,
      f"throttle {throttle_d:.4f}")
check("set-up: equity at the close of d differs between the two worlds", eq_w[days[D]] > eq_l[days[D]] * 1.05)
check("size of Y does not depend on equity or throttle at the close of d",
      same(risk_of(tr_w, "YYY"), risk_of(tr_l, "YYY")),
      f"win {risk_of(tr_w, 'YYY'):.6f} vs loss {risk_of(tr_l, 'YYY'):.6f}")
check("size of Y = equity at the close of d-1 x fixed fraction (throttle of d-1 = 1)",
      same(risk_of(tr_l, "YYY"), eq_l[days[D - 1]] * fixed_frac),
      f"{risk_of(tr_l, 'YYY'):.6f} vs {eq_l[days[D - 1]] * fixed_frac:.6f}")
check("size of Z (day d+1) = equity at the close of d x fixed fraction x throttle of the close of d",
      same(risk_of(tr_l, "ZZZ"), eq_l[days[D]] * fixed_frac * throttle_d),
      f"{risk_of(tr_l, 'ZZZ'):.6f} vs {eq_l[days[D]] * fixed_frac * throttle_d:.6f} (throttle {throttle_d:.4f})")

# ------------------------------------------------- 3. entry-day exit of an earlier ticker
print("3. Kelly sizer: an earlier ticker of the same day stops out or hits its target on its entry day")


def same_day_case(outcome):
    frames, rows = history(20)
    frames += [bars("AAP", {D: outcome}), bars("ZZQ")]            # AAP is sized before ZZQ (ticker order)
    rows += [signal(D, "AAP"), signal(D, "ZZQ")]
    return run(frames, rows, "kelly", KELLY_SCALE)


_, tr_w, _, _ = same_day_case("win")
_, tr_l, _, _ = same_day_case("loss")
check("set-up: the earlier ticker exits on its entry day in both worlds",
      all(tr[tr.ticker == "AAP"].exit_date.iloc[0] == days[D] for tr in (tr_w, tr_l)))
check("size of the later ticker does not depend on the earlier ticker's entry-day result",
      same(risk_of(tr_w, "ZZQ"), risk_of(tr_l, "ZZQ")),
      f"win {risk_of(tr_w, 'ZZQ'):.6f} vs loss {risk_of(tr_l, 'ZZQ'):.6f}")

# ------------------------------------------------- 4. results of a day without signals reach the sizer
print("4. Kelly sizer: a trade that closes on a day without signals completes the warm-up")
frames, rows = history(14)                           # 14 closed trades: one short of kelly_min_trades
frames += [bars("LST"), bars("NXT")]
rows += [signal(40, "LST"), signal(43, "NXT")]       # LST: time exit at the close of day 41 (no signals that day)
eq, tr, cfg, _ = run(frames, rows, "kelly", KELLY_SCALE)
lst = tr[tr.ticker == "LST"].iloc[0]
check("set-up: the 15th trade closes by time on a day without signals",
      lst.reason == "time" and lst.exit_date == days[41] and (tr.exit_date < days[43]).sum() == cfg.risk.kelly_min_trades)
warm_up = eq[days[42]] * cfg.risk.fixed_fraction * KELLY_SCALE
expected = eq[days[42]] * kelly_base(tr, cfg, days[43]) * KELLY_SCALE
check("the next entry is sized by the Kelly estimate of 15 trades, not by the warm-up fraction",
      same(risk_of(tr, "NXT"), expected) and not same(expected, warm_up),
      f"{risk_of(tr, 'NXT'):.6f} vs Kelly {expected:.6f} (warm-up would be {warm_up:.6f})")

# ------------------------------------------------- 5. the engine's own record
print("5. Engine sizing log (new engine only)")
_, _, _, bt = kelly_case("win")
log = getattr(bt, "sizing_log", None)
check("the engine records every sizing call", log is not None and len(log) > 0)
if log is not None and len(log):
    log = pd.DataFrame(log, columns=bt.SIZING_LOG_COLUMNS)
    past_warm_up = log[log.window_n > 0]
    check("newest exit date in the Kelly window is strictly before the entry date, every call",
          bool((past_warm_up.window_newest_exit < past_warm_up.date).all()), f"{len(past_warm_up)} calls")

if FAIL:
    print(f"\n{len(FAIL)} OF {len(PASS) + len(FAIL)} CHECKS FAILED: " + "; ".join(FAIL))
    sys.exit(1)
print(f"\nALL {len(PASS)} CHECKS PASSED")
