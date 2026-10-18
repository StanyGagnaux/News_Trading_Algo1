"""
newsdrift/strategy_c.py -- Strategy C: intraday entry, multi-day hold.

Tests whether the post-news edge needs DAYS rather than MINUTES: enter
intraday shortly after the headline (same latency-cost mechanics as
Strategy B), but instead of forcing a same-session exit, size the stop and
target off the DAILY price scale and hold for the signal's own per-headline
duration (1-3 trading days) -- the same duration field Strategy A uses.

MECHANICS (spec, not tuned):
  Filter    -- only news published during regular trading hours
               (14:30-19:30 UTC). Outside that window no minute bar exists
               to enter on.
  Direction -- long if strength > 0, short if strength < 0, skip if 0.
  Entry     -- news_ts + 15 minutes. Price = open of the first minute bar at
               or after that time, adjusted for the entry-latency cost
               (~3.7bps per side at t+15min, via intraday.latency_cost_bps).
  Stop      -- from the DAILY range, not intraday: mean(high - low) over the
               14 daily bars strictly BEFORE the entry date, x2.0, floored
               at 0.4% of entry price. Daily-scale because the hold is
               multi-day.
  Target    -- 2R from the stop distance.
  Exit      -- walk forward through the next `duration` daily bars (1-3,
               the same per-headline duration Pillar 1 already produces).
               Stop is checked before target within a bar (pessimistic
               fill). If neither hits, exit at the close of the final held
               day. Exit cost uses the empirical per-side rate (by day 1+
               the news-driven spread widening has decayed back to normal).
  Result    -- r_multiple = direction * (exit_net - entry) / stop_dist.

Portfolio replay is shared with Strategy B (portfolio.replay): candidates
are simulated independently, then replayed chronologically with a real
equity curve, the drawdown governor, sizer-independent admission under the
concurrent-risk cap, and one open position per ticker.
"""
from __future__ import annotations
from dataclasses import dataclass, fields
import numpy as np
import pandas as pd

from .intraday import latency_cost_bps, confirms_direction
from .portfolio import ReplayConfig, replay


@dataclass
class StrategyCConfig:
    entry_latency_min: int = 15
    atr_period_days: int = 14
    stop_atr_mult: float = 2.0
    stop_floor_frac: float = 0.004        # 0.4% of entry price
    tp_r_multiple: float = 2.0
    max_duration_days: int = 3            # ceiling matching Pillar 1

    # entry cost: latency-decayed (spread still wide right after news)
    entry_cost_base_bps: float = 3.0
    entry_cost_spike_bps: float = 15.0
    entry_cost_tau_min: float = 5.0
    # exit cost: empirical per-side rate (spread has normalised by day 1+)
    exit_cost_bps: float = 2.5

    # --- sizing (same fixed vs kelly axis as Strategies A and B) ---
    sizer: str = "fixed"
    risk_frac: float = 0.01
    kelly_fraction: float = 0.25
    kelly_lookback_trades: int = 40
    kelly_min_trades: int = 15
    max_concurrent_risk: float = 0.04

    # --- Sept 2026: see portfolio.py (Bugs 2 and 3) ---
    one_position_per_ticker: bool = True
    use_dd_governor: bool = True
    dd_cap: float = 0.05
    dd_throttle_start: float = 0.03
    dd_probe_floor: float = 0.05
    dd_peak_halflife_days: float | None = 60.0
    risk_scale: float = 1.0

    initial_equity: float = 100_000.0

    # --- entry variants (defaults = original spec) ---
    entry_mode: str = "intraday"              # "intraday" (t+latency) | "close"
    confirm_move_bps: float | None = None     # intraday mode only; see intraday.py


def _daily_range_stop(daily_hist: pd.DataFrame, period: int) -> float | None:
    """mean(high - low) over the trailing `period` daily bars, or None if
    there isn't enough history yet."""
    if len(daily_hist) < period:
        return None
    tail = daily_hist.tail(period)
    return float((tail["high"] - tail["low"]).mean())


class StrategyCBacktest:
    def __init__(self, daily_px: pd.DataFrame, minute_bars: pd.DataFrame,
                 events: pd.DataFrame, cfg: StrategyCConfig):
        """
        daily_px    : [date, ticker, open, high, low, close, ...]
        minute_bars : [ticker, ts, open, high, low, close]
        events      : [ticker, news_ts, strength, duration]
        """
        self.cfg = cfg
        self.daily = daily_px.sort_values(["ticker", "date"])
        self.minute = minute_bars.sort_values(["ticker", "ts"])
        self.events = events
        self._daily_by_ticker = {t: g.reset_index(drop=True)
                                 for t, g in self.daily.groupby("ticker")}
        self._minute_by_ticker = {t: g for t, g in self.minute.groupby("ticker")}

    def _entry(self, ev, direction: int):
        """Returns (entry_price, entry_ts, entry_date) or None. Daily bars are
        tz-naive dates, so entry_date drops the tz label."""
        cfg = self.cfg
        news_ts = pd.Timestamp(ev.news_ts)
        if cfg.entry_mode == "close":
            news_day = news_ts.tz_localize(None).normalize()
            dbars = self._daily_by_ticker.get(ev.ticker)
            day = None if dbars is None else dbars[dbars.date == news_day]
            if day is None or day.empty:
                return None
            entry_ts = pd.Timestamp(news_day, tz="UTC") + pd.Timedelta(hours=20)
            assert entry_ts > news_ts, "LOOK-AHEAD: close entry before the news"
            entry = day.iloc[0].close * (1 + direction * cfg.exit_cost_bps / 1e4)
            return entry, entry_ts, news_day

        mbars = self._minute_by_ticker.get(ev.ticker)
        if mbars is None or mbars.empty:
            return None
        entry_ts = news_ts + pd.Timedelta(minutes=cfg.entry_latency_min)
        post = mbars[mbars.ts >= entry_ts]
        if post.empty:
            return None
        entry_bar = post.iloc[0]
        assert entry_bar.ts >= entry_ts, "LOOK-AHEAD: entry before news+latency"
        if cfg.confirm_move_bps is not None and not confirms_direction(
                mbars, news_ts, entry_bar, direction, cfg.confirm_move_bps):
            return None
        entry_cost = latency_cost_bps(cfg.entry_latency_min, cfg.entry_cost_base_bps,
                                      cfg.entry_cost_spike_bps, cfg.entry_cost_tau_min) / 1e4
        entry = entry_bar.open * (1 + direction * entry_cost)
        return entry, entry_bar.ts, pd.Timestamp(entry_bar.ts).tz_localize(None).normalize()

    def _simulate_trade(self, ev) -> dict | None:
        cfg = self.cfg
        if ev.strength == 0:
            return None
        direction = 1 if ev.strength > 0 else -1
        entered = self._entry(ev, direction)
        if entered is None:
            return None
        entry, entry_ts, entry_date = entered

        dbars = self._daily_by_ticker.get(ev.ticker)
        if dbars is None:
            return None
        hist = dbars[dbars.date < entry_date]     # strictly before -- no look-ahead
        mean_range = _daily_range_stop(hist, cfg.atr_period_days)
        if mean_range is None or mean_range <= 0:
            return None
        stop_dist = max(cfg.stop_atr_mult * mean_range,
                        cfg.stop_floor_frac * entry)
        stop = entry - direction * stop_dist
        target = entry + direction * cfg.tp_r_multiple * stop_dist

        duration = int(np.clip(ev.duration, 1, cfg.max_duration_days))
        fwd = dbars[dbars.date > entry_date].head(duration)   # walk forward
        if fwd.empty:
            return None
        exit_px, exit_date, reason = None, None, None
        for bar in fwd.itertuples(index=False):
            if direction == 1:
                if bar.low <= stop:
                    exit_px, exit_date, reason = stop, bar.date, "stop"; break
                if bar.high >= target:
                    exit_px, exit_date, reason = target, bar.date, "target"; break
            else:
                if bar.high >= stop:
                    exit_px, exit_date, reason = stop, bar.date, "stop"; break
                if bar.low <= target:
                    exit_px, exit_date, reason = target, bar.date, "target"; break
        if exit_px is None:
            last = fwd.iloc[-1]
            exit_px, exit_date, reason = last.close, last.date, "time_exit"

        exit_net = exit_px * (1 - direction * cfg.exit_cost_bps / 1e4)
        r_mult = direction * (exit_net - entry) / stop_dist
        ret = direction * (exit_net - entry) / entry
        return {
            "ticker": ev.ticker, "strength": ev.strength, "duration": duration,
            "news_ts": ev.news_ts, "entry_ts": entry_ts,
            "exit_date": exit_date, "direction": direction, "ret": ret,
            "r_multiple": r_mult, "reason": reason,
            "stop_dist_bps": stop_dist / entry * 1e4,
        }

    def candidate_table(self) -> pd.DataFrame:
        """Every simulated trade, independent of sizing (replay input)."""
        candidates = [c for c in (self._simulate_trade(ev)
                                  for ev in self.events.itertuples(index=False))
                     if c is not None]
        if not candidates:
            return pd.DataFrame()
        cand = pd.DataFrame(candidates).sort_values("entry_ts").reset_index(drop=True)
        # exit_ts for portfolio sequencing: end-of-day on the exit date,
        # localized to UTC to match the (tz-aware) entry_ts from minute bars.
        cand["exit_ts"] = (pd.to_datetime(cand["exit_date"]).dt.tz_localize("UTC")
                           + pd.Timedelta(hours=23, minutes=59))
        return cand

    def replay_config(self) -> ReplayConfig:
        rc_fields = {f.name for f in fields(ReplayConfig)}
        return ReplayConfig(**{k: getattr(self.cfg, k) for k in rc_fields
                               if hasattr(self.cfg, k)})

    def run(self) -> tuple[pd.Series, pd.DataFrame]:
        cand = self.candidate_table()
        if cand.empty:
            return pd.Series(dtype=float), pd.DataFrame()
        equity_series, trades, stats = replay(cand, self.replay_config())
        self.replay_stats = stats
        return equity_series, trades
