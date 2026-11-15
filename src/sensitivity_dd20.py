"""
sensitivity_dd20.py -- DESCRIPTIVE sensitivity analysis at a 20% drawdown
target (note `…note_sensitivity_dd20_2026-10-25.md`). The official results
stay at 5%.

For every rung x strategy (A, B t+5, B t+15, minute-bar C; fixed and Kelly):
test return p.a., Sharpe, maximum drawdown, trades, share of test days on
which an exposure cap binds, and the Jobson-Korkie-Memmel Sharpe difference
vs continuous momentum (scaled to the same training drawdown), at 5% and 20%
side by side. The 5% runs must reproduce the official 5% results exactly.

USAGE (from the project root):  python3 src/sensitivity_dd20.py
"""
from __future__ import annotations

import json
from argparse import Namespace

import numpy as np
import pandas as pd

from paths import OUTPUTS, PRICES, NEWS_CLEAN
from run_both_strategies import load_inputs, compare_strategies
from momentum_continuous import full_history_prices, period_curve, read_curve, END
from newsdrift import momentum_backtest, performance_metrics
from calibrate_risk import calibrate

TAG = "2026-10-25"
SENS = OUTPUTS / f"sensitivity_dd20_{TAG}"
OUT = OUTPUTS / f"sensitivity_dd20_summary_{TAG}.csv"
OFFICIAL = {"keyword": "2026-10-24", "llm": "2026-10-24", "embed_minilm": "2026-10-24",
            "haiku": "2026-10-25", "sonnet": "2026-10-25"}
TARGETS = {"dd05": 0.05, "dd20": 0.20}
MATERIAL = 0.20                                  # |Sharpe change| flagged for explanation


def reproduced(rung: str) -> bool:
    a = pd.read_csv(OUTPUTS / f"results_both_strategies_{rung}_calibrated_cminute_{OFFICIAL[rung]}.csv", index_col=0)
    b = pd.read_csv(OUTPUTS / f"results_both_strategies_{rung}_calibrated_dd05check_{TAG}.csv", index_col=0)
    num = a.select_dtypes("number").columns
    return a.shape == b.shape and np.allclose(a[num].to_numpy(float), b.loc[a.index, num].to_numpy(float), equal_nan=True)


def momentum_curves() -> dict:
    """{target: {"scale", "IS", "OOS"}} for continuous momentum scaled to each training drawdown."""
    cfg, px, _, _, _, P = load_inputs(Namespace(prices=str(PRICES), news=str(NEWS_CLEAN), start="2016-01-01",
                                                end=END, train_frac=0.80, llm_scores=None, tier0=False))
    pxa = full_history_prices(px.ticker.unique())
    mom = lambda k: momentum_backtest(pxa, cfg.momentum, cfg.cost, cfg.initial_equity, risk_scale=k)
    out = {}
    for name, target in TARGETS.items():
        k = calibrate(f"momentum {name}", lambda s: performance_metrics(period_curve(mom(s), *P["IS"])), target)["risk_scale"]
        eq = mom(k)
        out[name] = {"scale": k, **{tag: period_curve(eq, *P[tag]) for tag in ("IS", "OOS")}}
    return out


def rung_rows(rung: str, mom: dict) -> list[dict]:
    rows = []
    for name in TARGETS:
        dump = SENS / name / rung
        res = pd.read_csv(OUTPUTS / f"results_both_strategies_{rung}_calibrated_{'dd05check' if name == 'dd05' else 'dd20'}_{TAG}.csv",
                          index_col=0)
        caps = json.loads((dump / "cap_days.json").read_text())
        curves = {}
        for f in sorted(dump.glob("equity_*.csv")):
            nm, tag = f.stem.removeprefix("equity_").rsplit("_", 1)
            if not nm.startswith("BENCHMARK"):
                curves.setdefault(nm, {})[tag] = read_curve(f)
        bench = {tag: mom[name][tag] for tag in ("IS", "OOS")}
        cmp = compare_strategies({**curves, "BENCHMARK_momentum": bench}, {})
        cmp = cmp[(cmp.comparison == "strategy_minus_momentum") & (cmp.period == "OOS")].set_index("strategy")
        for strat in cmp.index:
            m = res.loc[strat]
            test_days = max(len(curves[strat]["OOS"]) - 1, 1)
            rows.append({"rung": rung, "strategy": strat, "target": name, "IS_maxDD": m["IS_maxDD"],
                         "return_pa": m["OOS_return_pa"], "sharpe": m["OOS_sharpe"], "maxDD": m["OOS_maxDD"],
                         "trades": m["OOS_trades"], "cap_bind_share": len(caps.get(strat, {}).get("OOS", [])) / test_days,
                         "sr_diff_vs_momentum": cmp.loc[strat, "sr_diff"], "p_vs_momentum": cmp.loc[strat, "p"]})
    return rows


def main():
    mom = momentum_curves()
    rows, checks = [], {}
    for rung in OFFICIAL:
        checks[rung] = reproduced(rung)
        print(f"  {rung}: 5% repeat reproduces the official 5% results exactly: {checks[rung]}")
        rows += rung_rows(rung, mom)
    for name in TARGETS:
        m = performance_metrics(mom[name]["OOS"])
        rows.append({"rung": "benchmark", "strategy": f"momentum_continuous (scale {mom[name]['scale']})", "target": name,
                     "IS_maxDD": performance_metrics(mom[name]["IS"])["max_drawdown"], "return_pa": m["ann_return"],
                     "sharpe": m["sharpe"], "maxDD": m["max_drawdown"]})
    long = pd.DataFrame(rows)
    wide = long.pivot_table(index=["rung", "strategy"], columns="target",
                            values=["IS_maxDD", "return_pa", "sharpe", "maxDD", "trades", "cap_bind_share",
                                    "sr_diff_vs_momentum", "p_vs_momentum"], aggfunc="first")
    wide.columns = [f"{v}_{t}" for v, t in wide.columns]
    wide = wide.reset_index()
    wide["sharpe_change"] = wide.sharpe_dd20 - wide.sharpe_dd05
    wide["material"] = wide.sharpe_change.abs() > MATERIAL
    wide["dd05_reproduces_official"] = wide.rung.map(checks)
    wide.to_csv(OUT, index=False)
    pd.set_option("display.width", 250)
    print(wide.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
