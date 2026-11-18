# Bug 17 — addendum to the pre-run note: the fixture of one existing test (acceptance test C), dated 14 November 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written 2026-11-14 (Zurich) on the author's decision of the same day, after the correction was stopped at
acceptance test C and BEFORE the tests continue. It adds to
`outputs/FROZEN_CONFIG_2026-10-18_note_bug17_2026-11-14.md`
(`e96e94d7ee0596e92f0afebb3f3e5a11b24c5702937fd90a6e3964f6526c72cc`), which is not edited. Record of the stop:
`outputs/correction_bug17fix_2026-11-14/STOP_at_test_C_2026-11-14.md`.

## 1. What happened

Test C has two parts. Part 1 passed: the new `tests/test_bug17_admission_snapshot.py` fails each of its three
cases on the engine of 10 November (`fbf1e857…`) and passes 13 of 13 on the corrected engine (`424ae4ef…`).
Part 2 ("all 16 existing test files pass") did not: 15 of 16 passed and `tests/test_bug15_sizing_lag.py` failed
in its section 2 with `AssertionError: YYY: 0 trades`. The correction was stopped there. No test D, A, B or E, no
recalibration and no run had been started; no test-period result was read.

## 2. Why the unchanged test fails on the corrected engine

The fixture of section 2 relies on the defect that Bug 17 removes. Five positions of 17,506 notional each
(87,531 together) are held at the close of d−1 and all close during day d. The signal in `YYY` is effective d and
needs 17,506 more: 87,531 + 17,506 = 105,037, above the gross cap of 100,000 (`max_gross_exposure` 1.0 on an
equity of 100,000). The engine of 10 November judged the cap on the book after the day's exits (gross 0) and
admitted `YYY`. The corrected engine judges it on the book of the previous close and refuses `YYY`, as the rule
of the pre-run note requires (sizing log: `opened False`, `gross_at_decision` 87,530.62). Section 2 then has no
`YYY` trade whose size it could check and stops. The property the test is about, that the size of an entry at the
open of d uses only information of the close of d−1 (Bug 15), is not violated: section 1 passed before the stop.

## 3. The change (author's decision)

In `tests/test_bug15_sizing_lag.py`, function `fixed_case` (section 2) only, the fixture is given room under the
gross cap. One line, nothing else in the file changes:

    -    return run(frames, rows, "fixed", FIXED_SCALE)
    +    return run(frames, rows, "fixed", FIXED_SCALE, max_gross_exposure=2.0)

Sizes, equity and governor throttle of the fixture are unchanged; only the admission of `YYY` and `ZZZ` no longer
depends on capacity freed during day d.

    93427590ab01cf2324ed0a15c5646797ff8632f26547bb210edcf04ef5a131c5  tests/test_bug15_sizing_lag.py  (before; equal to the backup of 14 Nov)
    a8c0076094343d3e7fbfc22bda5bfcec04ca194dfff03759db302c42461f5638  tests/test_bug15_sizing_lag.py  (after)

## 4. The changed test on three engines

Run before the author's decision on a copy outside the project that is byte-identical to the file as changed
(`cmp` confirmed after the change); log `outputs/correction_bug17fix_2026-11-14/acceptance/diag_bug15_test_failure.log`.

| engine | `backtest.py` | result |
|---|---|---|
| corrected (Bug 17 fix) | `424ae4ef…` | 19 of 19 checks pass |
| engine of 10 November (Bug 16 version) | `fbf1e857…` | 19 of 19 checks pass |
| engine before the Bug 15 fix (`_archive/_backup_2026-11-10_before_bug15_fix/`) | — | 10 of 18 checks fail |

The unchanged test on the engine before the Bug 15 fix also fails 10 of 18. The changed fixture detects the
Bug 15 defect as before.

## 5. What this addendum changes in the pre-run note, and what it does not

- Test C, part 2 now reads: all 16 existing test files pass, `tests/test_bug15_sizing_lag.py` in the version
  `a8c00760…`. The stop of 14 November at the unchanged file stays on record and is reported in the results note
  and in `context/bugs.md`.
- Nothing else changes: the fix rule, the runtime assertions, tests D, A, B and E with their criteria and
  tolerances, the order of work, the specification of the correction run, the trial counts.
- Order from here: all test files, then D, A, B, E; if one fails, stop and report.
