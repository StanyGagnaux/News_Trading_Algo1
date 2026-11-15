"""
rung2_report.py -- comparison tests for rung 2 (Claude Haiku), strategies A
and B only (rung-2 note `…note_rung2_2026-10-24.md`): Jobson-Korkie-Memmel
Sharpe difference vs the CONTINUOUS momentum benchmark, deflated Sharpe from
the runner (N = 155), Kelly - fixed with Holm (rung 2 as its own family of 3).
Every number is labelled "exposed to look-ahead".

USAGE (from the project root):  python3 src/rung2_report.py
"""
from __future__ import annotations

import argparse
from datetime import datetime

import pandas as pd

from paths import OUTPUTS
from run_both_strategies import compare_strategies
from momentum_continuous import read_curve
from c_minute_report import continuous_benchmark
from correction_report import holm

TAG = "2026-10-25"
LABEL = "exposed to look-ahead"
RUNGS = {"haiku": ("rung2", 155), "sonnet": ("rung3", 161)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rung", choices=list(RUNGS), default="haiku")
    rung = ap.parse_args().rung
    tag, n_trials = RUNGS[rung]
    dump = OUTPUTS / f"{tag}_{TAG}"
    results = OUTPUTS / f"results_both_strategies_{rung}_calibrated_{TAG}"
    out_csv = OUTPUTS / f"{tag}_summary_{TAG}.csv"
    curves = {}
    for f in sorted(dump.glob("equity_*.csv")):
        name, period = f.stem.removeprefix("equity_").rsplit("_", 1)
        if not name.startswith("BENCHMARK"):
            curves.setdefault(name, {})[period] = read_curve(f)
    cmp = compare_strategies({**curves, "BENCHMARK_momentum": continuous_benchmark(curves)}, {})
    res = pd.read_csv(f"{results}.csv", index_col=0)
    kf = pd.read_csv(f"{results}_comparison.csv")
    kf = kf[(kf.comparison == "kelly_minus_fixed")].copy()
    oos = kf.period == "OOS"
    kf.loc[oos, "p_holm"] = holm(kf.loc[oos, "p"]).to_numpy()
    rows = []
    for r in cmp[cmp.comparison == "strategy_minus_momentum"].itertuples(index=False):
        m = res.loc[r.strategy]
        rows.append({"label": LABEL, "strategy": r.strategy, "period": r.period,
                     "return_pa": m[f"{r.period}_return_pa"], "sharpe": m[f"{r.period}_sharpe"],
                     "maxDD": m[f"{r.period}_maxDD"], "trades": m[f"{r.period}_trades"], "DSR": m.get(f"{r.period}_DSR"),
                     "sr_diff_vs_momentum": r.sr_diff, "se_vs_momentum": r.se, "p_vs_momentum": r.p})
    for r in kf.itertuples(index=False):
        rows.append({"label": LABEL, "strategy": r.strategy + "_kelly_minus_fixed", "period": r.period,
                     "sr_diff_kelly_minus_fixed": r.sr_diff, "p_kelly_minus_fixed": r.p, "p_holm": r.p_holm})
    out = pd.DataFrame(rows)
    out.to_csv(out_csv, index=False)
    print(out.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    pd.DataFrame([{"timestamp": datetime.now().isoformat(timespec="seconds"),
                   "script": f"src/run_both_strategies.py ({tag}, outputs/{tag}_{TAG}/run.sh) + src/rung2_report.py --rung {rung}",
                   "scorers": rung, "period": "2024-04-30 .. 2026-06-01",
                   "what": f"{tag} strategies A/B vs continuous momentum, N = {n_trials} (exposed to look-ahead)",
                   "output": out_csv.name}]).to_csv(OUTPUTS / "test_period_runs.csv", mode="a", index=False, header=False)


if __name__ == "__main__":
    main()
