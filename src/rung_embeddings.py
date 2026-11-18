"""
rung_embeddings.py -- cost-ladder rung 1b (ladder note of 24 Oct 2026, item b;
decisions note of the same day). Sentence embeddings + ridge -> strength.

- Model sentence-transformers/all-MiniLM-L6-v2, pinned to the Hub commit
  resolved at run time (recorded with package versions).
- Input: every headline row the Llama files scored, anonymised with the same
  anonymize()/load_aliases() as score_news_llm.py (each row's own headline
  and ticker).
- Target y (training only): unsigned NDX-adjusted return, entry open ->
  close of day 3, of the (ticker, entry day) event the headline belongs to
  (frozen event-study definition; event_study.event_returns with sign +1).
- Ridge with intercept. Fit: day-3 close <= 2021-12-31. Penalty from the grid
  below by validation MSE on entry >= 2022-01-01 and day-3 close <= 2024-04-29.
  No refit. s = clip(yhat / q95, -1, 1), q95 = 95th pct of |yhat| on the fit
  sample; duration 2; no importance. Training results are IN-SAMPLE.

Writes data_sources/news_scored_embed_minilm{,_incl_test}.csv (same format as
the Llama files), outputs/rung1b_model_2026-10-24.json (model, grid, choice,
timings). Uses NO test-period price or return.

USAGE (from the project root):  python3 src/rung_embeddings.py
"""
from __future__ import annotations

import json
import time
from importlib.metadata import version

import numpy as np
import pandas as pd

from paths import DATA, OUTPUTS, COMPANY_NAMES
from anonymize import anonymize, load_aliases
from calibrate_scorer import load_training, TRAIN_END, DATA_START
import event_study as es

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
GRID = [0.01, 0.1, 1, 10, 100, 1_000, 10_000]
FIT_END, VAL_START = pd.Timestamp("2021-12-31"), pd.Timestamp("2022-01-01")
DURATION = 2
SEED_LATENCY, N_LATENCY = 20261024, 200
SRC = DATA / "news_scored_llm_ollama_anon_incl_test.csv"
OUT_TRAIN = DATA / "news_scored_embed_minilm.csv"
OUT_FULL = DATA / "news_scored_embed_minilm_incl_test.csv"
META = OUTPUTS / "rung1b_model_2026-10-24.json"
PARAMS = OUTPUTS / "rung1b_params_2026-10-24.npz"


def load_model():
    from huggingface_hub import HfApi
    from sentence_transformers import SentenceTransformer
    sha = HfApi().model_info(MODEL_ID).sha
    return SentenceTransformer(MODEL_ID, revision=sha, device="cpu"), sha


def event_targets(rows: pd.DataFrame) -> pd.DataFrame:
    """Unsigned NDX-adjusted entry-open -> day-3-close return per training row."""
    px, _, _ = load_training()
    td = pd.DatetimeIndex(sorted(px.date.unique()))
    nd = pd.to_datetime(rows.timestamp, utc=True).dt.tz_localize(None).dt.normalize()
    pos = td.searchsorted(nd + pd.Timedelta(days=1))           # frozen rule, lag 1
    ok = pos < len(td)
    rows = rows[ok].assign(effective_date=td[pos[ok]])
    ev = rows[["effective_date", "ticker"]].drop_duplicates().assign(strength=1.0)
    ndx = es.load_ndx(DATA_START, TRAIN_END)
    ret = es.event_returns(px, ndx, ev)[["effective_date", "ticker", "mkt_3"]]
    bars = {t: pd.DatetimeIndex(g.date.sort_values()) for t, g in px.groupby("ticker")}

    def day3(r):
        b = bars.get(r.ticker)
        i = b.get_indexer([r.effective_date])[0] if b is not None else -1
        return b[i + 2] if i >= 0 and i + 2 < len(b) else pd.NaT
    ret["day3_close"] = [day3(r) for r in ret.itertuples(index=False)]
    return rows.merge(ret, on=["effective_date", "ticker"], how="left")


def ridge(X, y, lam):
    mx, my = X.mean(axis=0), y.mean()
    Xc = X - mx
    beta = np.linalg.solve(Xc.T @ Xc + lam * np.eye(X.shape[1]), Xc.T @ (y - my))
    return beta, my - mx @ beta


def embed_rows(model):
    """Every scored row with its unique anonymised text and that text's embedding."""
    rows = pd.read_csv(SRC, usecols=["timestamp", "ticker", "headline"])
    aliases = load_aliases(COMPANY_NAMES)
    uniq = rows[["headline", "ticker"]].drop_duplicates().reset_index(drop=True)
    texts = [anonymize(h, t, aliases.get(t, [])) for h, t in zip(uniq.headline, uniq.ticker)]
    t0 = time.perf_counter()
    emb = model.encode(texts, batch_size=256, show_progress_bar=False, convert_to_numpy=True)
    embed_s = time.perf_counter() - t0
    key = {k: i for i, k in enumerate(zip(uniq.headline, uniq.ticker))}
    rows["row"] = [key[k] for k in zip(rows.headline, rows.ticker)]
    return rows, texts, emb, embed_s


def fit_model(rows, emb) -> dict:
    """Fit 2016-2021, choose lambda on 2022-2024-04-29 (grid), no refit; q95 on fit."""
    ts = pd.to_datetime(rows.timestamp, utc=True).dt.tz_localize(None)
    train = event_targets(rows[ts < TRAIN_END + pd.Timedelta(days=1)])
    train = train[train.mkt_3.notna() & train.day3_close.notna()]
    fit = train[train.day3_close <= FIT_END]
    val = train[(train.effective_date >= VAL_START) & (train.day3_close <= TRAIN_END)]
    Xf, yf = emb[fit.row.to_numpy()], fit.mkt_3.to_numpy()
    Xv, yv = emb[val.row.to_numpy()], val.mkt_3.to_numpy()
    mse = {}
    for lam in GRID:
        b, a = ridge(Xf, yf, lam)
        mse[lam] = float(np.mean((yv - (a + Xv @ b)) ** 2))
    lam = min(mse, key=mse.get)
    beta, alpha = ridge(Xf, yf, lam)
    q95 = float(np.quantile(np.abs(alpha + Xf @ beta), 0.95))
    return {"alpha": float(alpha), "beta": beta, "lambda": lam, "q95": q95, "mse": mse,
            "fit": fit, "val": val, "yf": yf, "yv": yv, "Xf": Xf}


def strength_from_embedding(emb, alpha: float, beta, q95: float):
    """Prediction -> strength in [-1, 1] (the rung-1b scoring rule)."""
    return np.clip((alpha + emb @ beta) / q95, -1, 1)


def main():
    model, sha = load_model()
    rows, texts, emb, embed_s = embed_rows(model)
    m = fit_model(rows, emb)
    alpha, beta, lam, q95, mse = m["alpha"], m["beta"], m["lambda"], m["q95"], m["mse"]
    fit, val, yf, yv, Xf = m["fit"], m["val"], m["yf"], m["yv"], m["Xf"]
    ts = pd.to_datetime(rows.timestamp, utc=True).dt.tz_localize(None)

    t1 = time.perf_counter()
    strength = strength_from_embedding(emb, alpha, beta, q95)
    predict_s = time.perf_counter() - t1
    full = pd.read_csv(SRC, usecols=["timestamp", "ticker", "headline"]).assign(
        strength=strength[rows.row.to_numpy()], duration=DURATION, importance=np.nan)
    full.to_csv(OUT_FULL, index=False)
    full[ts < TRAIN_END + pd.Timedelta(days=1)].to_csv(OUT_TRAIN, index=False)

    rng = np.random.default_rng(SEED_LATENCY)
    lat = []
    for i in rng.choice(len(texts), N_LATENCY, replace=False):
        t = time.perf_counter()
        _ = alpha + model.encode([texts[i]], convert_to_numpy=True) @ beta
        lat.append((time.perf_counter() - t) * 1000)
    meta = {"model": MODEL_ID, "revision": sha, "sentence_transformers": version("sentence-transformers"),
            "torch": version("torch"), "device": "cpu", "grid": GRID, "val_mse": mse, "lambda": lam,
            "q95_bps": q95, "fit_rows": len(fit), "val_rows": len(val),
            "fit_r2": float(1 - np.mean((yf - (alpha + Xf @ beta)) ** 2) / np.var(yf)),
            "val_r2": float(1 - mse[lam] / np.var(yv)), "unique_texts": len(texts),
            "rows_scored": len(full), "compute_s_per_1000_headlines": (embed_s + predict_s) / len(texts) * 1000,
            "median_latency_ms_single_headline": float(np.median(lat)),
            "latency_sample": {"n": N_LATENCY, "seed": SEED_LATENCY}, "duration_fixed": DURATION,
            "share_abs_strength_ge_0.2": float((np.abs(strength) >= 0.2).mean())}
    META.write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


def save_params():
    """Refit (deterministic) and save the parameters the live pipeline uses;
    verify they reproduce the saved score file exactly."""
    model, sha = load_model()
    rows, _, emb, _ = embed_rows(model)
    m = fit_model(rows, emb)
    np.savez(PARAMS, alpha=m["alpha"], beta=m["beta"], q95=m["q95"], lam=m["lambda"], revision=sha)
    saved = pd.read_csv(OUT_FULL)
    redo = strength_from_embedding(emb, m["alpha"], m["beta"], m["q95"])[rows.row.to_numpy()]
    diff = float(np.max(np.abs(saved.strength.to_numpy() - redo)))
    print(f"saved {PARAMS.name}: lambda {m['lambda']}, q95 {m['q95']:.4f}, revision {sha}; "
          f"max |strength diff| vs {OUT_FULL.name}: {diff:.2e}")
    assert diff < 1e-9, "parameters do not reproduce the saved scores"


if __name__ == "__main__":
    import sys
    save_params() if "--save-params" in sys.argv else main()
