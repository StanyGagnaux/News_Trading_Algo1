# Rung 3 (Claude Sonnet 5.5) — added to the cost ladder, dated 25 October 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written 2026-10-25 BEFORE any rung-3 scoring or code change, by decision of the
author (after rung 2's results were seen; disclosed as such). Adds a rung to
`…note_ladder_2026-10-24.md`; rung 2 (`…note_rung2_2026-10-24.md`) is unchanged.

## Scoring — identical to rung 2 except the model

- Model `claude-sonnet-5-5` via the Message Batches API ($1 / $5 per MTok;
  standard $2 / $10). Same 57,665 representative headlines (same Tier-0
  filter, template dedup), same anonymised prompt and `parse_reply`,
  max_tokens 300, **default sampling** (non-default values are rejected),
  **effort `low`** (lowest valid value; the model default is `high`),
  **thinking at the model default** (adaptive; it cannot be disabled on this
  model). Unparseable replies retried once identically, then counted.
  Separate cache namespace (`sonnet_anon_`); outputs
  `data_sources/news_scored_sonnet_anon{,_incl_test}.csv`.
- **Spend cap $60** for rung 3 in total (main scoring + extras), including
  thinking tokens; estimated with the token-counting endpoint first; stop
  without submitting if the upper bound (every reply using all 300 output
  tokens) exceeds it. Expected ~$43 from rung 2's token usage.
- Extras as rung 2: memorisation check (1,000 test headlines, seed 20261024,
  anonymised vs named) and 200 real-time latency calls.

## Evaluation — as rung 2

Frozen event study (training and test), speed bound, **strategies A and B
only** (C and C1 excluded), risk scales calibrated on training (5% rule,
`calibrate_risk.py --skip-c`), one run over training + test, Jobson-Korkie-
Memmel vs the continuous momentum benchmark, Kelly − fixed with Holm (rung 3
as its own family of 3). **Deflated Sharpe N = 161** (155 + the 6 new rung-3
strategy rows). **Every rung-3 result is labelled "exposed to look-ahead"**
(knowledge cutoff after the sample).

Code to be generalised (additive; Haiku behaviour and file names unchanged):

| file | SHA-256 before |
|---|---|
| `src/score_news_llm.py` | `6e3e525630178773a4b92d32b050366bbef1b807a8e86b9a9572d26c0e55a956` |
| `src/haiku_batch.py` | `bbb3a4ddd02eba25299480eeab98e25cf2bda9883f0b911103bbca8a17a7ec3c` |
| `src/speed_bound.py` | `6c1c804cec3362a07c6df17792a31838a8f1b545c9708b77a8485bf749f70057` |
| `src/rung2_haiku_extras.py` | `2e307b6a4749ea2535eab0e70b09aa21d1e286f0cfefce24f25f0a569dcae999` |
| `src/rung2_report.py` | `b3136efeee22bdc24e77663004c4ed5b548be354c149941ad3e12bd078f91812` |
