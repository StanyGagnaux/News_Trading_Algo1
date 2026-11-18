"""
Central configuration for the news-drift research system.

All tunable parameters live here so that walk-forward experiments can be
reproduced exactly and so that no "magic numbers" hide inside modules.

References (thesis source library):
- Lopez-Lira & Tang (2024): post-news drift is absorbed within ~2 trading
  days -> DURATION_MAX_DAYS default of 3 is a hard ceiling, 2 is typical.
- Glasserman & Lin (2023): look-ahead bias in GPT sentiment -> SIGNAL_LAG_DAYS
  is structurally enforced (>= 1 for daily data) and headline anonymization
  is available in the LLM signal path.
- Lähteenmäki (2023): Kelly sizing can underperform fixed-fractional net of
  costs -> KELLY_FRACTIONS is a *grid*, incl. the fixed-fraction control.
"""
from dataclasses import dataclass, field


@dataclass
class SignalConfig:
    # --- Look-ahead bias control (hard constraint, Pillar 1) ---
    signal_lag_days: int = 1          # news on day t is tradable at t+1 open, earliest
    anonymize_headlines: bool = True  # Glasserman-Lin de-biasing for LLM scoring

    # --- Dual-output signal architecture ---
    strength_range: tuple = (-1.0, 1.0)   # continuous signal strength
    duration_min_days: int = 1
    duration_max_days: int = 3            # hard ceiling; drift dead after ~2 days
    min_abs_strength: float = 0.20        # ignore weak/ambiguous signals (noise gate)

    # --- Keyword baseline (Loughran-McDonald style) ---
    lm_positive: tuple = ("beat", "beats", "upgrade", "upgraded", "raises",
                          "raised", "record", "strong", "surge", "profit",
                          "exceeds", "approval", "wins", "buyback", "growth")
    lm_negative: tuple = ("miss", "misses", "downgrade", "downgraded", "cuts",
                          "cut", "lowers", "weak", "plunge", "loss", "lawsuit",
                          "probe", "recall", "warns", "warning", "bankruptcy",
                          "layoffs", "fraud", "halt", "delays")


@dataclass
class RiskConfig:
    # --- Sizing (Pillar 2) ---
    kelly_fraction: float = 0.25          # fractional Kelly multiplier (0.25x default)
    kelly_lookback_trades: int = 40       # rolling window of *closed* trades for p, b
    kelly_min_trades: int = 15            # before this, fall back to fixed fraction
    fixed_fraction: float = 0.02          # fixed-fractional control / fallback (2% risk)
    max_position_frac: float = 0.20       # hard cap: max 20% of equity per position
    max_gross_exposure: float = 1.0       # no net leverage by default
    leverage: float = 1.0                 # if >1, stop distances tighten (see stops)

    # --- Stops (Pillar 2) ---
    atr_period: int = 14
    stop_atr_mult: float = 2.0            # SL = k * ATR / leverage
    tp_r_multiple: float = 2.0            # TP at 2R
    strength_widens_tp: bool = True       # high-strength signals get wider TP (2.5R)

    # --- Drawdown governor (Pillar 2) ---
    dd_cap: float = 0.05                  # hard 5% max drawdown cap
    dd_throttle_start: float = 0.03       # start de-risking at 3% trailing DD
    # Exposure multiplier scales linearly from 1.0 at throttle_start to 0.0 at cap.
    use_dd_governor: bool = True
    dd_probe_floor: float = 0.05          # "designed" throttle; 0 + no decay = strict
    dd_peak_halflife_days: float | None = 60.0

    # --- Position scale (Oct 2026) ---
    # Multiplies every position's risk. Drawdown scales roughly with size while
    # Sharpe barely moves, so this is the lever for a drawdown target. Calibrate
    # it IN-SAMPLE only (calibrate_risk.py), then freeze it.
    risk_scale: float = 1.0


@dataclass
class CostConfig:
    # --- Transaction costs (Pillar 3), applied per side ---
    half_spread_bps: float = 2.5          # bid/offer half-spread assumption
    commission_bps: float = 1.0           # IBKR-tier commission approximation
    # total round-trip cost = 2 * (half_spread + commission) = 7 bps default

    @property
    def per_side_bps(self) -> float:
        return self.half_spread_bps + self.commission_bps


@dataclass
class MomentumConfig:
    # Time-series momentum baseline (Jegadeesh-Titman lineage, TS variant)
    lookback_days: int = 90               # ~ 4.5 months
    skip_days: int = 5                    # skip most recent week (reversal noise)
    vol_target_annual: float = 0.10       # 10% vol targeting
    vol_lookback: int = 20
    rebalance_days: int = 5               # weekly rebalance


@dataclass
class WalkForwardConfig:
    # Simple two-way split: earliest train_frac of dates = in-sample
    # (development), the rest = out-of-sample (reported test results).
    train_frac: float = 0.80
    test_frac: float = 0.20


@dataclass
class Config:
    signal: SignalConfig = field(default_factory=SignalConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    cost: CostConfig = field(default_factory=CostConfig)
    momentum: MomentumConfig = field(default_factory=MomentumConfig)
    walkforward: WalkForwardConfig = field(default_factory=WalkForwardConfig)
    initial_equity: float = 100_000.0
    seed: int = 42


DEFAULT = Config()
