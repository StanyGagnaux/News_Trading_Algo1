# Strategy B placebo, dated 25 October 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written 2026-10-25 BEFORE the run, by decision of the author (thesis audit:
B is the one engine without a placebo). Added after B's results are known.

Design — the same as A's placebo (`…note_bug14_2026-10-24.md`, item e):
- TRAINING period only; keyword B events (`market_hours_events(build_event_table(...))`,
  as in the runner); directions drawn at random with
  `numpy.random.default_rng(20261024)` on the sign of |strength|.
- Bug 14 engine (`IntradayBacktest`), fixed sizer, designed governor, the keyword
  **B-fixed** risk scale of the Bug 14 correction
  (`outputs/risk_calibration_keyword_bug14fix_2026-10-24.csv`): B has two
  variants, entry at t+5 and t+15 min, each run with its own fixed scale.
- **Criterion (one rule for all engines): mean R within 2 plain SE of minus the
  expected cost in R**, per trade −(latency-decayed entry cost + 2.43 bps exit)
  / stop distance. **B passes only if both variants pass.** Long-minus-short
  reported as descriptive.
- If it fails: B is disclosed as not validated by placebo; no fixes.
