"""
Offline replay test of src/live_pipeline.py against the historical pipeline.
One historical trading day is rebuilt as newswire items and fed through the
live Session exactly as the websocket would. No network, no model call
(any Ollama call fails the test), the real LLM cache is never written.
Run (from the project root):  python3 tests/test_live_pipeline.py [YYYY-MM-DD]
"""
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import live_pipeline as lp
from paths import NEWS_CLEAN, TICKERS, DATA
from newsdrift import Config, KeywordScorer

PASS = []
DAY = sys.argv[1] if len(sys.argv) > 1 else "2026-05-20"


def check(name, cond, detail=""):
    assert cond, f"FAIL: {name} {detail}"
    PASS.append(name)
    print(f"  ok  {name} {detail}")


def no_llm_call(prompt):
    raise AssertionError("the replay test must not call the model")


lp.save_cache = lambda cache: None                  # never write the real cache
news = pd.read_csv(NEWS_CLEAN)
day = news[pd.to_datetime(news.timestamp, utc=True).dt.strftime("%Y-%m-%d") == DAY]
items = [{"id": i, "created_at": ts, "updated_at": ts, "headline": h, "source": "benzinga",
          "symbols": sorted(g.ticker.tolist())}
         for i, ((ts, h), g) in enumerate(day.sort_values("timestamp").groupby(["timestamp", "headline"], sort=False))]
universe = {t.strip().upper() for t in open(TICKERS) if t.strip()}
scorers = lp.Scorers(use_llm=True, use_embed=True, llm_call=no_llm_call)
out = Path(tempfile.mkdtemp())
session = lp.Session(DAY, scorers, universe, out_dir=out)
received = pd.Timestamp(f"{DAY} 12:00", tz="UTC").to_pydatetime()
for it in items:
    session.handle(it, received)
scores = pd.read_csv(session.score_file)
print(f"replayed {DAY}: {len(items):,} items -> {len(scores):,} universe rows")

print("universe rows")
hist_rows = set(zip(day.timestamp, day.ticker, day.headline))
live_rows = set(zip(scores.created_at, scores.ticker, scores.headline))
check("live rows equal the historical rows for the day", live_rows == hist_rows,
      f"{len(live_rows)} vs {len(hist_rows)}")

print("keyword (rung 0)")
kw = KeywordScorer(Config().signal)
ref = np.array([kw.score(h, t)[0] for h, t in zip(scores.headline, scores.ticker)])
check("keyword scores identical", np.allclose(scores.kw_strength, ref))

print("embeddings (rung 1b)")
emb = pd.read_csv(DATA / "news_scored_embed_minilm_incl_test.csv")
m = scores.merge(emb.drop_duplicates(["headline", "ticker"]), on=["headline", "ticker"], how="inner")
check("embedding scores identical to the batch file", len(m) > 0 and np.allclose(m.emb_strength, m.strength, atol=1e-9),
      f"{len(m)} rows compared")

print("LLM (rung 1), template rule")
llm = pd.read_csv(DATA / "news_scored_llm_ollama_anon_incl_test.csv").drop_duplicates(["headline", "ticker"])
j = scores.merge(llm, on=["headline", "ticker"], how="left")
hist_scored, live_scored = j.strength.notna(), j.llm_strength.notna()
both = hist_scored & live_scored
same = np.isclose(j.loc[both, "llm_strength"], j.loc[both, "strength"])
print(f"    batch-scored rows {hist_scored.sum()}, live-scored {live_scored.sum()}, both {both.sum()}, "
      f"identical where both {same.mean() if both.any() else float('nan'):.1%}; "
      f"live sources: {scores.llm_source.value_counts().to_dict()}")
check("where both are scored, live LLM scores equal the batch file", bool(same.all()))

print("revisions")
first = dict(items[0])
session.handle({**first, "headline": first["headline"] + " (updated)", "updated_at": "later"}, received)
revs = pd.read_csv(session.rev_file)
check("every revision logged", (revs.news_id == first["id"]).sum() == 2)
check("latest revision kept", session.latest[first["id"]][1]["headline"].endswith("(updated)"))
session.close()
check("end-of-day tables written", (out / f"signals_keyword_{DAY}.csv").exists()
      and (out / f"news_latest_{DAY}.csv").exists())

print(f"\nALL {len(PASS)} CHECKS PASSED")
