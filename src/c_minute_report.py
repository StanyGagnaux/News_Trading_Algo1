"""
c_minute_report.py -- comparison tests for the minute-only Strategy C runs
(note `…note_c_minute_2026-10-24.md`, section 4): Jobson-Korkie-Memmel Sharpe
difference vs the CONTINUOUS momentum benchmark, Kelly - fixed with Holm
(family of 2: keyword + LLM C; rung 1b C on its own), deflated Sharpe from
the runner (N unchanged). Also checks that A and B in these runs equal the
24 Oct Bug 14 correction (same engine, same recalibrated scales).

USAGE (from the project root):  python3 src/c_minute_report.py
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from paths import OUTPUTS
from run_both_strategies import compare_strategies
from momentum_continuous import period_curve, read_curve
from correction_report import holm

TAG = "cminute_2026-10-24"
DUMP = OUTPUTS / "c_minute_2026-10-24"
RUNGS = ["keyword", "llm", "embed_minilm"]
FAMILIES = {"C_family_2": ["keyword", "llm"], "C_rung1b_alone": ["embed_minilm"]}
MOMENTUM = OUTPUTS / "momentum_continuous_equity_2026-10-24.csv"
EARLIER_AB = OUTPUTS / "comparison_vs_continuous_momentum_2026-10-24.csv"
OUT = OUTPUTS / "c_minute_summary_2026-10-24.csv"


def load_curves(rung: str) -> dict:
    curves = {}
    for f in sorted((DUMP / rung).glob("equity_*.csv")):
        name, tag = f.stem.removeprefix("equity_").rsplit("_", 1)
        curves.setdefault(name, {})[tag] = read_curve(f)
    return curves


def continuous_benchmark(curves: dict) -> dict:
    eq = pd.read_csv(MOMENTUM, index_col=0, parse_dates=True).continuous
    eq.index = eq.index.tz_localize("UTC")
    ref = curves["A_daily_1-3d_fixed" if "A_daily_1-3d_fixed" in curves else next(iter(curves))]
    return {tag: period_curve(eq, c.index.min(), c.index.max()) for tag, c in ref.items()}


def main():
    earlier = pd.read_csv(EARLIER_AB).set_index(["rung", "strategy", "period"])
    rows = []
    for rung in RUNGS:
        curves = {k: v for k, v in load_curves(rung).items() if not k.startswith("BENCHMARK")}
        cmp = compare_strategies({**curves, "BENCHMARK_momentum": continuous_benchmark(curves)}, {})
        vs_mom = cmp[cmp.comparison == "strategy_minus_momentum"]
        ab = vs_mom[~vs_mom.strategy.str.startswith("C_")].assign(rung=rung).set_index(["rung", "strategy", "period"])
        same = np.allclose(ab.sr_diff, earlier.loc[ab.index, "sr_diff"])
        print(f"  {rung}: A/B rows equal the Bug 14 correction vs continuous momentum: {same}")
        res = pd.read_csv(OUTPUTS / f"results_both_strategies_{rung}_calibrated_{TAG}.csv", index_col=0)
        kf = pd.read_csv(OUTPUTS / f"results_both_strategies_{rung}_calibrated_{TAG}_comparison.csv")
        kf = kf[(kf.comparison == "kelly_minus_fixed") & kf.strategy.str.startswith("C_")]
        for r in vs_mom[vs_mom.strategy.str.startswith("C_")].itertuples(index=False):
            m = res.loc[r.strategy]
            rows.append({"rung": rung, "strategy": r.strategy, "period": r.period,
                         "return_pa": m[f"{r.period}_return_pa"], "sharpe": m[f"{r.period}_sharpe"],
                         "maxDD": m[f"{r.period}_maxDD"], "trades": m[f"{r.period}_trades"],
                         "DSR": m.get(f"{r.period}_DSR"), "sr_diff_vs_momentum": r.sr_diff,
                         "se_vs_momentum": r.se, "p_vs_momentum": r.p})
        for r in kf.itertuples(index=False):
            rows.append({"rung": rung, "strategy": r.strategy + "_kelly_minus_fixed", "period": r.period,
                         "sr_diff_kelly_minus_fixed": r.sr_diff, "se_kelly_minus_fixed": r.se,
                         "p_kelly_minus_fixed": r.p})
    out = pd.DataFrame(rows)
    out["p_holm"] = np.nan
    for fam, rungs in FAMILIES.items():
        sel = out.strategy.str.endswith("_kelly_minus_fixed") & (out.period == "OOS") & out.rung.isin(rungs)
        out.loc[sel, "p_holm"] = holm(out.loc[sel, "p_kelly_minus_fixed"]).to_numpy()
        out.loc[sel, "holm_family"] = fam
    out.to_csv(OUT, index=False)
    print(out.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    pd.DataFrame([{"timestamp": datetime.now().isoformat(timespec="seconds"),
                   "script": "src/run_both_strategies.py --c-engine minute (outputs/c_minute_2026-10-24/run.sh) + src/c_minute_report.py",
                   "scorers": "keyword+llm_anon+embed_minilm", "period": "2024-04-30 .. 2026-06-01",
                   "what": "Strategy C minute-only (note …note_c_minute_2026-10-24.md), disclosed correction, vs continuous momentum",
                   "output": OUT.name}]).to_csv(OUTPUTS / "test_period_runs.csv", mode="a", index=False, header=False)


if __name__ == "__main__":
    main()
