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
from .risk import barrier_exit
from .portfolio import ReplayConfig, replay

BASIS_TZ = "America/New_York"
BASIS_CLOSE = pd.Timedelta(hours=16)
BASIS_MAX_STALE = pd.Timedelta(minutes=10)


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
        self._ratio_cache: dict = {}
        self.basis_dropped = 0

    # Bug 13 (fixed 24 Oct 2026): minute bars are split- but not
    # dividend-adjusted, daily bars are both. Entries on minute bars are put on
    # the daily basis with the entry day's ratio daily close / last minute
    # close at or before 16:00 New York time (bar within the last 10 minutes).
    def _basis_ratio(self, ticker: str, day: pd.Timestamp) -> float | None:
        if ticker not in self._ratio_cache:
            m = self._minute_by_ticker.get(ticker)
            d = self._daily_by_ticker.get(ticker)
            ratios = {}
            if m is not None and d is not None and len(m):
                end = (pd.to_datetime(m.ts, utc=True) + pd.Timedelta(minutes=1)).dt.tz_convert(BASIS_TZ)
                tod = end - end.dt.normalize()
                ok = (tod <= BASIS_CLOSE) & (tod >= BASIS_CLOSE - BASIS_MAX_STALE)
                last = (pd.DataFrame({"day": end.dt.normalize().dt.tz_localize(None), "close": m.close.values})
                        [ok.values].groupby("day").close.last())
                daily = d.set_index("date").close
                common = last.index.intersection(daily.index)
                ratios = (daily.loc[common] / last.loc[common]).to_dict()
            self._ratio_cache[ticker] = ratios
        return self._ratio_cache[ticker].get(pd.Timestamp(day))

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
        if self.cfg.entry_mode != "close":               # Bug 13: one price basis
            r = self._basis_ratio(ev.ticker, entry_date)
            if r is None or not np.isfinite(r):
                self.basis_dropped += 1
                return None
            entry = entry * r

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
        # Bug 14 rule (gaps fill at the open). C1 enters at the close, so no
        # bar of the entry day lies after its entry: checking starts next day.
        for bar in fwd.itertuples(index=False):
            exit_px, reason = barrier_exit(direction, bar.open, bar.high, bar.low, stop, target)
            if exit_px is not None:
                exit_date = bar.date
                break
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
        self.cap_days = stats.pop("cap_days", set())
        self.replay_stats = stats
        return equity_series, trades
