"""
Checks for the holdout window rule and the Holm step (src/holdout_eval.py).
Run (from the project root):  python3 tests/test_holdout_eval.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from holdout_eval import last_news_date, holm

PASS = []


def check(name, cond, detail=""):
    assert cond, f"FAIL: {name} {detail}"
    PASS.append(name)
    print(f"  ok  {name} {detail}")


print("Last news date (day-5 close on or before the last price date)")
td = pd.DatetimeIndex(pd.bdate_range("2026-06-22", "2026-07-14").drop(pd.Timestamp("2026-07-03")))
end = last_news_date(td, pd.Timestamp("2026-07-14"))
check("2026-07-14 with the 3 July holiday -> last news 2026-07-07", end == pd.Timestamp("2026-07-07"), str(end.date()))
entry = td[td.searchsorted(end + pd.Timedelta(days=1))]
day5 = td[td.get_loc(entry) + 4]
check("news on that date enters 07-08 and its day 5 is 07-14",
      entry == pd.Timestamp("2026-07-08") and day5 == pd.Timestamp("2026-07-14"))
nxt = td[td.searchsorted(end + pd.Timedelta(days=2))]
check("one day later enters 07-09, whose day 5 would fall after 07-14",
      td.get_loc(nxt) + 4 >= len(td))
fri = last_news_date(pd.DatetimeIndex(pd.bdate_range("2023-06-01", "2023-07-14")), pd.Timestamp("2023-07-14"))
check("price end on a Friday -> last news is the Sunday before the Monday entry",
      fri == pd.Timestamp("2023-07-09"), str(fri.date()))

print("Holm step-down")
p = np.array([0.01, 0.04, 0.03, 0.005])
check("Holm-adjusted p (known values)", np.allclose(holm(p), [0.03, 0.06, 0.06, 0.02]), str(holm(p)))
check("adjusted p never below raw p and capped at 1", (holm(p) >= p).all() and holm(np.array([0.9, 0.8])).max() <= 1)

print(f"\nALL {len(PASS)} CHECKS PASSED")
