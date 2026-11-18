"""
newsdrift/strategy_c_minute.py -- Strategy C priced on minute bars only
(note `…note_c_minute_2026-10-24.md`, section 3). One price basis by
construction: entry, stops, targets and exits all on split-adjusted IEX
minute bars; daily bars are used only for the stop distance as a RATIO
(mean (high - low) / close), which no multiplicative adjustment changes.

  Entry  -- first regular-session bar at or after news + latency, at its
            open, with C's latency-decayed entry cost (as StrategyCBacktest).
  Stop   -- entry x max(stop_atr_mult x mean over the atr_period daily bars
            BEFORE the entry day of (high - low) / close, stop_floor_frac).
            Target tp_r_multiple x stop distance.
  Walk   -- every regular-session bar (09:30-16:00 New York) from the entry
            bar inclusive to 16:00 New York on the exit day (the
            `duration`-th trading day after the entry day), Bug 14 fill rule
            (risk.barrier_exit).
  Time   -- close of the last regular-session bar at or before 16:00 New York
            on the exit day; if that day has no bar, the last earlier bar
            (counted in `stale_exits`).
  Dividends: none credited (split-adjusted minute prices drop on ex-dates);
            estimated descriptively by `implied_dividend`.
Events, sizing, candidate table and portfolio replay: unchanged from
StrategyCBacktest.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .intraday import latency_cost_bps
from .risk import barrier_exit
from .strategy_c import StrategyCBacktest, StrategyCConfig, BASIS_TZ

RTH_OPEN_MIN, RTH_CLOSE_MIN = 9 * 60 + 30, 16 * 60
CLOSE_T = pd.Timedelta(hours=16)


def regular_session(bars: pd.DataFrame) -> pd.DataFrame:
    """Bars stamped 09:30-15:59 New York on weekdays."""
    ny = pd.to_datetime(bars.ts, utc=True).dt.tz_convert(BASIS_TZ)
    m = ny.dt.hour * 60 + ny.dt.minute
    return bars[(m >= RTH_OPEN_MIN) & (m < RTH_CLOSE_MIN) & (ny.dt.weekday < 5)]


class StrategyCMinuteBacktest(StrategyCBacktest):
    def __init__(self, daily_px: pd.DataFrame, minute_bars: pd.DataFrame,
                 events: pd.DataFrame, cfg: StrategyCConfig):
        assert cfg.entry_mode == "intraday", "the minute engine prices intraday entries only"
        super().__init__(daily_px, regular_session(minute_bars), events, cfg)
        self._arrays = {}
        for t, g in self._minute_by_ticker.items():
            ts = pd.to_datetime(g.ts, utc=True)
            self._arrays[t] = {
                "ts": ts.dt.tz_convert(None).to_numpy(),
                "day": ts.dt.tz_convert(BASIS_TZ).dt.tz_localize(None).dt.normalize().to_numpy(),
                "open": g.open.to_numpy(float), "high": g.high.to_numpy(float),
                "low": g.low.to_numpy(float), "close": g.close.to_numpy(float)}
        self.stale_exits = 0

    def _stop_distance(self, ticker: str, entry_day, entry: float) -> float | None:
        d = self._daily_by_ticker.get(ticker)
        if d is None:
            return None
        hist = d[d.date < entry_day].tail(self.cfg.atr_period_days)   # strictly before: no look-ahead
        if len(hist) < self.cfg.atr_period_days:
            return None
        rel = float(((hist.high - hist.low) / hist.close).mean())
        if not np.isfinite(rel) or rel <= 0:
            return None
        return entry * max(self.cfg.stop_atr_mult * rel, self.cfg.stop_floor_frac)

    def _simulate_trade(self, ev) -> dict | None:
        cfg = self.cfg
        a = self._arrays.get(ev.ticker)
        if a is None or ev.strength == 0:
            return None
        direction = 1 if ev.strength > 0 else -1
        news = pd.Timestamp(ev.news_ts)
        news = news.tz_convert(None) if news.tzinfo else news
        earliest = np.datetime64(news + pd.Timedelta(minutes=cfg.entry_latency_min))
        i0 = int(np.searchsorted(a["ts"], earliest, "left"))
        if i0 >= len(a["ts"]):
            return None
        assert a["ts"][i0] >= earliest, "LOOK-AHEAD: entry before news + latency"
        entry_cost = latency_cost_bps(cfg.entry_latency_min, cfg.entry_cost_base_bps,
                                      cfg.entry_cost_spike_bps, cfg.entry_cost_tau_min) / 1e4
        entry = a["open"][i0] * (1 + direction * entry_cost)
        entry_day = pd.Timestamp(a["day"][i0])
        stop_dist = self._stop_distance(ev.ticker, entry_day, entry)
        if stop_dist is None:
            return None
        stop = entry - direction * stop_dist
        target = entry + direction * cfg.tp_r_multiple * stop_dist

        d = self._daily_by_ticker[ev.ticker]
        duration = int(np.clip(ev.duration, 1, cfg.max_duration_days))
        fwd = d[d.date > entry_day].head(duration)
        if fwd.empty:
            return None
        exit_day = pd.Timestamp(fwd.date.iloc[-1])
        exit_moment = (exit_day + CLOSE_T).tz_localize(BASIS_TZ).tz_convert("UTC").tz_localize(None)
        j = int(np.searchsorted(a["ts"], np.datetime64(exit_moment), "left"))   # bars starting before 16:00
        o, h, lo = a["open"][i0:j], a["high"][i0:j], a["low"][i0:j]
        adverse, favour = (lo, h) if direction == 1 else (h, lo)
        fire = ((direction * (o - stop) <= 0) | (direction * (o - target) >= 0)
                | (direction * (adverse - stop) <= 0) | (direction * (favour - target) >= 0))
        if fire.any():
            k = i0 + int(np.argmax(fire))
            exit_px, reason = barrier_exit(direction, a["open"][k], a["high"][k], a["low"][k], stop, target)
        else:
            k = j - 1
            exit_px, reason = a["close"][k], "time_exit"
            if pd.Timestamp(a["day"][k]) != exit_day:
                self.stale_exits += 1
        exit_net = exit_px * (1 - direction * cfg.exit_cost_bps / 1e4)
        return {
            "ticker": ev.ticker, "strength": ev.strength, "duration": duration,
            "news_ts": ev.news_ts, "entry_ts": pd.Timestamp(a["ts"][i0]).tz_localize("UTC"),
            "entry_day": entry_day, "exit_date": pd.Timestamp(a["day"][k]),
            "exit_bar_ts": pd.Timestamp(a["ts"][k]).tz_localize("UTC"),
            "direction": direction, "ret": direction * (exit_net - entry) / entry,
            "r_multiple": direction * (exit_net - entry) / stop_dist, "reason": reason,
            "stop_dist_bps": stop_dist / entry * 1e4,
        }

    def implied_dividend(self, trades: pd.DataFrame) -> pd.Series:
        """Descriptive: change of (daily adjusted close / last minute close at or
        before 16:00 New York) from entry day to exit day = the dividend the
        split-adjusted minute price dropped by (no credit given)."""
        out = []
        for r in trades.itertuples(index=False):
            r0, r1 = self._basis_ratio(r.ticker, r.entry_day), self._basis_ratio(r.ticker, r.exit_date)
            out.append(r1 / r0 - 1 if r0 and r1 else np.nan)
        return pd.Series(out, index=trades.index)
