"""
newsdrift/open_close.py -- single-session news trades on daily bars.

Strategy D  (OpenCloseBacktest): next-day OPEN -> same-day CLOSE.
    Same signals and entry as Strategy A (open of the first trading day after
    the news, via build_signal_table's effective_date), closed at that day's
    close. Captures the first trading SESSION only.

Strategy N  (OvernightBacktest): first CLOSE after the headline -> next OPEN.
    Uses the point-in-time event table (exact headline timestamps), so a
    headline published after the close is never bought at that same close.
    Captures the first OVERNIGHT gap only.

Together they split Strategy A's first day into its overnight and session
parts. Daily bars only, so both can trade news published outside market hours.

No stop or target: each trade lasts one session or one night. Position size is
set as if 1R = 2 x the mean daily range over the 14 bars before entry
(floored at 0.4% of price), the same risk unit as Strategy C. Costs: empirical
per-side rate on entry and exit.
"""
from __future__ import annotations
from dataclasses import dataclass, fields
import numpy as np
import pandas as pd

from .portfolio import ReplayConfig, replay

RTH_OPEN_UTC = pd.Timedelta(hours=14, minutes=30)
RTH_CLOSE_UTC = pd.Timedelta(hours=20)


@dataclass
class OpenCloseConfig:
    atr_period_days: int = 14
    risk_atr_mult: float = 2.0
    risk_floor_frac: float = 0.004
    cost_bps: float = 2.5

    sizer: str = "fixed"
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
    risk_scale: float = 1.0
    initial_equity: float = 100_000.0


def trade_record(cfg: OpenCloseConfig, ticker: str, strength: float,
                 entry_raw: float, exit_raw: float, hist: pd.DataFrame,
                 entry_ts: pd.Timestamp, exit_ts: pd.Timestamp,
                 reason: str) -> dict:
    """Cost-adjusted R-multiple for a no-stop trade, 1R = daily-range unit."""
    direction = 1 if strength > 0 else -1
    cost = cfg.cost_bps / 1e4
    entry = entry_raw * (1 + direction * cost)
    exit_net = exit_raw * (1 - direction * cost)
    risk_dist = max(cfg.risk_atr_mult * float((hist.high - hist.low).mean()),
                    cfg.risk_floor_frac * entry)
    return {
        "ticker": ticker, "strength": strength, "entry_ts": entry_ts,
        "exit_ts": exit_ts, "direction": direction,
        "ret": direction * (exit_net - entry) / entry,
        "r_multiple": direction * (exit_net - entry) / risk_dist,
        "reason": reason, "stop_dist_bps": risk_dist / entry * 1e4,
    }


class OpenCloseBacktest:
    def __init__(self, daily_px: pd.DataFrame, signals: pd.DataFrame,
                 cfg: OpenCloseConfig):
        """daily_px: [date, ticker, open, high, low, close]
        signals : D -> [news_date, effective_date, ticker, strength]
                  N -> [ticker, news_ts, strength]"""
        self.cfg = cfg
        self.signals = signals
        self._daily_by_ticker = {t: g.sort_values("date").reset_index(drop=True)
                                 for t, g in daily_px.groupby("ticker")}

    def _simulate_trade(self, s) -> dict | None:
        cfg = self.cfg
        if s.strength == 0:
            return None
        assert s.effective_date > s.news_date, "LOOK-AHEAD: trade on the news day"
        dbars = self._daily_by_ticker.get(s.ticker)
        if dbars is None:
            return None
        day = dbars[dbars.date == s.effective_date]
        hist = dbars[dbars.date < s.effective_date].tail(cfg.atr_period_days)
        if day.empty or len(hist) < cfg.atr_period_days:
            return None
        bar = day.iloc[0]
        entry_ts = pd.Timestamp(s.effective_date, tz="UTC") + RTH_OPEN_UTC
        return trade_record(cfg, s.ticker, s.strength, bar.open, bar.close, hist,
                            entry_ts, entry_ts - RTH_OPEN_UTC + RTH_CLOSE_UTC,
                            "close")

    def run(self) -> tuple[pd.Series, pd.DataFrame]:
        candidates = []
        for s in self.signals.itertuples(index=False):
            c = self._simulate_trade(s)
            if c is not None:
                if hasattr(s, "tie_rank"):          # Bug 12 robustness checks
                    c["tie_rank"] = s.tie_rank
                candidates.append(c)
        if not candidates:
            return pd.Series(dtype=float), pd.DataFrame()
        rc_fields = {f.name for f in fields(ReplayConfig)}
        rc = ReplayConfig(**{k: getattr(self.cfg, k) for k in rc_fields
                             if hasattr(self.cfg, k)})
        eq, trades, stats = replay(pd.DataFrame(candidates), rc)
        self.replay_stats = stats
        return eq, trades


class OvernightBacktest(OpenCloseBacktest):
    def _simulate_trade(self, ev) -> dict | None:
        cfg = self.cfg
        if ev.strength == 0:
            return None
        dbars = self._daily_by_ticker.get(ev.ticker)
        if dbars is None:
            return None
        news_ts = pd.Timestamp(ev.news_ts)
        # first daily close strictly after the headline (fixed 20:00 UTC close:
        # conservative in winter, when the real close is 21:00 UTC)
        closes = (dbars.date + RTH_CLOSE_UTC).values
        i = int(np.searchsorted(closes, np.datetime64(news_ts.tz_localize(None)),
                                side="right"))
        if i < cfg.atr_period_days or i >= len(dbars) - 1:
            return None
        entry_bar, exit_bar = dbars.iloc[i], dbars.iloc[i + 1]
        entry_ts = pd.Timestamp(entry_bar.date, tz="UTC") + RTH_CLOSE_UTC
        assert entry_ts > news_ts, "LOOK-AHEAD: bought at a close before the news"
        hist = dbars.iloc[i - cfg.atr_period_days:i]
        return trade_record(cfg, ev.ticker, ev.strength, entry_bar.close,
                            exit_bar.open, hist, entry_ts,
                            pd.Timestamp(exit_bar.date, tz="UTC") + RTH_OPEN_UTC,
                            "next_open")
