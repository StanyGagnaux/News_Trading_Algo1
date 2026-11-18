"""
Regression test for Bug 11 (fixed 18 Oct 2026): the daily signal table gated
|strength| >= 0.20 per HEADLINE only, so opposite headlines netted to 0 (and
the engine traded that as a short) or to a weak average that still traded.
Run (from the project root):  python3 tests/test_signal_gate.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from newsdrift import Config, NewsDriftBacktest, build_signal_table

PASS = []


def check(name, cond, detail=""):
    assert cond, f"FAIL: {name} {detail}"
    PASS.append(name)
    print(f"  ok  {name} {detail}")


class LookupScorer:
    def __init__(self, table):
        self.table = table

    def score(self, headline, ticker=""):
        return self.table[headline], 2


cfg = Config()
days = pd.bdate_range("2021-01-04", periods=60)
news = pd.DataFrame({
    "timestamp": [days[30]] * 2 + [days[31]] * 2 + [days[32]] * 2 + [days[33]],
    "ticker": ["AAA"] * 7,
    "headline": ["up1", "down1", "up03", "down02", "up05", "up03b", "weak"],
})
scores = {"up1": 1.0, "down1": -1.0, "up03": 0.3, "down02": -0.2,
          "up05": 0.5, "up03b": 0.3, "weak": 0.1}
sig = build_signal_table(news, LookupScorer(scores), days, cfg.signal)

print("daily signal table")
check("opposite headlines netting to 0 -> no signal", days[31] not in set(sig.effective_date))
check("weak daily average (+0.05) -> no signal", days[32] not in set(sig.effective_date))
check("strong average (+0.40) kept", len(sig) == 1 and np.isclose(sig.strength.iloc[0], 0.4),
      f"{sig.strength.tolist()}")
check("headline below the gate alone -> no signal", days[34] not in set(sig.effective_date))

print("engine guard")
rng = np.random.default_rng(3)
close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(days))))
px = pd.DataFrame({"date": days, "ticker": "AAA", "open": close, "high": close * 1.01,
                   "low": close * 0.99, "close": close})
raw = pd.DataFrame({"effective_date": [days[30], days[40]], "ticker": "AAA",
                    "strength": [0.0, 0.1], "duration": [1, 1]})
_, tr = NewsDriftBacktest(px, raw, cfg, sizer_kind="fixed").run()
check("strength 0 and 0.1 fed directly -> no trades", len(tr) == 0, f"{len(tr)} trades")
ok = raw.assign(strength=[0.5, -0.5])
_, tr2 = NewsDriftBacktest(px, ok, cfg, sizer_kind="fixed").run()
check("valid signals still trade", len(tr2) == 2, f"{len(tr2)} trades")

print(f"\nALL {len(PASS)} CHECKS PASSED")
