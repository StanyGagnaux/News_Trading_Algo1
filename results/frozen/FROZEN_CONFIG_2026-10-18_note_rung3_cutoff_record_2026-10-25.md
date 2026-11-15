# Rung 3 (Sonnet 5.5) — knowledge-cutoff record, dated 25 October 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written 2026-10-25 AFTER rung 3 was run. A record of what WAS run, not a
pre-registration. It completes `…note_rung3_sonnet_2026-10-25.md` (133bec5e…)
and its amendment (36f6421b…), which state the model, settings and that the
rung was added after rung 2's results, but give no source for the cutoff.

- **What was run:** `claude-sonnet-5-5`, Message Batches; prompt,
  anonymisation (`anonymize.py`), parsing (`parse_reply`) and headline set
  identical to rungs 1 and 2; max_tokens 300; default sampling; effort `low`;
  thinking at the model default (adaptive; 1 of 57,637 replies used it).
  Added after Haiku's (rung 2) results were seen.
- **Knowledge cutoff:** not published in the API model metadata available to
  this project (`client.models.retrieve` returns no cutoff field). The model's
  API release date is **2026-09-28** (Haiku 5.5: 2026-10-07), i.e. after the
  end of the sample (2026-06-01). The cutoff is therefore conservatively
  treated as covering the whole sample, and **every rung-3 result is labelled
  "exposed to look-ahead"**, as for Haiku.
