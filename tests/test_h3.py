"""
Checks for the H3 slope test (src/h3.py) on synthetic data.
Run (from the project root):  python3 tests/test_h3.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from h3 import clustered_slope, power, Z_95

PASS = []


def check(name, cond, detail=""):
    assert cond, f"FAIL: {name} {detail}"
    PASS.append(name)
    print(f"  ok  {name} {detail}")


rng = np.random.default_rng(3)
G, M = 150, 15                                    # dates x events per date


def draw(slope):
    g = np.repeat(np.arange(G), M)
    x = rng.uniform(0.2, 0.6, G * M) + np.repeat(rng.normal(0, 0.1, G), M)   # x correlated within date
    y = slope * x + np.repeat(rng.normal(0, 30, G), M) + rng.normal(0, 60, G * M)  # date shocks
    return y, x, g


print("Cluster-robust slope (CR1, clustered by date)")
sims = [clustered_slope(*draw(0.0)) for _ in range(1500)]
rej = np.mean([s["t"] > Z_95 for s in sims])
check("true slope 0: one-sided rejection rate near 5%", 0.03 < rej < 0.08, f"{rej:.3f}")
slopes = np.array([s["slope"] for s in sims])
mean_se = np.mean([s["se"] for s in sims])
check("clustered SE matches the simulated spread of the slope (within 10%)",
      abs(mean_se / slopes.std(ddof=1) - 1) < 0.10, f"SE {mean_se:.1f} vs spread {slopes.std(ddof=1):.1f}")
y, x, g = draw(0.0)
naive = clustered_slope(y, x, np.arange(len(y)))   # one obs per cluster = heteroskedasticity-robust
check("clustering by date widens the SE when shocks are shared within a date",
      clustered_slope(y, x, g)["se"] > naive["se"])
big = clustered_slope(*draw(150.0))
check("a large true slope is detected", big["t"] > Z_95, f"t {big['t']:.2f}")
check("power formula: effect = 1.645 SE gives 50%", abs(power(1.645, 1.0) - 0.5) < 1e-3)

print(f"\nALL {len(PASS)} CHECKS PASSED")
