"""
Regression test for Bug 12 (fixed 19 Oct 2026): results must not depend on the
row order of same-day / same-time signals when portfolio caps bind.
Run (from the project root):  python3 tests/test_order_invariance.py
"""
import os
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from newsdrift import Config, NewsDriftBacktest
from newsdrift.portfolio import ReplayConfig, replay

PASS = []


def check(name, cond, detail=""):
    assert cond, f"FAIL: {name} {detail}"
    PASS.append(name)
    print(f"  ok  {name} {detail}")


rng = np.random.default_rng(12)
days = pd.bdate_range("2021-01-04", periods=80)
tickers = [f"T{i:02d}" for i in range(12)]
frames = []
for t in tickers:
    close = 50 * np.exp(np.cumsum(rng.normal(0, 0.02, len(days))))
    frames.append(pd.DataFrame({"date": days, "ticker": t, "close": close,
                                "open": close * np.exp(rng.normal(0, 0.005, len(days))),
                                "high": close * 1.02, "low": close * 0.98}))
px = pd.concat(frames, ignore_index=True)
sig = pd.DataFrame([{"effective_date": d, "ticker": t, "news_date": d - pd.Timedelta(days=1),
                     "strength": float(rng.choice([-1, 1]) * rng.uniform(0.3, 1)), "duration": 2}
                    for d in days[20:70:3] for t in tickers])                  # 12 signals per day
tight = replace(Config(), risk=replace(Config().risk, max_gross_exposure=0.6, use_dd_governor=False))


def run_a(s):
    _, tr = NewsDriftBacktest(px, s, tight, sizer_kind="fixed").run()
    return tr[["ticker", "entry_date", "pnl"]].reset_index(drop=True)


print("Strategy A engine")
base = run_a(sig)
check("caps bind (fewer trades than signals)", len(base) < len(sig), f"{len(base)} of {len(sig)}")
check("5 shuffled signal tables give identical trades",
      all(run_a(sig.sample(frac=1, random_state=k)).equals(base) for k in range(5)))
ranked = run_a(sig.assign(tie_rank=np.random.default_rng(1).permutation(len(sig))))
check("a tie_rank column changes the admission order (the check is live)", not ranked.equals(base))

print("Portfolio replay (B, C, D, N)")
t0_ts = pd.Timestamp("2021-02-01 15:00", tz="UTC")
cand = pd.DataFrame({"ticker": tickers * 3,
                     "entry_ts": [t0_ts] * 24 + [t0_ts + pd.Timedelta(minutes=60)] * 12,
                     "exit_ts": t0_ts + pd.Timedelta(hours=5),
                     "strength": rng.uniform(0.3, 1, 36), "r_multiple": rng.normal(0, 1, 36)})
rc = ReplayConfig(max_concurrent_risk=0.03, use_dd_governor=False)
cols = ["ticker", "entry_ts", "pnl"]
_, t0, _ = replay(cand, rc)
check("caps bind in the replay", len(t0) < len(cand), f"{len(t0)} of {len(cand)}")
check("5 shuffled candidate tables give identical trades",
      all(replay(cand.sample(frac=1, random_state=k), rc)[1][cols].reset_index(drop=True)
          .equals(t0[cols].reset_index(drop=True)) for k in range(5)))

print(f"\nALL {len(PASS)} CHECKS PASSED")
