# Bug 13 decision — Strategy C invalid, C1 is the hybrid strategy, dated 24 October 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written 2026-10-24 after the C1 diagnostic, by decision of the author. Adds to
`…note_bug13_2026-10-24.md` (8a537056…) and `…note_bug13_addendum_2026-10-24.md`
(ecd30b37…); neither is edited.

## C1 diagnostic result (training, seed 20261024, same 12,410 keyword C events)

| | C (basis fix) | C1 (entry at news-day close) |
|---|---|---|
| mean R / expected cost R | −0.0029 / −0.0117 (2.04 SE) | +0.0017 / −0.0103 (2.88 SE) |
| long − short gap | +0.0590R (t 6.82) | +0.0063R (t 0.76) |

|g_C1 − g_C| = 0.0527 > SE_C = 0.0086: under the addendum rule C1 is
symmetric, so a basis error is taken to remain in C. Caveat recorded: C1 does
not hold the rest of the news day after C's intraday entry, so the rule cannot
separate a basis error from unsigned news-day drift.
Output: `outputs/placebo_c1_2026-10-24.csv`, log `outputs/logs/placebo_c1_2026-10-24.log`.

## Decision

1. **Bug 13 is unresolved within the project.** No further C diagnostics.
2. **Strategy C is reported as invalid** — the official 18 Oct C rows and the
   ladder's rung-1b C rows. C is not rerun.
3. **C1 replaces C as the hybrid strategy** (news-driven entry at the news-day
   daily close, multi-day hold, daily bars only, so no minute/daily mixing).
   Existing C1 results are the in-sample sweep only (keyword −4.2%, LLM +0.6%
   p.a., `outputs/sweep_new_strategies_*.csv`); C1 has no frozen test run. Any
   C1 test-period run needs its own dated note before it is run. C1 was one of
   the in-sample variants already counted in the deflated-Sharpe trial count.
4. C1's own placebo is also above its cost (2.88 SE); this is examined by code
   inspection (no change yet) and reported separately.
