"""
rung2_haiku_extras.py -- the two pre-registered rung-2 extras (decisions note
of 24 Oct 2026, section 4; ladder note, section d):

  memorisation  1,000 TEST-period headlines from the rung-2 headline set,
                drawn with numpy.random.default_rng(20261024), each scored
                twice by Haiku (Message Batches): anonymised as in the main
                run, and with company names. Strength correlation, sign
                agreement, mean absolute change (as for Llama).
  latency       200 real-time calls (standard Messages API) on random
                headlines; median latency per headline; cost counted.

Same prompt, parser, model and request parameters as haiku_batch.py. Every
result is "exposed to look-ahead" (knowledge cutoff after the sample).

USAGE (from the project root):  python3 src/rung2_haiku_extras.py
"""
from __future__ import annotations

import argparse
import json
import time
from types import SimpleNamespace

import anthropic
import numpy as np
import pandas as pd
from dotenv import load_dotenv

from paths import DATA, OUTPUTS, COMPANY_NAMES, PRICES, NEWS_CLEAN
from anonymize import anonymize, load_aliases, MASK
from score_news_llm import _build_prompt
from splits import backtest_train_end
import haiku_batch as hb

SEED, N_MEM, N_LAT = 20261024, 1_000, 200
RUNGS = {"haiku": ("rung2", hb.HAIKU, "Haiku 5.5"), "sonnet": ("rung3", hb.SONNET, "Sonnet 5.5")}


def paths_for(rung: str):
    tag, bm, name = RUNGS[rung]
    return (DATA / f"news_scored_{rung}_anon_incl_test.csv", OUTPUTS / f"{tag}_memorisation_2026-10-25.csv",
            OUTPUTS / f"{tag}_extras_2026-10-25.json", bm, name)


def prompt(headline: str, ticker: str, named: bool, aliases: dict) -> str:
    if named:
        return _build_prompt(SimpleNamespace(headline=headline, ticker=ticker), False)
    return _build_prompt(SimpleNamespace(headline=headline, ticker=ticker, prompt_ticker=MASK,
                                         prompt_headline=anonymize(headline, ticker, aliases.get(ticker, []))), False)


def strength(parsed: dict, key: str) -> float:
    return parsed[key]["strength"] if parsed.get(key) else np.nan


def memorisation(client, aliases: dict, test: pd.DataFrame, log: dict, bm, out_mem) -> dict:
    uniq = test.drop_duplicates("headline").reset_index(drop=True)
    pick = uniq.iloc[np.random.default_rng(SEED).choice(len(uniq), N_MEM, replace=False)].reset_index(drop=True)
    items = {}
    for i, r in pick.iterrows():
        items[f"mem_anon_{i}"] = prompt(r.headline, r.ticker, False, aliases)
        items[f"mem_named_{i}"] = prompt(r.headline, r.ticker, True, aliases)
    res = hb.run_batches(client, items, log, bm)
    parsed = {k: hb._parse(m) for k, m in res.items()}
    pick = pick.assign(s_anon=[strength(parsed, f"mem_anon_{i}") for i in range(len(pick))],
                       s_named=[strength(parsed, f"mem_named_{i}") for i in range(len(pick))])
    pick[["timestamp", "ticker", "headline", "s_anon", "s_named"]].to_csv(out_mem, index=False)
    both = pick.dropna(subset=["s_anon", "s_named"])
    return {"headlines": N_MEM, "both_parsed": len(both),
            "strength_corr": float(both.s_anon.corr(both.s_named)),
            "sign_agreement": float((np.sign(both.s_anon) == np.sign(both.s_named)).mean()),
            "mean_abs_change": float((both.s_anon - both.s_named).abs().mean())}


def latency(client, aliases: dict, rows: pd.DataFrame, bm) -> dict:
    pick = rows.iloc[np.random.default_rng(SEED + 1).choice(len(rows), N_LAT, replace=False)]
    ms, tin, tout = [], 0, 0
    for r in pick.itertuples(index=False):
        t = time.perf_counter()
        m = client.messages.create(**hb.params(prompt(r.headline, r.ticker, False, aliases), bm))
        ms.append((time.perf_counter() - t) * 1000)
        tin += m.usage.input_tokens
        tout += m.usage.output_tokens
    return {"calls": N_LAT, "median_latency_ms": float(np.median(ms)), "p90_latency_ms": float(np.percentile(ms, 90)),
            "cost_usd": (tin * bm.std_in + tout * bm.std_out) / 1e6, "api": "standard Messages API"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rung", choices=list(RUNGS), default="haiku")
    scores_file, out_mem, out_json, bm, name = paths_for(ap.parse_args().rung)
    load_dotenv()
    client = anthropic.Anthropic()
    aliases = load_aliases(COMPANY_NAMES)
    scored = pd.read_csv(scores_file)
    cut = backtest_train_end(PRICES, NEWS_CLEAN, "2016-01-01", "2026-06-01", 0.80)
    test = scored[pd.to_datetime(scored.timestamp, utc=True) >= pd.Timestamp(cut, tz="UTC") + pd.Timedelta(days=1)]
    main_log = json.loads(bm.usage_log.read_text())
    lat_worst = N_LAT * (main_log["estimate"]["mean_input_tokens"] * bm.std_in + hb.MAX_TOKENS * bm.std_out) / 1e6
    log = hb.new_log(bm, prior_usd=main_log["cost_usd"], reserve_usd=lat_worst,
                     worst_usd_per_request=main_log["estimate"]["worst_usd_per_request"], stopped_by_cap=False)
    mem = memorisation(client, aliases, test, log, bm, out_mem)
    if log["stopped_by_cap"]:
        raise SystemExit("memorisation batch would pass the cap -- extras stopped")
    lat = latency(client, aliases, scored.drop_duplicates("headline"), bm)
    out = {"label": f"exposed to look-ahead ({name} knowledge cutoff after the sample)",
           "memorisation": mem, "memorisation_batch_usage": log, "latency": lat,
           "extras_cost_usd": log["cost_usd"] + lat["cost_usd"]}
    out_json.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
