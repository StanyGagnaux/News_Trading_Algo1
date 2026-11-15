"""
descriptive_correlations_contmom.py -- descriptive item 2 recomputed against the
CONTINUOUS momentum benchmark (note `…note_momentum_2026-10-24.md`), 30 Oct 2026.

Daily-return correlation of every corrected strategy run (A and B after Bug 14,
minute-bar C; rungs keyword, llm, embed_minilm, haiku, sonnet) with the
continuous momentum series, training (IS) and test (OOS) separately. Daily
returns = equity.pct_change() (newsdrift.stats.daily_returns), correlated on
the overlapping days of each strategy's own equity file. For reference the
superseded per-period benchmark of the same run folder is kept in a second
column. Read-only inputs; the earlier file
`descriptive_correlations_bug14fix_2026-10-24.csv` is left unchanged.

USAGE (from the project root):  python3 src/descriptive_correlations_contmom.py
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from paths import OUTPUTS
from newsdrift.stats import daily_returns

TAG = "2026-10-30"
MOMENTUM = OUTPUTS / "momentum_continuous_equity_2026-10-24.csv"
RUN_DIRS = {"keyword": OUTPUTS / "c_minute_2026-10-24" / "keyword",
            "llm": OUTPUTS / "c_minute_2026-10-24" / "llm",
            "embed_minilm": OUTPUTS / "c_minute_2026-10-24" / "embed_minilm",
            "haiku": OUTPUTS / "c_minute_rungs23_2026-10-25" / "haiku",
            "sonnet": OUTPUTS / "c_minute_rungs23_2026-10-25" / "sonnet"}
PERIOD = {"IS": "train", "OOS": "test"}
OUT = OUTPUTS / f"descriptive_correlations_contmom_{TAG}.csv"
RUN_LOG = OUTPUTS / "descriptive_runs.csv"


def read_returns(path: Path) -> pd.Series:
    eq = pd.read_csv(path, index_col=0).iloc[:, 0]
    eq.index = pd.to_datetime(eq.index, utc=True).tz_localize(None).normalize()   # A naive, B/C UTC
    return daily_returns(eq)


def continuous_returns() -> pd.Series:
    eq = pd.read_csv(MOMENTUM, index_col=0, parse_dates=True).continuous
    return daily_returns(eq)


def corr_on_overlap(a: pd.Series, b: pd.Series) -> tuple[float, int]:
    both = pd.concat([a, b], axis=1, join="inner").dropna()
    return (float(both.iloc[:, 0].corr(both.iloc[:, 1])) if len(both) > 2 else float("nan")), len(both)


def build() -> pd.DataFrame:
    bench = continuous_returns()
    rows = []
    for rung, d in RUN_DIRS.items():
        old = {tag: read_returns(d / f"equity_BENCHMARK_momentum_{tag}.csv") for tag in PERIOD}
        for f in sorted(d.glob("equity_*.csv")):
            name, tag = f.stem.removeprefix("equity_").rsplit("_", 1)
            if name.startswith("BENCHMARK"):
                continue
            r = read_returns(f)
            c_new, n = corr_on_overlap(r, bench)
            c_old, _ = corr_on_overlap(r, old[tag])
            rows.append({"period": PERIOD[tag], "rung": rung, "strategy": name, "days": n,
                         "corr_continuous_momentum": c_new,
                         "corr_per_period_momentum_superseded": c_old})
    return pd.DataFrame(rows)


def main():
    tab = build()
    tab.to_csv(OUT, index=False)
    row = {"timestamp": datetime.now().isoformat(timespec="seconds"), "item": "2-rerun",
           "script": "src/descriptive_correlations_contmom.py",
           "what": "daily-return correlation with the CONTINUOUS momentum benchmark, corrected A/B + minute-bar C, five rungs, training and test",
           "kind": "descriptive (no new test, no tuning)", "outputs": OUT.name}
    pd.DataFrame([row]).to_csv(RUN_LOG, mode="a", index=False, header=not RUN_LOG.exists())
    print(tab.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(f"saved {OUT.name}")


if __name__ == "__main__":
    main()
