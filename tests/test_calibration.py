"""
Checks for the calibration layer (synthetic data only, no real files).
Run (from the project root):  python3 tests/test_calibration.py
"""
import os
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from newsdrift import Config, NewsDriftBacktest
from newsdrift.standalone import simulate_standalone
from calibrate_scorer import headline_type, fit_ridge, predict

PASS = []


def check(name, cond, detail=""):
    assert cond, f"FAIL: {name} {detail}"
    PASS.append(name)
    print(f"  ok  {name} {detail}")


rng = np.random.default_rng(1)


def synthetic_prices(tickers=("AAA", "BBB", "CCC"), n=300):
    days = pd.bdate_range("2020-01-01", periods=n)
    out = []
    for t in tickers:
        close = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
        opn = close * np.exp(rng.normal(0, 0.005, n))
        hi = np.maximum(opn, close) * (1 + rng.uniform(0, 0.02, n))
        lo = np.minimum(opn, close) * (1 - rng.uniform(0, 0.02, n))
        out.append(pd.DataFrame({"date": days, "ticker": t, "open": opn, "high": hi,
                                 "low": lo, "close": close}))
    return pd.concat(out, ignore_index=True)


def synthetic_signals(px, per_ticker=20):
    days = px.date.unique()[30:-10]                 # ATR warm-up and room to exit
    rows = []
    for t in px.ticker.unique():
        for i in np.sort(rng.choice(len(days), per_ticker, replace=False)):
            rows.append({"effective_date": pd.Timestamp(days[i]), "ticker": t,
                         "strength": float(rng.choice([-1, 1]) * rng.uniform(0.2, 1)),
                         "duration": int(rng.integers(1, 4))})
    return pd.DataFrame(rows).sort_values("effective_date").reset_index(drop=True)


cfg = replace(Config(), risk=replace(Config().risk, use_dd_governor=False))
px = synthetic_prices()
sig = synthetic_signals(px)

print("Standalone R vs engine R")
alone = simulate_standalone(px, sig, cfg)
_, tr = NewsDriftBacktest(px, sig, cfg, sizer_kind="fixed").run()
m = tr.merge(alone, left_on=["entry_date", "ticker"], right_on=["effective_date", "ticker"],
             suffixes=("_e", "_a"))
check("every engine trade has a standalone outcome", len(m) == len(tr), f"{len(m)}/{len(tr)}")
check("R-multiples identical", np.allclose(m.r_multiple_e, m.r_multiple_a, atol=1e-10))
check("exit dates identical", (m.exit_date_e.to_numpy() == m.exit_date_a.to_numpy()).all())
check("standalone ignores open-position conflicts: more outcomes than engine trades",
      len(alone) > len(tr), f"{len(alone)} vs {len(tr)}")
cut = px.date.unique()[150]
trunc = simulate_standalone(px[px.date <= cut], sig, cfg)
check("truncated prices -> no exit after the cut", len(trunc) > 0 and (trunc.exit_date <= cut).all())

print("size_weight sizing")
_, t1 = NewsDriftBacktest(px, sig.assign(size_weight=1.0), cfg, sizer_kind="fixed").run()
_, th = NewsDriftBacktest(px, sig.assign(size_weight=0.5), cfg, sizer_kind="fixed").run()
check("same trades at any weight", len(t1) == len(th) and
      (t1.entry_date.to_numpy() == th.entry_date.to_numpy()).all())
check("R-multiple independent of weight", np.allclose(t1.r_multiple, th.r_multiple))
small = replace(cfg, risk=replace(cfg.risk, fixed_fraction=0.002))   # below the 20% notional cap
_, s1 = NewsDriftBacktest(px, sig.assign(size_weight=1.0), small, sizer_kind="fixed").run()
_, sh = NewsDriftBacktest(px, sig.assign(size_weight=0.5), small, sizer_kind="fixed").run()
check("first trade pnl halves with weight 0.5 (cap not binding)",
      np.isclose(sh.pnl.iloc[0], 0.5 * s1.pnl.iloc[0]))
_, t_again = NewsDriftBacktest(px, sig, cfg, sizer_kind="fixed").run()
check("no size_weight column -> engine unchanged (deterministic)",
      len(t_again) == len(tr) and np.allclose(t_again.pnl, tr.pnl))

print("headline_type")
check("earnings", headline_type("Apple Q3 EPS beats estimates") == "earnings_guidance")
check("analyst", headline_type("Goldman upgrades MSFT, raises price target") == "analyst")
check("corporate event", headline_type("FDA approves new drug") == "corporate_event")
check("earnings wins over analyst (first match)",
      headline_type("Analyst downgrade after weak guidance") == "earnings_guidance")
check("other", headline_type("Shares trade higher") == "other")
check("word boundary: 'stakeholder' is not 'stake'", headline_type("stakeholder meeting") == "other")

print("ridge")
n = 5000
X = pd.DataFrame({"a": rng.normal(2, 1, n), "b": rng.integers(0, 2, n).astype(float)})
y = pd.Series(0.1 + 0.3 * X.a - 0.2 * X.b + rng.normal(0, 1, n))
mdl = fit_ridge(X, y, alpha=0.0)
design_ = np.column_stack([np.ones(n), X])
ols = np.linalg.lstsq(design_, y, rcond=None)[0]
check("alpha=0 equals OLS", np.allclose([mdl["intercept"], *mdl["coef"]], ols, atol=1e-8))
check("prediction uses fitted coefficients", np.allclose(predict(mdl, X), design_ @ ols))
shrunk = fit_ridge(X, y, alpha=1e5)
check("large alpha shrinks slopes towards 0", (shrunk["coef"].abs() < mdl["coef"].abs()).all())
check("t-stat of the real effect is large", mdl["t"]["a"] > 10, f"t {mdl['t']['a']:.1f}")

print(f"\nALL {len(PASS)} CHECKS PASSED")
