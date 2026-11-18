"""
haiku_batch.py -- ladder scoring through the Message Batches API: rung 2
(Claude Haiku 5.5; ladder + decisions notes of 24 Oct 2026, rung-2 note) and
rung 3 (Claude Sonnet 5.5; rung-3 note of 25 Oct 2026). Called by
score_news_llm.py (`--providers haiku|sonnet`), which builds the identical
headline set, anonymised prompt and parsing as the Llama runs.

- max_tokens 300 (as Llama), DEFAULT sampling (non-default temperature is
  rejected: recorded deviation), effort "low" (lowest valid value), thinking
  left at the model default.
- Cost: input tokens counted with the token-counting endpoint on a random
  sample (seed 20261024); upper bound assumes every reply uses all 300 output
  tokens; the memorisation check and the 200 latency calls are included.
  Stop without submitting if the bound exceeds the rung's cap.
- Unparseable or failed requests are retried once, identically, then left
  unscored and counted. Usage (incl. thinking) is logged.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import anthropic
import numpy as np

from paths import OUTPUTS


@dataclass(frozen=True)
class BatchModel:
    model: str
    price_in: float          # $/MTok, Message Batches
    price_out: float
    std_in: float            # $/MTok, standard Messages API (latency calls)
    std_out: float
    cap_usd: float
    usage_log: Path
    chunk: int = 20_000
    hard_stop: bool = False  # rung-3 amendment: guard every batch against the cap


HAIKU = BatchModel("claude-haiku-5-5", 0.05, 0.25, 0.10, 0.50, 30.0,
                   OUTPUTS / "rung2_haiku_usage_2026-10-25.json")
SONNET = BatchModel("claude-sonnet-5-5", 1.00, 5.00, 2.00, 10.00, 60.0,
                    OUTPUTS / "rung3_sonnet_usage_2026-10-25.json", chunk=5_000, hard_stop=True)
MODELS = {"haiku": HAIKU, "sonnet": SONNET}

MAX_TOKENS = 300
EFFORT = "low"
EXTRA_BATCH_REQUESTS = 2_000                # memorisation check: 1,000 headlines x 2
EXTRA_STD_REQUESTS = 200                    # latency calls
SAMPLE, SEED = 200, 20261024
POLL_S = 60


def params(prompt: str, bm: BatchModel = HAIKU) -> dict:
    return {"model": bm.model, "max_tokens": MAX_TOKENS, "output_config": {"effort": EFFORT},
            "messages": [{"role": "user", "content": prompt}]}


def text_of(message) -> str:
    return next((b.text for b in message.content if b.type == "text"), "")


def estimate(client, prompts: list[str], bm: BatchModel = HAIKU) -> dict:
    rng = np.random.default_rng(SEED)
    idx = rng.choice(len(prompts), min(SAMPLE, len(prompts)), replace=False)
    counts = [client.messages.count_tokens(model=bm.model, messages=[{"role": "user", "content": prompts[i]}]).input_tokens
              for i in idx]
    mean_in = float(np.mean(counts))
    per_batch = (mean_in * bm.price_in + MAX_TOKENS * bm.price_out) / 1e6
    main = len(prompts) * per_batch
    extras = EXTRA_BATCH_REQUESTS * per_batch + EXTRA_STD_REQUESTS * (mean_in * bm.std_in + MAX_TOKENS * bm.std_out) / 1e6
    return {"model": bm.model, "requests": len(prompts), "mean_input_tokens": mean_in,
            "worst_usd_per_request": per_batch,
            "upper_bound_main_usd": main, "upper_bound_extras_usd": extras,
            "upper_bound_total_usd": main + extras, "cap_usd": bm.cap_usd}


def run_batches(client, items: dict[str, str], log: dict, bm: BatchModel = HAIKU) -> dict:
    """{custom_id: Message or None}; batches of at most bm.chunk requests, each
    accounted as it ends. With bm.hard_stop, a batch is submitted only if
    prior + spent + its worst case + reserve <= cap (rung-3 amendment)."""
    out, keys = {}, list(items)
    for i in range(0, len(keys), bm.chunk):
        part = keys[i:i + bm.chunk]
        if bm.hard_stop:
            worst = len(part) * log["worst_usd_per_request"]
            if log.get("prior_usd", 0.0) + log["cost_usd"] + worst + log.get("reserve_usd", 0.0) > bm.cap_usd:
                log["stopped_by_cap"] = True
                print(f"  HARD STOP: spent ${log['cost_usd']:.2f}, next batch worst case ${worst:.2f} "
                      f"would pass the ${bm.cap_usd:.0f} cap -- nothing more submitted", flush=True)
                break
        batch = client.messages.batches.create(
            requests=[{"custom_id": k, "params": params(items[k], bm)} for k in part])
        log["batches"].append(batch.id)
        print(f"  {datetime.now():%H:%M} submitted batch {batch.id} ({len(part):,} requests)", flush=True)
        while client.messages.batches.retrieve(batch.id).processing_status != "ended":
            time.sleep(POLL_S)
        done = {r.custom_id: (r.result.message if r.result.type == "succeeded" else None)
                for r in client.messages.batches.results(batch.id)}
        account(done, log, bm)
        out.update(done)
        print(f"  {datetime.now():%H:%M} batch {batch.id} ended | spent ${log['cost_usd']:.2f}", flush=True)
    return out


def account(messages: dict, log: dict, bm: BatchModel = HAIKU) -> None:
    for m in messages.values():
        if m is None:
            continue
        log["input_tokens"] += m.usage.input_tokens
        log["output_tokens"] += m.usage.output_tokens
        log["responses_with_thinking"] += any(b.type == "thinking" for b in m.content)
        log["stopped_at_max_tokens"] += m.stop_reason == "max_tokens"
    log["cost_usd"] = (log["input_tokens"] * bm.price_in + log["output_tokens"] * bm.price_out) / 1e6


def new_log(bm: BatchModel, **extra) -> dict:
    return {"model": bm.model, "max_tokens": MAX_TOKENS, "effort": EFFORT, "sampling": "model default",
            "thinking": "model default (adaptive)", "started": datetime.now().isoformat(timespec="seconds"),
            "batches": [], "input_tokens": 0, "output_tokens": 0, "responses_with_thinking": 0,
            "stopped_at_max_tokens": 0, "cost_usd": 0.0, **extra}


def score_with_batches(todo, cache: dict, build_prompt, save_cache, bm: BatchModel = HAIKU) -> None:
    client = anthropic.Anthropic()                       # ANTHROPIC_API_KEY from .env
    items = {r.key: build_prompt(r) for r in todo.itertuples(index=False)}
    est = estimate(client, list(items.values()), bm)
    print(json.dumps(est, indent=2))
    if not bm.hard_stop and est["upper_bound_total_usd"] > bm.cap_usd:
        raise SystemExit(f"estimate ${est['upper_bound_total_usd']:.2f} exceeds the ${bm.cap_usd:.0f} cap -- nothing submitted")
    log = new_log(bm, estimate=est, worst_usd_per_request=est["worst_usd_per_request"],
                  reserve_usd=est["upper_bound_extras_usd"], stopped_by_cap=False)
    first = run_batches(client, items, log, bm)
    parsed = {k: _parse(m) for k, m in first.items()}
    retry = {k: items[k] for k in items if parsed.get(k) is None}
    log["retried"] = len(retry)
    if retry and not log["stopped_by_cap"]:
        second = run_batches(client, retry, log, bm)          # once, identically
        parsed.update({k: _parse(m) for k, m in second.items()})
    ok = {k: v for k, v in parsed.items() if v is not None}
    cache.update(ok)
    save_cache(cache)
    log.update({"requests": len(items), "scored": len(ok), "unscored": len(items) - len(ok),
                "finished": datetime.now().isoformat(timespec="seconds")})
    bm.usage_log.write_text(json.dumps(log, indent=2))
    print(f"  scored {len(ok):,}/{len(items):,} | unscored {len(items) - len(ok):,} | "
          f"cost ${log['cost_usd']:.2f} | usage log {bm.usage_log.name}")
    if log["stopped_by_cap"]:
        raise SystemExit("stopped by the cap: rung incomplete, NOT evaluated (amendment) -- no score file written")


def _parse(message):
    from score_news_llm import parse_reply                # same parser as the Llama runs
    return parse_reply(text_of(message)) if message is not None else None
