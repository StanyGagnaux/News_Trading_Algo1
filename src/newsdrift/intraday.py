"""
newsdrift/intraday.py -- Tier-3 intraday continuation engine.

THE TRADE: news at time T -> spike over the first 1-2 minutes (conceded) ->
continuation drift over the following minutes-to-hours (the target).
Entry at the first minute bar >= T + entry_latency. Exit on intraday stop,
intraday target, or end-of-day close.

THREE COMPONENTS:
1. make_synthetic_intraday(): minute bars with a PLANTED spike+continuation,
   ground truth for validating the engine (same philosophy as the daily
   pipeline: if we can't recover an edge we planted, the plumbing is broken).
2. latency_cost_bps(): per-side cost that DECAYS with entry latency --
   spreads widen sharply right after news and normalise within minutes:
       cost(t) = base + spike * exp(-t / tau)
   Defaults: base 3 bps, spike 15 bps, tau 5 min => t+2min costs ~13 bps,
   t+15min ~4 bps per side. Conservative and tunable; document in thesis.
3. IntradayBacktest.run(): event-driven, per-signal, pessimistic intrabar
   fills (stop checked before target). run_latency_sweep() produces the
   alpha-vs-latency decay table -- the thesis's headline experiment.
"""
from __future__ import annotations
from dataclasses import dataclass, fields
import numpy as np
import pandas as pd

from .portfolio import ReplayConfig, replay

MINUTES_PER_SESSION = 390  # 09:30-16:00 ET


# ----------------------------------------------------------------------------
# 1. Synthetic ground truth
# ----------------------------------------------------------------------------
def make_synthetic_intraday(
    n_events: int = 300,
    spike_bps: float = 80.0,          # conceded initial move (first 2 min)
    continuation_bps: float = 40.0,   # planted Tier-3 edge
    continuation_minutes: int = 120,  # edge decays linearly over this window
    noise_bps_per_min: float = 4.0,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (bars, events). One synthetic ticker-day per event.
    News lands at a random minute in [30, 240] of the session."""
    rng = np.random.default_rng(seed)
    bar_rows, ev_rows = [], []
    base_day = pd.Timestamp("2024-01-02 14:30:00", tz="UTC")  # 09:30 ET
    for i in range(n_events):
        tkr = f"EV{i:04d}"
        day0 = base_day + pd.Timedelta(days=int(i))
        news_min = int(rng.integers(30, 240))
        sign = 1 if rng.random() < 0.5 else -1
        rets = rng.normal(0, noise_bps_per_min / 1e4, MINUTES_PER_SESSION)
        # spike: minutes news_min .. news_min+1
        rets[news_min: news_min + 2] += sign * (spike_bps / 2) / 1e4
        # continuation: linearly decaying drift over the window
        w = np.linspace(1.0, 0.0, continuation_minutes)
        w = w / w.sum() * (continuation_bps / 1e4)
        lo = news_min + 2
        hi = min(lo + continuation_minutes, MINUTES_PER_SESSION)
        rets[lo:hi] += sign * w[: hi - lo]
        close = 100 * np.exp(np.cumsum(rets))
        opn = np.concatenate([[100.0], close[:-1]])
        spread_noise = np.abs(rng.normal(0, noise_bps_per_min / 2e4,
                                         MINUTES_PER_SESSION))
        high = np.maximum(opn, close) * (1 + spread_noise)
        low = np.minimum(opn, close) * (1 - spread_noise)
        ts = day0 + pd.to_timedelta(np.arange(MINUTES_PER_SESSION), unit="m")
        bar_rows.append(pd.DataFrame({
            "ticker": tkr, "ts": ts, "open": opn, "high": high,
            "low": low, "close": close}))
        ev_rows.append({"ticker": tkr, "news_ts": ts[news_min],
                        "strength": sign * float(rng.uniform(0.5, 1.0)),
                        "sign": sign, "session_end": ts[-1]})
    return (pd.concat(bar_rows, ignore_index=True),
            pd.DataFrame(ev_rows))


# ----------------------------------------------------------------------------
# 2. Latency-dependent cost
# ----------------------------------------------------------------------------
def latency_cost_bps(latency_min: float, base: float = 3.0,
                     spike: float = 15.0, tau: float = 5.0) -> float:
    """Per-side cost in bps as a function of minutes since the news."""
    return base + spike * float(np.exp(-latency_min / tau))


# ----------------------------------------------------------------------------
# 3. Intraday engine
# ----------------------------------------------------------------------------
@dataclass
class IntradayConfig:
    entry_latency_min: int = 5
    stop_vol_mult: float = 3.0       # stop = k * rolling minute-vol * price
    vol_lookback_min: int = 30
    tp_r_multiple: float = 2.0

    # --- sizing (v2: matches the daily engine's fixed vs kelly comparison) --
    sizer: str = "fixed"             # "fixed" | "kelly"
    risk_frac: float = 0.01          # per-trade risk when sizer="fixed"
    kelly_fraction: float = 0.25
    kelly_lookback_trades: int = 40
    kelly_min_trades: int = 15

    # --- v2: daily/concurrent portfolio risk cap -----------------------
    # Hard cap on total risk deployed across positions open AT THE SAME TIME,
    # as a fraction of equity. This -- not any single trade's stop -- is what
    # bounds maxDD when many signals cluster on the same day.
    max_concurrent_risk: float = 0.04

    # --- v2: stop-vs-cost floor ------------------------------------------
    # Skip a trade if its stop distance is too tight relative to round-trip
    # transaction costs to have any realistic edge -- a stop of 2bps against
    # a 6bps round-trip cost is a guaranteed-loss trade regardless of signal
    # quality. Requires stop_dist >= min_stop_to_cost_ratio * round-trip cost.
    min_stop_to_cost_ratio: float = 3.0

    cost_base_bps: float = 3.0
    cost_spike_bps: float = 15.0
    cost_tau_min: float = 5.0
    initial_equity: float = 100_000.0
    rth_session_end_utc_hour: float = 20.0   # NYSE RTH close in UTC

    # --- v3: resolve-only exits -------------------------------------------
    # Default (False) keeps the v2 same-session bound: a trade that hits
    # neither stop nor target by the entry day's close is forced out at the
    # last price ("eod"). Setting this True drops that forced close -- the
    # trade stays open past the session and keeps scanning forward bars
    # until stop or target actually fires, capped at max_hold_days as a
    # safety net (an unbounded scan on a quiet ticker can hang for hours).
    hold_until_resolved: bool = False
    max_hold_days: int = 5

    # --- v3: fixed-time exit ----------------------------------------------
    # When set, ignore stop/target entirely: exit at the first bar >=
    # entry_ts + exit_after_min, at market price, no matter where price is.
    # Overrides hold_until_resolved (there is no stop/target to "resolve").
    exit_after_min: int | None = None

    # --- v4 (Sept 2026): portfolio replay moved to portfolio.py ----------
    # Drawdown governor (Bug 3), sizer-independent admission (Bug 2),
    # one open position per ticker. See portfolio.py for the rationale.
    one_position_per_ticker: bool = True
    use_dd_governor: bool = True
    dd_cap: float = 0.05
    dd_throttle_start: float = 0.03
    dd_probe_floor: float = 0.05
    dd_peak_halflife_days: float | None = 60.0
    risk_scale: float = 1.0

    # --- v5: scale-out exits (None = single stop/target exit, as before) --
    # Sell partial_exit_frac at +partial_exit_r R, move the runner's stop to
    # breakeven, then let it run (no fixed target) until stop / trail /
    # session close. trail_r trails the runner's stop that many R behind its
    # best price. Stop moves take effect from the NEXT bar.
    partial_exit_r: float | None = None
    partial_exit_frac: float = 0.5
    breakeven_after_partial: bool = True
    trail_r: float | None = None

    # --- v6: confirmation entry (None = off) ------------------------------
    # Only enter if price has moved at least this many bps in the signal's
    # direction between the first bar after the headline and the entry bar.
    confirm_move_bps: float | None = None


def confirms_direction(bars: pd.DataFrame, news_ts: pd.Timestamp,
                       entry_bar, direction: int, min_bps: float) -> bool:
    """True if price moved >= min_bps with the signal between the first bar
    after the headline and the entry bar. Uses only bars up to entry."""
    after_news = bars[(bars.ts >= news_ts) & (bars.ts < entry_bar.ts)]
    if after_news.empty:
        return False
    ref = after_news.iloc[0].open
    return direction * (entry_bar.open - ref) / ref * 1e4 >= min_bps


def scale_out_legs(sess: pd.DataFrame, direction: int, entry: float,
                   stop_dist: float, cfg: IntradayConfig,
                   timeout_reason: str) -> tuple[list, str]:
    """Walk the bars after the entry bar for a scale-out trade.
    Returns ([(fraction, price, ts), ...], reason). Stop is checked before
    the partial target within a bar (pessimistic fill)."""
    stop = entry - direction * stop_dist
    partial_px = entry + direction * cfg.partial_exit_r * stop_dist
    legs, remaining, best = [], 1.0, entry
    for bar in sess.iloc[1:].itertuples(index=False):
        adverse = bar.low if direction == 1 else bar.high
        favour = bar.high if direction == 1 else bar.low
        if direction * (adverse - stop) <= 0:
            legs.append((remaining, stop, bar.ts))
            return legs, "partial_stop" if len(legs) > 1 else "stop"
        if not legs and direction * (favour - partial_px) >= 0:
            legs.append((cfg.partial_exit_frac, partial_px, bar.ts))
            remaining -= cfg.partial_exit_frac
            if remaining <= 1e-12:
                return legs, "target"
            if cfg.breakeven_after_partial:
                stop = entry
        if legs and cfg.trail_r is not None:
            if direction * (favour - best) > 0:
                best = favour
            trail = best - direction * cfg.trail_r * stop_dist
            if direction * (trail - stop) > 0:
                stop = trail
    last = sess.iloc[-1]
    legs.append((remaining, last.close, last.ts))
    return legs, ("partial_" + timeout_reason if len(legs) > 1 else timeout_reason)


class IntradayBacktest:
    def __init__(self, bars: pd.DataFrame, events: pd.DataFrame,
                 cfg: IntradayConfig):
        self.cfg = cfg
        self.bars = bars.sort_values(["ticker", "ts"])
        self.events = events
        # group once so each event does an O(1) lookup instead of rescanning
        # the full (multi-million-row) bars frame per event.
        self._bars_by_ticker = {t: g for t, g in self.bars.groupby("ticker")}

    def _simulate_trade(self, ev) -> dict | None:
        """Per-event trade mechanics: entry, stop/target search, exit.
        Bounded to the SAME trading session only (exit same session) -- a
        session that never hits stop/target does NOT bleed into the next
        event's bars, which previously caused both wrong "same session"
        trades and multi-hour hangs on quiet tickers.
        """
        cfg = self.cfg
        g = self._bars_by_ticker.get(ev.ticker)
        if g is None or g.empty or ev.strength == 0:
            return None
        direction = 1 if ev.strength > 0 else -1
        entry_ts = pd.Timestamp(ev.news_ts) + pd.Timedelta(
            minutes=cfg.entry_latency_min)
        if cfg.hold_until_resolved:
            window_end = entry_ts + pd.Timedelta(days=cfg.max_hold_days)
        else:
            window_end = entry_ts.normalize() + pd.Timedelta(
                hours=cfg.rth_session_end_utc_hour)
        sess = g[(g.ts >= entry_ts) & (g.ts <= window_end)]
        if sess.empty:
            return None
        entry_bar = sess.iloc[0]
        # LOOK-AHEAD GUARD: never enter before the headline + latency
        assert entry_bar.ts >= pd.Timestamp(ev.news_ts) + pd.Timedelta(
            minutes=cfg.entry_latency_min), "LOOK-AHEAD: entry before news+latency"
        if cfg.confirm_move_bps is not None and not confirms_direction(
                g, pd.Timestamp(ev.news_ts), entry_bar, direction,
                cfg.confirm_move_bps):
            return None
        entry_cost = latency_cost_bps(cfg.entry_latency_min, cfg.cost_base_bps,
                                      cfg.cost_spike_bps, cfg.cost_tau_min) / 1e4
        entry = entry_bar.open * (1 + direction * entry_cost)
        # intraday vol estimate from bars BEFORE entry only (no lookahead)
        hist = g[g.ts < entry_ts].close.pct_change().tail(cfg.vol_lookback_min)
        vol = float(hist.std())
        if not np.isfinite(vol) or vol <= 0:
            return None
        stop_dist = cfg.stop_vol_mult * vol * entry
        stop = entry - direction * stop_dist
        target = entry + direction * cfg.tp_r_multiple * stop_dist

        stop_dist_bps = (stop_dist / entry) * 1e4
        round_trip_cost_bps = 2 * cfg.cost_base_bps  # entry (decayed) + exit
        if stop_dist_bps < cfg.min_stop_to_cost_ratio * round_trip_cost_bps:
            return None      # stop-vs-cost floor: no realistic edge here

        timeout_reason = "timeout" if cfg.hold_until_resolved else "eod"
        exit_px, exit_ts, reason = None, None, None
        legs = None
        if cfg.exit_after_min is not None:
            target_exit_ts = entry_ts + pd.Timedelta(minutes=cfg.exit_after_min)
            post = sess[sess.ts >= target_exit_ts]
            if not post.empty:
                exit_bar = post.iloc[0]
                exit_px, exit_ts, reason = exit_bar.close, exit_bar.ts, "time_exit"
        elif cfg.partial_exit_r is not None:
            legs, reason = scale_out_legs(sess, direction, entry, stop_dist,
                                          cfg, timeout_reason)
        else:
            for bar in sess.iloc[1:].itertuples(index=False):
                if direction == 1:
                    if bar.low <= stop:
                        exit_px, exit_ts, reason = stop, bar.ts, "stop"; break
                    if bar.high >= target:
                        exit_px, exit_ts, reason = target, bar.ts, "target"; break
                else:
                    if bar.high >= stop:
                        exit_px, exit_ts, reason = stop, bar.ts, "stop"; break
                    if bar.low <= target:
                        exit_px, exit_ts, reason = target, bar.ts, "target"; break
        if legs is None:
            if exit_px is None:
                last = sess.iloc[-1]
                exit_px, exit_ts, reason = last.close, last.ts, timeout_reason
            legs = [(1.0, exit_px, exit_ts)]
        # exit cost at normalised spread (news effect has decayed), per leg
        exit_cost = cfg.cost_base_bps / 1e4
        r_mult = sum(f * direction * (px * (1 - direction * exit_cost) - entry)
                     for f, px, _ in legs) / stop_dist
        gross = sum(f * direction * (px - entry_bar.open) for f, px, _ in legs)
        return {
            "ticker": ev.ticker, "strength": ev.strength, "news_ts": ev.news_ts,
            "entry_ts": entry_bar.ts, "exit_ts": legs[-1][2], "direction": direction,
            "ret": r_mult * stop_dist / entry, "r_multiple": r_mult, "reason": reason,
            "stop_dist_bps": stop_dist_bps, "partial_hit": len(legs) > 1,
            "gross_ret": gross / entry_bar.open,
        }

    def run(self) -> tuple[pd.Series, pd.DataFrame]:
        """Simulate every candidate independently, then replay them through
        portfolio.replay(): drawdown governor, sizer-independent admission
        under max_concurrent_risk, one open position per ticker. Replay
        counters (skips by reason) are left on self.replay_stats.
        """
        cand = self.candidate_table()
        if cand.empty:
            return pd.Series(dtype=float), pd.DataFrame()
        equity_series, trades, stats = replay(cand, self.replay_config())
        self.replay_stats = stats
        return equity_series, trades

    def candidate_table(self) -> pd.DataFrame:
        """Every simulated trade, independent of sizing (replay input)."""
        candidates = [c for c in (self._simulate_trade(ev)
                                  for ev in self.events.itertuples(index=False))
                     if c is not None]
        return pd.DataFrame(candidates)

    def replay_config(self) -> ReplayConfig:
        rc_fields = {f.name for f in fields(ReplayConfig)}
        return ReplayConfig(**{k: getattr(self.cfg, k) for k in rc_fields
                               if hasattr(self.cfg, k)})


def run_latency_sweep(bars: pd.DataFrame, events: pd.DataFrame,
                      latencies=(2, 5, 15, 60, 120)) -> pd.DataFrame:
    """The thesis headline experiment: same signals, different entry latency."""
    rows = []
    for lat in latencies:
        cfg = IntradayConfig(entry_latency_min=lat)
        _, tr = IntradayBacktest(bars, events, cfg).run()
        if tr.empty:
            continue
        per_side = latency_cost_bps(lat)
        rows.append({
            "entry_latency_min": lat,
            "n_trades": len(tr),
            "cost_per_side_bps": round(per_side, 1),
            "mean_net_ret_bps": tr.ret.mean() * 1e4,
            "median_net_ret_bps": tr.ret.median() * 1e4,
            "mean_gross_ret_bps": tr.gross_ret.mean() * 1e4,
            "hit_rate": (tr.ret > 0).mean(),
            "t_stat": tr.ret.mean() / (tr.ret.std() / np.sqrt(len(tr))),
            "stop_rate": (tr.reason == "stop").mean(),
        })
    return pd.DataFrame(rows)
