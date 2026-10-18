"""
calibrate_scorer.py -- calibration layer for Strategy A: size positions by what
a scorer's outputs PREDICT about returns instead of by raw strength. Applied
identically to the keyword and LLM scorers.

TRAINING PERIOD ONLY (2016-01-04 -> 2024-04-29, the runner's 80% split). Rows
after TRAIN_END are dropped while reading, before any computation; the test
period is never loaded, scored or evaluated.

  FIT        = training start -> 2021-12-31  (model fitted only on signals whose
                                              standalone EXIT is before 2022)
  VALIDATION = 2022-01-01 -> TRAIN_END        (evaluation only)

Step 1  standalone per-signal R-multiples with Strategy A's exact rules
        (newsdrift/standalone.py), no portfolio caps or governor.
Step 2  ridge regression of R on: keyword |strength|, duration, 3 category
        dummies (5 coefs); LLM adds importance (6 coefs). alpha fixed a priori.
Step 3  direction = sign(strength); size ∝ max(predicted R, 0); skip <= 0;
        overall risk rescaled so FIT maxDD ~5% (risk_scale).
Step 4  VALIDATION table: keyword raw/calibrated, LLM raw/calibrated.
Every configuration is appended to outputs/experiments_log.csv (failures too).

USAGE (from the project root):  python3 src/calibrate_scorer.py
"""
from __future__ import annotations
import re
from dataclasses import replace
from datetime import datetime

import numpy as np
import pandas as pd

from paths import PRICES, NEWS_CLEAN, LLM_SCORES, OUTPUTS
from newsdrift import (Config, KeywordScorer, PrecomputedScorer, build_signal_table,
                       NewsDriftBacktest, performance_metrics)
from newsdrift.standalone import simulate_standalone
from newsdrift.stats import correlation_t, daily_returns, sharpe_se_lo
from calibrate_risk import calibrate
from splits import backtest_train_end

DATA_START = pd.Timestamp("2016-01-01")      # runner's --start
DATA_END = pd.Timestamp("2026-06-01")        # runner's --end (used ONLY to locate the split)
TRAIN_FRAC = 0.80
TRAIN_END = pd.Timestamp("2024-04-29")       # runner's in-sample end; verified below
FIT_END = pd.Timestamp("2021-12-31")
VAL_START = pd.Timestamp("2022-01-01")
ATR_WARMUP = pd.Timedelta(days=120)          # price history before VAL_START for ATR
RIDGE_ALPHA = 1.0                            # on standardised features, fixed a priori
MIN_CATEGORY_TRADES = 200
CATEGORIES = ["earnings_guidance", "analyst", "corporate_event"]   # baseline: other
INDEX_TICKERS = {"NDX", "SPX", "VIX", "RF"}
EXPERIMENT_LOG = OUTPUTS / "experiments_log.csv"
LOG_COLUMNS = ["timestamp", "scorer", "description", "status", "risk_scale",
               "val_return_pa", "val_sharpe", "val_sharpe_se", "val_maxDD", "val_trades",
               "val_hit_rate", "val_mean_R", "val_corr", "val_t", "val_corr_n"]
CHUNK = 200_000


def headline_type(h: str) -> str:
    t = str(h).lower()
    if re.search(r"\bearnings\b|\beps\b|\bquarterly results\b|\bguidance\b|\boutlook\b|\bforecast\b", t):
        return "earnings_guidance"
    if re.search(r"\bupgrade[sd]?\b|\bdowngrade[sd]?\b|\bprice target\b", t):
        return "analyst"
    if re.search(r"\bacquir\w*|\bmerger\b|\bbuyout\b|\bstake\b|\bfda\b|\btrial\b|"
                 r"\bapprov\w*|\bpatent\b|\blawsuit\b|\bprobe\b|\binvestigat\w*|"
                 r"\bsettl\w*|\bceo\b|\bcfo\b|\bresign\w*|\bappoint\w*", t):
        return "corporate_event"
    return "other"


# --------------------------------------------------------------- data
def verify_train_end() -> None:
    """TRAIN_END must equal the runner's split. Reads only the date/ticker
    columns (the trading calendar) -- no prices, returns or news text."""
    cut = backtest_train_end(PRICES, NEWS_CLEAN, str(DATA_START.date()), str(DATA_END.date()), TRAIN_FRAC)
    assert cut == TRAIN_END, f"split moved: runner gives {cut.date()}, script has {TRAIN_END.date()}"


def load_training() -> tuple[pd.DataFrame, pd.DataFrame, Config]:
    px = pd.concat(c[(c.date >= DATA_START) & (c.date <= TRAIN_END) & ~c.ticker.isin(INDEX_TICKERS)]
                   for c in pd.read_csv(PRICES, parse_dates=["date"], chunksize=CHUNK))
    parts = []
    for c in pd.read_csv(NEWS_CLEAN, chunksize=CHUNK, low_memory=False):
        ts = pd.to_datetime(c.timestamp, utc=True).dt.tz_localize(None)
        keep = (ts >= DATA_START) & (ts.dt.normalize() <= TRAIN_END)
        parts.append(c.loc[keep].assign(timestamp=ts[keep]))
    nw = pd.concat(parts, ignore_index=True)
    assert px.date.max() <= TRAIN_END and nw.timestamp.max().normalize() <= TRAIN_END
    common = set(px.ticker) & set(nw.ticker)
    px = px[px.ticker.isin(common)].reset_index(drop=True)
    nw = nw[nw.ticker.isin(common)].reset_index(drop=True)

    cfg = Config()
    hs = ((px.ask - px.bid) / (2 * px.close) * 1e4).replace([np.inf, -np.inf], np.nan).dropna()
    cfg.cost.half_spread_bps = float(hs[(hs > 0) & (hs < 100)].median())
    return px, nw, cfg


def build_features(nw, scorer, cfg, trading_days, importance: dict | None) -> pd.DataFrame:
    """build_signal_table's rows plus importance and category taken from the
    day's strongest headline. Asserted identical to build_signal_table."""
    td = pd.DatetimeIndex(sorted(trading_days.unique()))
    rows = []
    for r in nw.itertuples(index=False):
        s, d = scorer.score(r.headline, r.ticker)
        if abs(s) < cfg.signal.min_abs_strength:
            continue
        news_date = pd.Timestamp(r.timestamp).normalize()
        pos = td.searchsorted(news_date + pd.Timedelta(days=1)) + cfg.signal.signal_lag_days - 1
        if pos >= len(td):
            continue
        imp = importance.get((r.headline, r.ticker), np.nan) if importance else np.nan
        rows.append({"news_date": news_date, "effective_date": td[pos], "ticker": r.ticker,
                     "strength": s, "duration": d, "abs_s": abs(s), "importance": imp,
                     "category": headline_type(r.headline)})      # original text, not anonymised
    df = pd.DataFrame(rows)
    keys = ["effective_date", "ticker"]
    rep = df.loc[df.groupby(keys)["abs_s"].idxmax(), keys + ["importance", "category"]]
    agg = df.groupby(keys, as_index=False).agg(news_date=("news_date", "min"),
                                               strength=("strength", "mean"),
                                               duration=("duration", "max"))
    sig = agg.merge(rep, on=keys, validate="one_to_one")
    sig = sig[sig.strength.abs() >= cfg.signal.min_abs_strength]    # Bug 11 gate
    assert (sig.effective_date > sig.news_date).all(), "LOOK-AHEAD VIOLATION"
    ref = build_signal_table(nw, scorer, trading_days, cfg.signal).sort_values(keys)
    mine = sig.sort_values(keys)
    assert len(ref) == len(mine) \
        and (ref.effective_date.to_numpy() == mine.effective_date.to_numpy()).all() \
        and np.allclose(ref.strength, mine.strength) \
        and (ref.duration.to_numpy() == mine.duration.to_numpy()).all(), \
        "feature table differs from build_signal_table"
    return sig.sort_values("effective_date").reset_index(drop=True)


# --------------------------------------------------------------- model
def design(sig: pd.DataFrame, scorer: str, cats: list[str]) -> pd.DataFrame:
    X = pd.DataFrame({"abs_strength": sig.strength.abs(), "duration": sig.duration.astype(float)},
                     index=sig.index)
    if scorer == "llm":
        X["importance"] = sig.importance.astype(float)
    for c in cats:
        X[f"cat_{c}"] = (sig.category == c).astype(float)
    return X


def fit_ridge(X: pd.DataFrame, y: pd.Series, alpha: float = RIDGE_ALPHA) -> dict:
    """Ridge on standardised features with an unpenalised intercept. t-values
    use the OLS covariance (approximate for ridge; fine as a noise check)."""
    mu, sd = X.mean(), X.std(ddof=0).replace(0, 1.0)
    Z = ((X - mu) / sd).to_numpy()
    yv = y.to_numpy(dtype=float)
    ybar, k = float(yv.mean()), Z.shape[1]
    b = np.linalg.solve(Z.T @ Z + alpha * np.eye(k), Z.T @ (yv - ybar))
    coef = pd.Series(b / sd.to_numpy(), index=X.columns)
    intercept = ybar - float((coef * mu).sum())
    resid = yv - (intercept + X.to_numpy() @ coef.to_numpy())
    se_std = np.sqrt(np.diag(resid.var(ddof=k + 1) * np.linalg.pinv(Z.T @ Z)))
    return {"intercept": intercept, "coef": coef, "coef_std": pd.Series(b, index=X.columns),
            "t": pd.Series(b / se_std, index=X.columns), "n": len(yv)}


def predict(model: dict, X: pd.DataFrame) -> pd.Series:
    return model["intercept"] + X[model["coef"].index] @ model["coef"]


# --------------------------------------------------------------- portfolio
def run_a(px, sig, cfg, scale):
    c = replace(cfg, risk=replace(cfg.risk, risk_scale=scale))
    return NewsDriftBacktest(px, sig, c, sizer_kind="fixed").run()


def evaluate(label, sig, px, cfg, val_outcomes, predictor) -> dict:
    """Rescale on FIT to ~5% maxDD, then measure on VALIDATION only."""
    sig_fit = sig[sig.effective_date <= FIT_END]
    sig_val = sig[sig.effective_date >= VAL_START]
    px_fit = px[px.date <= FIT_END]
    px_val = px[px.date >= VAL_START - ATR_WARMUP]
    scale = calibrate(label, lambda s: performance_metrics(*run_a(px_fit, sig_fit, cfg, s)))["risk_scale"]
    eq, tr = run_a(px_val, sig_val, cfg, scale)
    eq = eq[eq.index >= VAL_START]
    m = performance_metrics(eq, tr)
    ct = correlation_t(predictor, val_outcomes)
    return {"risk_scale": scale, "val_return_pa": m["ann_return"], "val_sharpe": m["sharpe"],
            "val_sharpe_se": sharpe_se_lo(daily_returns(eq)), "val_maxDD": m["max_drawdown"],
            "val_trades": m.get("n_trades", 0), "val_hit_rate": m.get("hit_rate", np.nan),
            "val_mean_R": float(tr.r_multiple.mean()) if len(tr) else np.nan,
            "val_corr": ct["corr"], "val_t": ct["t"], "val_corr_n": ct["n"]}


def log_experiment(scorer: str, description: str, result: dict | None, status: str) -> None:
    row = {"timestamp": datetime.now().isoformat(timespec="seconds"), "scorer": scorer,
           "description": description, "status": status, **(result or {})}
    pd.DataFrame([row]).reindex(columns=LOG_COLUMNS).to_csv(
        EXPERIMENT_LOG, mode="a", index=False, header=not EXPERIMENT_LOG.exists())


# --------------------------------------------------------------- per scorer
def fit_scorer(name, sig, px, cfg) -> tuple[pd.DataFrame, dict]:
    """Steps 1-2: standalone FIT outcomes (exit < VAL_START) and the ridge fit."""
    fit_sig = sig[sig.effective_date <= FIT_END]
    out_fit = simulate_standalone(px[px.date <= FIT_END], fit_sig, cfg)
    assert (out_fit.exit_date < VAL_START).all(), "FIT outcome overlaps VALIDATION"
    train = fit_sig.merge(out_fit, on=["effective_date", "ticker"], validate="one_to_one")
    counts = train.category.value_counts()
    cats = [c for c in CATEGORIES if counts.get(c, 0) >= MIN_CATEGORY_TRADES]
    model = fit_ridge(design(train, name, cats), train.r_multiple)
    info = {"model": model, "cats": cats, "category_counts": counts,
            "merged": [c for c in CATEGORIES if c not in cats],
            "fit_mean_R": float(train.r_multiple.mean()),
            "engine_check": engine_consistency(px, fit_sig, cfg, out_fit)}
    return sig.assign(pred_R=predict(model, design(sig, name, info["cats"]))), info


def process_scorer(name, scorer, importance, px, nw, cfg, trading_days) -> tuple[list, dict]:
    print(f"\n{'=' * 70}\n{name.upper()} SCORER\n{'=' * 70}")
    sig, info = fit_scorer(name, build_features(nw, scorer, cfg, trading_days, importance), px, cfg)
    val_sig = sig[sig.effective_date >= VAL_START]
    val = val_sig.merge(simulate_standalone(px, val_sig, cfg),
                        on=["effective_date", "ticker"], validate="one_to_one")
    fit_pred = sig.loc[sig.effective_date <= FIT_END, "pred_R"]
    pos_mean = float(fit_pred[fit_pred > 0].mean())
    cal_sig = sig[sig.pred_R > 0].assign(size_weight=lambda d: d.pred_R / pos_mean)
    info.update({"signals": len(sig), "val_signals": len(val_sig), "val_with_outcome": len(val),
                 "pred_pos_share_fit": float((fit_pred > 0).mean()),
                 "pred_pos_share_val": float((val_sig.pred_R > 0).mean()),
                 "share_strength_1": float((sig.strength.abs() == 1).mean()),
                 "top_duration_share": float(sig.duration.value_counts(normalize=True).iloc[0]),
                 "last_signal": sig.effective_date.max()})

    feats = "|strength|, duration" + (", importance" if name == "llm" else "")
    configs = [
        (f"{name} raw", "Strategy A current fixed sizer from strength; risk rescaled to FIT maxDD 5%",
         sig, val.strength.abs()),
        (f"{name} calibrated", f"ridge alpha={RIDGE_ALPHA} on {feats} + category dummies "
         f"{info['cats']} (merged into other: {info['merged'] or 'none'}); size ~ "
         f"max(pred_R,0)/{pos_mean:.4f}, skip pred_R<=0; risk rescaled to FIT maxDD 5%",
         cal_sig, val.pred_R),
    ]
    rows = []
    for label, desc, s, predictor in configs:
        try:
            res = evaluate(label, s, px, cfg, val.r_multiple, predictor)
            log_experiment(name, f"{label}: {desc}", res, "ok")
            rows.append({"configuration": label, **res})
        except Exception as e:                      # failures are logged too (DSR trial count)
            log_experiment(name, f"{label}: {desc}", None, f"failed: {e!r}")
            print(f"  !! {label} failed: {e!r}")
    return rows, info


def engine_consistency(px, fit_sig, cfg, out_fit) -> dict:
    """Standalone R must equal the engine's R for every FIT trade the engine took."""
    _, tr = run_a(px[px.date <= FIT_END], fit_sig, cfg, 1.0)
    m = tr.merge(out_fit, left_on=["entry_date", "ticker"],
                 right_on=["effective_date", "ticker"], suffixes=("_engine", "_alone"))
    diff = (m.r_multiple_engine - m.r_multiple_alone).abs()
    return {"matched": len(m), "engine_trades": len(tr),
            "max_abs_diff": float(diff.max()) if len(m) else np.nan}


# --------------------------------------------------------------- report
def report(rows: list, infos: dict) -> None:
    print(f"\n{'=' * 70}\nVALIDATION ONLY ({VAL_START.date()} -> {TRAIN_END.date()}), "
          f"risk rescaled to ~5% maxDD on FIT\n{'=' * 70}")
    fmt = {"val_return_pa": "{:+.1%}", "val_sharpe": "{:+.2f}", "val_sharpe_se": "{:.2f}",
           "val_maxDD": "{:.1%}", "val_trades": "{:,.0f}", "val_hit_rate": "{:.1%}",
           "val_mean_R": "{:+.3f}", "val_corr": "{:+.3f}", "val_t": "{:+.2f}",
           "val_corr_n": "{:,.0f}", "risk_scale": "{:.4f}"}
    if rows:
        print(pd.DataFrame(rows).set_index("configuration")
              .to_string(formatters={k: v.format for k, v in fmt.items()}))
    print("  corr/t: predictor vs realised standalone R over ALL validation signals with an "
          "exit (raw: |strength|; calibrated: predicted R)")
    for name, info in infos.items():
        print_model(name, info)
    print_flags(infos)


def print_model(name: str, info: dict) -> None:
    m = info["model"]
    print(f"\n--- {name}: {info['signals']:,} signals; fitted on {m['n']:,} FIT trades "
          f"(exit < {VAL_START.date()}), mean realised R {info['fit_mean_R']:+.4f}")
    print("  category counts (FIT trades): " +
          ", ".join(f"{k} {v:,}" for k, v in info["category_counts"].items()))
    print(f"  merged into 'other' (<{MIN_CATEGORY_TRADES} trades): {info['merged'] or 'none'}")
    print(f"  {'term':<24} {'coef (R units)':>15} {'standardised':>13} {'t (approx)':>11}")
    print(f"  {'intercept':<24} {m['intercept']:>+15.5f}")
    for k in m["coef"].index:
        print(f"  {k:<24} {m['coef'][k]:>+15.5f} {m['coef_std'][k]:>+13.5f} {m['t'][k]:>+11.2f}")
    print(f"  predicted R > 0: {info['pred_pos_share_fit']:.0%} of FIT signals, "
          f"{info['pred_pos_share_val']:.0%} of VALIDATION signals "
          f"({info['val_with_outcome']:,} of {info['val_signals']:,} with an exit)")
    e = info["engine_check"]
    print(f"  standalone vs engine R: {e['matched']:,} of {e['engine_trades']:,} FIT engine "
          f"trades matched, max |diff| {e['max_abs_diff']:.2e}")


def print_flags(infos: dict) -> None:
    flags = ["Strategy A never checks stop/target on the ENTRY day (only from the next bar); "
             "the standalone target copies this, so R is optimistic on days that gap through."]
    for name, info in infos.items():
        m = info["model"]
        if m["coef"].get("abs_strength", 0) < 0:
            flags.append(f"{name}: |strength| coefficient is NEGATIVE (stronger signal -> lower R).")
        weak = [k for k in m["t"].index if abs(m["t"][k]) < 2]
        if weak:
            flags.append(f"{name}: |t| < 2 for {weak} -- those effects are within noise.")
        if not 0.1 <= info["pred_pos_share_fit"] <= 0.9:
            flags.append(f"{name}: predicted R > 0 for {info['pred_pos_share_fit']:.0%} of FIT "
                         "signals -- the layer is close to all-or-nothing.")
        if info["merged"]:
            flags.append(f"{name}: categories merged into 'other': {info['merged']}.")
        if not info["engine_check"]["max_abs_diff"] <= 1e-9:
            flags.append(f"{name}: standalone R does NOT match the engine -- do not trust the target.")
        if info["top_duration_share"] > 0.8:
            flags.append(f"{name}: {info['top_duration_share']:.0%} of signals share one duration "
                         "value, so the duration coefficient rests on few distinct values.")
        if info["share_strength_1"] > 0.5:
            flags.append(f"{name}: {info['share_strength_1']:.0%} of signals have |strength| = 1.")
        if info["last_signal"] < TRAIN_END - pd.Timedelta(days=14):
            flags.append(f"{name}: last signal {info['last_signal'].date()} -- scores end before "
                         f"TRAIN_END, so its VALIDATION window is shorter.")
    print(f"\n{'=' * 70}\nFLAGS -- check before trusting\n{'=' * 70}")
    for f in flags:
        print(f"  - {f}")


def main():
    verify_train_end()
    px, nw, cfg = load_training()
    trading_days = pd.DatetimeIndex(sorted(px.date.unique()))
    print(f"training only: {px.date.min().date()} -> {px.date.max().date()} | "
          f"{px.ticker.nunique()} tickers | {len(nw):,} headlines | "
          f"cost {cfg.cost.per_side_bps:.2f} bps/side (training spreads)")
    llm = pd.read_csv(LLM_SCORES)
    assert pd.to_datetime(llm.timestamp, utc=True).max().tz_localize(None).normalize() <= TRAIN_END, \
        "LLM score file contains test-period rows"
    importance = dict(zip(zip(llm.headline, llm.ticker), llm.importance))
    rows, infos = [], {}
    for name, scorer, imp in (("keyword", KeywordScorer(cfg.signal), None),
                              ("llm", PrecomputedScorer(str(LLM_SCORES)), importance)):
        r, infos[name] = process_scorer(name, scorer, imp, px, nw, cfg, trading_days)
        rows += r
    report(rows, infos)
    print(f"\nlogged {len(rows)} ok configuration(s) to {EXPERIMENT_LOG}")


if __name__ == "__main__":
    main()
