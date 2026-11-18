"""
c_minute_rungs23_report.py -- minute-bar-only Strategy C for rungs 2 (Haiku)
and 3 (Sonnet) (note `…note_c_minute_rungs2_3_2026-10-25.md`): C vs the
CONTINUOUS momentum benchmark (Jobson-Korkie-Memmel), Kelly - fixed for C
(each rung's C on its own, unadjusted), deflated Sharpe from the runner.
Checks that the A/B rows of these runs reproduce each rung's A/B summary.
Every number is labelled "exposed to look-ahead".

USAGE (from the project root):  python3 src/c_minute_rungs23_report.py
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from paths import OUTPUTS
from run_both_strategies import compare_strategies
from momentum_continuous import read_curve
from c_minute_report import continuous_benchmark

TAG = "2026-10-25"
DUMP = OUTPUTS / f"c_minute_rungs23_{TAG}"
RUNGS = {"haiku": "rung2", "sonnet": "rung3"}
OUT = OUTPUTS / f"c_minute_rungs2_3_summary_{TAG}.csv"
LABEL = "exposed to look-ahead"


def main():
    rows = []
    for rung, tag in RUNGS.items():
        curves = {}
        for f in sorted((DUMP / rung).glob("equity_*.csv")):
            name, period = f.stem.removeprefix("equity_").rsplit("_", 1)
            if not name.startswith("BENCHMARK"):
                curves.setdefault(name, {})[period] = read_curve(f)
        cmp = compare_strategies({**curves, "BENCHMARK_momentum": continuous_benchmark(curves)}, {})
        vs = cmp[cmp.comparison == "strategy_minus_momentum"].set_index(["strategy", "period"])
        ab = pd.read_csv(OUTPUTS / f"{tag}_summary_{TAG}.csv").dropna(subset=["sr_diff_vs_momentum"])
        ab = ab.set_index(["strategy", "period"]).sr_diff_vs_momentum
        same = np.allclose(vs.loc[ab.index, "sr_diff"], ab)
        print(f"  {rung}: A/B rows reproduce the {tag} summary: {same}")
        res = pd.read_csv(OUTPUTS / f"results_both_strategies_{rung}_calibrated_cminute_{TAG}.csv", index_col=0)
        kf = pd.read_csv(OUTPUTS / f"results_both_strategies_{rung}_calibrated_cminute_{TAG}_comparison.csv")
        kf = kf[(kf.comparison == "kelly_minus_fixed") & kf.strategy.str.startswith("C_")]
        for (strategy, period), r in vs[vs.index.get_level_values(0).str.startswith("C_")].iterrows():
            m = res.loc[strategy]
            rows.append({"label": LABEL, "rung": rung, "ab_reproduced": same, "strategy": strategy, "period": period,
                         "return_pa": m[f"{period}_return_pa"], "sharpe": m[f"{period}_sharpe"],
                         "maxDD": m[f"{period}_maxDD"], "trades": m[f"{period}_trades"], "DSR": m.get(f"{period}_DSR"),
                         "sr_diff_vs_momentum": r.sr_diff, "se_vs_momentum": r.se, "p_vs_momentum": r.p})
        for r in kf.itertuples(index=False):
            rows.append({"label": LABEL, "rung": rung, "strategy": r.strategy + "_kelly_minus_fixed",
                         "period": r.period, "sr_diff_kelly_minus_fixed": r.sr_diff, "p_kelly_minus_fixed": r.p})
    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    print(out.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    pd.DataFrame([{"timestamp": datetime.now().isoformat(timespec="seconds"),
                   "script": "src/run_both_strategies.py --c-engine minute (outputs/c_minute_rungs23_2026-10-25/run.sh) + src/c_minute_rungs23_report.py",
                   "scorers": "haiku+sonnet", "period": "2024-04-30 .. 2026-06-01",
                   "what": "minute-only Strategy C for rungs 2 and 3 vs continuous momentum (exposed to look-ahead)",
                   "output": OUT.name}]).to_csv(OUTPUTS / "test_period_runs.csv", mode="a", index=False, header=False)


if __name__ == "__main__":
    main()
