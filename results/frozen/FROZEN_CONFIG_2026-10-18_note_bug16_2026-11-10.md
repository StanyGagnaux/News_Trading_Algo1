# Bug 16 — Strategy A never closes a position in a ticker that stops trading: fix rule, acceptance tests and disclosed correction run, dated 10 November 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written 2026-11-10 (Zurich) BEFORE any change to `src/` or `tests/` and before any run, by decision of the
author of the same day. Diagnosis and evidence, not edited:

    d6577a76ef9c333795c4442aac50d45d1f4e9e4143fd0e08ae7ce21854ff31fa  review_2026-11-10/BUG16_note_2026-11-10.md
    2d054c04da9a31b5fe7ec037e092f89b9420f26f3a723ebb307489f2b7a8bb14  review_2026-11-10/BUG16_addendum_1_test_period_2026-11-10.md

Results are not in this note; they follow in `…note_bug16_results_2026-11-10.md`.

## 1. Diagnosis (found 10 Nov 2026, after the freeze, in the course of the external review)

`src/newsdrift/backtest.py` (`50fc92f63f018e72132f4b836e9b641207cad90944a2147b500991cc4585a651`, the Bug 15
engine), `NewsDriftBacktest.run`: a held position whose ticker has no bar on day d is skipped in the exit loop
(l. 200) and left out of the mark-to-market (l. 220), while its notional keeps counting against the gross cap
(l. 270). A position opened in the last bars of a stock that stops trading (acquisitions) is never closed; its
full value leaves equity on the next trading day and no trade is booked. Always against the strategy; not a
look-ahead. Found while reconciling the exploratory Strategy F, whose first engine had the same defect.
Training, official dumps of the Bug 15 run: keyword 3 stuck positions (ATVI, ESRX, SPLK), Llama 5 (ESRX, MXIM, MYL,
SHPG, WFM), MiniLM 6 (the same and XLNX), Haiku and Sonnet none; 26% to 77% of a row's training loss, and about
half of the "five percent" drawdown of keyword fixed and Llama fixed. Test period: one position (MiniLM, ANSS).
Not caught earlier: every assertion and placebo worked on booked trades; nothing compared equity with them.

## 2. Fix rule

1. A held position is always **marked at its last available close**.
2. The holding period is counted on the **trading calendar** (every trading day counts, with or without a bar
   for the ticker). Stops and targets are checked only on days with a bar.
3. When the time exit falls on a day without a bar, the position **exits at its last available close** (exit
   cost applied, reason `stale`); the result is booked and reaches the sizer like any other trade.

Unchanged: signals, direction, entry, stop, target, fills (Bug 14 rule), costs, sizing inputs at the previous
close with their runtime assertions (Bug 15 rule), order of same-day signals, admission.

**Runtime check added:** every day, equity − initial equity = booked trade results + unrealised result of the
open positions (each marked at its last available close).

Files to be changed (backup `_archive/_backup_2026-11-10_before_bug16_fix/`): `src/newsdrift/backtest.py`
(`50fc92f6…`); new `tests/test_bug16_stopped_ticker.py`; new `src/bug16_report.py` (derived tables from stored
files, the rules of `bug15_report.py` with the Bug 15 A rows as "previous"); harness: new
`bughunt/bh_reconciliation.py`, `bh_A.py` (stale exits handled), `bug16_harness.*`. No option or default of any
runner changes. Interpreter: `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3`.

## 3. Acceptance tests (if any fails: stop, report, no run; no criterion is amended after its result)

**R. Reconciliation from dumps (the harness assertion).** For Strategy A, every trading day: equity − initial =
booked results (exit date ≤ d) + unrealised result of the positions opened (sizing log) and not yet exited,
marked at the last available close; tolerance 0.01 currency units. For Strategies B and minute-bar C (realised
daily equity): equity − initial = booked results with exit date ≤ d, every day. For momentum: the stored
continuous series equals an independent recomputation of weights × returns − turnover costs (daily returns
within 1e-9).

1. **Old logs fail on exactly the listed positions.** On the official dumps of the Bug 15 run, R must fail, and
   the positions never closed in tickers that end inside the period must be exactly — training: keyword {ATVI,
   ESRX, SPLK}; Llama {ESRX, MXIM, MYL, SHPG, WFM}; MiniLM {ESRX, MXIM, MYL, SHPG, WFM, XLNX}; Haiku, Sonnet none;
   test period: MiniLM {ANSS}, all other rows none (fixed and Kelly, 5% and 20% alike).
2. **Unit test** (`tests/test_bug16_stopped_ticker.py`): a ticker stops trading mid-holding; the position exits
   on its time-exit day at the last close, equity changes by the trade result only; a one-day gap in a ticker's
   bars; must FAIL on the code before the fix and PASS after. All 15 existing test files pass.
3. **Fixed engine, training period, at the Bug 15 scales** (ten configurations): R passes on every row with 0
   failing days; the positions of item 1 appear as booked `stale` trades; the Bug 15 strict assertion
   (`bh_bug15_sizing.py`) has 0 violations.
4. **B, minute-bar C and momentum pass R unchanged**, on the official dumps of 24/25 October (every rung, fixed
   and Kelly, both periods) and on the stored momentum series. Read only; these strategies are not rerun
   (momentum is recomputed for the check only).
5. **After the run:** R and the strict assertion on every official dump of the run (5% and 20%, both periods);
   a violation there voids the run.

## 4. Disclosed correction run (only if 1 to 4 pass)

As the Bug 15 run, Strategy A only, names `bug16fix_2026-11-10`, driver
`outputs/correction_bug16fix_2026-11-10/run.sh`: 5% recalibration on training (unchanged mechanical rule), one
run per rung, training + test, against the stored continuous momentum series of 24 Oct, N = 139 / 139 / 155 /
155 / 161; 20% recalibration and one run (N = 139 / 139 / 155 / 155 / 163). Derived tables from stored files
(`src/bug16_report.py`): forty configurations against momentum and recounts, Holm (same families), 20% summary,
yearly, correlations, rung comparisons, cost ladder, Llama and Haiku equity charts, old-against-new A rows
(previous = Bug 15 rows). Placebos on the new engine: fixed sizer; Kelly with random directions; Kelly with
common directions (criteria of the Bug 15 addendum). Harness rerun with R added for A, B, C and momentum.
Every run logged in `outputs/test_period_runs.csv`. B, C and momentum are not run.

## 5. Trial counts

Unchanged at **139 / 155 / 161 / 163**: the corrected configurations replace the earlier ones (precedents of
24 Oct and of the Bug 15 run). Counting them as new trials would be the stricter choice.

## 6. Superseded by this run (files stay in place)

Every `…_bug15fix_2026-11-10` Strategy A result file and the tables derived from them (A rows): results,
comparison, deflated-Sharpe sensitivity, calibrations (5% and 20%), `comparison_vs_continuous_momentum`, `holm`,
`sensitivity_dd20_summary`, yearly, correlations, `rung_comparisons`, `cost_ladder`, `a_rows_old_vs_new`,
`recounts`, the two equity charts, the placebo files. The acceptance tests and notes of Bug 15 stand.
