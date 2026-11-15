"""
Tests for the Sept 2026 fixes (CLAUDE.md section 7):
  Bug 2 -- sizing must not change WHICH signals trade
  Bug 3 -- drawdown governor must act in Strategies B and C
  Bug 5 -- B/C events must be point-in-time (no same-day look-ahead, no
           duplicated trades from one daily signal)
Run (from the project root):  python3 tests/test_portfolio_fixes.py
"""
import os
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from newsdrift import (ReplayConfig, replay, build_event_table, Config,
                       make_synthetic_intraday, IntradayBacktest, IntradayConfig)

T0 = pd.Timestamp("2022-01-03 15:00", tz="UTC")
PASS = []


def check(name, cond, detail=""):
    assert cond, f"FAIL: {name} {detail}"
    PASS.append(name); print(f"  ok  {name} {detail}")


def cands(n, r, overlap_days=0.0, ticker=None, strength=0.8, spacing_days=1.0):
    rows = []
    for i in range(n):
        e = T0 + pd.Timedelta(days=i * spacing_days)
        rows.append({"ticker": ticker or f"T{i % 50:02d}", "strength": strength,
                     "entry_ts": e,
                     "exit_ts": e + pd.Timedelta(hours=1) + pd.Timedelta(days=overlap_days),
                     "r_multiple": r[i] if hasattr(r, "__len__") else r})
    return pd.DataFrame(rows)


print("Bug 2 -- admission independent of sizer")
rng = np.random.default_rng(0)
# losing-ish history drives Kelly f* to 0 -> probe floor (4x smaller bets)
r = np.where(rng.random(3000) < 0.30, 2.0, -1.0)
c = cands(3000, r, overlap_days=2.5, spacing_days=0.05)
off = dict(use_dd_governor=False)
_, tf, sf = replay(c, ReplayConfig(sizer="fixed", **off))
_, tk, sk = replay(c, ReplayConfig(sizer="kelly", **off))
check("kelly actually hits probe floor (smaller bets)",
      tk.risk_frac.median() < 0.5 * tf.risk_frac.median(),
      f"median frac kelly {tk.risk_frac.median():.4f} vs fixed {tf.risk_frac.median():.4f}")
ratio = len(tk) / len(tf)
check("trade counts comparable fixed vs kelly", 0.8 < ratio < 1.25,
      f"fixed {len(tf)} kelly {len(tk)} (old code: several x apart)")
same = len(set(tf.entry_ts) & set(tk.entry_ts)) / max(len(tf), 1)
check("same signals admitted", same > 0.8, f"overlap {same:.0%}")

print("Bug 3 -- governor binds")
lose = cands(400, -1.0)                          # 400 sequential losers, no overlap
_, t_off, _ = replay(lose, ReplayConfig(use_dd_governor=False))
e_off, _, _ = replay(lose, ReplayConfig(use_dd_governor=False))
e_des, t_des, s_des = replay(lose, ReplayConfig(use_dd_governor=True))
e_str, t_str, s_str = replay(lose, ReplayConfig(use_dd_governor=True, dd_probe_floor=0.0,
                                                 dd_peak_halflife_days=None))
dd = lambda e: float((1 - e / e.cummax().clip(lower=100_000)).max())
check("no governor -> unbounded loss", dd(e_off) > 0.9, f"maxDD {dd(e_off):.1%}")
check("designed governor throttles", dd(e_des) < dd(e_off) and s_des["governor_throttled"] > 0,
      f"maxDD {dd(e_des):.1%}, throttled {s_des['governor_throttled']}")
check("strict governor holds the cap", dd(e_str) <= 0.05 + 0.011,
      f"maxDD {dd(e_str):.1%} (cap 5% + one trade's risk)")
# death-spiral guard still works for the designed variant: it keeps trading
check("designed governor never goes to zero size", (t_des.risk_amount > 0).all()
      and len(t_des) == 400, f"{len(t_des)} trades")

print("Concurrent cap binds on ACTUAL risk (kelly can size above reference)")
win = np.where(rng.random(2000) < 0.6, 2.0, -1.0)          # strong history -> big kelly
cw = cands(2000, win, overlap_days=3, spacing_days=0.02)
_, tkw, skw = replay(cw, ReplayConfig(sizer="kelly", use_dd_governor=False))
check("scaling kicks in when kelly > room", skw["scaled_to_cap"] > 0, f"scaled {skw['scaled_to_cap']}")
worst = 0.0
for _, t in tkw.iterrows():
    live = tkw[(tkw.entry_ts <= t.entry_ts) & (tkw.exit_ts > t.entry_ts)]
    worst = max(worst, live.risk_amount.sum() / t.equity_at_entry)
check("open actual risk never above 4% of equity at any entry", worst <= 0.04 + 1e-9,
      f"worst {worst:.4%}")

print("One position per ticker")
stack = cands(50, 1.0, overlap_days=2, ticker="AAPL", spacing_days=0.001)
_, ts_, ss_ = replay(stack, ReplayConfig(use_dd_governor=False))
check("stacked same-ticker headlines -> 1 trade", len(ts_) == 1 and ss_["ticker_open"] == 49)
_, ts2, _ = replay(stack, ReplayConfig(use_dd_governor=False, one_position_per_ticker=False))
check("--allow-stacking restores old behaviour", len(ts2) > 1, f"{len(ts2)} trades")

print("Bug 5 -- point-in-time events")
class FakeScorer:
    table = {"early good": (0.9, 2), "late bad": (-0.9, 1), "noise": (0.05, 1),
             "same-second a": (0.6, 1), "same-second b": (0.2, 3)}
    def score(self, h, t=""): return self.table.get(h, (0.0, 1))
news = pd.DataFrame({
    "timestamp": pd.to_datetime(["2022-03-01 14:40", "2022-03-01 18:00",
                                 "2022-03-01 15:00", "2022-03-01 16:00",
                                 "2022-03-01 16:00", "2022-03-01 17:00"], utc=True),
    "ticker": ["X", "X", "X", "Y", "Y", "Z"],
    "headline": ["early good", "late bad", "noise", "same-second a", "same-second b",
                 "never scored"]})
ev = build_event_table(news, FakeScorer(), Config().signal)
early = ev[(ev.ticker == "X") & (ev.news_ts.dt.hour == 14)]
check("early event unaffected by later headline", len(early) == 1
      and early.strength.iloc[0] == 0.9, f"strength {early.strength.tolist()}")
check("noise-gated headline creates no event", (ev.news_ts.dt.hour == 15).sum() == 0)
check("unscored headline creates no event", (ev.ticker == "Z").sum() == 0)
y = ev[ev.ticker == "Y"]
check("same-timestamp headlines netted", len(y) == 1 and abs(y.strength.iloc[0] - 0.4) < 1e-9
      and y.duration.iloc[0] == 3)
check("one row per (ticker, ts)", not ev.duplicated(["ticker", "news_ts"]).any())

print("End-to-end: planted edge still recovered by Strategy B engine")
bars, events = make_synthetic_intraday(n_events=300, seed=1)
eq, tr = IntradayBacktest(bars, events, IntradayConfig(entry_latency_min=5)).run()
check("synthetic run produces trades", len(tr) > 100, f"{len(tr)} trades")
check("planted continuation edge positive", tr.r_multiple.mean() > 0,
      f"mean R {tr.r_multiple.mean():+.3f}")
print("Scale-out exits (half at 1R, runner to breakeven / trail)")
from newsdrift.intraday import scale_out_legs


def path(hl_close):
    """First row = entry bar (skipped by the walker); then (high, low, close)."""
    rows = [(100.0, 100.0, 100.0)] + list(hl_close)
    ts = [T0 + pd.Timedelta(minutes=i) for i in range(len(rows))]
    return pd.DataFrame({"ts": ts, "open": [r[2] for r in rows],
                         "high": [r[0] for r in rows], "low": [r[1] for r in rows],
                         "close": [r[2] for r in rows]})


def legs_r(legs, direction, entry=100.0, stop_dist=1.0):
    return sum(f * direction * (px - entry) for f, px, _ in legs) / stop_dist


half = IntradayConfig(partial_exit_r=1.0, partial_exit_frac=0.5)
trail = IntradayConfig(partial_exit_r=1.0, partial_exit_frac=0.5, trail_r=1.0)
legs, why = scale_out_legs(path([(101.2, 100.1, 101.0), (100.5, 99.9, 100.2)]),
                           1, 100.0, 1.0, half, "eod")
check("half at 1R, rest stopped at breakeven", why == "partial_stop"
      and abs(legs_r(legs, 1) - 0.5) < 1e-9, f"R {legs_r(legs, 1):+.2f}")
legs, why = scale_out_legs(path([(101.5, 98.9, 100.0)]), 1, 100.0, 1.0, half, "eod")
check("stop before target in the same bar (pessimistic)", why == "stop"
      and abs(legs_r(legs, 1) + 1.0) < 1e-9, f"R {legs_r(legs, 1):+.2f}")
legs, why = scale_out_legs(path([(101.0, 100.2, 100.8), (104.0, 101.5, 103.8),
                                 (103.5, 102.8, 103.0)]), 1, 100.0, 1.0, trail, "eod")
check("runner trails 1R behind the best price", why == "partial_stop"
      and abs(legs_r(legs, 1) - 2.0) < 1e-9, f"R {legs_r(legs, 1):+.2f}")
legs, why = scale_out_legs(path([(99.8, 98.9, 99.0), (100.1, 99.5, 99.9)]),
                           -1, 100.0, 1.0, half, "eod")
check("short side mirrors the long logic", why == "partial_stop"
      and abs(legs_r(legs, -1) - 0.5) < 1e-9, f"R {legs_r(legs, -1):+.2f}")
legs, why = scale_out_legs(path([(100.5, 99.5, 100.2)]), 1, 100.0, 1.0, half, "eod")
check("no move -> whole position out at the close", why == "eod"
      and len(legs) == 1 and abs(legs_r(legs, 1) - 0.2) < 1e-9)
bars_s, events_s = make_synthetic_intraday(n_events=300)
_, tr_s = IntradayBacktest(bars_s, events_s, IntradayConfig(
    entry_latency_min=5, partial_exit_r=1.0, trail_r=1.0)).run()
check("scale-out engine runs end-to-end", len(tr_s) > 0 and tr_s.partial_hit.any(),
      f"{len(tr_s)} trades, {tr_s.partial_hit.mean():.0%} took the partial")

print("New entry variants (confirmation filter, C at the news-day close)")
from newsdrift.intraday import confirms_direction
from newsdrift.strategy_c import StrategyCBacktest, StrategyCConfig
from types import SimpleNamespace

mins = pd.DataFrame({"ts": [T0 + pd.Timedelta(minutes=i) for i in range(1, 15)],
                     "open": 100.0})
at_entry = lambda px: SimpleNamespace(ts=T0 + pd.Timedelta(minutes=15), open=px)
check("confirmation passes when price moved with the signal",
      confirms_direction(mins, T0, at_entry(100.5), 1, 0.0))
check("confirmation rejects a move against the signal",
      not confirms_direction(mins, T0, at_entry(99.5), 1, 0.0)
      and confirms_direction(mins, T0, at_entry(99.5), -1, 0.0))
check("confirmation rejects when no post-news bar before entry",
      not confirms_direction(mins.iloc[:0], T0, at_entry(101.0), 1, 0.0))

days = pd.bdate_range("2022-01-03", periods=20)
daily = pd.DataFrame({"date": days, "ticker": "X", "open": 100.0, "high": 101.0,
                      "low": 99.0, "close": 100.0})
daily.loc[16, ["high", "low", "close"]] = [104.5, 99.0, 104.0]
news_c = pd.Timestamp(days[15], tz="UTC") + pd.Timedelta(hours=15)
ev_c = pd.DataFrame({"ticker": ["X"], "news_ts": [news_c], "strength": [0.8],
                     "duration": [1]})
bt_c = StrategyCBacktest(daily, pd.DataFrame(columns=["ticker", "ts"]), ev_c,
                         StrategyCConfig(entry_mode="close", exit_cost_bps=0.0,
                                         tp_r_multiple=1e9))
trade_c = bt_c._simulate_trade(next(ev_c.itertuples(index=False)))
check("C close entry: enters at the news-day close, after the news",
      trade_c["entry_ts"] > news_c and trade_c["entry_ts"].date() == days[15].date())
check("C close entry: R computed from the close (hand check +1.0R)",
      abs(trade_c["r_multiple"] - 1.0) < 1e-9, f"R {trade_c['r_multiple']:+.2f}")

print("Strategy D -- next-day open-to-close")
from newsdrift.open_close import OpenCloseBacktest, OpenCloseConfig
daily_d = daily.copy()
daily_d.loc[16, ["open", "high", "low", "close"]] = [100.0, 102.5, 99.5, 102.0]
sig_d = pd.DataFrame({"news_date": [days[15]], "effective_date": [days[16]],
                      "ticker": ["X"], "strength": [0.8], "duration": [1]})
bt_d = OpenCloseBacktest(daily_d, sig_d, OpenCloseConfig(cost_bps=0.0))
tr_d = bt_d._simulate_trade(next(sig_d.itertuples(index=False)))
check("D long: open 100 -> close 102, 1R = 2 x range 2 = 4 -> +0.5R",
      abs(tr_d["r_multiple"] - 0.5) < 1e-9, f"R {tr_d['r_multiple']:+.2f}")
check("D enters at the open and exits the same day's close",
      tr_d["entry_ts"].date() == tr_d["exit_ts"].date() == days[16].date()
      and tr_d["exit_ts"] > tr_d["entry_ts"])
short_d = sig_d.assign(strength=-0.8)
tr_ds = bt_d._simulate_trade(next(short_d.itertuples(index=False)))
check("D short mirrors the long", abs(tr_ds["r_multiple"] + 0.5) < 1e-9)
same_day = sig_d.assign(effective_date=days[15])
try:
    bt_d._simulate_trade(next(same_day.itertuples(index=False)))
    lookahead_caught = False
except AssertionError:
    lookahead_caught = True
check("D refuses to trade on the news day itself (look-ahead guard)", lookahead_caught)

print("Strategy N -- first close after the news -> next open")
from newsdrift.open_close import OvernightBacktest
daily_n = daily.copy()
daily_n.loc[16, ["open", "close"]] = [102.0, 102.0]
bt_n = OvernightBacktest(daily_n, pd.DataFrame(), OpenCloseConfig(cost_bps=0.0))
ev_in = SimpleNamespace(ticker="X", strength=0.8,
                        news_ts=pd.Timestamp(days[15], tz="UTC") + pd.Timedelta(hours=15))
tr_n = bt_n._simulate_trade(ev_in)
check("N: in-session news -> buy that close 100, sell next open 102 -> +0.5R",
      abs(tr_n["r_multiple"] - 0.5) < 1e-9 and tr_n["entry_ts"].date() == days[15].date(),
      f"R {tr_n['r_multiple']:+.2f}")
ev_late = SimpleNamespace(ticker="X", strength=0.8,
                          news_ts=pd.Timestamp(days[15], tz="UTC") + pd.Timedelta(hours=22))
tr_late = bt_n._simulate_trade(ev_late)
check("N: after-close news is NOT bought at that day's close (next close instead)",
      tr_late["entry_ts"].date() == days[16].date() and tr_late["entry_ts"] > ev_late.news_ts)
check("N: exit is the next day's open, after entry",
      tr_late["exit_ts"].date() == days[17].date() and abs(tr_late["r_multiple"] + 0.5) < 1e-9,
      f"R {tr_late['r_multiple']:+.2f}")

print("Risk scale (position sizing lever for the drawdown target)")
mixed = cands(200, np.where(np.random.default_rng(3).random(200) < 0.5, 1.5, -1.0))
no_gov = dict(use_dd_governor=False)
_, t_full, _ = replay(mixed, ReplayConfig(**no_gov))
_, t_quarter, _ = replay(mixed, ReplayConfig(risk_scale=0.25, **no_gov))
check("scale 0.25 -> every position exactly a quarter of the size",
      np.allclose(t_quarter.risk_frac, t_full.risk_frac)
      and len(t_quarter) == len(t_full)
      and t_quarter.risk_amount.iloc[0] == 0.25 * t_full.risk_amount.iloc[0])
check("scale does not change which trades are taken",
      list(t_quarter.entry_ts) == list(t_full.entry_ts))
check("Strategy A config carries the same governor + scale fields",
      all(hasattr(Config().risk, k) for k in
          ("use_dd_governor", "dd_probe_floor", "dd_peak_halflife_days", "risk_scale")))

print("Equity curve is daily (annualisation follows calendar time)")
rng_d = np.random.default_rng(1)
bdays = pd.bdate_range("2023-01-02", "2023-12-29", tz="UTC")
ent = (pd.to_datetime(rng_d.choice(bdays, 1000)) + pd.Timedelta(hours=14, minutes=30)
       + pd.to_timedelta(rng_d.integers(0, 300, 1000), unit="m"))
minute_exits = pd.DataFrame({
    "ticker": [f"T{i % 50}" for i in range(1000)], "strength": 0.8,
    "entry_ts": ent, "exit_ts": ent + pd.to_timedelta(rng_d.integers(5, 90, 1000), unit="m"),
    "r_multiple": rng_d.normal(0.05, 1.0, 1000)})
e_day, _, _ = replay(minute_exits, ReplayConfig(use_dd_governor=False,
                                                one_position_per_ticker=False))
implied_years = (len(e_day) - 1) / 252
check("one equity point per trading day", 0.95 < implied_years < 1.05,
      f"implied {implied_years:.2f}y for a 1-year run (old code: ~3.9y)")
check("curve starts at initial equity", e_day.iloc[0] == 100_000.0)

print(f"\nALL {len(PASS)} CHECKS PASSED")
