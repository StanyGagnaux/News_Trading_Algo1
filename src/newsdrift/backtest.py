"""
Pillar 3 -- Backtesting engine and performance metrics.

Event-driven daily simulator for the news-drift strategy:

  * Entries at the OPEN of the signal's effective_date (never the news bar --
    look-ahead is structurally impossible because the engine keys on
    effective_date, which build_signal_table asserts is > news_date).
  * Intrabar exit logic (Bug 14 rule, risk.barrier_exit): a bar opening
    beyond the stop/target fills at the open; otherwise at the level when the
    low/high crosses it; if both are touched in one bar the STOP fills first.
    Checked from the ENTRY day's bar onward.
  * Time exit at the close after `duration` full trading days (Pillar 1's
    second output), counted on the trading calendar. A position is always
    marked at its ticker's last available close; if the ticker has no bar on
    the exit day the exit fills at that last close, reason "stale" (Bug 16
    rule, note of 10 Nov 2026). Every day the engine asserts that the equity
    change equals booked trade results plus the open positions' result.
  * Costs: (half-spread + commission) bps applied per side.
  * Sizing: pluggable (KellySizer vs FixedFractionSizer) -- the Kelly-vs-fixed
    comparison is an experimental axis.
  * Drawdown governor throttles or blocks new entries.
  * Sizing inputs are those of the PREVIOUS close (Bug 15 rule, note of
    10 Nov 2026): a position opened at the open of day d is sized with the
    Kelly window of trades closed strictly before d and with the equity and
    governor throttle of the close of d-1. Asserted at runtime.
  * Admission uses the book of the PREVIOUS close (Bug 17 rule, note of
    14 Nov 2026): a ticker held at the close of d-1 is not entered at the
    open of d, whatever happens to that position during d, and the gross
    figure of the cap test is the notional held at the close of d-1 plus the
    notional already admitted at this open, still open or not. Asserted at
    runtime.

Metrics: total/annualized return, annualized vol, Sharpe, Sortino, max
drawdown, Calmar, hit rate, profit factor, expectancy (R), trade count.
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

from .config import Config
from .risk import KellySizer, FixedFractionSizer, DrawdownGovernor, \
    compute_stop_targets, barrier_exit


# ----------------------------------------------------------------------------
# Metrics
# ----------------------------------------------------------------------------
def performance_metrics(equity: pd.Series, trades: pd.DataFrame | None = None,
                        freq: int = 252) -> dict:
    rets = equity.pct_change().dropna()
    total = equity.iloc[-1] / equity.iloc[0] - 1
    years = len(rets) / freq
    ann_ret = (1 + total) ** (1 / years) - 1 if years > 0 else np.nan
    ann_vol = rets.std() * np.sqrt(freq)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else np.nan
    downside = rets[rets < 0].std() * np.sqrt(freq)
    sortino = ann_ret / downside if downside and downside > 0 else np.nan
    dd = 1 - equity / equity.cummax()
    max_dd = dd.max()
    calmar = ann_ret / max_dd if max_dd > 0 else np.nan
    out = {
        "total_return": total, "ann_return": ann_ret, "ann_vol": ann_vol,
        "sharpe": sharpe, "sortino": sortino, "max_drawdown": max_dd,
        "calmar": calmar,
    }
    if trades is not None and len(trades):
        r = trades["r_multiple"]
        gross_win = trades.loc[trades.pnl > 0, "pnl"].sum()
        gross_loss = -trades.loc[trades.pnl <= 0, "pnl"].sum()
        out.update({
            "n_trades": len(trades),
            "hit_rate": (trades.pnl > 0).mean(),
            "profit_factor": gross_win / gross_loss if gross_loss > 0 else np.inf,
            "expectancy_R": r.mean(),
            "r2": signal_r2(trades),
        })
    return out


def signal_r2(trades: pd.DataFrame) -> float:
    """R^2 of realized trade return (r_multiple) explained by signal
    strength -- how much of the P&L variance the score actually predicts.
    NaN if the strategy has no per-trade strength (e.g. momentum baseline)
    or too few trades / no strength variance to fit a line.
    """
    if "strength" not in trades.columns or len(trades) < 2:
        return np.nan
    x, y = trades["strength"], trades["r_multiple"]
    if x.std() == 0 or y.std() == 0:
        return np.nan
    corr = np.corrcoef(x, y)[0, 1]
    return corr ** 2 if not np.isnan(corr) else np.nan


# ----------------------------------------------------------------------------
# Engine
# ----------------------------------------------------------------------------
def attach_atr(prices: pd.DataFrame, period: int) -> pd.DataFrame:
    """Copy of `prices` with an `atr` column: the ticker's Wilder ATR up to the
    PREVIOUS bar, so the value used at an entry is known at that day's open.

    Bug 10 (13 Oct 2026): the old version computed ATR in sorted order and
    dropped the index, so values were assigned by position to a filtered table
    and landed on the wrong rows and tickers; it also included the entry day's
    own high/low. Index-preserving now; tests/test_atr_alignment.py checks it.
    """
    px = prices.sort_values(["ticker", "date"])
    prev_close = px.groupby("ticker")["close"].shift(1)
    tr = pd.concat([px["high"] - px["low"],
                    (px["high"] - prev_close).abs(),
                    (px["low"] - prev_close).abs()], axis=1).max(axis=1)
    atr_t = tr.groupby(px["ticker"]).transform(
        lambda s: s.ewm(alpha=1 / period, adjust=False).mean())
    return px.assign(atr=atr_t.groupby(px["ticker"]).shift(1))


@dataclass
class Position:
    ticker: str
    direction: int
    shares: float
    entry: float
    stop: float
    target: float
    stop_dist: float
    bars_left: int
    risk_amount: float
    entry_date: pd.Timestamp
    strength: float
    last_close: float = float("nan")   # last available close of the ticker (Bug 16)


@dataclass
class NewsDriftBacktest:
    prices: pd.DataFrame
    signals: pd.DataFrame
    cfg: Config
    sizer_kind: str = "kelly"          # "kelly" | "fixed"
    _trades: list = field(default_factory=list)

    # one row per call of the sizer (reporting only; dumped by the runner).
    # gross_at_decision (Bug 17): the gross figure of the admission test,
    # NaN where the call is refused before that test.
    SIZING_LOG_COLUMNS = ("date", "ticker", "direction", "base_frac", "throttle",
                          "sizing_equity", "window_n", "window_newest_exit",
                          "risk_amount", "opened", "gross_at_decision")

    def _close(self, tkr, p: Position, exit_px: float, reason: str, d, cost: float,
               closed_today: list) -> float:
        """Book an exit; returns the cash released (margin + PnL).

        Bug 15 (10 Nov 2026): the result is NOT passed to the sizer here. It is
        appended to `closed_today` and reaches the sizer after the day's last
        entry (run, step 4), so no entry of day d is sized with a result of day d.
        """
        exit_px_net = exit_px * (1 - p.direction * cost)
        pnl = p.direction * (exit_px_net - p.entry) * p.shares
        r_mult = pnl / p.risk_amount if p.risk_amount > 0 else 0.0
        closed_today.append(r_mult)
        self._booked += pnl                # for the daily equity reconciliation (Bug 16)
        self._trades.append({
            "ticker": tkr, "entry_date": p.entry_date,
            "exit_date": d, "direction": p.direction,
            "entry": p.entry, "exit": exit_px_net, "pnl": pnl,
            "r_multiple": r_mult, "strength": p.strength,
            "reason": reason, "stop_dist_bps": p.stop_dist / p.entry * 1e4,
        })
        return p.shares * p.entry + pnl

    def run(self) -> tuple[pd.Series, pd.DataFrame]:
        cfg = self.cfg
        self.cap_days = set()          # days on which an exposure cap bound (reporting only)
        self._booked = 0.0             # sum of booked trade results (daily reconciliation, Bug 16)
        px = attach_atr(self.prices, cfg.risk.atr_period)
        px = px.set_index(["date", "ticker"]).sort_index()
        dates = px.index.get_level_values(0).unique().sort_values()

        # Bug 12 (fixed 19 Oct 2026): same-day signals were admitted in input
        # row order, which differed across equivalent inputs and changed the
        # trades when caps bind. Deterministic order: stable sort by date,
        # then `tie_rank` if given (robustness checks), else ticker.
        tie = (["tie_rank"] if "tie_rank" in self.signals.columns
               else ["ticker", "strength"])            # (date, ticker) is unique in practice
        ordered = self.signals.sort_values(["effective_date", *tie], kind="mergesort")
        sig_by_date = {d: g for d, g in ordered.groupby("effective_date", sort=False)}
        sizer = (KellySizer(cfg.risk) if self.sizer_kind == "kelly"
                 else FixedFractionSizer(cfg.risk))
        governor = (DrawdownGovernor(cfg.risk, cfg.initial_equity,
                                     probe_floor=cfg.risk.dd_probe_floor,
                                     peak_halflife_days=cfg.risk.dd_peak_halflife_days)
                    if cfg.risk.use_dd_governor else None)
        cost = cfg.cost.per_side_bps / 1e4

        cash = cfg.initial_equity
        open_pos: dict[str, Position] = {}
        equity_curve = {}

        # Bug 15 (10 Nov 2026): sizing inputs of day d are fixed at the close
        # of d-1. Before the first day: initial equity, no throttle.
        prev_date = None
        sizing_equity, sizing_throttle = cfg.initial_equity, 1.0
        # exit dates of the trades in the sizer's window, for the runtime check
        window_exit_dates = deque(maxlen=cfg.risk.kelly_lookback_trades)
        self.sizing_log = []

        for d in dates:
            day = px.loc[d]
            closed_today = []          # results of day d, held back until step 4

            # ---- 0. the book at the decision time (Bug 17, 14 Nov 2026) ----
            # The entries of day d are decided before the open of d. Step 3
            # used to test them against `open_pos` as left by step 1, i.e.
            # after day d's stops, targets and time exits: a ticker closed
            # during d was entered again at that day's open, and capacity
            # freed during d admitted entries at the open. The entry step now
            # sees only this snapshot of the close of d-1 (posted notional per
            # ticker) plus its own orders of this open.
            book_prev_close = {t: p.shares * p.entry for t, p in open_pos.items()}
            gross_prev_close = sum(book_prev_close.values())
            assert abs(gross_prev_close - (cfg.initial_equity + self._booked - cash)) \
                <= 1e-9 * cfg.initial_equity, \
                f"BOOK DOES NOT RECONCILE at the open of {d}: posted notional != initial equity + booked results - cash (Bug 17)"
            entered_today = {}         # ticker -> notional admitted at this open, still open or not
            admitted_today = 0.0
            exited_today = set()       # tickers with a trade booked on day d

            # ---- 1. manage open positions (exits) ----
            # Bug 16 (10 Nov 2026): a held ticker without a bar used to be
            # skipped here and in the mark-to-market, so a position in a stock
            # that stopped trading was never closed and its value left equity.
            # Now every trading day counts towards the holding period; stops
            # and targets are checked on days with a bar; a time exit on a day
            # without a bar fills at the last available close (reason "stale").
            for tkr in list(open_pos):
                p = open_pos[tkr]
                has_bar = tkr in day.index
                exit_px = reason = None
                if has_bar:
                    bar = day.loc[tkr]
                    p.last_close = bar.close
                    exit_px, reason = barrier_exit(p.direction, bar.open, bar.high,
                                                   bar.low, p.stop, p.target)
                p.bars_left -= 1
                if exit_px is None and p.bars_left <= 0:      # duration reached
                    exit_px, reason = p.last_close, ("time" if has_bar else "stale")
                if exit_px is not None:
                    cash += self._close(tkr, p, exit_px, reason, d, cost, closed_today)
                    exited_today.add(tkr)
                    del open_pos[tkr]

            # ---- 2. mark to market (margin-account convention) ----
            # At entry, `notional` is debited from cash for longs and shorts
            # alike (margin posting). Position value = posted margin +
            # direction-signed unrealized PnL, which nets correctly for shorts.
            # Every open position is marked, at its last available close.
            unrealised = sum(p.direction * (p.last_close - p.entry) * p.shares
                             for p in open_pos.values())
            mtm = cash + sum(p.shares * p.entry for p in open_pos.values()) + unrealised
            assert abs(mtm - cfg.initial_equity - self._booked - unrealised) <= 1e-9 * cfg.initial_equity, \
                f"EQUITY DOES NOT RECONCILE on {d}: equity change != booked results + open positions (Bug 16)"
            throttle = governor.update(mtm) if governor else 1.0
            equity_curve[d] = mtm

            # ---- 3. new entries at this date's open ----
            # Sized with the previous close's equity, throttle and Kelly window
            # (Bug 15); `mtm` and `throttle` of step 2 are day d's CLOSE and
            # act from day d+1. Admitted on the previous close's book (Bug 17):
            # `open_pos` is written here, never read.
            todays = sig_by_date.get(d)
            if todays is not None and sizing_throttle > 0:
                assert sizing_equity == (cfg.initial_equity if prev_date is None
                                         else equity_curve[prev_date]), \
                    f"LOOK-AHEAD (Bug 15): sizing equity of {d} is not the previous close's"
                for s in todays.itertuples(index=False):
                    # eligibility (Bug 17): held at the previous close, or
                    # already ordered at this open -> no entry today
                    if (s.ticker in book_prev_close or s.ticker in entered_today
                            or s.ticker not in day.index):
                        continue
                    assert s.ticker not in exited_today and s.ticker not in open_pos, \
                        (f"LOOK-AHEAD (Bug 17): entry in {s.ticker} at the open of {d} "
                         f"although a position in it was held or closed on that day")
                    if abs(s.strength) < cfg.signal.min_abs_strength:
                        continue     # Bug 11: no direction / below the noise gate
                    bar = day.loc[s.ticker]
                    if np.isnan(bar.atr) or bar.atr <= 0:
                        continue
                    direction = 1 if s.strength > 0 else -1
                    entry = bar.open * (1 + direction * cost)
                    stop, target, stop_dist = compute_stop_targets(
                        entry, direction, bar.atr, s.strength, cfg.risk)
                    newest_exit = max(window_exit_dates) if window_exit_dates else pd.NaT
                    assert not window_exit_dates or newest_exit < d, \
                        (f"LOOK-AHEAD (Bug 15): a trade closed on {newest_exit} is in the "
                         f"sizer's window for an entry at the open of {d}")
                    # optional calibration layer: a size_weight column replaces the
                    # strength-based sizer (fixed_fraction x weight); absent -> unchanged
                    weight = getattr(s, "size_weight", None)
                    base = (cfg.risk.fixed_fraction * weight if weight is not None
                            else sizer.risk_fraction(s.strength))
                    risk_frac = base * sizing_throttle * cfg.risk.risk_scale
                    risk_amount = sizing_equity * risk_frac
                    call = (d, s.ticker, direction, base, sizing_throttle, sizing_equity,
                            len(window_exit_dates), newest_exit)
                    if risk_amount <= 0 or stop_dist <= 0:
                        self.sizing_log.append((*call, risk_amount, False, float("nan")))
                        continue
                    shares = risk_amount / stop_dist
                    notional = shares * entry
                    cap = cfg.risk.max_position_frac * sizing_equity
                    if notional > cap:                    # hard notional cap
                        shares = cap / entry
                        notional = cap
                        risk_amount = shares * stop_dist
                        self.cap_days.add(d)
                    # gross exposure (Bug 17): the book of the previous close
                    # plus every entry admitted at this open, still open or not
                    gross = gross_prev_close + admitted_today
                    assert abs(gross - (sum(book_prev_close.values()) + sum(entered_today.values()))) \
                        <= 1e-9 * cfg.initial_equity, \
                        f"LOOK-AHEAD (Bug 17): gross figure of {d} is not previous-close book + this open's entries"
                    if gross + notional > cfg.risk.max_gross_exposure * sizing_equity:
                        self.cap_days.add(d)
                        self.sizing_log.append((*call, risk_amount, False, gross))
                        continue
                    cash -= notional
                    admitted_today += notional
                    entered_today[s.ticker] = notional
                    self.sizing_log.append((*call, risk_amount, True, gross))
                    pos = Position(
                        ticker=s.ticker, direction=direction, shares=shares,
                        entry=entry, stop=stop, target=target,
                        stop_dist=stop_dist, bars_left=int(s.duration),
                        risk_amount=risk_amount, entry_date=d,
                        strength=s.strength, last_close=bar.close)
                    # Bug 14: the entry day's bar is checked too (entered at its
                    # open, so only its low/high can trigger); duration unchanged
                    exit_px, reason = barrier_exit(direction, bar.open, bar.high,
                                                   bar.low, stop, target)
                    if exit_px is not None:
                        cash += self._close(s.ticker, pos, exit_px, reason, d, cost,
                                            closed_today)
                        exited_today.add(s.ticker)
                    else:
                        open_pos[s.ticker] = pos

            # ---- 4. end of day: day d's information becomes available ----
            # On EVERY path (also days without signals or with a non-positive
            # throttle): results of day d go to the sizer in trade-log order;
            # equity and throttle of this close size the entries of d+1.
            for r_mult in closed_today:
                sizer.record_trade(r_mult)
                window_exit_dates.append(d)
            prev_date, sizing_equity, sizing_throttle = d, mtm, throttle

        equity = pd.Series(equity_curve).sort_index()
        trades = pd.DataFrame(self._trades)
        return equity, trades
