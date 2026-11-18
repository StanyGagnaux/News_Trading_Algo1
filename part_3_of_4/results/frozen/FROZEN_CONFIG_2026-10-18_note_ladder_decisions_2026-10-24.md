# Note to FROZEN_CONFIG_2026-10-18 — decisions on the ladder note, dated 24 October 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written 2026-10-24 15:12 CEST, before Phase 1. Amends
`FROZEN_CONFIG_2026-10-18_note_ladder_2026-10-24.md` only where stated.

## 1. Open choices: approved as written

Embedding target (NDX-adjusted return, entry open to day-3 close), penalty
grid, q95 scaling, no refit; the factor specification including the stated
day-1 approximation; Llama-only paper orders, exit after 30 minutes or at
15:55 ET, $1,000 notional; 200 real-time latency calls per rung.
**Rung 1b's training-period results are in-sample** (2016–2021 is its fit
sample; 2022–2024-04-29 chose the penalty) and are labelled so in every table.

## 2. Rung 2 sampling (deviation from the Llama runs)

`claude-haiku-5-5` via the Message Batches API rejects non-default
temperature / top_p / top_k, so rung 2 runs at the model's **default
sampling**, not temperature 0.2 as the Llama runs. Recorded as a deviation.
The effort parameter is set to its **lowest valid value** for every request;
the valid values are checked against the API documentation before
submission, and the value used, any thinking tokens and their cost are
recorded in the Phase 3 report.

## 3. Look-ahead (known limitation, no clean window)

Haiku 5.5's knowledge cutoff (June 2026) covers the whole sample (training
and test). Anonymisation does not remove this risk. **Every rung-2 result is
labelled "exposed to look-ahead".**

## 4. Memorisation check (rung 2)

1,000 test-period headlines drawn at random from the rung-2 headline set with
`numpy.random.default_rng(20261024)`; each scored by Haiku twice — anonymised
as in the main run, and with company names. Reported: strength correlation,
sign agreement, mean absolute change in strength (as for Llama).

## 5. Spend cap

$30 in total for Phase 3, **including thinking tokens**. Estimate first with
the token-counting endpoint; stop without submitting if the estimate exceeds
the cap.

## 6. Phase 2 replaced: live/historical parity, then paper trading

a) Audit: list every difference between the live scripts and the
   historical pipeline (universe, pre-filter, exact and template
   deduplication, anonymisation, model, prompt, temperature, ticker source,
   daily aggregation, zero-netting and noise gate, timestamps logged) before
   changing anything.
b) One code path: the live system imports the same functions as the
   historical pipeline for every step; no re-implemented logic. Ticker =
   newswire tag; universe = `data_sources/nasdaq100.txt`. Keep the latest
   version of each news ID and log every revision; log newswire created_at
   and updated_at, receipt time, score time per rung, order and fill times.
c) Shadow mode, NO orders: Monday 26 and Tuesday 27 October 2026, US market
   hours (14:30–21:00 Swiss time that week).
d) Parity test: the same two days from the historical news API through the
   batch pipeline, compared item by item (kept vs dropped, tickers, keyword
   scores — must match exactly —, Llama score correlation and sign agreement,
   revisions seen live but absent historically). Report and stop.
e) Paper trading only after approval: Wednesday 28 October → Friday
   6 November 2026, paper endpoint only (the earlier 26 October start is
   withdrawn).

## 7. Installs and data

Approved: `sentence-transformers`, `torch`, `anthropic`; downloading the
Kenneth French factor files. `ANTHROPIC_API_KEY` is stored only in `.env` for
the scoring script, never in a shell profile.

## Order of work

Phase 1 (factor robustness, rung 1b, speed bound) → report. Phase 2 (6a–d)
→ report → 6e after approval. Phase 3 when the key is in `.env` → report.
Phase 4 (`outputs/cost_ladder_<date>.csv`, everything to `outputs/summary/`) → stop.
