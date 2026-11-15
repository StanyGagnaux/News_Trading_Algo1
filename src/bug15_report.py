"""
bug15_report.py -- derived tables of the Bug 15 correction run (notes
`…note_bug15_2026-11-10.md` and `…note_bug15_addendum_testD2_2026-11-10.md`).

Built from STORED files only: the Strategy A runs of 10 Nov 2026 (5% and 20%),
the unchanged B and C rows of the official files of 24/25 Oct, and the stored
continuous momentum series of 24 Oct. No strategy and no benchmark is run.
Wherever a rule of an earlier script is re-applied (Holm, best strategy per
rung, adjacent-rung difference, Sharpe test against scaled momentum), it is
first checked to reproduce the earlier official file from the earlier inputs.

USAGE (from the project root):  python3 src/bug15_report.py
"""
from __future__ import annotations

import json
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from paths import OUTPUTS
from run_both_strategies import compare_strategies, _naive_returns
from momentum_continuous import read_curve
from c_minute_report import continuous_benchmark
from correction_report import holm, yearly
from newsdrift.stats import sharpe_diff_test, daily_returns

DATE = "2026-11-10"
TAG = f"bug15fix_{DATE}"
DUMP = OUTPUTS / f"correction_{TAG}"
RUNGS = ["keyword", "llm", "embed_minilm", "haiku", "sonnet"]
FREE = ["keyword", "llm", "embed_minilm"]
OLD_AB = {r: f"{r}_calibrated_bug14fix_2026-10-24" for r in FREE} | {r: f"{r}_calibrated_2026-10-25" for r in ("haiku", "sonnet")}
OLD_C = {r: f"{r}_calibrated_cminute_2026-10-24" for r in FREE} | {r: f"{r}_calibrated_cminute_2026-10-25" for r in ("haiku", "sonnet")}
OLD_AB_DUMP = {r: OUTPUTS / "correction_bug14fix_2026-10-24" / r for r in FREE} | {
    "haiku": OUTPUTS / "rung2_2026-10-25", "sonnet": OUTPUTS / "rung3_2026-10-25"}
OLD_C_DUMP = {r: OUTPUTS / "c_minute_2026-10-24" / r for r in FREE} | {
    r: OUTPUTS / "c_minute_rungs23_2026-10-25" / r for r in ("haiku", "sonnet")}
OLD_CAL = {r: f"risk_calibration_{r}_bug14fix_2026-10-24.csv" for r in FREE} | {
    r: f"risk_calibration_{r}_2026-10-25.csv" for r in ("haiku", "sonnet")}
RUNG_SUMMARY = {"haiku": "rung2_summary_2026-10-25.csv", "sonnet": "rung3_summary_2026-10-25.csv"}
N_AB = {"keyword": 139, "llm": 139, "embed_minilm": 155, "haiku": 155, "sonnet": 161}
N_C = {"keyword": 139, "llm": 139, "embed_minilm": 155, "haiku": 155, "sonnet": 163}
FAMILIES = {"H2b_family_6": ["keyword", "llm"], "rung1b_family_3": ["embed_minilm"],
            "rung2_family_3": ["haiku"], "rung3_family_3": ["sonnet"]}
LADDER_LABEL = {"keyword": "keyword", "llm": "llm_anon", "embed_minilm": "embed_minilm", "haiku": "haiku", "sonnet": "sonnet"}
PERIOD = {"IS": "train", "OOS": "test"}
JK = ["sr_diff", "se", "z", "p", "n", "rho"]
ANNUAL = 252
MATERIAL = 0.20
NEW_SOURCE = f"Bug 15 correction run {DATE}"


def out(name: str):
    return OUTPUTS / name


def results(stem: str) -> pd.DataFrame:
    return pd.read_csv(OUTPUTS / f"results_both_strategies_{stem}.csv", index_col=0)


def comparison(stem: str) -> pd.DataFrame:
    return pd.read_csv(OUTPUTS / f"results_both_strategies_{stem}_comparison.csv")


def a_curves(dump) -> dict:
    """{strategy: {IS|OOS: equity}} for the Strategy A dumps of one run folder."""
    curves = {}
    for f in sorted(dump.glob("equity_A_*.csv")):
        name, tag = f.stem.removeprefix("equity_").rsplit("_", 1)
        curves.setdefault(name, {})[tag] = read_curve(f)
    return curves


def vs_momentum(curves: dict) -> pd.DataFrame:
    cmp = compare_strategies({**curves, "BENCHMARK_momentum": continuous_benchmark(curves)}, {})
    return cmp[cmp.comparison == "strategy_minus_momentum"].set_index(["strategy", "period"])[JK]


def sharpe_arith(equity: pd.Series) -> float:
    r = daily_returns(equity)
    return float(r.mean() / r.std() * np.sqrt(ANNUAL))


# ---------------------------------------------------------------- ten A rows, old beside new
def old_vs_new() -> pd.DataFrame:
    rows = []
    for target, new_suffix, old_stem, old_cal in (
            ("dd05", f"calibrated_{TAG}", OLD_AB, OLD_CAL),
            ("dd20", f"calibrated_dd20_{TAG}", {r: f"{r}_calibrated_dd20_2026-10-25" for r in RUNGS},
             {r: f"risk_calibration_{r}_dd20_2026-10-25.csv" for r in RUNGS})):
        for rung in RUNGS:
            new, old = results(f"{rung}_{new_suffix}"), results(old_stem[rung])
            cal_name = f"risk_calibration_{rung}_{TAG}.csv" if target == "dd05" else f"risk_calibration_{rung}_dd20_{TAG}.csv"
            cal_new = pd.read_csv(OUTPUTS / cal_name).set_index("sizer").risk_scale
            cal_old = pd.read_csv(OUTPUTS / old_cal[rung])
            cal_old = cal_old[cal_old.strategy == "A_daily_1-3d"].set_index("sizer").risk_scale
            curves = a_curves(DUMP / target / rung)
            for strat in [s for s in new.index if s.startswith("A_")]:
                sizer = "kelly" if "_kelly" in strat else "fixed"
                for tag in PERIOD:
                    cell = lambda df, col: df.loc[strat, f"{tag}_{col}"]
                    rows.append({"target": target, "rung": rung, "strategy": strat, "sizer": sizer, "period": PERIOD[tag],
                                 "scale_old": cal_old[sizer], "scale_new": cal_new[sizer],
                                 **{f"{k}_{v}": cell(df, col) for v, df in (("old", old), ("new", new))
                                    for k, col in (("return_pa", "return_pa"), ("sharpe", "sharpe"), ("maxDD", "maxDD"),
                                                   ("trades", "trades"), ("DSR", "DSR"))},
                                 "sharpe_mean_over_sd_new": sharpe_arith(curves[strat][tag])})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- forty configurations vs continuous momentum
def carried_rows(rung: str) -> pd.DataFrame:
    """Unchanged B and C rows with their official continuous-momentum comparison."""
    ab, cm = results(OLD_AB[rung]), results(OLD_C[rung])
    if rung in FREE:
        b = pd.read_csv(out("comparison_vs_continuous_momentum_2026-10-24.csv"))
        b = b[(b.rung == rung) & b.strategy.str.startswith("B_")][["strategy", "period", *JK]]
        b_file = "comparison_vs_continuous_momentum_2026-10-24.csv"
        c = pd.read_csv(out("c_minute_summary_2026-10-24.csv"))
        c_file = "c_minute_summary_2026-10-24.csv"
    else:
        b = pd.read_csv(out(RUNG_SUMMARY[rung]))
        b = b[b.strategy.str.startswith("B_") & b.return_pa.notna()].rename(columns={
            "sr_diff_vs_momentum": "sr_diff", "se_vs_momentum": "se", "p_vs_momentum": "p"})[["strategy", "period", "sr_diff", "se", "p"]]
        b_file = RUNG_SUMMARY[rung]
        c = pd.read_csv(out("c_minute_rungs2_3_summary_2026-10-25.csv"))
        c_file = "c_minute_rungs2_3_summary_2026-10-25.csv"
    c = c[(c.rung == rung) & c.strategy.str.startswith("C_") & c.return_pa.notna()].rename(columns={
        "sr_diff_vs_momentum": "sr_diff", "se_vs_momentum": "se", "p_vs_momentum": "p"})[["strategy", "period", "sr_diff", "se", "p"]]
    parts = []
    for part, res, n, src in ((b, ab, N_AB[rung], b_file), (c, cm, N_C[rung], c_file)):
        part = part.copy()
        for col in ("return_pa", "sharpe", "maxDD", "trades", "DSR"):
            part[col] = [res.loc[s, f"{p}_{col}"] for s, p in zip(part.strategy, part.period)]
        parts.append(part.assign(dsr_trials_N=n, source=f"carried over unchanged: {src}"))
    return pd.concat(parts, ignore_index=True)


def superseded_a(rung: str) -> pd.DataFrame:
    if rung in FREE:
        s = pd.read_csv(out("comparison_vs_continuous_momentum_2026-10-24.csv"))
        s = s[(s.rung == rung) & s.strategy.str.startswith("A_")][["strategy", "period", "sr_diff", "se", "p"]]
    else:
        s = pd.read_csv(out(RUNG_SUMMARY[rung]))
        s = s[s.strategy.str.startswith("A_") & s.return_pa.notna()].rename(columns={
            "sr_diff_vs_momentum": "sr_diff", "se_vs_momentum": "se", "p_vs_momentum": "p"})[["strategy", "period", "sr_diff", "se", "p"]]
    old = results(OLD_AB[rung])
    s = s.assign(sharpe=[old.loc[st, f"{p}_sharpe"] for st, p in zip(s.strategy, s.period)],
                 return_pa=[old.loc[st, f"{p}_return_pa"] for st, p in zip(s.strategy, s.period)])
    return s.set_index(["strategy", "period"]).add_suffix("_superseded").reset_index()


def forty_configurations() -> pd.DataFrame:
    parts = []
    for rung in RUNGS:
        new = results(f"{rung}_calibrated_{TAG}")
        vs = vs_momentum(a_curves(DUMP / "dd05" / rung)).reset_index()
        runner = comparison(f"{rung}_calibrated_{TAG}")
        runner = runner[runner.comparison == "strategy_minus_momentum"].set_index(["strategy", "period"])[JK]
        assert np.allclose(vs.set_index(["strategy", "period"])[JK], runner.loc[list(zip(vs.strategy, vs.period))],
                           rtol=0, atol=1e-12), f"{rung}: recomputed comparison differs from the runner's own file"
        for col in ("return_pa", "sharpe", "maxDD", "trades", "DSR"):
            vs[col] = [new.loc[s, f"{p}_{col}"] for s, p in zip(vs.strategy, vs.period)]
        vs = vs.assign(dsr_trials_N=N_AB[rung], source=NEW_SOURCE).merge(superseded_a(rung), on=["strategy", "period"], how="left")
        parts.append(pd.concat([vs, carried_rows(rung)], ignore_index=True).assign(rung=rung))
    table = pd.concat(parts, ignore_index=True)
    assert len(table) == 80 and table.groupby("rung").size().eq(16).all(), "expected 40 configurations x 2 periods"
    front = ["rung", "strategy", "period", "source", "return_pa", "sharpe", "maxDD", "trades", "DSR", "dsr_trials_N"]
    return table[front + [c for c in table.columns if c not in front]]


def recounts(table: pd.DataFrame, label: str) -> dict:
    test, train = table[table.period == "OOS"], table[table.period == "IS"]
    worse = test[(test.sr_diff < 0) & (test.p < 0.05)]
    best = test.loc[test.groupby("rung").sharpe.idxmax()].set_index("rung")
    return {"basis": label, "configurations": len(test), "losing_in_test": int((test.return_pa < 0).sum()),
            "significantly_worse_than_momentum_5pct": int(len(worse)),
            "largest_p_among_significantly_worse": float(worse.p.max()), "smallest_p_not_significant": float(test[test.p >= 0.05].p.min()),
            "better_than_momentum_point_estimate": int((test.sr_diff > 0).sum()),
            "se_sharpe_diff_min": float(test.se.min()), "se_sharpe_diff_max": float(test.se.max()),
            "training_maxDD_min": float(train.maxDD.min()), "training_maxDD_max": float(train.maxDD.max()),
            **{f"best_{r}": f"{best.loc[r, 'strategy']} | Sharpe {best.loc[r, 'sharpe']:.4f} | DSR {best.loc[r, 'DSR']:.6f} "
                            f"(N {best.loc[r, 'dsr_trials_N']}) | vs momentum {best.loc[r, 'sr_diff']:+.4f}, p {best.loc[r, 'p']:.4f}"
               for r in RUNGS}}


def with_superseded_a(table: pd.DataFrame) -> pd.DataFrame:
    """The forty configurations as they stood before the correction (old A rows), for the before/after recount."""
    old = table.copy()
    a = old.strategy.str.startswith("A_")
    for rung in RUNGS:
        res, sel = results(OLD_AB[rung]), a & (old.rung == rung)
        for col in ("return_pa", "sharpe", "maxDD", "DSR"):
            old.loc[sel, col] = [res.loc[s, f"{p}_{col}"] for s, p in zip(old[sel].strategy, old[sel].period)]
    for col in ("sr_diff", "se", "p"):
        old.loc[a, col] = old.loc[a, f"{col}_superseded"]
    return old


# ---------------------------------------------------------------- Holm, Kelly minus fixed
def holm_table() -> pd.DataFrame:
    cols = ["sr_diff", "se", "p", "mean_diff_pa", "t_mean_diff", "gross_exposure_kelly", "gross_exposure_fixed"]
    parts = []
    for family, rungs in FAMILIES.items():
        rows = []
        for rung in rungs:
            new, old = comparison(f"{rung}_calibrated_{TAG}"), comparison(OLD_AB[rung])
            pick = lambda c, prefix: c[(c.comparison == "kelly_minus_fixed") & (c.period == "OOS") & c.strategy.str.startswith(prefix)]
            rows.append(pick(new, "A_").assign(scorer=rung, source=NEW_SOURCE))
            rows.append(pick(old, "B_").assign(scorer=rung, source=f"carried over unchanged: results_both_strategies_{OLD_AB[rung]}_comparison.csv"))
        f = pd.concat(rows, ignore_index=True)
        f["family"], f["p_holm"] = family, holm(f.p).to_numpy()
        parts.append(f[["family", "scorer", "strategy", *cols[:3], "p_holm", *cols[3:], "source"]])
    return pd.concat(parts, ignore_index=True)


def check_holm_rule() -> None:
    """The family construction reproduces the official Holm file of 24 Oct from the old A rows."""
    official = pd.read_csv(out("holm_kelly_vs_fixed_bug14fix_2026-10-24.csv")).set_index(["scorer", "strategy"])
    for family in ("H2b_family_6", "rung1b_family_3"):
        f = pd.concat([comparison(OLD_AB[r]).query("comparison == 'kelly_minus_fixed' and period == 'OOS'").assign(scorer=r)
                       for r in FAMILIES[family]], ignore_index=True)
        f["p_holm"] = holm(f.p).to_numpy()
        ref = official.loc[list(zip(f.scorer, f.strategy)), "p_holm"].to_numpy()
        assert np.allclose(f.p_holm, ref, rtol=0, atol=1e-12), f"{family}: Holm rule does not reproduce the 24 Oct file"


# ---------------------------------------------------------------- 20% sensitivity
def check_scale_free_momentum_test() -> float:
    """The 25 Oct summary tested against momentum SCALED to the same training drawdown. The Sharpe test is
    scale-free, so the stored unscaled series must reproduce those cells from the old dumps. Returns the max gap."""
    official = pd.read_csv(out("sensitivity_dd20_summary_2026-10-25.csv")).set_index(["rung", "strategy"])
    gap = 0.0
    for rung in RUNGS:
        for target in ("dd05", "dd20"):
            vs = vs_momentum(a_curves(OUTPUTS / "sensitivity_dd20_2026-10-25" / target / rung))
            for (strat, tag), row in vs.iterrows():
                if tag == "OOS":
                    ref = official.loc[(rung, strat)]
                    gap = max(gap, abs(row.sr_diff - ref[f"sr_diff_vs_momentum_{target}"]), abs(row.p - ref[f"p_vs_momentum_{target}"]))
    assert gap < 1e-9, f"unscaled momentum does not reproduce the 25 Oct scaled-momentum tests (max gap {gap})"
    return gap


def sensitivity_summary(table_a: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for rung in RUNGS:
        row_by_strat = {}
        for target in ("dd05", "dd20"):
            dump = DUMP / target / rung
            curves, caps = a_curves(dump), json.loads((dump / "cap_days.json").read_text())
            vs = vs_momentum(curves)
            for strat, cur in curves.items():
                a = table_a[(table_a.target == target) & (table_a.rung == rung) & (table_a.strategy == strat)].set_index("period")
                test_days = max(len(cur["OOS"]) - 1, 1)
                row_by_strat.setdefault(strat, {"rung": rung, "strategy": strat}).update({
                    f"risk_scale_{target}": a.loc["test", "scale_new"], f"IS_maxDD_{target}": a.loc["train", "maxDD_new"],
                    f"cap_bind_share_{target}": len(caps.get(strat, {}).get("OOS", [])) / test_days,
                    f"maxDD_{target}": a.loc["test", "maxDD_new"], f"p_vs_momentum_{target}": vs.loc[(strat, "OOS"), "p"],
                    f"return_pa_{target}": a.loc["test", "return_pa_new"], f"sharpe_{target}": a.loc["test", "sharpe_new"],
                    f"sharpe_mean_over_sd_{target}": a.loc["test", "sharpe_mean_over_sd_new"],
                    f"sr_diff_vs_momentum_{target}": vs.loc[(strat, "OOS"), "sr_diff"], f"trades_{target}": a.loc["test", "trades_new"]})
        rows += list(row_by_strat.values())
    wide = pd.DataFrame(rows)
    wide["sharpe_change"] = wide.sharpe_dd20 - wide.sharpe_dd05
    wide["sharpe_mean_over_sd_change"] = wide.sharpe_mean_over_sd_dd20 - wide.sharpe_mean_over_sd_dd05
    wide["material"] = wide.sharpe_change.abs() > MATERIAL
    return wide


# ---------------------------------------------------------------- descriptive: yearly, correlations
def naive_returns_of(path) -> pd.Series:
    eq = pd.read_csv(path, index_col=0).iloc[:, 0]
    eq.index = pd.to_datetime(eq.index, utc=True).tz_localize(None).normalize()
    return daily_returns(eq)


def yearly_and_correlations() -> tuple[pd.DataFrame, pd.DataFrame]:
    bench = daily_returns(pd.read_csv(out("momentum_continuous_equity_2026-10-24.csv"), index_col=0, parse_dates=True).continuous)
    rets, corr = {}, []
    for rung in RUNGS:
        for f in sorted((DUMP / "dd05" / rung).glob("equity_A_*.csv")):
            name, tag = f.stem.removeprefix("equity_").rsplit("_", 1)
            r = naive_returns_of(f)
            rets[(PERIOD[tag], f"{rung}:{name}")] = r
            both = pd.concat([r, bench], axis=1, join="inner").dropna()
            old = pd.concat([r, naive_returns_of(OLD_C_DUMP[rung] / f"equity_BENCHMARK_momentum_{tag}.csv")], axis=1, join="inner").dropna()
            corr.append({"period": PERIOD[tag], "rung": rung, "strategy": name, "days": len(both),
                         "corr_continuous_momentum": float(both.iloc[:, 0].corr(both.iloc[:, 1])),
                         "corr_per_period_momentum_superseded": float(old.iloc[:, 0].corr(old.iloc[:, 1]))})
    return yearly(rets), pd.DataFrame(corr)


# ---------------------------------------------------------------- rung comparisons, cost ladder
def a_kelly_oos(dump_of: dict, rung: str) -> pd.Series:
    return _naive_returns(read_curve(next(iter(sorted(dump_of[rung].glob("equity_A_daily_1-3d_kelly*_OOS.csv"))))))


def rung_comparisons() -> pd.DataFrame:
    official = pd.read_csv(out("rung_comparisons_2026-10-25.csv"))
    new = official.rename(columns={c: f"{c}_superseded" for c in official.columns if c.startswith("A_kelly")})
    new_dump = {r: DUMP / "dd05" / r for r in RUNGS}
    new = new.assign(A_kelly_test_sr_diff=np.nan, A_kelly_test_se=np.nan, A_kelly_test_p=np.nan)
    for i, (lo, hi) in enumerate(zip(RUNGS[:-1], RUNGS[1:])):
        check = sharpe_diff_test(a_kelly_oos(OLD_AB_DUMP, hi), a_kelly_oos(OLD_AB_DUMP, lo))
        assert abs(check["sr_diff"] - official.loc[i, "A_kelly_test_sr_diff"]) < 1e-9, "rule does not reproduce the 25 Oct file"
        jk = sharpe_diff_test(a_kelly_oos(new_dump, hi), a_kelly_oos(new_dump, lo))
        new.loc[i, ["A_kelly_test_sr_diff", "A_kelly_test_se", "A_kelly_test_p"]] = [jk["sr_diff"], jk["se"], jk["p"]]
    front = ["comparison", "kind", "A_kelly_test_sr_diff", "A_kelly_test_se", "A_kelly_test_p"]
    return new[front + [c for c in new.columns if c not in front]]


def cost_ladder(forty: pd.DataFrame) -> pd.DataFrame:
    official = pd.read_csv(out("cost_ladder_2026-10-25.csv"))
    lad = official.copy().astype({"best_strategy_test": object})
    before = with_superseded_a(forty)
    for rung in RUNGS:
        i = lad.index[lad.scorer == LADDER_LABEL[rung]][0]
        pick = lambda t: t[(t.rung == rung) & (t.period == "OOS")].pipe(lambda c: c.loc[c.sharpe.idxmax()])
        old_best = pick(before)
        assert old_best.strategy == official.loc[i, "best_strategy_test"] and abs(old_best.sharpe - official.loc[i, "best_sharpe"]) < 1e-9, \
            f"{rung}: selection rule does not reproduce the 25 Oct ladder"
        best = pick(forty)
        lad.loc[i, ["best_strategy_test", "best_return_pa", "best_sharpe", "best_sr_diff_vs_cont_momentum", "best_p_vs_momentum",
                    "best_DSR"]] = [best.strategy, best.return_pa, best.sharpe, best.sr_diff, best.p, best.DSR]
        lad.loc[i, "best_DSR_trials_N_used"] = best.dsr_trials_N
        lad.loc[i, "best_strategy_test_superseded"], lad.loc[i, "best_sharpe_superseded"] = old_best.strategy, old_best.sharpe
    return lad.assign(note_bug15="best-strategy cells re-selected 10 Nov 2026 with the corrected A rows; every other cell carried "
                                 "over from cost_ladder_2026-10-25.csv (timing cells not re-measured)")


# ---------------------------------------------------------------- equity charts (Llama, Haiku)
def chart(rung: str) -> str:
    """The runner's chart of the minute-bar-C run with the A curves replaced by the corrected ones."""
    old = OLD_C_DUMP[rung]
    names = [f.stem.removeprefix("equity_").rsplit("_", 1)[0] for f in sorted(old.glob("equity_*_IS.csv"))]
    order = sorted(set(names), key=lambda n: (not n.startswith("A_"), not n.startswith("BENCH"), n.startswith("C_"),
                                              "t+15" in n, "_kelly" in n))
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    for tag, ax in zip(PERIOD, axes):
        for name in order:
            folder = DUMP / "dd05" / rung if name.startswith("A_") else old
            e = pd.read_csv(folder / f"equity_{name}_{tag}.csv", index_col=0).iloc[:, 0]
            e.index = pd.to_datetime(e.index, utc=True).tz_localize(None)
            ax.plot(e.index, e / e.iloc[0], lw=1.2, label=name)
        ax.axhline(1.0, color="grey", lw=0.5)
        ax.set_title("IN-SAMPLE (fitted)" if tag == "IS" else "OUT-OF-SAMPLE (unseen)")
        ax.legend(fontsize=6)
    axes[0].set_ylabel("Growth of 1")
    fig.suptitle(f"{rung}: Strategy A corrected for Bug 15 (run of {DATE}); B, C and the per-period benchmark as in the "
                 "official minute-bar-C run -- REAL DATA, net of costs")
    fig.tight_layout()
    name = f"equity_both_strategies_{rung}_calibrated_cminute_{TAG}.png"
    fig.savefig(out(name), dpi=140)
    plt.close(fig)
    return name


# ---------------------------------------------------------------- run log
def log_runs(times: dict) -> None:
    log = OUTPUTS / "test_period_runs.csv"
    if TAG in log.read_text():
        print("  test_period_runs.csv already holds the correction run -- not appended again")
        return
    scorers = {"keyword": "keyword", "llm": "llm_anon", "embed_minilm": "embed_minilm", "haiku": "haiku", "sonnet": "sonnet"}
    base = {"script": f"src/run_both_strategies.py --only-a --benchmark-equity (Bug 15 correction; outputs/correction_{TAG}/run.sh run05)",
            "period": "2024-04-30 .. 2026-06-01"}
    rows = [{"timestamp": times["run05"], **base, "scorers": scorers[r],
             "what": f"Strategy A only, Bug 15 fixed engine (sizing inputs at the previous close), scales recalibrated on training, "
                     f"vs stored continuous momentum, N = {N_AB[r]}; B, C and momentum not run (note …note_bug15_2026-11-10.md + addendum)",
             "output": f"results_both_strategies_{r}_calibrated_{TAG}.csv"} for r in RUNGS]
    rows.append({"timestamp": times["run20"], "script": f"src/run_both_strategies.py --only-a --dd-cap 0.20 --dd-throttle-start 0.12 "
                 f"(outputs/correction_{TAG}/run.sh cal20 + run20) + src/bug15_report.py", "scorers": "+".join(scorers.values()),
                 "period": "2024-04-30 .. 2026-06-01",
                 "what": "20% drawdown sensitivity, Strategy A only, Bug 15 fixed engine (descriptive; N = 139/139/155/155/163)",
                 "output": f"sensitivity_dd20_summary_{TAG}.csv"})
    rows.append({"timestamp": datetime.now().isoformat(timespec="seconds"), "script": "src/bug15_report.py (stored files only; no strategy run)",
                 "scorers": "+".join(scorers.values()), "period": "2024-04-30 .. 2026-06-01",
                 "what": "derived tables of the Bug 15 correction: 40 configurations vs continuous momentum, Holm, yearly, correlations, "
                         "rung comparisons, cost ladder", "output": f"comparison_vs_continuous_momentum_{TAG}.csv"})
    pd.DataFrame(rows)[["timestamp", "script", "scorers", "period", "what", "output"]].to_csv(log, mode="a", index=False, header=False)


def main():
    check_holm_rule()
    gap = check_scale_free_momentum_test()
    print(f"  checks: Holm rule reproduces the 24 Oct file; unscaled momentum reproduces the 25 Oct scaled-momentum tests (max gap {gap:.1e})")
    rows_a = old_vs_new()
    forty = forty_configurations()
    counts = pd.DataFrame([recounts(with_superseded_a(forty), "before (A rows of 24/25 Oct)"), recounts(forty, f"after ({NEW_SOURCE})")])
    yearly_tab, corr_tab = yearly_and_correlations()
    written = {f"a_rows_old_vs_new_{TAG}.csv": rows_a,
               f"comparison_vs_continuous_momentum_{TAG}.csv": forty,
               f"recounts_forty_configurations_{TAG}.csv": counts.set_index("basis").T.reset_index(names="item"),
               f"holm_kelly_vs_fixed_{TAG}.csv": holm_table(),
               f"sensitivity_dd20_summary_{TAG}.csv": sensitivity_summary(rows_a),
               f"descriptive_yearly_performance_contmom_{TAG}.csv": yearly_tab,
               f"descriptive_correlations_contmom_{TAG}.csv": corr_tab,
               f"rung_comparisons_{TAG}.csv": rung_comparisons(),
               f"cost_ladder_{TAG}.csv": cost_ladder(forty)}
    for name, table in written.items():
        table.to_csv(out(name), index=False)
        print(f"  saved {name} ({len(table)} rows)")
    for rung in ("llm", "haiku"):
        print(f"  saved {chart(rung)}")
    times = dict(line.split()[::2] for line in (DUMP / "run_times.txt").read_text().splitlines() if "end" in line)
    log_runs(times)
    pd.set_option("display.width", 250)
    print(counts.set_index("basis").T.to_string())


if __name__ == "__main__":
    main()
