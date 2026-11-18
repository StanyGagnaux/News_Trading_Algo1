# Bug 17 — the entry step of Strategy A admits positions on the book as it stands after the day's exits: fix rule, acceptance tests and disclosed correction run, dated 14 November 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written 2026-11-14 (Zurich) BEFORE any change to `src/` or `tests/` and before any run, by decision of the
author of the same day. Diagnosis, rule, reference and order of work follow the specification, not edited:

    964ad2d408fcbfebc62439eea70e7d6cb8f6f7d51245d434f811943939fb7426  review_2026-11-14/BUG17_note_2026-11-14.md
    d56f09936cdb28ad2b512a0192cd0fe1f9e480924130dca8c8f889e9605754a0  review_2026-11-14/BUG17_reference_2026-11-14.md

Both hashes were verified on the files as read before this note was written. Where the two differ, the reference
governs (it corrects the note in two places: the description of scheduled exits, and the day selection of
test D). Results are not in this note; they follow in `…note_bug17_results_2026-11-14.md`.

## 1. Diagnosis (found after the freeze, in the course of the external review)

`src/newsdrift/backtest.py` (`fbf1e857928075c4afdfcc61ac6739685c9b1d5f9f4c86f0df909d98be5f7bbd`, the Bug 16
engine), `NewsDriftBacktest.run`. One iteration for date d runs: (1) exits of day d, which use day d's high, low
and close; (2) mark to market at the close of d; (3) entries at day d's open. Since Bug 15 the size of an entry
uses previous-close information only; its **admission** does not. Three places use the book as it stands after
step 1 and after the earlier entries of the same open were checked against the day's range:

- l. 251, `if s.ticker in open_pos`: a ticker held at the open of d and closed during d is entered again at the
  open of d;
- l. 286–287, `gross = sum(... open_pos ...)`: the gross-exposure cap is judged on the book after the day's exits;
- l. 303–307: an entry closed on its entry day never enters `open_pos` and does not count in `gross` for the later
  tickers of the same open.

Bug 17 is two things under one rule (reference, Section 3). In the official training runs of 10 November, 3.7 to
25.2 percent of the trades are entered on the exit day of the previous trade in the same ticker. Between 71 and 91
percent of these follow a **scheduled time exit**: no future information is used, but two positions are held in one
ticker from the open to the close of d, against the rule of one position per ticker, and the old one is left out
of the gross figure. The remaining 9 to 29 percent follow a **stop or a target hit during d**: there the admission
depends on the day's range and is a look-ahead in the strict sense (hard rule 1). Direction, entry price, stop,
target, size and exit of every admitted trade are correct; what is wrong is which trades are admitted.

Not caught earlier: the Bug 15 assertion covers the sizing inputs, not the book; the Bug 16 reconciliation holds
whatever is admitted; the placebos do not depend on which tickers are free. Disclosed, not corrected, on
10 November. Not affected: Strategies B and C (`portfolio.py` closes by timestamp before each admission), the
momentum benchmark, the event study, the exploratory Strategy F.

## 2. Fix rule (one rule: the book at the decision time)

The decision time of every entry of day d is before the open of d. The entry step receives a **snapshot of the
book taken at the close of d−1**, before step 1 of day d runs, and uses nothing else about the book:

1. **Eligibility.** A ticker with a position in the snapshot is not entered at the open of d, whatever happens to
   that position during d. It is eligible again from d+1 if it was closed on d.
2. **Gross exposure.** Gross = posted notional (shares × entry price) of all positions in the snapshot + notional
   of the entries already admitted at this open, whether or not they are still open at the close of d. The cap
   test is otherwise unchanged (`gross + notional > max_gross_exposure × sizing equity`).
3. Nothing else changes: order of same-day signals, noise gate, ATR, entry price, stop, target, size (Bug 15 rule),
   position cap, fills (Bug 14 rule), stale exits and reconciliation (Bug 16 rules), costs.

A position that gaps through its stop at the open of d is still in the snapshot. The arithmetic of the gross figure
follows the reference implementation (sum over the snapshot in book order, plus a running sum of the admitted
notionals).

**Runtime assertions added:** for every entry on d, (a) the ticker is not in the snapshot of the close of d−1;
(b) no trade in that ticker has been booked with exit date d before the entry is made; (c) the gross figure used
equals snapshot notional + notional admitted earlier at this open. **Sizing log:** new last column
`gross_at_decision` (the gross figure of the admission test; empty where a call is refused before that test).

Files to be changed (backup `_archive/_backup_2026-11-14_before_bug17_fix/`, `src/` and `tests/`):
`src/newsdrift/backtest.py`; new `tests/test_bug17_admission_snapshot.py`; new `src/bug17_report.py` (derived
tables from stored files, the rules of `bug16_report.py` with the Bug 16 A rows as "previous"); harness: new
`bughunt/bh_bug17_admission.py`, `bug17_harness.*`. No option or default of any runner changes. Interpreter:
`/Library/Frameworks/Python.framework/Versions/3.13/bin/python3`. Working folder
`outputs/correction_bug17fix_2026-11-14/`.

## 3. Acceptance tests, in this order (if one fails: stop, report, no test-period run; no criterion is amended after its result is seen)

"Engine of 10 November" = the backup of `src/` taken before the fix (`backtest.py` `fbf1e857…`). All pre-run
tests use the training period only (4 January 2016 to 29 April 2024) and the scales of
`risk_calibration_*_bug16fix_2026-11-10.csv`.

**C. Unit tests, synthetic data** (`tests/test_bug17_admission_snapshot.py`). Each of the three cases must FAIL on
the engine of 10 November and PASS on the new one:
1. a ticker is held; its target is hit on day d; a signal for the same ticker is effective d: no entry at d; with
   a further signal effective d+1: entry at d+1;
2. the book is at the gross cap at the close of d−1; one position is closed during d; a signal in another ticker
   is effective d: refused;
3. two signals at the same open; the first is admitted and stops out on its entry day; its notional still counts
   when the second is tested against the gross cap.
All 16 existing test files pass.

**D. Perturbation test on real data, training period** (corrected selection of the reference, Section 5). For each
selected day d the engine is rerun with the high, low and close of every ticker on day d replaced by its open
(data cut after d), and the positions opened on day d are compared with the unperturbed run: same tickers, same
directions, same shares, same entry prices, stops and targets (1e-9 relative). Configurations: keyword and Llama,
fixed and Kelly. Days per configuration: those of `review_2026-11-14/ref_out/reentries_after_stop_or_target_<rung>_<sizer>.csv`
(re-entry after a stop or target, engine of 10 November), up to 100 drawn with
`numpy.random.default_rng(20261024)`, then 50 drawn from all training days with the same generator (the
drawing code of the specification, `test_D_perturb.py`, with 100 and 50). Requirement, each of the four configurations:
the engine of 10 November differs on at least one selected day; the corrected engine on none. The test does not
detect the double position on scheduled exit days; that part is covered by B (1) and by case 1 of C.

**A. Cross-check against the reference.** The corrected engine, driven by the official pipeline
(`run_both_strategies.load_inputs`, `build_signal_table`, the designed governor), returns the ten training cells
of the reference, Section 4: return p.a., Sharpe and maximum drawdown to 1e-9, trades exact. Caution of the specification,
taken over: if only Haiku Kelly or Sonnet Kelly differ beyond 1e-9 while the other eight agree, the difference
and its cause are reported before proceeding; that alone is not a failed test.

**B. Strict assertion from the dumps**, independent of the engine's loop (new `bh_bug17_admission.py`):
(1) no trade's entry date equals the exit date of an earlier trade in the same ticker; (2) for every admitted
entry, notional of the positions open at the previous close + notional admitted earlier that day + its own
notional ≤ gross cap × equity of the previous close (1e-9 relative). Pre-run: (1) must FAIL on the ten official
training dumps of 10 November with exactly the counts of the reference, Section 6 — keyword 6,150; Llama 4,241;
MiniLM 5,351; Haiku 1,046; Sonnet 184 (fixed) and 183 (Kelly) — and both checks must show 0 violations on the
ten training dumps of the corrected engine (test A). Post-run: every dump of the correction run, both periods,
5 and 20 percent; a violation voids the run.

**E. Everything that passed on 10 November still passes** on the corrected engine: the Bug 15 strict assertion
(`bh_bug15_sizing.py`) and the Bug 16 reconciliation (`bh_reconciliation.py`) on the ten training dumps of test A,
0 violations and 0 failing days; the three placebos on the training period, keyword signals, criteria unchanged
(fixed sizer at the 18 Oct scale: criterion (i) within 2 SE; Kelly with random directions, seed 20261024, at the
Bug 16 Kelly scale: (i) and (ii); common direction, all long and all short: excess within +2 clustered SE); all
test files. After the run: the same three placebos as official files at the recalibrated keyword Kelly scale
(a failure there is reported and voids the run), and the harness of 8 November.

## 4. Disclosed correction run (only if C, D, A, B and E pass)

As the Bug 15 and Bug 16 runs, Strategy A only, names `bug17fix_2026-11-14`, driver
`outputs/correction_bug17fix_2026-11-14/run.sh`: 5% recalibration on training (unchanged mechanical rule), one
run per rung, training + test, against the stored continuous momentum series of 24 Oct, N = 139 / 139 / 155 /
155 / 161; 20% recalibration and one run (N = 139 / 139 / 155 / 155 / 163). Derived tables from stored files
(`src/bug17_report.py`): forty configurations against momentum and recounts, Holm (same families), 20% summary,
yearly, correlations, rung comparisons, cost ladder, Llama and Haiku equity charts, old-against-new A rows
(previous = Bug 16 rows). Hash register `FROZEN_RUN_outputs_hashes_bug17fix_2026-11-14.txt`. Dated notes
appended to `context/bugs.md` and `context/results.md` (nothing above is edited). Every run logged in
`outputs/test_period_runs.csv`. B, C and momentum are not run. The fixed-size rows move as well, because
admission does not depend on the sizer. One run; every result reported regardless of outcome.

## 5. Trial counts

Unchanged at **139 / 155 / 161 / 163** (the exploratory Strategy F is trial 164), as the author has decided so
far: the corrected configurations replace the earlier ones (precedents of 24 Oct and of the Bug 15 and Bug 16
runs). Counting the reruns as new trials would be the stricter choice; the decision is the author's.

## 6. Superseded by this run (files stay in place)

Every `…_bug16fix_2026-11-10` Strategy A result file and the tables derived from them (A rows): results,
comparison, deflated-Sharpe sensitivity, calibrations (5% and 20%), `comparison_vs_continuous_momentum`, `holm`,
`sensitivity_dd20_summary`, yearly, correlations, `rung_comparisons`, `cost_ladder`, `a_rows_old_vs_new`,
`recounts`, the two equity charts, the placebo files. The acceptance tests and notes of Bugs 15 and 16 stand.
