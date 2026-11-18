# Amendment to the rung-3 note — spend control, dated 25 October 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written 2026-10-25 BEFORE any rung-3 request was submitted (only free
token-counting calls were made), by decision of the author. Amends the spend
rule of `…note_rung3_sonnet_2026-10-25.md` (133bec5e…), which is not edited.

Why: the rung-3 note's rule compares the WORST-CASE cost (every reply using all
300 output tokens) with the cap. For Sonnet 5.5 that bound is $110.05 against
the $60 cap, so the first attempt stopped with nothing submitted. The cap was
chosen on the expected cost (~$43 from rung 2's token use); the rule and the
cap did not match.

New rule (rung 3 only; rung 2 unchanged): **hard stop at $60 in total.**
- Requests are submitted in batches of at most 5,000. Before each batch, the
  actual billed cost so far + that batch's worst case + a reserve for the
  extras (memorisation 2,000 batch requests + 200 latency calls, worst case)
  must not exceed $60; otherwise nothing more is submitted.
- If the stop is reached before every headline is scored, **rung 3 is left
  incomplete and NOT evaluated** (a partial headline set would select on
  submission order); the scored part stays in the cache, the stop is recorded.
- The retry pass (once, identically) is governed by the same rule.
Everything else in the rung-3 note is unchanged.
