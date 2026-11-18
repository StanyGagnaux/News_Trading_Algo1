"""
llama_latency.py -- rung 1 latency for the cost ladder (ladder note of
24 Oct 2026, section d: 200 real-time calls per rung). Same anonymised
prompt, model, call and parser as the Llama scoring (score_news_llm.py), on
200 random scored headlines (numpy.random.default_rng(20261024)). Also
reports how often the live reply's sign matches the stored score (the model
runs at temperature 0.2, so replies can vary).

USAGE (from the project root):  python3 src/llama_latency.py
"""
from __future__ import annotations

import json
import os
import time

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

from paths import DATA, OUTPUTS
from score_news_llm import PROVIDERS, _anonymize, _build_prompt, _call_ollama, parse_reply

SEED, N = 20261024, 200
SCORES = DATA / "news_scored_llm_ollama_anon_incl_test.csv"
OUT = OUTPUTS / "rung1_llama_latency_2026-10-25.json"


def main():
    load_dotenv(".env")
    client = OpenAI(api_key="ollama", base_url=os.environ["OLLAMA_BASE_URL"])
    rows = pd.read_csv(SCORES).drop_duplicates("headline").reset_index(drop=True)
    pick = _anonymize(rows.iloc[np.random.default_rng(SEED).choice(len(rows), N, replace=False)])
    ms, parsed, same_sign = [], 0, []
    for r in pick.itertuples(index=False):
        t = time.perf_counter()
        reply = _call_ollama(client, _build_prompt(r, False))
        ms.append((time.perf_counter() - t) * 1000)
        p = parse_reply(reply)
        if p:
            parsed += 1
            same_sign.append(np.sign(p["strength"]) == np.sign(r.strength))
    out = {"model": PROVIDERS["ollama"]["model"], "calls": N, "median_latency_ms": float(np.median(ms)),
           "p90_latency_ms": float(np.percentile(ms, 90)), "mean_latency_ms": float(np.mean(ms)),
           "seconds_per_1000_sequential": float(np.mean(ms)), "parsed": parsed,
           "sign_agreement_with_stored_score": float(np.mean(same_sign)) if same_sign else None,
           "host": "local Ollama over LAN/VPN", "cost_usd": 0.0}
    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
