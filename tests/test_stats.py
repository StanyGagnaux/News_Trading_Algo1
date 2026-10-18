"""
Checks for newsdrift/stats.py against independent calculations.
Run (from the project root):  python3 tests/test_stats.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from newsdrift.stats import (strength_return_stats, sharpe_se_lo, sharpe_per_period,
                             expected_max_sharpe, deflated_sharpe)

PASS = []


def check(name, cond, detail=""):
    assert cond, f"FAIL: {name} {detail}"
    PASS.append(name)
    print(f"  ok  {name} {detail}")


rng = np.random.default_rng(0)

print("R², signed correlation, t-statistic, n")
s = rng.uniform(-1, 1, 500)
r_mult = 0.3 * np.abs(s) + rng.normal(0, 1, 500)
st = strength_return_stats(pd.DataFrame({"strength": s, "r_multiple": r_mult}))
x = np.abs(s)
old_r2 = float(np.corrcoef(x, r_mult)[0, 1] ** 2)          # the runner's original formula
check("R² identical to the original runner formula", abs(st["r2"] - old_r2) < 1e-12)
slope, intercept = np.polyfit(x, r_mult, 1)
resid = r_mult - (slope * x + intercept)
se_slope = np.sqrt(resid.var(ddof=2) / ((x - x.mean()) ** 2).sum())
check("t-stat equals OLS slope / standard error", abs(st["t"] - slope / se_slope) < 1e-9,
      f"t {st['t']:.3f}")
check("correlation keeps its sign", st["corr"] > 0 and abs(st["corr"] ** 2 - st["r2"]) < 1e-12)
neg = strength_return_stats(pd.DataFrame({"strength": s, "r_multiple": -r_mult}))
check("negative relation gives negative corr and t", neg["corr"] < 0 and neg["t"] < 0)
few = strength_return_stats(pd.DataFrame({"strength": s[:20], "r_multiple": r_mult[:20]}))
check("fewer than 30 trades: no R² but n reported", np.isnan(few["r2"]) and few["n"] == 20)

print("Lo (2002) Sharpe standard error vs Monte Carlo")
T, true_sr, sims = 500, 0.1, 4000
draws = rng.normal(true_sr, 1.0, size=(sims, T))
est = draws.mean(axis=1) / draws.std(axis=1, ddof=1)
mc_se = est.std(ddof=1) * np.sqrt(252)
lo_se = sharpe_se_lo(pd.Series(draws[0]))
check("Lo SE within 5% of the simulated spread", abs(lo_se / mc_se - 1) < 0.05,
      f"Lo {lo_se:.3f} vs simulated {mc_se:.3f}")

print("Expected maximum Sharpe vs Monte Carlo")
n_trials = 100
mc_max = rng.normal(0, 1, size=(20000, n_trials)).max(axis=1).mean()
formula = expected_max_sharpe(1.0, n_trials)
check("expected max of 100 trials within 3%", abs(formula / mc_max - 1) < 0.03,
      f"formula {formula:.3f} vs simulated {mc_max:.3f}")
check("one trial: no deflation", expected_max_sharpe(1.0, 1) == 0.0)
T0, n0 = 500, 8
zero_skill = rng.normal(0, 1, size=(5000, n0, T0))
best = (zero_skill.mean(axis=2) / zero_skill.std(axis=2, ddof=1)).max(axis=1).mean()
null_sr0 = expected_max_sharpe(1 / T0, n0)
check("null luck benchmark = best of 8 zero-skill Sharpes (within 5%)",
      abs(null_sr0 / best - 1) < 0.05, f"formula {null_sr0:.4f} vs simulated {best:.4f}")

print("Deflated Sharpe ratio")
rets = pd.Series(rng.normal(0.05, 1.0, 1000))
check("DSR = 0.5 when the benchmark equals the observed Sharpe",
      abs(deflated_sharpe(rets, sharpe_per_period(rets)) - 0.5) < 1e-12)
short = pd.Series(rng.normal(0.05, 1, 250))
longer = pd.Series(np.tile(short.to_numpy(), 10))      # same Sharpe, skew, kurtosis
check("same Sharpe, 10x more data -> higher DSR",
      deflated_sharpe(longer, 0.0) > deflated_sharpe(short, 0.0))
check("higher benchmark (more trials) -> lower DSR",
      deflated_sharpe(rets, 0.05) < deflated_sharpe(rets, 0.0))

print("Sharpe difference: Jobson-Korkie with Memmel's correction (Monte Carlo)")
from newsdrift.stats import sharpe_diff_test, paired_mean_diff
T1, sims1, rho1, sr1 = 500, 4000, 0.6, 0.05
cov = [[1, rho1], [rho1, 1]]
diffs, rejects = [], 0
for _ in range(sims1):
    x = rng.multivariate_normal([sr1, sr1], cov, size=T1)
    res = sharpe_diff_test(pd.Series(x[:, 0]), pd.Series(x[:, 1]))
    diffs.append(res["sr_diff"]); rejects += res["p"] < 0.05
x0 = rng.multivariate_normal([sr1, sr1], cov, size=T1)
formula_se = sharpe_diff_test(pd.Series(x0[:, 0]), pd.Series(x0[:, 1]))["se"]
check("SE of the Sharpe difference within 5% of the simulated spread",
      abs(formula_se / np.std(diffs, ddof=1) - 1) < 0.05,
      f"formula {formula_se:.3f} vs simulated {np.std(diffs, ddof=1):.3f}")
check("equal true Sharpes: rejection rate near 5%", 0.035 < rejects / sims1 < 0.065,
      f"{rejects / sims1:.3f}")
x1 = rng.multivariate_normal([0.15, 0.0], cov, size=2000)   # expected z ~ 7: not flaky
check("clearly different Sharpes are detected",
      sharpe_diff_test(pd.Series(x1[:, 0]), pd.Series(x1[:, 1]))["p"] < 0.01)
dates = pd.bdate_range("2021-01-01", periods=10)
noise = pd.Series(rng.normal(0, 0.01, 10), index=dates)
pm = paired_mean_diff(noise + 0.001, noise.iloc[2:])
check("paired difference: common dates only; zero-variance difference gives no t",
      pm["n"] == 8 and np.isnan(pm["t"]))

print("Gross exposure from trade logs")
from newsdrift.exposure import average_gross_exposure
d = pd.bdate_range("2021-03-01", periods=5)
eq = pd.Series(10_000.0, index=d)
a_tr = pd.DataFrame({"entry_date": [d[1]], "exit_date": [d[3]], "direction": [1],
                     "entry": [100.0], "exit": [110.0], "pnl": [100.0]})   # 10 shares
check("Strategy A: notional from pnl, alive entry..exit inclusive",
      np.isclose(average_gross_exposure(a_tr, eq), 1000 / 10_000 * 3 / 5))
short = a_tr.assign(direction=[-1], exit=[90.0])                           # short, +100 pnl
check("Strategy A: shorts count as gross exposure",
      np.isclose(average_gross_exposure(short, eq), 1000 / 10_000 * 3 / 5))
bc_tr = pd.DataFrame({"entry_ts": [pd.Timestamp(d[2], tz="UTC") + pd.Timedelta(hours=15)],
                      "exit_ts": [pd.Timestamp(d[2], tz="UTC") + pd.Timedelta(hours=19)],
                      "risk_amount": [50.0], "stop_dist_bps": [50.0]})     # notional 10,000
eq_bc = pd.Series(100_000.0, index=pd.DatetimeIndex(d).tz_localize("UTC"))
check("Strategies B/C: notional = risk / stop distance, tz-aware curve",
      np.isclose(average_gross_exposure(bc_tr, eq_bc), 10_000 / 100_000 / 5))

print(f"\nALL {len(PASS)} CHECKS PASSED")
