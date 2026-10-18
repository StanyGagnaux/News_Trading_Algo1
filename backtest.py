"""
Pillar 3 -- Backtesting engine and performance metrics.

Event-driven daily simulator for the news-drift strategy:

  * Entries at the OPEN of the signal's effective_date (never the news bar --
    look-ahead is structurally impossible because the engine keys on
    effective_date, which build_signal_table asserts is > news_date).
  * Intrabar exit logic: stop and target checked against the bar's low/high,
    with the conservative convention that if both are touched in one bar the
    STOP fills first (pessimistic fill assumption).
  * Time exit at the close after `duration` full trading days (Pillar 1's
    second output).
  * Costs: (half-spread + commission) bps applied per side.
  * Sizing: pluggable (KellySizer vs FixedFractionSizer) -- the Kelly-vs-fixed
    comparison is an experimental axis.
  * Drawdown governor throttles or blocks new entries.

Metrics: total/annualized return, annualized vol, Sharpe, Sortino, max
drawdown, Calmar, hit rate, profit factor, expectancy (R), trade count.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

from .config import Config
from .risk import KellySizer, FixedFractionSizer, DrawdownGovernor, \
    compute_stop_targets


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


@dataclass
class NewsDriftBacktest:
    prices: pd.DataFrame
    signals: pd.DataFrame
    cfg: Config
    sizer_kind: str = "kelly"          # "kelly" | "fixed"
    _trades: list = field(default_factory=list)

    def run(self) -> tuple[pd.Series, pd.DataFrame]:
        cfg = self.cfg
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

        for d in dates:
            day = px.loc[d]

            # ---- 1. manage open positions (exits) ----
            for tkr in list(open_pos):
                if tkr not in day.index:
                    continue
                p = open_pos[tkr]
                bar = day.loc[tkr]
                exit_px, reason = None, None
                # pessimistic: stop checked before target
                if p.direction == 1:
                    if bar.low <= p.stop:
                        exit_px, reason = p.stop, "stop"
                    elif bar.high >= p.target:
                        exit_px, reason = p.target, "target"
                else:
                    if bar.high >= p.stop:
                        exit_px, reason = p.stop, "stop"
                    elif bar.low <= p.target:
                        exit_px, reason = p.target, "target"
                p.bars_left -= 1
                if exit_px is None and p.bars_left <= 0:
                    exit_px, reason = bar.close, "time"   # duration reached
                if exit_px is not None:
                    exit_px_net = exit_px * (1 - p.direction * cost)
                    pnl = p.direction * (exit_px_net - p.entry) * p.shares
                    cash += p.shares * p.entry + pnl
                    r_mult = pnl / p.risk_amount if p.risk_amount > 0 else 0.0
                    sizer.record_trade(r_mult)
                    self._trades.append({
                        "ticker": tkr, "entry_date": p.entry_date,
                        "exit_date": d, "direction": p.direction,
                        "entry": p.entry, "exit": exit_px_net, "pnl": pnl,
                        "r_multiple": r_mult, "strength": p.strength,
                        "reason": reason,
                    })
                    del open_pos[tkr]

            # ---- 2. mark to market (margin-account convention) ----
            # At entry, `notional` is debited from cash for longs and shorts
            # alike (margin posting). Position value = posted margin +
            # direction-signed unrealized PnL, which nets correctly for shorts.
            mtm = cash + sum(
                p.direction * (day.loc[tkr].close - p.entry) * p.shares
                + p.shares * p.entry
                for tkr, p in open_pos.items() if tkr in day.index
            )
            throttle = governor.update(mtm) if governor else 1.0
            equity_curve[d] = mtm

            # ---- 3. new entries at this date's open ----
            todays = sig_by_date.get(d)
            if todays is None or throttle <= 0:
                continue
            for s in todays.itertuples(index=False):
                if s.ticker in open_pos or s.ticker not in day.index:
                    continue
                if abs(s.strength) < cfg.signal.min_abs_strength:
                    continue     # Bug 11: no direction / below the noise gate
                bar = day.loc[s.ticker]
                if np.isnan(bar.atr) or bar.atr <= 0:
                    continue
                direction = 1 if s.strength > 0 else -1
                entry = bar.open * (1 + direction * cost)
                stop, target, stop_dist = compute_stop_targets(
                    entry, direction, bar.atr, s.strength, cfg.risk)
                # optional calibration layer: a size_weight column replaces the
                # strength-based sizer (fixed_fraction x weight); absent -> unchanged
                weight = getattr(s, "size_weight", None)
                base = (cfg.risk.fixed_fraction * weight if weight is not None
                        else sizer.risk_fraction(s.strength))
                risk_frac = base * throttle * cfg.risk.risk_scale
                risk_amount = mtm * risk_frac
                if risk_amount <= 0 or stop_dist <= 0:
                    continue
                shares = risk_amount / stop_dist
                notional = shares * entry
                cap = cfg.risk.max_position_frac * mtm
                if notional > cap:                    # hard notional cap
                    shares = cap / entry
                    notional = cap
                    risk_amount = shares * stop_dist
                gross = sum(pp.shares * pp.entry for pp in open_pos.values())
                if gross + notional > cfg.risk.max_gross_exposure * mtm:
                    continue
                cash -= notional
                open_pos[s.ticker] = Position(
                    ticker=s.ticker, direction=direction, shares=shares,
                    entry=entry, stop=stop, target=target,
                    stop_dist=stop_dist, bars_left=int(s.duration),
                    risk_amount=risk_amount, entry_date=d,
                    strength=s.strength)

        equity = pd.Series(equity_curve).sort_index()
        trades = pd.DataFrame(self._trades)
        return equity, trades
