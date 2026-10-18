"""
newsdrift/stats.py -- statistical significance of backtest results.

1. strength_return_stats: R² of trade R-multiple on |signal strength|, plus the
   SIGNED correlation (R² hides the sign), its t-statistic
   t = r·sqrt((n−2)/(1−r²)), and the trade count n. Same inputs and 30-trade
   minimum as the runner's original R², so R² values are unchanged.

2. sharpe_se_lo: Lo (2002) standard error of the Sharpe ratio under IID
   returns, SE = sqrt((1 + SR²/2) / T) per period, annualised by sqrt(freq).
   SR here is mean/std of daily returns; the runner's headline Sharpe is
   CAGR/vol, so the SE is approximate for that column. Serial correlation
   (multi-day holds) is NOT corrected -- treat the SE as a lower bound.

3. deflated_sharpe: Bailey & López de Prado (2014). Probability that the true
   Sharpe exceeds SR0, the Sharpe expected from the best of N trials by luck:
       SR0 = sqrt(V) · ((1−γ)·Φ⁻¹(1−1/N) + γ·Φ⁻¹(1−1/(N·e)))
       DSR = Φ( (SR − SR0)·sqrt(T−1) / sqrt(1 − skew·SR + (kurt−1)/4·SR²) )
   with V the variance of the trials' Sharpe ratios, γ Euler-Mascheroni and
   kurt the (non-excess) kurtosis. All per period, not annualised.
"""
from __future__ import annotations
import math
from statistics import NormalDist

import numpy as np
import pandas as pd

EULER_GAMMA = 0.5772156649015329
MIN_TRADES_FOR_R2 = 30
_NORMAL = NormalDist()
_NO_STATS = {"r2": np.nan, "corr": np.nan, "t": np.nan}
_TINY = 1e-12                        # below this a daily-return std is rounding noise


def correlation_t(x, y, min_n: int = MIN_TRADES_FOR_R2) -> dict:
    """{r2, corr, t, n} for two aligned arrays (non-finite pairs dropped)."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    n = len(x)
    if n < min_n or x.std() == 0 or y.std() == 0:
        return {**_NO_STATS, "n": n}
    r = float(np.corrcoef(x, y)[0, 1])
    t = r * math.sqrt((n - 2) / (1 - r * r)) if r * r < 1 else math.copysign(math.inf, r)
    return {"r2": r * r, "corr": r, "t": t, "n": n}


def strength_return_stats(trades: pd.DataFrame | None,
                          ret_col: str = "r_multiple") -> dict:
    """{r2, corr, t, n}: does |strength| predict the trade's R-multiple?"""
    if trades is None or len(trades) == 0 or "strength" not in trades:
        return {**_NO_STATS, "n": 0}
    return correlation_t(trades["strength"].abs(), trades[ret_col])


def daily_returns(equity: pd.Series | None) -> pd.Series:
    if equity is None or len(equity) < 2:
        return pd.Series(dtype=float)
    return equity.pct_change().dropna()


def sharpe_per_period(rets: pd.Series) -> float:
    if len(rets) < 2 or rets.std() == 0:
        return np.nan
    return float(rets.mean() / rets.std())


def sharpe_se_lo(rets: pd.Series, freq: int = 252) -> float:
    """Lo (2002) IID standard error, annualised."""
    sr = sharpe_per_period(rets)
    if not np.isfinite(sr):
        return np.nan
    return math.sqrt((1 + 0.5 * sr * sr) / len(rets)) * math.sqrt(freq)


def expected_max_sharpe(sr_variance: float, n_trials: int) -> float:
    """Expected maximum per-period Sharpe of n_trials zero-skill strategies."""
    if n_trials < 2 or not np.isfinite(sr_variance) or sr_variance <= 0:
        return 0.0
    z = _NORMAL.inv_cdf
    return math.sqrt(sr_variance) * ((1 - EULER_GAMMA) * z(1 - 1 / n_trials)
                                     + EULER_GAMMA * z(1 - 1 / (n_trials * math.e)))


def _aligned(r1: pd.Series, r2: pd.Series) -> pd.DataFrame:
    """Daily returns of two strategies on the dates both have."""
    return pd.concat([r1.rename("a"), r2.rename("b")], axis=1, join="inner").dropna()


def sharpe_diff_test(r1: pd.Series, r2: pd.Series, freq: int = 252) -> dict:
    """Jobson-Korkie (1981) test of SR1 = SR2 with Memmel's (2003) correction,
    on per-period Sharpe ratios over the common dates:
        Var(SR1 - SR2) = [2(1 - rho) + 0.5(SR1^2 + SR2^2 - 2 SR1 SR2 rho^2)] / T
    Assumes IID normal returns (no autocorrelation correction). Difference and
    SE are annualised by sqrt(freq); p is two-sided."""
    d = _aligned(r1, r2)
    t = len(d)
    if t < 3 or d.a.std() < _TINY or d.b.std() < _TINY:
        return {"sr_diff": np.nan, "se": np.nan, "z": np.nan, "p": np.nan, "n": t, "rho": np.nan}
    s1, s2 = d.a.mean() / d.a.std(), d.b.mean() / d.b.std()
    rho = float(d.a.corr(d.b))
    var = (2 * (1 - rho) + 0.5 * (s1 * s1 + s2 * s2 - 2 * s1 * s2 * rho * rho)) / t
    se = math.sqrt(var) if var > 0 else np.nan
    z = (s1 - s2) / se if np.isfinite(se) else np.nan
    p = 2 * (1 - _NORMAL.cdf(abs(z))) if np.isfinite(z) else np.nan
    return {"sr_diff": (s1 - s2) * math.sqrt(freq), "se": se * math.sqrt(freq),
            "z": z, "p": p, "n": t, "rho": rho}


def paired_mean_diff(r1: pd.Series, r2: pd.Series, freq: int = 252) -> dict:
    """Paired t-test on the daily return difference r1 - r2 (IID); the mean
    difference is annualised by freq."""
    d = _aligned(r1, r2)
    diff = d.a - d.b
    t = len(diff)
    if t < 3 or diff.std() < _TINY:      # float noise, not a real spread
        return {"mean_diff_pa": np.nan, "t": np.nan, "n": t}
    return {"mean_diff_pa": diff.mean() * freq,
            "t": diff.mean() / (diff.std() / math.sqrt(t)), "n": t}


def deflated_sharpe(rets: pd.Series, sr0: float) -> float:
    """Probability that the true per-period Sharpe exceeds sr0."""
    sr = sharpe_per_period(rets)
    if not np.isfinite(sr) or len(rets) < 3:
        return np.nan
    skew, kurt = float(rets.skew()), float(rets.kurt()) + 3.0
    denom = 1 - skew * sr + (kurt - 1) / 4 * sr * sr
    if denom <= 0:
        return np.nan
    return _NORMAL.cdf((sr - sr0) * math.sqrt(len(rets) - 1) / math.sqrt(denom))
