"""
reconcile_intraday.py -- reconcile the 18 Oct intraday description (LLM,
training, RTH: headline -> +30 min = +2.9 bps) with the 24 Oct speed bound
(LLM +30 min = +0.02 bps). TRAINING PERIOD ONLY; descriptive.

Both scripts share the event definition (intraday_description.headline_events
+ rth_only), the price convention (_price_at: close of the last 1-minute bar
ENDING at or before the moment, <= 10 min stale, same session) and raw returns
(no market adjustment). They differ in
  - sample: the description's main table keeps events where -30, +30, +60 and
    the close all exist ("common"); the speed bound needs only the +30 price;
  - LLM file: 18 Oct used the training scores before the 2024-03-26..04-29
    rows were added (pre-gap); the speed bound uses the current file.
This computes +30 (and the other windows) in all four combinations with one
function, and checks the two published cells are reproduced.

USAGE (from the project root):  python3 src/reconcile_intraday.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from paths import OUTPUTS
from newsdrift import PrecomputedScorer
from calibrate_scorer import load_training
from event_study import clustered_mean
from descriptive_analyses import official_train_llm_file, log_run
import intraday_description as idd

OUT = OUTPUTS / "reconcile_intraday_2026-10-24.csv"
WINDOWS = ["pre_30", "post_30", "post_60", "post_close"]
PUBLISHED = {("pre_gap", "common", "post_30"): (2.927230, 7054),          # intraday_description_2026-10-18.csv
             ("current", "post_30_available", "post_30"): (0.020521, 11308)}  # speed_bound_train_2026-10-24.csv


def main():
    _, nw, cfg = load_training()
    bars = idd.load_bars_training()
    nw = nw[nw.timestamp >= bars.ts.min().tz_convert(None).normalize()]
    files = {"pre_gap": official_train_llm_file(), "current": str(idd.LLM_ANON)}
    rows = []
    for label, path in files.items():
        ev = idd.window_returns(idd.rth_only(idd.headline_events(nw, PrecomputedScorer(path), cfg)), bars)
        samples = {"common": ev.dropna(subset=WINDOWS), "post_30_available": ev[ev.post_30.notna()]}
        print(f"  {label}: {len(ev):,} RTH events; common {len(samples['common']):,}; "
              f"+30 available {len(samples['post_30_available']):,}")
        for sname, s in samples.items():
            for w in WINDOWS:
                m, t, n = clustered_mean(s[w], s.day)
                rows.append({"llm_file": label, "sample": sname, "window": w,
                             "mean_bps": m, "t_clustered": t, "N": n})
    tab = pd.DataFrame(rows)
    for (f, s, w), (m, n) in PUBLISHED.items():
        r = tab[(tab.llm_file == f) & (tab["sample"] == s) & (tab.window == w)].iloc[0]
        assert np.isclose(r.mean_bps, m, atol=1e-5) and r.N == n, f"published cell not reproduced: {f} {s} {w}"
    print("  both published cells reproduced exactly")
    tab.to_csv(OUT, index=False)
    log_run("reconcile", "intraday description vs speed bound, identical sample and price convention, training", [OUT])
    print(tab.pivot_table(index=["llm_file", "sample"], columns="window", values="mean_bps").round(2).to_string())
    print(tab.pivot_table(index=["llm_file", "sample"], columns="window", values="t_clustered").round(2).to_string())


if __name__ == "__main__":
    main()
