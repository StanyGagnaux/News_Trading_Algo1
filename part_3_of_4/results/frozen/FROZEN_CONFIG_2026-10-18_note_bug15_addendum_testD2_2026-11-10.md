# Bug 15 — addendum to the pre-run note: acceptance test D as run, and test D2 (common-direction placebo), dated 10 November 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written 2026-11-10 (Zurich), by decision of the author of the same day, **BEFORE any run of test D2** and before
any test-period run. Adds to `outputs/FROZEN_CONFIG_2026-10-18_note_bug15_2026-11-10.md`
(`7a66229bf806ac38d6994543f72df0cd032059f2e742c02d8606e9468cf6676a`), which is not edited. Implements the
the specification's design, which is not edited:

    401d7215ee2f9801fdbf4c0ce4c2fb461b59e20da534c72a36dac16a6ae0320b  review_2026-11-10/BUG15_addendum_2_testD_2026-11-10.md

No criterion is changed beyond what is written here.

## 1. Acceptance tests so far (training period only; `outputs/correction_bug15fix_2026-11-10/ACCEPTANCE_TESTS_bug15_2026-11-10.md`)

- **A, C, E: passed.** The fixed engine equals the reference variant V2 (difference 0.0 on the ten training cells
  and on the equity curves); the unit test passes 19/19 and the code of 10 Nov fails 10 of its 18 checks.
- **B, training part: passed**, and it has power: 0 violations in 168,703 sizing calls on the new code; the
  independent recomputation flags 97.3–99.9% of the trades of the official training dumps of 24/25 October.
- **D (random directions, seed 20261024, Kelly sizer, scale 0.0033): stays in the record as run.** The new code
  passes (i) (0.48 SE) and (ii) (−1.11 bps, −0.54 plain SE). The requirement "the old code fails (ii)" is recorded
  as **not met and not meetable by that design** (old code −1.58 bps, −0.81 SE): with directions drawn independently
  per signal the direction of an entry is independent of its size under either code. It is not deleted and not
  reinterpreted.
- The supplement on the real signal directions (old logic +9.6, +8.7, +17.1 bps on the three free rungs; fixed logic
  within 1.4 clustered SE on every rung) is **descriptive and post hoc; it is not a criterion.**

## 2. Test D2 — common-direction placebo (replaces the power requirement of test D; not yet run in the project)

A placebo that carries no information about direction but keeps the property the error needs: a book whose
positions point the same way.

- **Inputs:** as test D — keyword daily signals, training period only (2016-01-04 → 2024-04-29), Kelly sizer,
  designed governor, script `src/placebo_a.py` with the additive option `--directions random|long|short`
  (default `random` = the existing placebo, unchanged).
- **D2-long:** strength = +|strength| for every signal. **D2-short:** strength = −|strength|. No random number is drawn.
- **Scale:** the keyword A Kelly scale of the 5% recalibration, **0.0033**, for both codes
  (`outputs/risk_calibration_keyword_bug15fix_2026-11-10.csv`, `352eb489…7d11ece`). The old code additionally at its
  own official scale 0.0082, descriptive.
- **Statistic:** exactly criterion (ii) of test D. Per trade i: oc_i = direction × (close / open − 1) of the entry
  day; size s_i = risk amount = pnl_i / R_i from the trade log (trades with R = 0 dropped and counted);
  w_i = s_i / mean(s); excess = mean((w_i − 1) × oc_i).
- **Standard error:** clustered by entry date (`clustered_se_of_mean` in `src/placebo_a.py`), not the plain one —
  with a common direction the terms of one day are correlated.
- Criterion (i) of test D is **not applied** to D2 (a book long everything earns the market's drift); mean R is
  reported, descriptive.

**Criteria, fixed here:**

1. **New code:** excess ≤ +2 clustered SE in D2-long **and** in D2-short (one-sided: a negative excess is not a
   look-ahead).
2. **Old code** (backup of 10 Nov in the sandbox `acceptance/D_oldcode/`, same script, same scale):
   excess > +2 clustered SE in D2-long **and** in D2-short.

**Outputs:** `outputs/placebo_a_kelly_common_direction_bug15fix_2026-11-10.csv` (new code, two rows) and
`acceptance/D_oldcode/outputs/placebo_a_kelly_common_direction_oldcode_2026-11-10.csv` (old code, two rows; the 0.0082
rows in `…_oldcode_oldscale_…`).

**Cross-check against the non-official reference implementation** (`review_2026-11-10/sizing_lag/testD2_reviewer_train.jsonl`,
training, scale 0.0033): old logic long +37.07 bps (7.77 SE), short +42.21 bps (6.93 SE); fixed logic long
+1.72 bps (0.33 SE), short −2.21 bps (−0.34 SE); trades 25,084 (long) and 25,090 (short). If the project's numbers
differ beyond rounding: stop and report before anything else.

**If a criterion is not met:** stop and report; no test-period run; the criteria are not amended after the result.
**If both are met:** the acceptance tests are complete; the stop report is updated and the correction run proceeds
exactly as in the pre-run note, Section 4: `run.sh run05`, then `cal20`, `run20`; the strict assertion (test B,
post-run part) on every official dump; the fixed-sizer A placebo rerun; the 8 November harness rerun; outputs to
`outputs/summary/` under dated names with SHA-256 (both placebo files and the D2 files included); dated correction notes
appended to `bugs.md` and `results.md`.

## 3. To be stated with the results (author's decision)

- The movement of the fixed rows, including the changed fixed scales (keyword 0.0039 → 0.0041, Sonnet
  0.0359 → 0.0361), and the Sonnet Kelly calibration at a training drawdown of 4.32% (the mechanical search
  alternated around 5%; the rule keeps the largest scale under 5.25%).
- Trial counts stay 139 / 155 / 161 / 163.
- A random-direction placebo cannot detect a look-ahead in position size, with any sizer; the strict assertion on
  every sizing call and the common-direction placebo are the checks that detect it.
