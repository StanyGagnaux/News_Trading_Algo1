"""
run_both_strategies.py -- REAL DATA test of BOTH strategies, clearly labelled.

  STRATEGY A -- "DAILY DRIFT"   : enter next day's OPEN, hold 1-3 days
  STRATEGY B -- "INTRADAY"      : enter N MINUTES after the headline,
                                  exit same session (stop / 2R target / close)
                                  swept across several entry latencies

Both use the SAME signals (keyword baseline) and the SAME 80/20 chronological
split, so the comparison is apples-to-apples. For each strategy you get:

  * IN-SAMPLE  (first 80% of the timeline) -- where a strategy is "fitted"
  * OUT-OF-SAMPLE (last 20%) -- never used for any decision
  * R2         -- how much of a trade's return is explained by how strong the
                  signal was. 0 = the strength score carries no information
                  about the SIZE of the move (it is a filter, not a dial).
  * OVERFIT SCORE -- out-of-sample Sharpe / in-sample Sharpe.
                  1.0 = held up perfectly. <0.3 = probably overfitted.

REQUIRES the v2 intraday engine (newsdrift/intraday.py with the stop-vs-cost
floor and daily portfolio accounting). If you see -100% returns, you are
still running the old v1 engine.

USAGE (from the project root):
  python3 src/run_both_strategies.py
  python3 src/run_both_strategies.py --llm-scores data_sources/news_scored_llm_ollama.csv
  python3 src/run_both_strategies.py --risk-scales outputs/frozen_risk_scales_2026-10-11_keyword.csv
"""
from __future__ import annotations
import argparse
from dataclasses import replace

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from paths import PRICES, NEWS_CLEAN, BARS, DATA, OUTPUTS
from newsdrift import (Config, KeywordScorer, PrecomputedScorer,
                       build_signal_table, build_event_table, NewsDriftBacktest,
                       performance_metrics, momentum_backtest, slice_period)
from newsdrift.intraday import IntradayBacktest, IntradayConfig
from newsdrift.stats import (strength_return_stats, daily_returns, sharpe_per_period,
                             sharpe_se_lo, expected_max_sharpe, deflated_sharpe,
                             sharpe_diff_test, paired_mean_diff)
from newsdrift.exposure import average_gross_exposure
from newsdrift.strategy_c import StrategyCBacktest, StrategyCConfig


# --------------------------------------------------------------- helpers
def r_squared(trades: pd.DataFrame, ret_col: str = "r_multiple") -> dict:
    """R², signed correlation, t-stat and n: does |strength| explain return?"""
    return strength_return_stats(trades, ret_col)


NO_R2_STATS = {"r2": np.nan, "corr": np.nan, "t": np.nan, "n": 0}


def add_sharpe_significance(df: pd.DataFrame, curves: dict, n_trials: int | None,
                            dsr_variance: str = "null") -> tuple[pd.DataFrame, dict]:
    """Lo (2002) Sharpe SE for every row; deflated Sharpe for strategy rows
    (benchmark excluded), against the best of n_trials by luck.

    dsr_variance="null": luck = sampling noise of zero-skill strategies,
      V = 1/T per row. Right when the trials differ for real (A wins, B loses).
    dsr_variance="trials": V = cross-sectional variance of the trials'
      Sharpes (Bailey & Lopez de Prado). Treats real differences between
      strategies as luck, so with heterogeneous strategies it is extreme.
    """
    out = df.copy()
    trials = [k for k in out.index if not k.startswith("BENCHMARK")]
    n = n_trials or len(trials)
    info = {"n_trials": n, "dsr_variance": dsr_variance}
    for tag in ("IS", "OOS"):
        rets = {k: daily_returns(curves.get(k, {}).get(tag)) for k in out.index}
        srs = [sharpe_per_period(rets[k]) for k in trials]
        srs = [s for s in srs if np.isfinite(s)]
        cross_var = float(np.var(srs, ddof=1)) if len(srs) > 1 else np.nan
        sr0 = {k: expected_max_sharpe(
                   1 / len(rets[k]) if dsr_variance == "null" and len(rets[k]) else cross_var, n)
               for k in trials}
        annual = [v * np.sqrt(252) for v in sr0.values() if np.isfinite(v)]
        info[f"{tag}_sr0_annual"] = (min(annual), max(annual)) if annual else (np.nan, np.nan)
        out[f"{tag}_sharpe_se"] = [sharpe_se_lo(rets[k]) for k in out.index]
        out[f"{tag}_DSR"] = [deflated_sharpe(rets[k], sr0[k]) if k in trials else np.nan
                             for k in out.index]
    return out, info


DSR_SENSITIVITY_TRIALS = (25, 50, 100)


def _naive_returns(equity) -> pd.Series:
    r = daily_returns(equity)
    if len(r):
        idx = pd.DatetimeIndex(r.index)
        r.index = (idx.tz_convert(None) if idx.tz is not None else idx).normalize()
    return r


def compare_strategies(curves: dict, trade_logs: dict) -> pd.DataFrame:
    """Pre-registered comparisons (strategy note, 18 Oct 2026): every news
    strategy vs momentum, and Kelly minus fixed, on the Sharpe DIFFERENCE
    (Jobson-Korkie with Memmel's correction); paired mean daily-return
    difference for Kelly vs fixed; average gross exposure."""
    rows = []
    bench = curves.get("BENCHMARK_momentum", {})
    for name, cur in curves.items():
        if name.startswith("BENCHMARK"):
            continue
        for tag in ("IS", "OOS"):
            jk = sharpe_diff_test(_naive_returns(cur.get(tag)), _naive_returns(bench.get(tag)))
            rows.append({"comparison": "strategy_minus_momentum", "strategy": name, "period": tag,
                         **jk, "gross_exposure": average_gross_exposure(
                             trade_logs.get(name, {}).get(tag), cur.get(tag))})
    for name in [k for k in curves if "_kelly" in k]:
        fixed = name.replace("_kelly", "_fixed")
        if fixed not in curves:
            continue
        for tag in ("IS", "OOS"):
            rk, rf = _naive_returns(curves[name].get(tag)), _naive_returns(curves[fixed].get(tag))
            pm = paired_mean_diff(rk, rf)
            rows.append({"comparison": "kelly_minus_fixed", "strategy": name.replace("_kelly", ""),
                         "period": tag, **sharpe_diff_test(rk, rf),
                         "mean_diff_pa": pm["mean_diff_pa"], "t_mean_diff": pm["t"],
                         "gross_exposure_kelly": average_gross_exposure(
                             trade_logs.get(name, {}).get(tag), curves[name].get(tag)),
                         "gross_exposure_fixed": average_gross_exposure(
                             trade_logs.get(fixed, {}).get(tag), curves[fixed].get(tag))})
    return pd.DataFrame(rows)


def dsr_sensitivity(df: pd.DataFrame, curves: dict, dsr_variance: str) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for n in DSR_SENSITIVITY_TRIALS:
        d, _ = add_sharpe_significance(df, curves, n, dsr_variance)
        out[f"IS_DSR_N{n}"], out[f"OOS_DSR_N{n}"] = d["IS_DSR"], d["OOS_DSR"]
    return out


def print_comparison(cmp: pd.DataFrame, dsr_sens: pd.DataFrame, sig_info: dict) -> None:
    print("\n" + "=" * 70)
    print("SHARPE DIFFERENCES (Jobson-Korkie with Memmel correction; annualised)")
    print("=" * 70)
    if cmp.empty:
        print("  (no comparisons)")
        return
    for kind, part in cmp.groupby("comparison", sort=False):
        print(f"  [{kind}]")
        for r in part.itertuples():
            extra = (f" | exposure {r.gross_exposure:.2f}" if kind == "strategy_minus_momentum"
                     else f" | mean diff {r.mean_diff_pa:+.2%} p.a. (t {r.t_mean_diff:+.2f})"
                          f" | exposure kelly {r.gross_exposure_kelly:.2f} fixed {r.gross_exposure_fixed:.2f}")
            print(f"    {r.strategy:<34}{r.period:<4} dSR {r.sr_diff:+.2f} +- {r.se:.2f}"
                  f"  z {r.z:+.2f}  p {r.p:.3f}{extra}")
    print(f"\n  deflated Sharpe sensitivity (primary N = {sig_info['n_trials']} above):")
    print(dsr_sens.to_string(float_format=lambda v: f"{v:.2f}"))


def simple_verdict(is_sharpe: float, oos_sharpe: float) -> tuple[float, str]:
    if not np.isfinite(is_sharpe) or is_sharpe <= 0:
        return np.nan, "in-sample edge was already negative/zero"
    ratio = oos_sharpe / is_sharpe
    if ratio >= 0.8:
        v = "HELD UP -- edge survived on unseen data"
    elif ratio >= 0.5:
        v = "PARTIALLY HELD -- lost some edge, still positive"
    elif ratio >= 0.2:
        v = "WEAK -- most of the edge disappeared out-of-sample"
    elif ratio > 0:
        v = "LIKELY OVERFITTED -- barely any edge survived"
    else:
        v = "FAILED -- lost money out-of-sample"
    return ratio, v


def summarize(name, is_m, oos_m, is_r2, oos_r2) -> dict:
    ratio, verdict = simple_verdict(is_m.get("sharpe", np.nan),
                                    oos_m.get("sharpe", np.nan))
    s_is = is_r2 if isinstance(is_r2, dict) else NO_R2_STATS
    s_oos = oos_r2 if isinstance(oos_r2, dict) else NO_R2_STATS
    return {
        "strategy": name,
        "IS_return_pa": is_m.get("ann_return", np.nan),
        "IS_sharpe": is_m.get("sharpe", np.nan),
        "IS_maxDD": is_m.get("max_drawdown", np.nan),
        "IS_trades": is_m.get("n_trades", np.nan),
        "IS_hit_rate": is_m.get("hit_rate", np.nan),
        "IS_R2": s_is["r2"],
        "IS_corr": s_is["corr"],
        "IS_t": s_is["t"],
        "IS_R2_n": s_is["n"],
        "OOS_return_pa": oos_m.get("ann_return", np.nan),
        "OOS_sharpe": oos_m.get("sharpe", np.nan),
        "OOS_maxDD": oos_m.get("max_drawdown", np.nan),
        "OOS_trades": oos_m.get("n_trades", np.nan),
        "OOS_hit_rate": oos_m.get("hit_rate", np.nan),
        "OOS_R2": s_oos["r2"],
        "OOS_corr": s_oos["corr"],
        "OOS_t": s_oos["t"],
        "OOS_R2_n": s_oos["n"],
        "overfit_score": ratio,
        "verdict": verdict,
    }


# --------------------------------------------------------------- loading
class Tier0Filtered:
    """Wraps a scorer so headlines failing score_news_llm.py's Tier-0 filter
    score 0 (dropped by the noise gate) -- i.e. the same headline set the LLM
    was asked to score. Isolates scorer quality from headline coverage."""

    def __init__(self, scorer, keep):
        self._scorer, self._keep = scorer, keep

    def score(self, headline: str, ticker: str = "") -> tuple[float, int]:
        if not self._keep(str(headline), str(ticker)):
            return 0.0, 1
        return self._scorer.score(headline, ticker)


def load_inputs(args):
    """Load prices + news, calibrate costs from the empirical bid/ask, build
    the scorer and the fixed chronological IS/OOS split."""
    cfg = Config()
    np.random.seed(cfg.seed)
    print("loading real data...")
    px = pd.read_csv(args.prices, parse_dates=["date"])
    nw = pd.read_csv(args.news, parse_dates=["timestamp"], low_memory=False)
    nw["timestamp"] = pd.to_datetime(nw["timestamp"], utc=True)

    px = px[~px.ticker.isin({"NDX", "SPX", "VIX", "RF"})]
    px = px[(px.date >= args.start) & (px.date <= args.end)]
    nwn = nw.timestamp.dt.tz_localize(None)
    nw = nw[(nwn >= args.start) & (nwn <= args.end)]

    common = sorted(set(px.ticker.unique()) & set(nw.ticker.unique()))
    px, nw = px[px.ticker.isin(common)], nw[nw.ticker.isin(common)]
    print(f"  {len(common)} tickers | {len(px):,} price rows | "
          f"{len(nw):,} headlines")

    hs = ((px["ask"] - px["bid"]) / (2 * px["close"]) * 1e4)
    hs = hs.replace([np.inf, -np.inf], np.nan).dropna()
    hs = hs[(hs > 0) & (hs < 100)]
    cfg.cost.half_spread_bps = float(hs.median())
    print(f"  empirical half-spread {cfg.cost.half_spread_bps:.2f} bps "
          f"-> {cfg.cost.per_side_bps:.2f} bps per side")

    if args.llm_scores:
        scorer = PrecomputedScorer(args.llm_scores)
        print(f"  using LLM scores from {args.llm_scores} "
              f"({len(scorer._lookup):,} headlines scored -- CAUTION: this is "
              f"a small subset of the ~40k that would need scoring for a fair "
              f"comparison against the keyword baseline; treat results as "
              f"preliminary/noisy until coverage is much larger)")
    else:
        scorer = KeywordScorer(cfg.signal)
    if getattr(args, "tier0", False):
        from score_news_llm import tier0_keep
        scorer = Tier0Filtered(scorer, tier0_keep)
        print("  Tier-0 filter ON: only headlines the LLM pipeline would score")

    trading_days =pd.DatetimeIndex(sorted(px.date.unique()))
    cut_i = int(len(trading_days) * args.train_frac)
    P = {"IS": (trading_days[0], trading_days[cut_i]),
         "OOS": (trading_days[min(cut_i + 1, len(trading_days) - 1)],
                 trading_days[-1])}
    return cfg, px, nw, scorer, trading_days, P


def load_bars(path: str) -> pd.DataFrame:
    bars = pd.read_csv(path, parse_dates=["ts"])
    bars["ts"] = pd.to_datetime(bars["ts"], utc=True)
    print(f"  {len(bars):,} minute bars | "
          f"{bars.ts.min().date()} -> {bars.ts.max().date()}")
    return bars


def market_hours_events(ev_all: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    """Events inside the 14:30-19:30 UTC entry window with minute-bar coverage."""
    h = ev_all.news_ts.dt.hour + ev_all.news_ts.dt.minute / 60
    ev = ev_all[(h >= 14.5) & (h <= 19.5)]
    return ev[ev.ticker.isin(bars.ticker.unique())]


def print_significance(df: pd.DataFrame, info: dict) -> None:
    def num(v, fmt):
        return format(v, fmt) if pd.notna(v) else "-"

    print("\n" + "=" * 70)
    print("STATISTICAL SIGNIFICANCE")
    print("=" * 70)
    lo_is, hi_is = info["IS_sr0_annual"]
    lo_oos, hi_oos = info["OOS_sr0_annual"]
    print(f"  deflated Sharpe vs the best of N = {info['n_trials']} tries by luck, "
          f"luck = {info['dsr_variance']} variance")
    print(f"  luck benchmark (annual Sharpe): IS {lo_is:.2f}-{hi_is:.2f}, "
          f"OOS {lo_oos:.2f}-{hi_oos:.2f}")
    print(f"  {'strategy':<32} {'period':<4} {'Sharpe':>7} {'± SE':>6} {'DSR':>5}"
          f" {'R2':>7} {'corr':>7} {'t':>6} {'n':>7}")
    for name, r in df.iterrows():
        for tag in ("IS", "OOS"):
            print(f"  {name:<32} {tag:<4} {num(r[f'{tag}_sharpe'], '7.2f')} "
                  f"{num(r[f'{tag}_sharpe_se'], '6.2f')} {num(r[f'{tag}_DSR'], '5.2f')} "
                  f"{num(r[f'{tag}_R2'], '7.4f')} {num(r[f'{tag}_corr'], '+7.3f')} "
                  f"{num(r[f'{tag}_t'], '+6.2f')} {int(r[f'{tag}_R2_n']):>7,}")


def load_risk_scales(path: str | None) -> dict:
    """{(strategy, sizer): risk_scale} from a calibrate_risk.py CSV."""
    if not path:
        return {}
    df = pd.read_csv(path)
    return {(r.strategy, r.sizer): float(r.risk_scale) for r in df.itertuples()}


# --------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices", default=str(PRICES))
    ap.add_argument("--news", default=str(NEWS_CLEAN))
    ap.add_argument("--bars", default=None,
                    help="minute bars for STRATEGY B; auto-detects "
                         "data_sources/bars_intraday.csv if omitted")
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--end", default="2026-06-01")
    ap.add_argument("--train-frac", type=float, default=0.80)
    ap.add_argument("--latencies", type=int, nargs="+", default=[5, 15],
                    help="entry latencies in minutes for STRATEGY B")
    ap.add_argument("--sizers", nargs="+", default=["fixed", "kelly"])
    ap.add_argument("--tp-r", type=float, default=2.0,
                    help="take-profit as an R multiple")
    ap.add_argument("--max-concurrent-risk", type=float, default=0.04,
                    help="cap on total risk deployed per day (drives maxDD)")
    ap.add_argument("--hold-until-resolved", action="store_true",
                    help="STRATEGY B: drop the same-session forced close; "
                         "hold past EOD until stop or target actually hits "
                         "(capped at --max-hold-days)")
    ap.add_argument("--max-hold-days", type=int, default=5,
                    help="safety cap for --hold-until-resolved")
    ap.add_argument("--exit-after-min", type=int, default=None,
                    help="STRATEGY B: ignore stop/target, exit at market "
                         "price this many minutes after entry")
    ap.add_argument("--dd-governor", choices=["designed", "strict", "off"],
                    default="designed",
                    help="drawdown governor for ALL strategies: 'designed' = "
                         "throttle (5%% probe floor, 60d peak decay); "
                         "'strict' = no probe, all-time peak; 'off' = none")
    ap.add_argument("--risk-scale", type=float, default=1.0,
                    help="multiply every position's risk (all strategies); "
                         "calibrate in-sample with calibrate_risk.py")
    ap.add_argument("--n-trials", type=int, default=None,
                    help="number of strategy configurations tried, for the "
                         "deflated Sharpe (default: strategy rows in this run; "
                         "for the thesis pass ALL variants ever tried)")
    ap.add_argument("--dsr-variance", choices=["null", "trials"], default="null",
                    help="deflated Sharpe luck model: 'null' = zero-skill "
                         "sampling noise (1/T); 'trials' = spread of this "
                         "run's Sharpes (Bailey & Lopez de Prado)")
    ap.add_argument("--tier0", action="store_true",
                    help="only score headlines passing score_news_llm.py's "
                         "Tier-0 filter (same headline set as the LLM)")
    ap.add_argument("--risk-scales", default=None,
                    help="CSV from calibrate_risk.py: one scale per strategy "
                         "and sizer (overrides --risk-scale where listed)")
    ap.add_argument("--allow-stacking", action="store_true",
                    help="STRATEGIES B/C: allow several open positions on the "
                         "same ticker (pre-Sept-2026 behaviour)")
    ap.add_argument("--llm-scores", default=None,
                    help="path to a score_news_llm.py output CSV -- use "
                         "these precomputed LLM scores instead of the "
                         "keyword scorer for signal construction")
    ap.add_argument("--stop-vol-mult", type=float, default=3.0,
                    help="STRATEGY B: stop = this x recent minute-vol x price")
    ap.add_argument("--partial-exit-r", type=float, default=None,
                    help="STRATEGY B: take --partial-exit-frac off at this R, "
                         "move the runner's stop to breakeven, no fixed target")
    ap.add_argument("--partial-exit-frac", type=float, default=0.5)
    ap.add_argument("--trail-r", type=float, default=None,
                    help="STRATEGY B: after the partial, trail the runner's "
                         "stop this many R behind its best price")
    ap.add_argument("--no-breakeven", action="store_true",
                    help="STRATEGY B: keep the original stop after the partial")
    args = ap.parse_args()

    # auto-detect the intraday bars file so STRATEGY B is never silently
    # skipped just because the --bars flag was forgotten
    if args.bars is None:
        for cand in (BARS, DATA / "bars_intraday_clean.csv"):
            if cand.exists():
                args.bars = str(cand)
                print(f"[auto-detected intraday bars: {cand}]")
                break

    cfg, px, nw, scorer, trading_days, P = load_inputs(args)

    gov_kw = {"off": dict(use_dd_governor=False),
              "designed": dict(use_dd_governor=True, dd_probe_floor=0.05,
                               dd_peak_halflife_days=60.0),
              "strict": dict(use_dd_governor=True, dd_probe_floor=0.0,
                             dd_peak_halflife_days=None)}[args.dd_governor]
    # Strategy A reads the same governor from its RiskConfig, so all
    # strategies run under identical risk rules (no confounded comparison).
    cfg.risk = replace(cfg.risk, **gov_kw)
    scales = load_risk_scales(args.risk_scales)

    def scale_for(strategy: str, sizer: str) -> float:
        return scales.get((strategy, sizer), args.risk_scale)
    gov_kw.update(one_position_per_ticker=not args.allow_stacking,
                  dd_cap=cfg.risk.dd_cap,
                  dd_throttle_start=cfg.risk.dd_throttle_start)

    # ---------------- signals (shared)
    nw_naive = nw.copy()
    nw_naive["timestamp"] = nw_naive["timestamp"].dt.tz_localize(None)
    sig = build_signal_table(nw_naive, scorer, trading_days, cfg.signal)
    print(f"  {len(sig):,} signals pass the noise gate")
    print(f"  drawdown governor (all strategies): {args.dd_governor} | "
          f"risk scale: {args.risk_scales or args.risk_scale} | "
          f"one position per ticker: {not args.allow_stacking}\n")
    score_tag = "_llm" if args.llm_scores else ""
    scorer_name = (("llm" if args.llm_scores else "keyword")
                   + ("" if args.dd_governor == "designed" else f"_{args.dd_governor}")
                   + ("" if args.risk_scale == 1.0 else f"_scale{args.risk_scale:g}")
                   + ("_calibrated" if args.risk_scales else "")
                   + ("_tier0" if args.tier0 else ""))

    print(f"SPLIT ({args.train_frac:.0%}/{1 - args.train_frac:.0%}), "
          f"fixed before any tuning:")
    print(f"  IN-SAMPLE     {P['IS'][0].date()} -> {P['IS'][1].date()}")
    print(f"  OUT-OF-SAMPLE {P['OOS'][0].date()} -> {P['OOS'][1].date()}\n")

    rows, curves, trade_logs = [], {}, {}

    # ============ STRATEGY A: DAILY DRIFT =============================
    print("=" * 70)
    print("STRATEGY A -- DAILY DRIFT: enter next day's open, hold 1-3 days")
    print("=" * 70)
    for sizer in args.sizers:
        m, r2s, cur, trs = {}, {}, {}, {}
        for tag, period in P.items():
            px_p = slice_period(px, period)
            sig_p = sig[(sig.effective_date >= period[0])
                        & (sig.effective_date <= period[1])]
            cfg_a = replace(cfg, risk=replace(
                cfg.risk, risk_scale=scale_for("A_daily_1-3d", sizer)))
            eq, tr = NewsDriftBacktest(px_p, sig_p, cfg_a,
                                       sizer_kind=sizer).run()
            m[tag] = performance_metrics(eq, tr)
            r2s[tag] = r_squared(tr)
            cur[tag] = eq
            trs[tag] = tr
        name = f"A_daily_1-3d_{sizer}{score_tag}"
        rows.append(summarize(name, m["IS"], m["OOS"], r2s["IS"], r2s["OOS"]))
        curves[name] = cur
        trade_logs[name] = trs
        print(f"  {name}: IS Sharpe {m['IS']['sharpe']:.2f} | "
              f"OOS Sharpe {m['OOS']['sharpe']:.2f}")

    m, cur = {}, {}
    for tag, period in P.items():
        eq = momentum_backtest(slice_period(px, period), cfg.momentum,
                               cfg.cost, cfg.initial_equity)
        m[tag] = performance_metrics(eq)
        cur[tag] = eq
    rows.append(summarize("BENCHMARK_momentum", m["IS"], m["OOS"],
                          np.nan, np.nan))
    curves["BENCHMARK_momentum"] = cur

    # ============ STRATEGY B: INTRADAY LATENCY SWEEP ==================
    if args.bars:
        lat_str = ", ".join(f"t+{l}min" for l in args.latencies)
        print("\n" + "=" * 70)
        print(f"STRATEGY B -- INTRADAY: enter {lat_str} after headline, "
              f"exit same session ({args.tp_r:.0f}R target)")
        print("=" * 70)
        bars = load_bars(args.bars)

        # POINT-IN-TIME events: one per headline that passes the noise gate
        # on its own score (see signals.build_event_table). The old code
        # merged the DAILY aggregate onto every headline -> look-ahead and
        # duplicated trades. Shared by B and C.
        ev_all = build_event_table(nw, scorer, cfg.signal)
        ev = market_hours_events(ev_all, bars)
        print(f"  {len(ev):,} signals during market hours with bar coverage")

        for lat in args.latencies:
            print(f"\n  -- entry latency t+{lat}min --")
            for sizer in args.sizers:
                m, r2s, cur, trs = {}, {}, {}, {}
                for tag, period in P.items():
                    lo = pd.Timestamp(period[0], tz="UTC")
                    hi = pd.Timestamp(period[1], tz="UTC") + pd.Timedelta(days=1)
                    ev_p = ev[(ev.news_ts >= lo) & (ev.news_ts <= hi)]
                    bars_p = bars[(bars.ts >= lo) & (bars.ts <= hi)]
                    if ev_p.empty or bars_p.empty:
                        m[tag], r2s[tag] = {}, np.nan
                        continue
                    icfg = IntradayConfig(
                        entry_latency_min=lat, sizer=sizer,
                        tp_r_multiple=args.tp_r,
                        max_concurrent_risk=args.max_concurrent_risk,
                        cost_base_bps=cfg.cost.per_side_bps,
                        hold_until_resolved=args.hold_until_resolved,
                        max_hold_days=args.max_hold_days,
                        exit_after_min=args.exit_after_min,
                        stop_vol_mult=args.stop_vol_mult,
                        partial_exit_r=args.partial_exit_r,
                        partial_exit_frac=args.partial_exit_frac,
                        trail_r=args.trail_r,
                        breakeven_after_partial=not args.no_breakeven,
                        risk_scale=scale_for(f"B_intraday_t+{lat}min", sizer),
                        **gov_kw)
                    bt_b = IntradayBacktest(bars_p, ev_p, icfg)
                    eq, tr = bt_b.run()
                    print(f"     {sizer:<6} {tag:<3} replay: "
                          f"{getattr(bt_b, 'replay_stats', {})}")
                    if tr.empty or eq.empty:
                        m[tag], r2s[tag] = {}, np.nan
                        continue
                    m[tag] = performance_metrics(eq, tr)
                    r2s[tag] = r_squared(tr)
                    cur[tag] = eq
                    trs[tag] = tr
                    if tag == "IS" and len(tr):
                        print(f"     {sizer:<6} median stop "
                              f"{tr.stop_dist_bps.median():.0f}bps | "
                              f"stop-outs {(tr.reason=='stop').mean():.0%} | "
                              f"targets {(tr.reason=='target').mean():.0%} | "
                              f"partials {tr.partial_hit.mean():.0%}")
                name = f"B_intraday_t+{lat}min_{sizer}{score_tag}"
                rows.append(summarize(name, m.get("IS", {}), m.get("OOS", {}),
                                      r2s.get("IS", np.nan),
                                      r2s.get("OOS", np.nan)))
                curves[name] = cur
                trade_logs[name] = trs

        # ========== STRATEGY C: INTRADAY ENTRY, MULTI-DAY HOLD =========
        print("\n" + "=" * 70)
        print("STRATEGY C -- INTRADAY ENTRY, MULTI-DAY HOLD: enter t+15min "
              "after headline, hold up to `duration` daily bars (1-3d)")
        print("=" * 70)

        ev_c = market_hours_events(ev_all, bars)
        print(f"  {len(ev_c):,} signals during market hours with bar coverage")

        for sizer in args.sizers:
            m, r2s, cur, trs = {}, {}, {}, {}
            for tag, period in P.items():
                lo = pd.Timestamp(period[0], tz="UTC")
                hi = pd.Timestamp(period[1], tz="UTC") + pd.Timedelta(days=1)
                ev_c_p = ev_c[(ev_c.news_ts >= lo) & (ev_c.news_ts <= hi)]
                bars_p = bars[(bars.ts >= lo) & (bars.ts <= hi)]
                px_p = slice_period(px, period)
                if ev_c_p.empty or bars_p.empty:
                    m[tag], r2s[tag] = {}, np.nan
                    continue
                ccfg = StrategyCConfig(sizer=sizer,
                                       max_concurrent_risk=args.max_concurrent_risk,
                                       exit_cost_bps=cfg.cost.per_side_bps,
                                       risk_scale=scale_for("C_intraday_multiday", sizer),
                                       **gov_kw)
                bt_c = StrategyCBacktest(px_p, bars_p, ev_c_p, ccfg)
                eq, tr = bt_c.run()
                print(f"     {sizer:<6} {tag:<3} replay: "
                      f"{getattr(bt_c, 'replay_stats', {})}")
                if tr.empty or eq.empty:
                    m[tag], r2s[tag] = {}, np.nan
                    continue
                m[tag] = performance_metrics(eq, tr)
                r2s[tag] = r_squared(tr)
                cur[tag] = eq
                trs[tag] = tr
                if tag == "IS" and len(tr):
                    print(f"     {sizer:<6} median stop "
                          f"{tr.stop_dist_bps.median():.0f}bps | "
                          f"stop-outs {(tr.reason=='stop').mean():.0%} | "
                          f"targets {(tr.reason=='target').mean():.0%} | "
                          f"time-exits {(tr.reason=='time_exit').mean():.0%}")
            name = f"C_intraday_multiday_{sizer}{score_tag}"
            rows.append(summarize(name, m.get("IS", {}), m.get("OOS", {}),
                                  r2s.get("IS", np.nan), r2s.get("OOS", np.nan)))
            curves[name] = cur
            trade_logs[name] = trs
    else:
        print("\n" + "!" * 70)
        print("WARNING: STRATEGY B AND STRATEGY C (INTRADAY) DID NOT RUN")
        print("  No minute-bar file found. Strategies B and C need")
        print("  bars_intraday.csv either in this folder, or passed with")
        print("  --bars <path>.")
        print("  Only STRATEGY A (daily) results are shown below.")
        print("!" * 70)

    # ============ REPORT ==============================================
    df = pd.DataFrame(rows).set_index("strategy")
    df, sig_info = add_sharpe_significance(df, curves, args.n_trials, args.dsr_variance)
    show = df.copy()
    for c in ["IS_return_pa", "IS_maxDD", "IS_hit_rate",
              "OOS_return_pa", "OOS_maxDD", "OOS_hit_rate"]:
        show[c] = show[c].map(lambda v: f"{v:.1%}" if pd.notna(v) else "-")
    for c in ["IS_sharpe", "OOS_sharpe", "overfit_score"]:
        show[c] = show[c].map(lambda v: f"{v:.2f}" if pd.notna(v) else "-")
    for c in ["IS_R2", "OOS_R2"]:
        show[c] = show[c].map(lambda v: f"{v:.4f}" if pd.notna(v) else "-")
    for c in ["IS_trades", "OOS_trades"]:
        show[c] = show[c].map(lambda v: f"{v:,.0f}" if pd.notna(v) else "-")

    print("\n" + "=" * 70)
    print("RESULTS -- IN-SAMPLE (fitted) vs OUT-OF-SAMPLE (unseen)")
    print("=" * 70)
    print(show[["IS_return_pa", "IS_sharpe", "IS_maxDD", "IS_trades",
                "IS_hit_rate", "IS_R2"]].to_string())
    print()
    print(show[["OOS_return_pa", "OOS_sharpe", "OOS_maxDD", "OOS_trades",
                "OOS_hit_rate", "OOS_R2"]].to_string())
    print("\n" + "=" * 70)
    print("OVERFITTING CHECK (OOS Sharpe / IS Sharpe)")
    print("=" * 70)
    for name, r in df.iterrows():
        s = f"{r['overfit_score']:.2f}" if pd.notna(r["overfit_score"]) else "-"
        print(f"  {name:<32} {s:>6}   {r['verdict']}")

    print_significance(df, sig_info)
    comparison = compare_strategies(curves, trade_logs)
    dsr_sens = dsr_sensitivity(df, curves, args.dsr_variance)
    print_comparison(comparison, dsr_sens, sig_info)

    if args.bars and len(args.latencies) > 1:
        print("\n" + "=" * 70)
        print("LATENCY DECAY -- does entering later cost you edge?")
        print("=" * 70)
        for sizer in args.sizers:
            print(f"  [{sizer}]")
            for lat in args.latencies:
                k = f"B_intraday_t+{lat}min_{sizer}"
                if k in df.index:
                    r = df.loc[k]
                    isr = (f"{r['IS_return_pa']:+.1%}"
                           if pd.notna(r['IS_return_pa']) else "-")
                    oosr = (f"{r['OOS_return_pa']:+.1%}"
                            if pd.notna(r['OOS_return_pa']) else "-")
                    print(f"    t+{lat:>3}min  IS {isr:>8}  OOS {oosr:>8}")

    print("\nHOW TO READ THIS:")
    print("  return_pa   annualised return")
    print("  sharpe      return per unit of risk (>1 good, >2 excellent)")
    print("  maxDD       worst peak-to-trough loss")
    print("  R2          does signal STRENGTH predict return SIZE?")
    print("              0.00 = no, strength is a filter, not a dial")
    print("  corr / t    signed correlation of |strength| with trade R, and")
    print("              its t-stat (|t| > 2 ~ significant at 5%); n = trades")
    print("  Sharpe SE   Lo (2002), IID; Sharpe within 2 SE of 0 = not significant")
    print("  DSR         deflated Sharpe: probability the true Sharpe beats the")
    print("              best of N tries by luck (> 0.95 = significant)")
    print("  overfit     1.0 = edge fully survived on unseen data")

    # head-to-head: which strategy is better?
    print("\n" + "=" * 70)
    print("HEAD-TO-HEAD: STRATEGY A (daily) vs B (intraday) vs C (intraday "
          "entry, multi-day hold)")
    print("=" * 70)
    a_rows = df[df.index.str.startswith("A_")]
    b_rows = df[df.index.str.startswith("B_")]
    c_rows = df[df.index.str.startswith("C_")]
    if len(b_rows) == 0 and len(c_rows) == 0:
        print("  STRATEGY B and C did not run -- cannot compare. See warning above.")
    else:
        # idxmax() on an all-NaN column (every arm had zero OOS trades)
        # returns NaN rather than raising -- guard explicitly instead of
        # feeding NaN into df.loc[], which raises KeyError.
        best_a = (a_rows["OOS_sharpe"].idxmax()
                 if a_rows["OOS_sharpe"].notna().any() else None)
        best_b = (b_rows["OOS_sharpe"].idxmax()
                 if len(b_rows) and b_rows["OOS_sharpe"].notna().any() else None)
        best_c = (c_rows["OOS_sharpe"].idxmax()
                 if len(c_rows) and c_rows["OOS_sharpe"].notna().any() else None)
        best = {"A (daily)": best_a, "B (intraday same-session)": best_b,
               "C (intraday entry, multi-day hold)": best_c}
        for label, k in (("BEST A (daily)                    ", best_a),
                         ("BEST B (intraday same-session)    ", best_b),
                         ("BEST C (intraday, multi-day hold) ", best_c)):
            if k is None:
                continue
            r = df.loc[k]
            print(f"  {label}  {k}")
            print(f"      OOS return {r['OOS_return_pa']:+.1%} | "
                  f"Sharpe {r['OOS_sharpe']:.2f} | "
                  f"maxDD {r['OOS_maxDD']:.1%} | "
                  f"trades {r['OOS_trades']:,.0f}")
        scored = {name: df.loc[k, "OOS_sharpe"] for name, k in best.items()
                 if k is not None and pd.notna(df.loc[k, "OOS_sharpe"])}
        if not scored:
            print("\n  >>> no OOS trades on any side -- "
                 "cannot declare a winner on unseen data.")
        else:
            winner = max(scored, key=scored.get)
            print(f"\n  >>> WINNER on out-of-sample Sharpe: STRATEGY {winner}")
            ranked = sorted(scored.items(), key=lambda kv: -kv[1])
            print("      " + " > ".join(f"{n} ({s:.2f})" for n, s in ranked))

    out_csv = OUTPUTS / f"results_both_strategies_{scorer_name}.csv"
    df.to_csv(out_csv)
    cmp_csv = out_csv.with_name(out_csv.stem + "_comparison.csv")
    comparison.to_csv(cmp_csv, index=False)
    dsr_sens.to_csv(out_csv.with_name(out_csv.stem + "_dsr_sensitivity.csv"))
    print(f"\nsaved {out_csv.relative_to(OUTPUTS.parent)}")

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    for tag, ax in zip(["IS", "OOS"], axes):
        for name, cur in curves.items():
            if tag in cur and len(cur[tag]):
                e = cur[tag]
                ax.plot(e.index, e / e.iloc[0], lw=1.2, label=name)
        ax.axhline(1.0, color="grey", lw=0.5)
        ax.set_title("IN-SAMPLE (fitted)" if tag == "IS"
                     else "OUT-OF-SAMPLE (unseen)")
        ax.legend(fontsize=6)
    axes[0].set_ylabel("Growth of 1")
    fig.suptitle("Strategy A (daily 1-3d) vs Strategy B (intraday sweep) "
                 "-- REAL DATA, net of costs")
    fig.tight_layout()
    out_png = OUTPUTS / f"equity_both_strategies_{scorer_name}.png"
    fig.savefig(out_png, dpi=140)
    print(f"saved {out_png.relative_to(OUTPUTS.parent)}")


if __name__ == "__main__":
    main()
