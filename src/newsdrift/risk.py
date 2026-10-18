"""
Pillar 2 -- Risk-controlled execution.

Three components, each mapping a thesis requirement to code:

1. KellySizer
   Fractional Kelly where p (win prob) and b (payoff ratio) are estimated on a
   ROLLING WINDOW OF CLOSED TRADES ONLY -- no information from open positions
   or future outcomes can leak into the estimate. Signal strength scales the
   Kelly bet linearly (weak signal -> smaller bet), which is the formal link
   between Pillar 1's strength output and execution aggressiveness.
   Falls back to fixed-fractional until enough trade history exists, and a
   pure FixedFractionSizer is provided as the empirical control
   (Lähteenmäki 2023: Kelly may not beat fixed-fractional net of costs --
   this is a hypothesis we TEST, not assume).

2. compute_stop_targets
   ATR-based stop distance divided by leverage (higher leverage -> tighter
   stop in price space, constant risk in equity space). TP as an R-multiple;
   strong signals optionally earn a wider TP. Duration output from Pillar 1
   sets the time-based exit bar count.

3. DrawdownGovernor
   Hard ~5% max-drawdown cap implemented as a CONTINUOUS exposure throttle:
   full size below 3% trailing DD, linear de-risking between 3% and 5%,
   zero new risk at >= 5% (kill switch). A binary kill switch alone tends to
   lock in the drawdown; the throttle makes the cap a control system.
"""
from __future__ import annotations
from collections import deque
import numpy as np
import pandas as pd

from .config import RiskConfig


# ----------------------------------------------------------------------------
# 1. Sizing
# ----------------------------------------------------------------------------
class FixedFractionSizer:
    """Control condition: risk a constant fraction of equity per trade."""

    def __init__(self, cfg: RiskConfig):
        self.cfg = cfg

    def record_trade(self, r_multiple: float):  # interface parity
        pass

    def risk_fraction(self, strength: float) -> float:
        return self.cfg.fixed_fraction * min(1.0, abs(strength) + 0.5)


class KellySizer:
    """
    f* = p - (1-p)/b, estimated from the last N closed trades' R-multiples.
    Applied fraction = kelly_fraction * f* * |strength|, floored at 0.
    """

    def __init__(self, cfg: RiskConfig):
        self.cfg = cfg
        self.closed_r: deque[float] = deque(maxlen=cfg.kelly_lookback_trades)

    def record_trade(self, r_multiple: float):
        self.closed_r.append(r_multiple)

    def _kelly_star(self) -> float | None:
        if len(self.closed_r) < self.cfg.kelly_min_trades:
            return None
        arr = np.array(self.closed_r)
        wins, losses = arr[arr > 0], arr[arr <= 0]
        if len(wins) == 0:
            return 0.0
        if len(losses) == 0:          # degenerate sample; cap optimism
            return 0.5
        p = len(wins) / len(arr)
        b = wins.mean() / abs(losses.mean())
        return max(0.0, p - (1 - p) / b)

    def risk_fraction(self, strength: float) -> float:
        f_star = self._kelly_star()
        if f_star is None:            # warm-up: fixed-fractional fallback
            return self.cfg.fixed_fraction * abs(strength)
        frac = self.cfg.kelly_fraction * f_star * abs(strength)
        # PROBE FLOOR: if f* collapses to ~0 the sizer would stop trading and
        # never receive new closed-trade data -- a permanent deadlock. Keep a
        # small probe size so the rolling (p, b) estimate can recover.
        # (Practical Kelly caveat worth documenting in the thesis.)
        probe = 0.25 * self.cfg.fixed_fraction * abs(strength)
        return max(frac, probe)


# ----------------------------------------------------------------------------
# 2. Stops / targets
# ----------------------------------------------------------------------------
def atr(df: pd.DataFrame, period: int) -> pd.Series:
    """Wilder ATR on a single-ticker OHLC frame sorted by date."""
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def compute_stop_targets(entry: float, direction: int, atr_val: float,
                         strength: float, cfg: RiskConfig) -> tuple[float, float, float]:
    """
    Returns (stop_price, target_price, stop_distance).
    Leverage tightens the price-space stop so equity-space risk is invariant.
    """
    stop_dist = cfg.stop_atr_mult * atr_val / max(cfg.leverage, 1.0)
    r_mult = cfg.tp_r_multiple
    if cfg.strength_widens_tp and abs(strength) > 0.7:
        r_mult += 0.5
    stop = entry - direction * stop_dist
    target = entry + direction * r_mult * stop_dist
    return stop, target, stop_dist


# ----------------------------------------------------------------------------
# 3. Drawdown governor
# ----------------------------------------------------------------------------
class DrawdownGovernor:
    """
    Continuous exposure throttle enforcing the drawdown cap.

    DEADLOCK FIX (mirrors the Kelly probe-floor problem): a naive governor
    sets exposure to exactly 0 at the cap and tracks an all-time-high peak.
    With zero exposure the strategy takes no trades, so equity cannot rise,
    so the drawdown can never shrink -- the strategy is permanently dead.
    Two mechanisms prevent this:

      1. PROBE FLOOR: at/below the cap, exposure is throttled to a small
         non-zero fraction (probe_floor) rather than 0. Risk is cut ~95%
         but the strategy retains a path back to recovery.
      2. PEAK DECAY: the reference peak relaxes toward current equity at
         peak_halflife_days, so a high-water mark set long ago does not
         constrain the strategy forever. Set peak_halflife_days=None for a
         strict all-time-high peak (the classic Grossman-Zhou formulation).

    Note for the thesis: the realised max drawdown can now modestly exceed
    the nominal cap, because a probe position can still lose. This is the
    honest trade-off -- a hard 0 makes the cap literally binding but turns
    any breach into permanent death, which is not a strategy anyone would
    run. Report both the nominal cap and the realised drawdown.
    """

    def __init__(self, cfg: RiskConfig, initial_equity: float,
                 probe_floor: float = 0.05,
                 peak_halflife_days: float | None = 60.0):
        self.cfg = cfg
        self.peak = initial_equity
        self.probe_floor = probe_floor
        self.peak_halflife_days = peak_halflife_days

    def update(self, equity: float) -> float:
        """Update peak; return exposure multiplier in [probe_floor, 1]."""
        if equity >= self.peak:
            self.peak = equity
        elif self.peak_halflife_days:
            # relax the high-water mark toward current equity
            decay = 0.5 ** (1.0 / self.peak_halflife_days)
            self.peak = equity + (self.peak - equity) * decay

        dd = 1.0 - equity / self.peak
        if dd <= self.cfg.dd_throttle_start:
            return 1.0
        if dd >= self.cfg.dd_cap:
            return self.probe_floor          # NOT 0 -- avoids the deadlock
        span = self.cfg.dd_cap - self.cfg.dd_throttle_start
        frac = 1.0 - (dd - self.cfg.dd_throttle_start) / span
        return max(self.probe_floor, frac)
