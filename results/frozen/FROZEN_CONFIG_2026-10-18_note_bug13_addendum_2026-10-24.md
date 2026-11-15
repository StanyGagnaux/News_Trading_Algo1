# Addendum to the Bug 13 note — C1 decision rule, dated 24 October 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written 2026-10-24 16:25 CEST, BEFORE the C1 diagnostic is run. Adds to
`FROZEN_CONFIG_2026-10-18_note_bug13_2026-10-24.md`; that note is not edited.

The C placebo failed (long-minus-short gap +0.0590R, SE 0.0086R, t 6.82;
mean R -0.0029 vs expected cost -0.0117). Diagnostic: the same
placebo through **C1** (entry at the news-day daily close, exits on daily bars,
so no minute/daily basis mixing): same training sample, same events, same
random directions (`numpy.random.default_rng(20261024)`).

**Decision rule:** let g_C = +0.0590R (C's long-minus-short gap) and SE_C = 0.0086R.
- If |g_C1 − g_C| ≤ SE_C, the residual is drift or selection, not price basis:
  the basis fix is **accepted**, Bug 13 is closed, and C is rerun for all rungs
  in training and test as a disclosed correction (as in the Bug 13 note).
- If C1 is symmetric (its gap is not within that band), a basis error remains
  in C: keep investigating; C is **not** rerun.
