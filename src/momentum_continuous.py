"""
momentum_continuous.py -- momentum benchmark corrections (note
`…note_momentum_2026-10-24.md`):

  1. one continuous momentum series from the first price date to the end of
     the test period on the runner's universe; training/test = slices; a
     truncation check asserts no look-ahead;
  2. a scaled series, scale chosen on TRAINING by calibrate_risk.calibrate
     (maxDD ~5%); Sharpe unchanged by construction (checked);
  3. Jobson-Korkie-Memmel Sharpe difference of every corrected A/B strategy
     (24 Oct Bug 14 runs, three rungs) vs the continuous benchmark, after
     checking the old benchmark reproduces the existing comparison exactly.

USAGE (from the project root):  python3 src/momentum_continuous.py
"""
from __future__ import annotations

from argparse import Namespace
from datetime import datetime

import numpy as np
import pandas as pd

from paths import PRICES, NEWS_CLEAN, OUTPUTS
from run_both_strategies import load_inputs, compare_strategies
from newsdrift import momentum_backtest, performance_metrics
from calibrate_risk import calibrate

TAG = "2026-10-24"
END = "2026-06-01"
TRUNCATE_AT = pd.Timestamp("2025-04-30")             # inside the test period
INDEX_TICKERS = {"NDX", "SPX", "VIX", "RF"}
CORR = OUTPUTS / "correction_bug14fix_2026-10-24"
RUNGS = {"keyword": "keyword", "llm": "llm", "embed_minilm": "embed_minilm"}
OUT_SUMMARY = OUTPUTS / f"momentum_continuous_{TAG}.csv"
OUT_EQUITY = OUTPUTS / f"momentum_continuous_equity_{TAG}.csv"
OUT_CMP = OUTPUTS / f"comparison_vs_continuous_momentum_{TAG}.csv"
JK_COLS = ["sr_diff", "se", "z", "p", "n", "rho"]


def full_history_prices(tickers) -> pd.DataFrame:
    px = pd.read_csv(PRICES, parse_dates=["date"])
    px = px[~px.ticker.isin(INDEX_TICKERS) & px.ticker.isin(tickers) & (px.date <= END)]
    return px


def period_curve(eq: pd.Series, lo, hi) -> pd.Series:
    """Equity from the last day before `lo` through `hi`, so every day of the
    period carries its return."""
    prev = eq.index[eq.index < lo]
    start = prev[-1] if len(prev) else eq.index[0]
    return eq.loc[start:hi]


def read_curve(path) -> pd.Series:
    s = pd.read_csv(path, index_col=0).iloc[:, 0]
    s.index = pd.to_datetime(s.index, utc=True)
    return s


def comparisons(bench: dict) -> pd.DataFrame:
    rows = []
    for rung in RUNGS:
        curves = {}
        for f in sorted((CORR / rung).glob("equity_*.csv")):
            name, tag = f.stem.removeprefix("equity_").rsplit("_", 1)
            curves.setdefault(name, {})[tag] = read_curve(f)
        old = compare_strategies(curves, {})
        old = old[old.comparison == "strategy_minus_momentum"]
        off = pd.read_csv(OUTPUTS / f"results_both_strategies_{rung}_calibrated_bug14fix_2026-10-24_comparison.csv")
        off = off[off.comparison == "strategy_minus_momentum"].merge(old, on=["strategy", "period"], suffixes=("_off", ""))
        assert len(off) == len(old) and all(np.allclose(off[c + "_off"], off[c], equal_nan=True) for c in JK_COLS), \
            f"{rung}: old benchmark does not reproduce the official comparison"
        res = {}
        for label, b in bench.items():
            c = compare_strategies({**curves, "BENCHMARK_momentum": b}, {})
            res[label] = c[c.comparison == "strategy_minus_momentum"].set_index(["strategy", "period"])[JK_COLS]
        assert np.allclose(res["continuous"], res["continuous_scaled"], equal_nan=True), "scaling changed a Sharpe test"
        new = res["continuous"].reset_index().assign(rung=rung)
        prev = old.set_index(["strategy", "period"])[["sr_diff", "se", "p"]].add_suffix("_superseded").reset_index()
        rows.append(new.merge(prev, on=["strategy", "period"]))
        print(f"  {rung}: old benchmark reproduces the official comparison; scaled = unscaled in every test")
    return pd.concat(rows, ignore_index=True)


def main():
    cfg, px, _, _, _, P = load_inputs(Namespace(
        prices=str(PRICES), news=str(NEWS_CLEAN), start="2016-01-01", end=END,
        train_frac=0.80, llm_scores=None, tier0=False))
    pxa = full_history_prices(px.ticker.unique())
    print(f"  continuous momentum: {pxa.ticker.nunique()} tickers, {pxa.date.min().date()} -> {pxa.date.max().date()}")
    mom = lambda d, k=1.0: momentum_backtest(d, cfg.momentum, cfg.cost, cfg.initial_equity, risk_scale=k)
    eq = mom(pxa)

    cut = mom(pxa[pxa.date <= TRUNCATE_AT])                 # no look-ahead
    assert np.allclose(cut.to_numpy(), eq.loc[:TRUNCATE_AT].to_numpy(), rtol=0, atol=1e-9), \
        "LOOK-AHEAD: momentum up to the cut depends on later prices"
    print(f"  truncation check passed: series cut at {TRUNCATE_AT.date()} identical up to that date")

    is_lo, is_hi = P["IS"]
    k = calibrate("momentum", lambda s: performance_metrics(period_curve(mom(pxa, s), is_lo, is_hi)))["risk_scale"]
    eq_k = mom(pxa, k)
    rows, bench = [], {"continuous": {}, "continuous_scaled": {}}
    for tag, (lo, hi) in P.items():
        frozen = momentum_backtest(px[(px.date >= lo) & (px.date <= hi)], cfg.momentum, cfg.cost, cfg.initial_equity)
        for label, curve, scale in (("frozen_per_period", frozen, 1.0),
                                    ("continuous", period_curve(eq, lo, hi), 1.0),
                                    ("continuous_scaled", period_curve(eq_k, lo, hi), k)):
            m = performance_metrics(curve)
            r = curve.pct_change().dropna()
            rows.append({"series": label, "period": tag, "risk_scale": scale, "return_pa": m["ann_return"],
                         "sharpe": m["sharpe"], "sharpe_arith": r.mean() / r.std() * np.sqrt(252),
                         "maxDD": m["max_drawdown"],
                         "vol_ann": curve.pct_change().std() * np.sqrt(252), "days": len(curve) - 1})
            if label != "frozen_per_period":
                bench[label][tag] = curve
        # mean/std Sharpe (the one the comparison tests use) is scale-free exactly;
        # the reported Sharpe (CAGR / vol) moves only by volatility drag
        assert abs(rows[-1]["sharpe_arith"] - rows[-2]["sharpe_arith"]) < 1e-9, "scaled Sharpe differs"
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT_SUMMARY, index=False)
    pd.DataFrame({"continuous": eq, "continuous_scaled": eq_k}).to_csv(OUT_EQUITY)
    print(f"  scale k = {k} (training maxDD ~5%); mean/std Sharpe identical scaled vs unscaled (checked)")
    print(summary.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    cmp = comparisons(bench)
    cmp.to_csv(OUT_CMP, index=False)
    print(cmp[cmp.period == "OOS"][["rung", "strategy", "sr_diff", "se", "p", "sr_diff_superseded", "p_superseded"]]
          .to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    pd.DataFrame([{"timestamp": datetime.now().isoformat(timespec="seconds"),
                   "script": "src/momentum_continuous.py (note …note_momentum_2026-10-24.md)",
                   "scorers": "keyword+llm_anon+embed_minilm", "period": "2024-04-30 .. 2026-06-01",
                   "what": "continuous momentum benchmark; Sharpe difference vs momentum rerun for corrected A/B",
                   "output": OUT_CMP.name}]).to_csv(OUTPUTS / "test_period_runs.csv", mode="a", index=False, header=False)


if __name__ == "__main__":
    main()
