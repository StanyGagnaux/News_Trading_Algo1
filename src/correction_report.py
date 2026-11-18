"""
correction_report.py -- after the Bug 14 A/B correction run (note
`…note_c1_and_ab_correction_2026-10-24.md`):

  holm   Holm step-down for Kelly vs fixed, TEST period: family of 6
         (keyword + LLM x A, B t+5, B t+15) and rung 1b as a family of 3.
  1(b)   per calendar year, return and annualised Sharpe of every corrected
         A/B strategy plus momentum (descriptive).
  2      correlation matrices of daily returns, training and test (descriptive).

USAGE (from the project root):  python3 src/correction_report.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from paths import OUTPUTS
from newsdrift.stats import daily_returns
from descriptive_analyses import log_run

TAG = "bug14fix_2026-10-24"
DUMP = OUTPUTS / f"correction_{TAG}"
RUNGS = ["keyword", "llm", "embed_minilm"]
FAMILIES = {"H2b_family_6": ["keyword", "llm"], "rung1b_family_3": ["embed_minilm"]}
OUT_HOLM = OUTPUTS / f"holm_kelly_vs_fixed_{TAG}.csv"
OUT_YEARLY = OUTPUTS / f"descriptive_yearly_performance_{TAG}.csv"
OUT_CORR = OUTPUTS / f"descriptive_correlations_{TAG}.csv"
PERIOD = {"IS": "train", "OOS": "test"}
ANNUAL = 252


def holm(p: pd.Series) -> pd.Series:
    """Holm step-down adjusted p-values."""
    order = p.sort_values().index
    m = len(p)
    adj = (p[order] * np.arange(m, 0, -1)).cummax().clip(upper=1.0)
    return adj.reindex(p.index)


def holm_table() -> pd.DataFrame:
    parts = []
    for fam, rungs in FAMILIES.items():
        rows = []
        for rung in rungs:
            c = pd.read_csv(OUTPUTS / f"results_both_strategies_{rung}_calibrated_{TAG}_comparison.csv")
            c = c[(c.comparison == "kelly_minus_fixed") & (c.period == "OOS")]
            rows.append(c.assign(scorer=rung))
        f = pd.concat(rows, ignore_index=True)
        f["family"] = fam
        f["p_holm"] = holm(f.p).to_numpy()
        parts.append(f[["family", "scorer", "strategy", "sr_diff", "se", "p", "p_holm",
                        "gross_exposure_kelly", "gross_exposure_fixed"]])
    return pd.concat(parts, ignore_index=True)


def load_returns() -> dict:
    """{(period, series name): daily returns} for corrected A/B + momentum."""
    out = {}
    for rung in RUNGS:
        for f in sorted((DUMP / rung).glob("equity_*.csv")):
            name, tag = f.stem.removeprefix("equity_").rsplit("_", 1)
            if name.startswith("BENCHMARK") and rung != "keyword":
                continue                                   # momentum once
            label = name if name.startswith("BENCHMARK") else f"{rung}:{name}"
            eq = pd.read_csv(f, index_col=0).iloc[:, 0]
            eq.index = pd.to_datetime(eq.index, utc=True).tz_localize(None).normalize()   # A naive, B UTC
            out[(PERIOD[tag], label)] = daily_returns(eq)
    return out


def yearly(rets: dict) -> pd.DataFrame:
    rows = []
    for (period, name), r in rets.items():
        for yr, g in r.groupby(r.index.year):
            sd = g.std()
            rows.append({"period": period, "series": name, "year": yr, "days": len(g),
                         "return": float((1 + g).prod() - 1),
                         "sharpe_ann": float(g.mean() / sd * np.sqrt(ANNUAL)) if sd > 0 else np.nan})
    return pd.DataFrame(rows)


def correlations(rets: dict) -> pd.DataFrame:
    parts = []
    for period in ("train", "test"):
        wide = pd.DataFrame({n: r for (p, n), r in rets.items() if p == period})
        c = wide.corr()                                    # pairwise, overlapping days
        c.index.name = "series"
        parts.append(c.reset_index().assign(period=period))
    return pd.concat(parts, ignore_index=True)


def main():
    h = holm_table()
    h.to_csv(OUT_HOLM, index=False)
    print(h.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    rets = load_returns()
    yearly(rets).to_csv(OUT_YEARLY, index=False)
    correlations(rets).to_csv(OUT_CORR, index=False)
    log_run("1b", "yearly return and Sharpe, corrected A/B (Bug 14) + momentum, training + test", [OUT_YEARLY])
    log_run("2", "correlation matrices of daily returns, corrected A/B + momentum, training and test", [OUT_CORR])
    print(f"saved {OUT_HOLM.name}, {OUT_YEARLY.name}, {OUT_CORR.name}")


if __name__ == "__main__":
    main()
