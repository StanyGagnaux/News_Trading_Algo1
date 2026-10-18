"""
newsdrift/portfolio.py -- shared portfolio replay for the event-driven
strategies (B: intraday, C: intraday entry / multi-day hold).

Trade candidates are simulated independently by each engine (entry, stop,
target, exit, r_multiple do not depend on sizing). This module replays them
chronologically against a real equity curve. It replaces the two copies of
the replay loop that used to live in intraday.py and strategy_c.py.

FIXES (Sept 2026, see CLAUDE.md section 7):

Bug 3 -- no drawdown governor in B and C.
    The old loops only had max_concurrent_risk, which bounds risk open AT
    THE SAME TIME but not losses accumulated one after another. Neither
    engine ever called risk.DrawdownGovernor (only Strategy A did). Now the
    same governor as Strategy A throttles every new position's size. It is
    updated once per calendar day, as in backtest.py, on REALISED equity
    (B/C have no daily mark-to-market; unrealised risk is bounded by
    max_concurrent_risk through the stops).
    NOTE: with the default probe floor (5%) and decaying peak (60d
    half-life) the governor is a throttle, not a hard cap -- realised maxDD
    measured from the all-time peak can exceed dd_cap. Report realised maxDD.
    dd_probe_floor=0, dd_peak_halflife_days=None gives the strict variant.

Bug 2 -- sizing changed WHICH signals traded, not just their size.
    The concurrent-risk cap was checked against the sizer's own risk amount,
    so a smaller Kelly bet (often the probe floor) let many more signals fit
    under the same cap: 11,906 Kelly vs 1,738 fixed trades in Strategy C.
    Now ADMISSION is decided on a sizer-independent reference risk (the
    fixed-fractional rule), so both sizers see the same opportunity set and
    the Kelly-vs-fixed comparison isolates sizing. The cap still binds on
    actual risk: if a position's actual risk would breach it, the position
    is scaled down to fit (counted as 'scaled_to_cap').

Also new: one open position per ticker (as Strategy A already enforces), so
several headlines on one ticker cannot stack into several identical bets.
"""
from __future__ import annotations
from dataclasses import dataclass
from types import SimpleNamespace
import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay

from .risk import DrawdownGovernor


@dataclass
class ReplayConfig:
    sizer: str = "fixed"                 # "fixed" | "kelly"
    risk_frac: float = 0.01
    kelly_fraction: float = 0.25
    kelly_lookback_trades: int = 40
    kelly_min_trades: int = 15
    max_concurrent_risk: float = 0.04
    one_position_per_ticker: bool = True
    use_dd_governor: bool = True
    dd_cap: float = 0.05
    dd_throttle_start: float = 0.03
    dd_probe_floor: float = 0.05
    dd_peak_halflife_days: float | None = 60.0
    risk_scale: float = 1.0      # pure position scaling; admission unaffected
    initial_equity: float = 100_000.0


def reference_risk_frac(strength: float, rc: ReplayConfig) -> float:
    """Sizer-independent risk used for ADMISSION (and the fixed sizer)."""
    return rc.risk_frac * min(1.0, abs(strength) + 0.5)


def kelly_risk_frac(strength: float, closed_r: list[float],
                    rc: ReplayConfig) -> float:
    """Fractional Kelly on the rolling window of CLOSED trades, with the
    probe floor that prevents the f*=0 deadlock (CLAUDE.md bug 6.1)."""
    if len(closed_r) < rc.kelly_min_trades:
        return reference_risk_frac(strength, rc)          # warm-up
    arr = np.array(closed_r[-rc.kelly_lookback_trades:])
    wins, losses = arr[arr > 0], arr[arr <= 0]
    if len(wins) == 0:
        f_star = 0.0
    elif len(losses) == 0:
        f_star = 0.5
    else:
        p = len(wins) / len(arr)
        b = wins.mean() / abs(losses.mean())
        f_star = max(0.0, p - (1 - p) / b)
    frac = rc.kelly_fraction * f_star * abs(strength)
    probe = 0.25 * rc.risk_frac * abs(strength)
    return max(frac, probe)


SKIP_REASONS = ("ticker_open", "risk_cap", "zero_size")


def daily_equity(points: pd.Series, start_ts: pd.Timestamp,
                 initial_equity: float) -> pd.Series:
    """End-of-day realised equity on a business-day calendar, forward-filled,
    anchored at initial equity the business day before the first entry."""
    # performance_metrics annualises at 252 per observation, so the curve must
    # have one point per trading day (as Strategy A's does), not one per close.
    start = pd.Timestamp(start_ts).normalize() - BDay(1)
    if points.empty:
        return pd.Series([initial_equity], index=[start], dtype=float)
    eod = points.groupby(points.index.normalize()).last()
    idx = pd.bdate_range(start, max(eod.index.max(), start))
    daily = eod.reindex(idx.union(eod.index)).ffill().reindex(idx)
    return daily.fillna(initial_equity)


def replay(cand: pd.DataFrame, rc: ReplayConfig,
           extra_cols: tuple[str, ...] = ()):
    """
    cand: one row per simulated trade with at least
          [ticker, strength, entry_ts, exit_ts, r_multiple] (tz-aware ts).
    Returns (equity_series, trades_df, stats_dict).
    """
    # Bug 12: break entry-time ties deterministically -- by tie_rank if given
    # (robustness checks), else by content (ticker, news time, strength, R),
    # never by input position. Two headlines seconds apart can share a ticker
    # AND an entry minute, so ticker alone is not enough.
    tie = (["tie_rank"] if "tie_rank" in cand.columns else
           [c for c in ("ticker", "news_ts", "strength", "r_multiple") if c in cand.columns])
    cand = cand.sort_values(["entry_ts", *tie], kind="stable").reset_index(drop=True)
    assert (cand["exit_ts"] >= cand["entry_ts"]).all(), \
        "exit before entry -- candidate simulation is broken"

    equity = rc.initial_equity
    open_pos: list[dict] = []
    closed_r: list[float] = []
    equity_curve: dict = {}
    trades_out: list[dict] = []
    stats = {k: 0 for k in SKIP_REASONS}
    stats.update(candidates=len(cand), taken=0, scaled_to_cap=0,
                 governor_throttled=0)

    gov = None
    if rc.use_dd_governor:
        gov = DrawdownGovernor(
            SimpleNamespace(dd_cap=rc.dd_cap,
                            dd_throttle_start=rc.dd_throttle_start),
            rc.initial_equity, probe_floor=rc.dd_probe_floor,
            peak_halflife_days=rc.dd_peak_halflife_days)
    last_day, throttle = None, 1.0

    def close_due(now_ts):
        nonlocal equity, open_pos
        due = sorted((p for p in open_pos if p["exit_ts"] <= now_ts),
                     key=lambda p: p["exit_ts"])
        for p in due:
            equity += p["r_multiple"] * p["risk_amount"]
            closed_r.append(p["r_multiple"])
            equity_curve[p["exit_ts"]] = equity
        open_pos = [p for p in open_pos if p["exit_ts"] > now_ts]

    for row in cand.itertuples(index=False):
        close_due(row.entry_ts)

        # governor: once per calendar day, same cadence as backtest.py
        if gov is not None:
            day = row.entry_ts.normalize()
            if day != last_day:
                last_day, throttle = day, gov.update(equity)

        if rc.one_position_per_ticker and any(
                p["ticker"] == row.ticker for p in open_pos):
            stats["ticker_open"] += 1
            continue

        # ---- admission: sizer-independent (Bug 2) ----
        ref_amt = equity * reference_risk_frac(row.strength, rc)
        open_ref = sum(p["ref_amount"] for p in open_pos)
        if ref_amt <= 0 or open_ref + ref_amt > rc.max_concurrent_risk * equity:
            stats["risk_cap"] += 1
            continue

        # ---- sizing ----
        if rc.sizer == "kelly":
            frac = kelly_risk_frac(row.strength, closed_r, rc)
        else:
            frac = reference_risk_frac(row.strength, rc)
        if throttle < 1.0:
            stats["governor_throttled"] += 1
        risk_amount = equity * frac * throttle * rc.risk_scale

        # the cap also binds on ACTUAL risk: scale down rather than skip
        room = rc.max_concurrent_risk * equity - sum(p["risk_amount"] for p in open_pos)
        if risk_amount > room:
            risk_amount = max(room, 0.0)
            stats["scaled_to_cap"] += 1
        if risk_amount <= 0:
            stats["zero_size"] += 1
            continue

        stats["taken"] += 1
        open_pos.append({"ticker": row.ticker, "exit_ts": row.exit_ts,
                         "risk_amount": risk_amount, "ref_amount": ref_amt,
                         "r_multiple": row.r_multiple})
        rec = {c: getattr(row, c) for c in cand.columns}
        rec.update(risk_amount=risk_amount, risk_frac=frac,
                   equity_at_entry=equity,
                   gov_throttle=throttle, pnl=row.r_multiple * risk_amount)
        trades_out.append(rec)

    if len(cand):
        close_due(cand["exit_ts"].max() + pd.Timedelta(days=1))

    trades = pd.DataFrame(trades_out)
    points = pd.Series(equity_curve, dtype=float).sort_index()
    eq = (daily_equity(points, cand["entry_ts"].iloc[0], rc.initial_equity)
          if len(cand) else points)
    trades.attrs["replay_stats"] = stats
    return eq, trades, stats
