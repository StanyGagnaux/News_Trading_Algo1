# Changelog

Newest first. Bug details in `bugs.md`; results in `results.md`.

## 2026-11-14 (evening) — order robustness rerun on the Bug 17 engine (training, descriptive); `github_release/` rebuilt
- New `src/order_robustness_bug17fix_2026-11-14.py`, a dated copy of `src/order_robustness.py` (not run; the
  official `order_robustness_2026-10-19.csv`, cb2a6d4a…, is unchanged). A at the Bug 17 scales read from
  `for_claude/`; B, C, D at the 18 Oct scale files the October run read (hashes pinned in the script). Output
  `for_claude/order_robustness_bug17fix_2026-11-14.csv` (efc2d079…), log and note beside it.
- Standard deviation of the training Sharpe ratio over 20 orderings, A: keyword fixed 0.000 (Oct 0.000), keyword
  Kelly 0.038 (0.090), Llama fixed 0.000 (0.000), Llama Kelly 0.029 (0.041). Control on the engine before the
  Bug 17 fix: the 13 B, C, D rows are identical (difference 0.0). Against October: D identical; B and C differ,
  because `intraday.py`, `risk.py` and `strategy_c.py` were changed on 24 Oct (Bugs 13, 14) after the October check.
- Record: appended line in `results.md`; row in `for_claude/README.md`; file, log and note added to the Bug 17
  register; the three registers regenerated (digests in
  `outputs/correction_bug17fix_2026-11-14/REGISTER_DIGESTS_2026-11-14.txt`).
- `github_release/` rebuilt with the Bug 17 engine and all 17 test files (16 earlier files, one of them with the
  approved fixture change, plus `test_bug17_admission_snapshot.py`). Allow-list of `src/make_github_release.py`
  extended: the `…_bug17fix_2026-11-14` tables and charts (current), the new robustness file, the clustering
  table; the Bug 16 folder stays as a record.
- `github_release/` FINISHED (same evening, on the author's instructions): the body of `github_README.md`
  rewritten to the current state (the dated note at its top removed; test-period table of all forty
  configurations; table of the official files; superseded files named; Bugs 10 to 17 with their correction runs;
  17 test files; warning never to run `src/order_robustness.py`; Haiku and Sonnet described as released after the
  end of the sample). Allow-list extended by the official B and C files, new folder
  `results/strategies_B_C_2026-10-24_25/` (52 files): B rows in `…_calibrated_bug14fix_2026-10-24*` (keyword,
  Llama, MiniLM) and `…_calibrated_2026-10-25*` (Haiku, Sonnet), minute-bar C in `…_cminute_2026-10-24*` /
  `…_cminute_2026-10-25*`, their calibrations, the two C summaries and the charts; the A rows inside these files
  are superseded by the run of 14 Nov. Final build: 400 files (396 copied, three generated, the build marker),
  safety checks passed, engine `424ae4ef…`. Registers regenerated once more; digests in
  `outputs/correction_bug17fix_2026-11-14/REGISTER_DIGESTS_2026-11-14.txt`.
- **Project closed for changes on 14 Nov 2026 (author's decision), except the author's own edits to the thesis.**

## 2026-11-14 (later) — Bug 17 correction run COMPLETED: all ten Strategy A rows superseded
- Author's decision after the stop at test C: `tests/test_bug15_sizing_lag.py`, section 2 fixture, gets room under
  the gross cap (`max_gross_exposure=2.0` in `fixed_case`; 93427590… → a8c00760…). Addendum
  `outputs/FROZEN_CONFIG_2026-10-18_note_bug17_addendum_testC_2026-11-14.md` (705714f1…) written and registered
  before the tests continued. Changed test: 19/19 on the corrected engine and on the engine of 10 Nov, 10 of 18
  fail on the engine before the Bug 15 fix.
- Acceptance, all passed before the run: C 17 of 17 test files; D perturbation test, old engine differs on 31 of
  150 days (keyword) and 55 of 150 (Llama), corrected engine on 0 of 600; A the ten reference cells of the reviewer
  with a difference of exactly 0; B the old training logs fail with exactly the reviewer's counts, the corrected
  ones show 0; E Bug 15 strict assertion, reconciliation and three placebos pass. The first version of the B
  checker compared the wrong count (all opened positions instead of trades) and was corrected before the run;
  first output kept.
- Run (`outputs/correction_bug17fix_2026-11-14/run.sh`; only A; one run): recalibration at 5% and 20%, ten
  configurations. 13% to 23% fewer trades in the free rungs; scales of the free rungs up by a fifth to two thirds.
  Test-period Sharpe ratios move by −0.09 to +0.65: **Llama A Kelly 1.08 → 1.30** (+1.8% p.a., DSR(139) 0.20, vs
  momentum +0.56 ± 0.96, p 0.56; training −0.44 → −0.09), Llama fixed −0.12 → +0.01, Haiku Kelly −1.55 → −0.90,
  MiniLM Kelly −1.18 → −0.79, keyword Kelly −1.36 → −1.45. **35 of 40 lose (was 36), 22 significantly worse than
  momentum (was 24).** 20%: four rows material (was one); two Kelly calibrations did not converge (Haiku 14.9%,
  Sonnet 17.5% training drawdown). Trial counts unchanged (139/155/161/163).
- After the run: admission assertion 80 of 80, Bug 15 strict assertion 80 of 80, reconciliation 40 of 40, three
  placebos pass; harness 204 of 204 files, 17 of 17 test files, 461 assertions, 457 pass (four calibration-band
  findings). New: `src/bug17_report.py`, `bughunt/bh_bug17_admission.py`, `scripts/bug17_harness.*`.
- Files: `outputs/*bug17fix_2026-11-14*`; notes, result files and harness files in `for_claude/`; hashes
  `FROZEN_RUN_outputs_hashes_bug17fix_2026-11-14.txt`; the Bug 15 and Bug 16 registers regenerated so that every
  line verifies (digests before and after: `outputs/correction_bug17fix_2026-11-14/REGISTER_DIGESTS_2026-11-14.txt`);
  the `…_bug16fix_…` A files marked superseded in `for_claude/README.md`. `bugs.md` and `results.md`: appended
  sections. `CLAUDE.md`, `for_claude/` copies synced. `github_release/` NOT rebuilt (open).

## 2026-11-14 — Bug 17 (Strategy A admits entries on the book after the day's exits): fix in `src/`, correction STOPPED at acceptance test C; clustering table; register digest confirmed
- Reviewer's note and reference (`review_2026-11-14/BUG17_note_2026-11-14.md`, 964ad2d4…;
  `BUG17_reference_2026-11-14.md`, d56f0993…), hashes verified. Bug 17: the entry step read `open_pos` after the
  day's exits, so a ticker closed during day d was entered again at the open of d (3.7 to 25.2% of the training
  trades of 10 Nov; 71 to 91% of these after a scheduled time exit = a double position, the rest after a stop or
  target = look-ahead in admission), and the gross cap was judged on the book after the exits.
- Pre-run note `outputs/FROZEN_CONFIG_2026-10-18_note_bug17_2026-11-14.md` (e96e94d7…, registered before any
  change). Backup `_archive/_backup_2026-11-14_before_bug17_fix/`.
- Fix in `src/newsdrift/backtest.py` (fbf1e857… → 424ae4ef…): admission on a snapshot of the book at the close of
  d−1 plus the entries of this open; three runtime assertions; sizing-log column `gross_at_decision`. New
  `tests/test_bug17_admission_snapshot.py` (13 checks; the engine of 10 Nov fails each of its three cases).
- **STOPPED at test C:** 15 of the 16 existing test files pass; `tests/test_bug15_sizing_lag.py` fails in section 2
  because its fixture relies on capacity freed during day d (five positions, 87,531 notional, all closed on d; the
  entry of d needs 17,506 more against a cap of 100,000). Not a violation of the Bug 15 rule. Record and the
  decision needed: `outputs/correction_bug17fix_2026-11-14/STOP_at_test_C_2026-11-14.md`. Tests D, A, B, E, the
  recalibration and the run were NOT started; no test-period run; no criterion amended. **`src/` now holds an
  engine (424ae4ef…) that is not the one behind the official `…_bug16fix_2026-11-10` results (fbf1e857…).**
- Descriptive, training only: new `src/descriptive_event_study_clustering.py` →
  `outputs/descriptive_event_study_clustering_train_2026-11-14.csv` (39dfb338…, copy in `for_claude/`): event-study
  standard errors clustered by entry date, ISO week and month. The eight official cells are reproduced; all eight
  upper bounds stay below 4.86 bps; keyword day 5 standard error +25.2% by week; bounds below zero: 5 / 3 / 4.
  Appended section in `results.md`.
- Register digest confirmed: `FROZEN_RUN_outputs_hashes_bug16fix_2026-11-10.txt` was written at 20:21:10 on 10 Nov
  (73ca5f4b…) and rewritten at 20:51:29 (1ca08a7a…) when the Strategy F run was recorded; 6 of its 56 lines changed
  (`results.md`, `changelog.md`, `current_state.md`, `CLAUDE.md`, `test_period_runs.csv`, the Bug 15 register); both
  digests were rebuilt exactly from the files. No result file changed.
- Not synced on purpose until the run is completed: the `for_claude/` copies of `results.md` and `changelog.md`,
  `for_claude/README.md`, the hash registers, `github_release/`. One line of the Bug 15 and Bug 16 registers
  (`FROZEN_CONFIG_hashes_notes_2026-10-19.txt`) no longer verifies, because the Bug 17 note was registered.

## 2026-11-10 (night) — EXPLORATORY Strategy F (news fade): training run and one test-period run recorded
- Strategy F (fade keyword corporate-event headlines, 3-day hold, index hedge) lives only in
  `review_2026-11-10/exploration/fade/` on a copy of `src/`; nothing in `src/` was changed for it. Training run
  first (Sharpe 0.24 at 5%); its reconciliation against the trade log is what found Bug 16.
- Test period run ONCE on the author's instruction (pre-run note `FADE_note_test_2026-11-10.md`, a472af76…): 5%
  scale +3.61% p.a., Sharpe 1.11, +30.2 bps per trade (clustered t 2.09); vs momentum +0.38 ± 0.98 (p 0.70);
  DSR(164) 0.13. Not blind (the subgroup's test-period reversal was known), concentrated in a few trades;
  exploratory, not a confirmed finding. Trial 164.
- Recorded on the author's instruction: row 38 of `outputs/test_period_runs.csv`, appended section in
  `context/results.md`, `CLAUDE.md` (exploratory bullet); `for_claude/` copies and hash registers refreshed;
  `github_release/` rebuilt. The F files themselves are not in `for_claude/` or the release.

## 2026-11-10 (evening) — Bug 16 (Strategy A never closed a position in a ticker that stops trading): fix and correction run; all ten Strategy A rows superseded again
- Found by the external review after the freeze (`review_2026-11-10/BUG16_note_2026-11-10.md`, d6577a76…;
  addendum 1 on the test period, 2d054c04…), while the exploratory Strategy F was reconciled against its trade log.
  A skipped a ticker without a bar in the exit loop and in the mark to market: the position was never closed and
  its margin vanished from equity (training: WFM, SPLK, ATVI, MXIM, SHPG, ESRX, MYL, XLNX; test: ANSS, MiniLM);
  a one-day gap in the price file made a one-day hole in equity (BIIB, DXCM).
- Pre-run note `outputs/FROZEN_CONFIG_2026-10-18_note_bug16_2026-11-10.md` (c17fce3f…, registered before the run);
  results note `…_note_bug16_results_2026-11-10.md` (7e896671…).
- Fix in `src/newsdrift/backtest.py` (50fc92f6… → fbf1e857…; backup
  `_archive/_backup_2026-11-10_before_bug16_fix/`): mark at the last available close, holding days on the trading
  calendar, exit at the last close when the exit day has no bar (reason `stale`); runtime assertion equity − initial
  = booked results + unrealised result of open positions, every day. New `tests/test_bug16_stopped_ticker.py`
  (9 checks; old engine fails 5 of 6); 16 test files pass. New harness assertion
  `exploratory_B_exit/verification/scripts/bughunt/bh_reconciliation.py` (A, B, minute-bar C, momentum).
- Acceptance, all passed before the run: the Bug 15 logs fail the reconciliation on exactly the listed positions
  (40 of 40 as expected); fixed engine 10 of 10; strict Bug 15 assertion 20 of 20; B 40 of 40, C 20 of 20,
  momentum 5.5e-16.
- Run (`outputs/correction_bug16fix_2026-11-10/run.sh`; only A; one run): recalibration at 5% and 20%, ten
  configurations. Test-period Sharpe ratios move by at most 0.013 (MiniLM fixed −2.18 → −2.10); Llama A Kelly
  stays 1.08 (+1.0% p.a., DSR(139) 0.13, vs momentum +0.34 ± 0.95, p 0.72), training −0.54 → −0.44; fixed scales
  of keyword and Llama about double (0.0041 → 0.0079, 0.0072 → 0.0145), so their test returns and drawdowns
  double. 36 of 40 lose, 24 significantly worse than momentum: unchanged. Trial counts unchanged
  (139/155/161/163).
- After the run: reconciliation 40 of 40, strict assertion 80 of 80, three placebos pass (fixed 0.48 SE; Kelly
  random; common direction +2.66 / −1.77 bps, 0.53 / −0.28 clustered SE); harness 204 of 204 files, 381 assertions,
  378 pass (the three known calibration findings).
- Files: `outputs/*bug16fix_2026-11-10*` (derived tables by the new `src/bug16_report.py`); 42 result files, two
  notes and three harness files in `for_claude/`; hashes `FROZEN_RUN_outputs_hashes_bug16fix_2026-11-10.txt`; the
  `…_bug15fix_…` A files marked superseded in `for_claude/README.md`. `bugs.md` and `results.md`: dated sections
  appended, nothing edited. 7 rows added to `outputs/test_period_runs.csv`.
- Housekeeping done: `CLAUDE.md` updated; `for_claude/changelog.md`, `current_state.md` and `CLAUDE.md` replaced
  by current copies (previous versions in `outputs/correction_bug16fix_2026-11-10/`); `github_release/` rebuilt
  with `src/make_github_release.py` (allow-list extended by the `*bug16fix_2026-11-10*` tables and charts, changed
  after the harness run; dated note at the top of `github_README.md`, whose body is still the 18 Oct text).
- Not done: B, C, momentum and the event study were not rerun (reconciled only); the corrected B/C files of 24/25
  Oct are not in the release allow-list; the thesis text (Thesis_v14) is not touched.

## 2026-11-10 (later) — Bug 15 correction run COMPLETED: all ten Strategy A rows superseded
- Author's decision on test D: the reviewer's common-direction placebo (test D2). Addendum
  `outputs/FROZEN_CONFIG_2026-10-18_note_bug15_addendum_testD2_2026-11-10.md` (e1532c0f…, registered before any D2
  run). `placebo_a.py --directions random|long|short` (default unchanged). D2 met: new code +1.72 bps (0.33
  clustered SE) long, −2.21 (−0.34) short; code before the fix +37.07 (7.77), +42.21 (6.93); equal to the
  reviewer's reference to 2e-14.
- Single run, Strategy A only (`outputs/correction_bug15fix_2026-11-10/run.sh run05`, `cal20`, `run20`), against the
  stored continuous momentum series; B, C and momentum not run. Test Sharpe old → new at 5%: keyword Kelly 0.03 →
  −1.36, Llama Kelly 0.75 → 1.08 (training +0.24 → −0.54; vs momentum +0.34 ± 0.95, p 0.72; DSR 0.13), MiniLM
  −0.63 → −1.19, Haiku −1.21 → −1.55, Sonnet −0.93 → −1.39; fixed rows within 0.002. 36 of 40 configurations lose
  (was 35), 24 significantly worse than momentum (was 22). Trial counts unchanged 139/155/161/163.
- Strict sizing assertion on every official dump: 0 violations in 474,557 trades. A placebo (fixed sizer) rerun
  unchanged. Harness of 8 Nov rerun in `exploratory_B_exit/verification/sandbox_bug15_2026-11-10/`: 204/204 files,
  15/15 tests, 268/272 assertions (4 calibration-bookkeeping failures, no number changes).
- New: `src/bug15_report.py` (derived tables from stored files), results note `…note_bug15_results_2026-11-10.md`
  (462fe412…), 60 files hashed in `for_claude/FROZEN_RUN_outputs_hashes_bug15fix_2026-11-10.txt`. Dated notes
  APPENDED to `bugs.md` and `results.md` (Bug 15 + corrections of earlier sentences); nothing edited.
- Later the same day, on the author's instruction: root `CLAUDE.md` updated (current state, last-updated line,
  test count, bug count, next steps); `for_claude/README.md`: the 24/25 Oct Strategy A files marked SUPERSEDED
  (Bug 15) in their status cells, 17 rows added for the new files, banner on the key-numbers section (previous
  version kept in `outputs/correction_bug15fix_2026-11-10/`); hash register regenerated with `README.md`.
- Still not updated: `for_claude/changelog.md`, `for_claude/current_state.md`, `for_claude/CLAUDE.md`,
  `github_release/`.

## 2026-11-10 — Bug 15 (same-day information in Strategy A's sizing): fix in `src/`, correction run STOPPED at acceptance test D
- Found by the reviewer's code review (`review_2026-11-10/BUG15_note_2026-11-10.md`, handoff `…decisions_and_handoff…`):
  a position opened at the open of day d was sized with the Kelly window, equity and governor throttle of day d's close.
- Pre-run note `outputs/FROZEN_CONFIG_2026-10-18_note_bug15_2026-11-10.md` (7a66229b…, in the hash register; copy in
  `for_claude/`), written before any change. Backup `_archive/_backup_2026-11-10_before_bug15_fix/`.
- Fix in `newsdrift/backtest.py` (db6d438f… -> 50fc92f6…), reference variant V2: all sizing inputs at the previous
  close; runtime assertions; per-call sizing log. Additive options, defaults unchanged: `run_both_strategies.py`
  `--only-a`, `--benchmark-equity`; `calibrate_risk.py` `--only-a`; `placebo_a.py` `--sizer`, `--scales`, `--out`.
  New `tests/test_bug15_sizing_lag.py` (19 checks; the old code fails 10) — 15 test files pass.
- Acceptance tests, TRAINING ONLY: A (ten cells at the old scales = reference V2, difference 0.0), B pre-run part
  (0 violations in 168,703 sizing calls; the independent check fails on the old dumps), C, E (SRC = V2) PASS.
  A scales recalibrated on training (`outputs/risk_calibration_<rung>_bug15fix_2026-11-10.csv`).
- **Test D (Kelly placebo, random directions): the fixed code passes (i) 0.48 SE and (ii) −0.54 SE, but the code of
  10 Nov does NOT fail (ii) (−0.81 SE), which the handoff required.** Random directions remove the common direction
  through which the bug earns (predicted in the note before the test). Per the author's instruction the procedure
  stopped: **no test-period run, no result file changed; every official A row is still from the code of 24/25 Oct
  while `src/` holds the fixed engine.** Report and options:
  `outputs/correction_bug15fix_2026-11-10/ACCEPTANCE_TESTS_bug15_2026-11-10.md`. `bugs.md` and `results.md` not yet
  touched (notes follow the run).

## 2026-10-30 (later) — item 2 recomputed vs continuous momentum; CLAUDE.md reworded
- `src/descriptive_correlations_contmom.py` -> `outputs/descriptive_correlations_contmom_2026-10-30.csv`
  (descriptive, read-only inputs; old `…bug14fix_2026-10-24.csv` kept): daily-return
  correlation of corrected A/B and minute-bar C, five rungs, with the continuous
  benchmark, training and test; logged in `descriptive_runs.csv` (2-rerun).
- `CLAUDE.md` system-layers line: paper trading cancelled 30 Oct (dated note); no logger.

## 2026-10-30 — paper trading cancelled; shadow run empty; parity test not performable
- Decision note `…note_paper_trading_cancelled_2026-10-30.md` (SHA-256 in
  `FROZEN_CONFIG_hashes_notes_2026-10-19.txt`): cancelled 30 Oct before any
  order; no order code, no paper-trading data; latency measured only to the score.
- Shadow run 26–27 Oct (PID 34811): `time.sleep` did not advance while the Mac
  slept; the process woke 30 Oct 03:46 UTC, closed 26 Oct with 0 items, skipped
  27 Oct. `outputs/live/` empty, cache unchanged. Parity test (item 6d) has no
  live side: NOT RUN; historical side not fetched. `outputs/parity_report_2026-10-30.md`;
  complete log copied to `outputs/logs/`. No code changed (freeze).

## 2026-10-26 — duration split of the Haiku / Sonnet event studies extracted (read-only)
- The frozen "2 vs not 2" split was part of the 25 Oct rung 2/3 event-study
  runs; post-entry cells by duration, period and model (NDX-adj., t, N) now
  tabulated in `results.md`. No run; files unchanged.

## 2026-10-26 — duration-output shares for Haiku and Sonnet (read-only)
- Computed from the existing training score files (scored headline-ticker rows,
  the basis of Llama's 5.7% / 94.3% / 0.0%): Haiku 5.5 49.9% / 47.6% / 2.5%
  (n 59,999), Sonnet 5.5 61.6% / 37.7% / 0.8% (n 60,229); test rows and
  distinct-text bases in `results.md` (Rung 2 / Rung 3 sections). No re-scoring.

## 2026-10-25 (night, audit) — Tier-0 pre-filter reconciliation recorded (read-only)
- `for_claude/data_description_2026-10-25.md` §5: the two circulating counts
  have different bases — 62,212 distinct headline texts passing `tier0_keep`
  (22.0% of 282,292; 57,665 template representatives scored; 2015-09-15 ->
  2026-06-01) vs 64,352 distinct (timestamp, headline) pairs with an LLM score
  (2016-01-01 -> 2026-06-01). Same 92,737 rows; every pre-filtered pair is
  scored and nothing else is.
- Descent check on `news_scored_llm_ollama_anon_incl_test.csv`: 92,737 of
  92,737 rows have a text in the filtered set; 0 rows from outside the filter,
  0 from the stray unprefixed cache key (matches no clean headline), 0 strength
  mismatches against the template representative's cached score. No code or
  data changed; README row and copies updated.

## 2026-10-25 (night) — 20% drawdown sensitivity analysis done (descriptive)
- Additive options `--target-dd`, `--dd-cap`, `--dd-throttle-start`; cap-day
  counters in `backtest.py` / `portfolio.py` (no trade changes; all tests pass;
  all five 5% repeats reproduce the official results exactly).
- `outputs/sensitivity_dd20_2026-10-25/run.sh`, `src/sensitivity_dd20.py` ->
  `outputs/sensitivity_dd20_summary_2026-10-25.csv`. Momentum 20%: +4.5%, 0.71;
  news strategies lose; 12/40 material Sharpe changes explained (CAGR-based
  Sharpe for fixed B; caps binding under Kelly).

## 2026-10-25 (night, audit) — B placebo; data description; small items
- Note `…note_placebo_b_2026-10-25.md` (f0e695ce…) before the run; `src/placebo_b.py`:
  B PASSED (t+5 1.76 SE, t+15 0.55 SE).
- `for_claude/data_description_2026-10-25.md`: sourced figures (raw/clean news,
  duplicates, trading-hours shares on both bases, minute bars, coverage by
  horizon, half-spread percentiles, price rows, factor checksums).
- 1(b) momentum row rerun with the continuous benchmark (descriptive); FF6
  event-count difference explained (counting definition + late-scored rows);
  Fama-French download date and checksums reported (zips and extracted CSVs).
- Corrected-run equity PNGs copied to for_claude/.

## 2026-10-25 (night, later) — Llama latency measured (Ollama back online)
- `src/llama_latency.py`: 200 real-time calls, same prompt/model/call/parser:
  median 1.57 s, p90 1.67 s, 200/200 parsed, sign agreement with stored scores
  93.5%. Cost ladder rebuilt with the measured values (rung comparisons unchanged).
- 20% drawdown sensitivity analysis running (note `…note_sensitivity_dd20_2026-10-25.md`).

## 2026-10-25 (night) — Phase 4: cost ladder
- Check: rung-3 note complete except a cutoff source -> record note
  `…note_rung3_cutoff_record_2026-10-25.md` (4a6c8f08…; written after the run,
  not a pre-registration): no cutoff in the API metadata, release 2026-09-28,
  treated as exposed to look-ahead. C for Haiku/Sonnet already run.
- `src/cost_ladder.py` -> `outputs/cost_ladder_2026-10-25.csv` (5 rungs) and
  `outputs/rung_comparisons_2026-10-25.csv`.
- **The rung comparisons (A Kelly Sharpe differences, news-day mean
  differences between adjacent rungs) were added AFTER the results and are
  DESCRIPTIVE, not pre-registered.** Per-rung test news-day means reproduce
  the official event-study files exactly.

## 2026-10-25 (evening, later) — C for rungs 2/3 done
- Delta fetch 173 ticker-days / 21 ranges (19:23); C runs Haiku and Sonnet
  (`outputs/c_minute_rungs23_2026-10-25/`), report `src/c_minute_rungs23_report.py`:
  A/B reproduced; best C = Haiku Kelly +2.7% / 0.76, level with momentum.

## 2026-10-25 (evening) — Rung 3: Claude Sonnet 5.5; C for rungs 2/3 started
- Notes: `…note_rung3_sonnet_2026-10-25.md` (133bec5e…), amendment ($60 hard
  stop, 36f6421b… — the first attempt stopped at the worst-case check, nothing
  spent), `…note_c_minute_rungs2_3_2026-10-25.md` (b8514c22…).
- `haiku_batch.py` generalised (`BatchModel`; Sonnet: 5,000-request batches,
  guard tested offline); extras / report take `--rung`; Haiku outputs reproduce.
- Sonnet: 57,637 scored, $28.14 + $1.16 extras; A and B lose in test; no drift;
  test +30-min speed-bound cell +10.5 bps not replicated in training.
- `fetch_c_hold_bars.py --plan-delta` / `--ranges`; `src/c_minute_rungs23_report.py`;
  driver `outputs/c_minute_rungs23_2026-10-25/run.sh` running (delta fetch, then C).

## 2026-10-25 (afternoon) — Phase 3: rung 2 (Claude Haiku 5.5)
- `ANTHROPIC_API_KEY` stored only in `.env` (to be rotated: it was pasted in chat).
- `score_news_llm.py`: provider `haiku` (Message Batches branch, `_anonymize`
  helper shared with the Llama path); `src/haiku_batch.py` (token-count
  estimate, $30 cap check, chunked batches, one identical retry, usage log).
  Cache backed up first (`llm_score_cache_snapshot_2026-10-25_before_haiku.json`).
- Scored 57,411 / 57,665 for $2.16; extras (`src/rung2_haiku_extras.py`):
  memorisation corr 0.86, latency median 0.94 s, $0.09.
- Downstream (`outputs/rung2_2026-10-25/run.sh`, `src/rung2_report.py`):
  frozen event study, speed bound (stamp 2026-10-25, existing files untouched),
  A/B calibrated on training, one run, N = 155, vs continuous momentum, Holm 3.
  Result: no drift, A and B lose, A worse than momentum. Exposed to look-ahead.

## 2026-10-25 — Strategy C reopened once, minute-bar only
- Note `…note_c_minute_2026-10-24.md` (281afbb2…) before any fetch or change:
  one placebo criterion for all engines (mean only; harmonisation decided after
  C's result, disclosed); C1 unaffected; refetch for C only (reverses the
  no-refetch choice); minute-only spec; one attempt; deadline 28 Oct.
- `src/fetch_c_hold_bars.py`: full-session IEX bars for every C hold day,
  7,173 ranges (2020-07-27 ->), `data_sources/bars_c_hold.csv`; finished 24 Oct
  23:36. `bars_intraday.csv` untouched.
- `src/newsdrift/strategy_c_minute.py` + `tests/test_c_minute.py` (11 checks);
  `--c-engine minute` in `run_both_strategies.py` / `calibrate_risk.py`;
  `placebo_c.py --variant Cmin`. Placebo PASSED (−0.09 SE; long−short t 12.4).
- Runs (`outputs/c_minute_2026-10-24/run.sh`), report `src/c_minute_report.py`
  -> `outputs/c_minute_summary_2026-10-24.csv`: C does not beat continuous
  momentum (best LLM Kelly Sharpe 0.42, −0.29 ± 0.96); keyword and rung 1b lose.
  A/B identical to the Bug 14 correction.

## 2026-10-24 (after final) — momentum benchmark corrected
- Note `…note_momentum_2026-10-24.md` (5b6c210b…) before any change.
- `baseline.momentum_backtest(..., risk_scale=1.0)` additive; `src/momentum_continuous.py`:
  continuous momentum from 2015-01-07 (truncation check: no look-ahead); scaled
  k = 0.726 by the 5% training rule (mean/std Sharpe identical, checked);
  Sharpe difference vs momentum rerun for corrected A/B, three rungs (old
  benchmark reproduces the earlier comparison exactly).
- Result: continuous momentum test Sharpe 0.72 (per-period 1.08 overstated it;
  the earlier "understates" reading was wrong); LLM A Kelly vs momentum +0.02
  ± 0.95 (p 0.98). Earlier strategy-vs-momentum rows superseded. Drift between
  rebalances and the 5-day rebalance recorded as disclosed limitations.

## 2026-10-24 (final) — momentum check; official intraday number
- Momentum code review: spec matched (90/5, 20-day vol, weekly, one-day lag,
  turnover costs); deviations recorded in `bugs.md` (per-name vol /193 ->
  2–3% realised; 90-day flat warm-up in the test period, Sharpe 1.07 vs 1.18;
  drift not costed). Not changed.
- `baseline.py`: weight construction moved into `momentum_weights(close, mcfg,
  direction=None)` (backup `_archive/_backup_2026-10-24_before_momentum_placebo/`);
  `momentum_backtest` reproduces the archived engine exactly; all tests pass.
- `src/placebo_momentum.py` (training, seed 20261024): net −0.198 vs cost
  −0.180 bps/day (−0.15 SE); long−short +0.8 bps/day (t 1.2).
- Membership addendum `…note_membership_addendum_2026-10-24.md` (e9d8f375…):
  the universe look-ahead likely favours momentum more than the news strategies.
- `results.md`: official intraday timing figure = full sample, headline ->
  +30 min +0.0 bps (t 0.0, N 11,308); pre-news ≈ +12 bps; +2.9 = 7,054-event sub-sample.

## 2026-10-24 (end of day) — intraday reconciliation; rung 2 note
- `src/reconcile_intraday.py` (training, descriptive): the 18 Oct intraday
  +2.9 bps (headline -> +30 min, LLM) and the speed bound's +0.02 share events,
  price convention (bar ending at or before) and raw returns; they differ by
  sample (common −30/+30/+60/close vs +30 available; ~2.7 bps) and LLM file
  version (pre-gap vs current; ~0.2 bps). Both published cells reproduced.
  Thesis number: +0.0 bps (t 0.0, N 11,308). Note: the speed bound's LLM
  training maximum is +1.5 bps at +15 min (t 1.2), not +0.4.
- Rung 2 note `…note_rung2_2026-10-24.md` (d6328fcb…) before any run: corrected
  engine (Bug 14), A and B only, C and C1 excluded, training risk scales by the
  same rule, N = 155, Holm family of 3.
- Nothing else until the shadow run (Mon 26 Oct, 14:30 CET).

## 2026-10-24 (late night) — C1 decision; A/B correction run (Bug 14)
- Note `…note_c1_and_ab_correction_2026-10-24.md` (24a9940a…) before the run:
  C1 not validated (criterion not amended); A placebo long−short (t 3.9)
  consistent with the membership limitation; scope A and B only.
- Additive options: `run_both_strategies.py --skip-c --out-name --dump-dir`,
  `calibrate_risk.py --skip-c --out`; defaults unchanged.
- Recalibrated scales `outputs/risk_calibration_{keyword,llm,embed_minilm}_bug14fix_2026-10-24.csv`;
  runs `results_both_strategies_*_calibrated_bug14fix_2026-10-24*`; trade logs and
  equity in `outputs/correction_bug14fix_2026-10-24/`; driver `run.sh` there.
- `src/correction_report.py`: Holm (family 6 + rung 1b family 3), descriptive
  1(b) yearly performance and 2 correlations.
- Result: LLM A Kelly test +1.4% p.a., Sharpe 0.75 (was 1.80), vs momentum
  −0.32 ± 0.96; no news strategy beats momentum. 18 Oct A/B rows superseded.

## 2026-10-24 (night) — Bug 14 fix; placebos (A passed, C1 failed, stopped); membership note
- Note `…note_bug14_2026-10-24.md` (5f2ce391…) before any change. Shared fill
  rule `risk.barrier_exit` in A (`backtest.py`, entry day checked), B
  (`intraday.py`, entry bar + scale-out), C/C1 (`strategy_c.py`),
  `standalone.py`. Test `tests/test_bug14_fills.py` (15 checks); all tests pass.
- Placebos, training: `src/placebo_a.py` -> A PASSED (0.48 SE);
  `src/placebo_c.py --variant C1 --tag bug14fix_2026-10-24` -> C1 FAILED (2.30 SE).
  Stopped: no recalibration, no correction run, no 1(b)/2.
- Membership recorded as a known limitation (`…note_membership_2026-10-24.md`, 11c352cd…).
- Record: the official training LLM event study
  (`event_study_train_keyword+llm_anon_2026-10-18_bug11fix.csv`, 18 Oct 07:35)
  excludes the 1,098 LLM rows of 2024-03-26 → 04-29, scored afterwards (08:00);
  those rows are in no official event study (the test period starts 2024-04-30).

## 2026-10-24 (late evening) — C1 diagnostic; Bug 13 decision; inspections; descriptives
- Code inspections (no runs, no code change): Bug 14 (stop/target fills
  ignore gaps; A, C, C1, partly B) and point-in-time membership not applied
  (`bugs.md`).
- Descriptive runs (`src/descriptive_analyses.py`, log `outputs/descriptive_runs.csv`):
  1(a) yearly event study, 3 news-sample statistics, 4 subgroup table, 1(c)
  per-year |strength| vs R for A and B from the reproduced 18 Oct runs.
- C1 placebo (`src/placebo_c.py --variant C1`, `outputs/placebo_c1_2026-10-24.csv`):
  long−short +0.0063R (t 0.76) vs C +0.0590R -> symmetric under the addendum rule.
- Decision note `…note_bug13_decision_2026-10-24.md` (f1218fd9…): Bug 13
  unresolved; C invalid, not rerun; C1 replaces C as the hybrid strategy; no
  further C diagnostics.

## 2026-10-24 (evening) — Phase 2 a–c; Bug 13 fix + placebo (failed, stopped)
- Phase 2: audit `outputs/phase2_live_audit_2026-10-24.md`; one code path
  `src/live_pipeline.py` + `src/news_cleaning.py` (fetcher uses it), replay test
  `tests/test_live_pipeline.py` (7 checks); shadow run scheduled for 26–27 Oct
  (PID 34811); LLM cache snapshot for the parity batch.
- Rung 1b parameters saved (`outputs/rung1b_params_2026-10-24.npz`, reproduce the
  score file exactly); `rung_embeddings.py` split into functions.
- Bug 13 note (8a537056…), fix in `strategy_c.py`, unit test passes; placebo
  FAILED (long/short t 6.8; NDX-adjusted t 4.4) -> stopped, C not rerun.

## 2026-10-24 — Ladder Phase 1 (factor robustness, rung 1b, speed bound); Bug 13 found
- Notes: `…note_ladder_2026-10-24.md` (4b26f9e1…), `…note_ladder_decisions_2026-10-24.md`
  (1e37bd82…), both read-only and registered.
- Factor robustness (`src/factor_event_study.py`, FF5+Mom, betas −259..−10):
  conclusion unchanged; LLM test day-1 +6.2 bps (NDX) -> +0.2 (factors).
- Rung 1b (`src/rung_embeddings.py`, MiniLM rev 1110a243…): validation R² < 0,
  λ at the grid edge (10,000), predictions ≈ intercept -> 99% short. Pipeline
  via `src/run_rung.py` (official files backed up, restored, SHA-verified).
- Speed bound (`src/speed_bound.py`): no rung above the 4.86 bps cost at any
  horizon in either period.
- Bug 13 (open): Strategy C mixes minute (split-adjusted) and daily
  (dividend-adjusted) prices -> all C results invalid, incl. official C rows.

## 2026-10-18 (22:20, decision dated 2026-10-19) — Holdout dropped
- Dated note `FROZEN_CONFIG_2026-10-18_note_holdout_dropped.md` (read-only,
  SHA-256 ffc101cf... in `FROZEN_CONFIG_hashes_notes_2026-10-19.txt`):
  "Holdout not evaluated; dropped by decision on 2026-10-19. No holdout
  returns were ever computed." Official evaluation = training + test (18 Oct).
- Holdout files and `src/holdout_eval.py` marked unused in README.md (kept).

## 2026-10-18 (night) — Holdout switched to Bloomberg prices (Phase 1, frozen; not run)
- Dated note `FROZEN_CONFIG_2026-10-18_note_holdout_bloomberg_2026-10-18.md`
  (read-only, SHA-256 31d2e6fa... in `FROZEN_CONFIG_hashes_notes_2026-10-19.txt`):
  Bloomberg `prices.csv` (ends 2026-07-14) replaces Yahoo; holdout news
  2026-06-02 .. 2026-07-07 (day-5 rule); 22,564 later rows excluded; events
  keyword 579, LLM 411, corporate 46 (24 / 24 / 19 entry dates); power low for
  every hypothesis (H1 cells 1-11%, H2 9-15%, H3 7-10%). Date-label correction
  for the notes labelled 19 Oct.
- `event_study.load_window` (shared loader; `load_test` output verified
  identical); `src/holdout_eval.py` (--counts / --validate / --run);
  `tests/test_holdout_eval.py` (6 checks). Holdout NOT run (awaiting review).

## 2026-10-18 (late) — Bug 12 fixed; H2b Holm; H3 pre-registered
(Files from this step carry the label 2026-10-19 by mistake; written 18 Oct, 20:50–21:15.)
- Bug 12 fixed (deterministic tie-break) with dated note
  `FROZEN_CONFIG_2026-10-18_note_bug12_2026-10-19.md`; 18 Oct test runs stay
  official. Training robustness (20 orders): see `results.md`. Explains the
  keyword D discrepancy (order noise: -6.3% to +0.3% at a constant 8,040 trades).
- H2b Holm (8 comparisons): Kelly beats fixed only for B; A not significant.
- H3 pre-registered before holdout prices: dated note
  `FROZEN_CONFIG_2026-10-18_note_H3_2026-10-19.md` (SHA-256 in
  `FROZEN_CONFIG_hashes_notes_2026-10-19.txt`), code `src/h3.py`
  (`tests/test_h3.py`); ex-ante power ~0.19. Test-period effect-size run logged.

## 2026-10-18 (night) — Strategy layer frozen; test-period strategy runs
- `outputs/FROZEN_CONFIG_2026-10-18_note_strategies.md` (read-only, SHA-256 in
  `FROZEN_CONFIG_hashes_strategies.txt`): decisions D/N training-only,
  designed governor, N = 139 trials (+25/50/100), Jobson-Korkie-Memmel vs
  momentum, H2b Kelly vs fixed with exposure; no strategy on the holdout.
- New: `newsdrift.stats.sharpe_diff_test`, `paired_mean_diff`;
  `newsdrift/exposure.py`; runner comparison section; tests (19 stats checks).
  Validated on training only (`outputs/validation_2026-10-18/`).
- Test runs (logged): best LLM A Kelly +4.0% p.a., Sharpe 1.80 vs momentum
  1.08 -- difference +0.70 +- 0.96, DSR(139) 0.46; nothing significant.
- Bug 12 found (signal row order changes trades when caps bind).
- Holdout headlines scored (6,723 rows, no prices), `outputs/holdout_runs.csv`.

## 2026-10-18 (evening) — Training-period rerun of all strategies
- `calibrate_risk.py` (keyword, anonymised LLM), `sweep_new_strategies.py`,
  momentum: training only, fixed engine, Bug 11 rule. Table in `results.md`.
  Best training row: A LLM Kelly +1.4% p.a., Sharpe 0.61 (SE ~0.35); momentum
  +0.9%, Sharpe 0.30. Old outputs in `_archive/_backup_2026-10-18_before_training_rerun/`.
- Open check: keyword D has the same trade count (8,040) before and after the
  Bug 11 fix but a different return; not yet explained. Keyword D is not
  quoted anywhere until it is.

## 2026-10-18 (evening) — Test period scored; test-period event study, both scorers
- LLM test period scored once with the frozen setup: 32,485 rows (100% of
  pre-filtered test headlines), `news_scored_llm_ollama_anon_incl_test.csv`
  (SHA-256 in `outputs/FROZEN_RUN_outputs_hashes.txt`). Bug 1 resolved.
- `event_study.py --period test --scorers keyword llm_anon` (logged): LLM
  mkt-adj day 1 +6.2 (t 2.1), days 2-5 ~0; keyword unchanged. Exploratory:
  LLM importance 7-10 +20 to +42 bps (t 2.4-3.2) in test, ~0 in training.
- Holdout news downloaded (29,919 clean rows) and being scored (no prices);
  `fetch_historical_news.py --progress` added.

## 2026-10-18 — Configuration frozen; holdout hypotheses pre-registered
- `outputs/FROZEN_CONFIG_2026-10-18.md` + final note
  `outputs/FROZEN_CONFIG_2026-10-18_note_2026-10-18.md` (both read-only;
  SHA-256 in `outputs/FROZEN_CONFIG_hashes.txt`). Holdout 2026-06-02 ->
  2026-10-16, Yahoo prices; H1 = Holm-corrected one-sided 95% upper bound
  below 4.86 bps in each of 8 cells; H2 = keyword corporate_event day-3
  reversal, one-sided 5%.
- Scoring cutoff aligned to the backtest (`src/splits.py`); training gap
  2024-03-26..04-29 scored (1,098 rows). Test period scoring started with the
  frozen setup (`--include-test-period` -> `*_anon_incl_test.csv`).
- `src/source_consistency.py`: Yahoo vs Bloomberg returns corr 0.9994,
  mean |diff| 0.94 bps; Yahoo cannot supply 27/193 universe tickers.

## 2026-10-18 — Bug 11 fixed; intraday description test; first logged test-period run
- Bug 11 fixed (`bugs.md` #11): daily netted strength re-gated at 0.20; engine
  guard; `tests/test_signal_gate.py` (6 checks; fails on old code).
- `src/intraday_description.py` (training, RTH news, raw minute returns):
  LLM signed move -30m->t +12.5 bps (t 2.3) vs t->+30m +2.9 (1.5),
  t->close +6.1 (2.0); keyword ~0 in every window. Pre window is 30 min
  (bars were fetched from 30 min before the news).
- `src/event_study.py --period test --scorers keyword` = FIRST entry in the new
  `outputs/test_period_runs.csv` (earlier keyword OOS looks predate the log).
  Test period: day 0 +62.7 bps mkt-adj; days 1-5 +0.6 / -1.7 / -0.8 / +6.4
  (all |t| < 1). Keyword corporate_event reversal replicates (day 2 -33.5 bps,
  t -3.0; training -13.0, t -1.9).
- Training event study rerun with the fix: keyword unchanged (27,042 events);
  LLM 30,591 -> 26,209 events, market-adjusted days 1-5 still -2.0 to -4.4 bps.

## 2026-10-18 — Diagnostics on anonymised LLM scores + event study (training only)
- `src/event_study.py` -> `outputs/event_study_2026-10-18.{csv,png}`, log
  `outputs/logs/event_study_2026-10-18.log`. Zero-netting days excluded in the
  study only (engine issue still open).
- Main finding: signed day-0 (news day) return +57 bps market-adjusted for
  both scorers (t > 20); from the entry open on, market-adjusted returns are
  0 to -7 bps for both, below the 4.86 bps round-trip cost. The LLM's positive
  raw day-5 return (+10.6 bps) is market exposure (62% of its signals long).

## 2026-10-18 — Anonymized 3B scoring complete; 27B dropped
- llama3.2:3b, anonymized, training period: all 39,649 headlines scored
  -> `data_sources/news_scored_llm_ollama_anon.csv` (59,154 rows, 187 tickers,
  2016-01-03 -> 2024-03-25). Strength std 0.27; 0.0% neutral (flag: the model
  almost never says 0); duration 94% = 2 (carries little information).
- qwen3.8:27b cancelled by user decision: mostly CPU on the Ollama host, first
  request timed out after ~20 min, 0 headlines scored. No 27B outputs exist.
- `score_news_llm.py`: stops a run after 20 consecutive errors (was: timed out
  on every remaining headline when the server dropped).

## 2026-10-16 — Two-model Ollama scoring started (llama3.2:3b, then qwen3.8:27b)
- Ollama now reached via Tailscale (`OLLAMA_BASE_URL` = 100.75.252.66).
- `score_news_llm.py --ollama-model <name>`: non-default models get their own
  cache namespace and output (`news_scored_llm_ollama-<model>_anon.csv`);
  default (3B) unchanged. Ollama calls send `think: false`.
- `src/score_two_models.sh`: training period, anonymized, Ollama only (no
  Google/Groq fallback), 3B first, then 27B; resumes across passes. Log:
  `outputs/logs/score_two_models_2026-10-16.log`.
- 27B caveat: only 1.7 of 18.3 GB fits in GPU memory on the Ollama host, so it
  runs mostly on CPU; a first test call gave no reply within 10 minutes.

## 2026-10-13 — Bug 10 fixed: Strategy A ATR alignment + same-day look-ahead
- `newsdrift/backtest.py`: new `attach_atr()` (index-preserving, ATR up to the
  previous bar); trades now record `reason` (stop/target/time).
  `newsdrift/standalone.py` uses `attach_atr`. New `tests/test_atr_alignment.py`.
- Strategy A turns from profitable to slightly negative in-sample (raw size);
  see `bugs.md` #10 and `results.md`. All earlier A results invalid.
- New `outputs/frozen_risk_scales_2026-10-13_{keyword,llm}.csv` supersede the
  11 Oct files (kept); note in `frozen_risk_scales_2026-10-13_NOTE.md`.
  B/C scales unchanged. Before/after table:
  `outputs/logs/atr_fix_before_after_2026-10-13.csv`.
- Calibration layer (`src/calibrate_scorer.py`, `newsdrift/standalone.py`,
  `tests/test_calibration.py`) built; its 4 logged runs used the buggy engine
  and must be rerun.

## 2026-10-13 — Headline anonymization added
- `src/anonymize.py` + `data_sources/company_names.csv` (191 tickers) +
  `tests/test_anonymize.py` (11 checks). `score_news_llm.py` masks the scored
  company's names + ticker by default, separate cache namespace, output
  `*_anon.csv`; `--no-anonymize` keeps the old behaviour. Existing scores
  unchanged; needs a re-score to take effect.
- Full post-restructure verification: 7 main outputs byte-identical; 4 of 6
  sweeps byte-identical, the other 2 identical row-for-row plus the new
  Strategy N row (added after they were last generated).

## 2026-10-13 — Project restructured
- New layout: `context/`, `skills/`, `data_sources/` (was `data/` + LLM scores
  + cache), `outputs/` (was `results/` + `logs/` + `for_claude/`), `src/`
  (all code; the `newsdrift` package moved out of `newsdrift_system/`),
  `tests/`. All paths centralised in `src/paths.py`; scripts run from the root
  as `python3 src/<script>.py`.
- `fetch_historical_news.py` and `raw_news_pusher.py` now load `.env` from the
  project root (they looked next to the script, which would have broken after
  the move).
- CLAUDE.md rewritten as a navigator; its detailed content moved to
  `context/`. Old CLAUDE.md and all code backed up in
  `_archive/_backup_2026-10-13_before_restructure/`.
- Verified: 41 tests + freshness guard pass; all 7 main outputs reproduced
  byte-for-byte against pre-move checksums.

## 2026-10-11/12
- `--tier0`: keyword scorer on the LLM's headline set → no clear winner on
  the same headlines.
- Anonymization gap found (scores in use were not anonymized).
- Per-strategy risk scales calibrated in-sample (`calibrate_risk.py`, A/B/C),
  frozen in `outputs/frozen_risk_scales_2026-10-11_*.csv`; runner
  `--risk-scales`. Keyword A OOS at frozen scale: 10.8% / Sharpe 2.58 / maxDD
  2.8%.
- `--dd-governor` now applies to Strategy A too; new `risk_scale` lever.
- Strategies D (open → close) and N (close → next open) added: A's edge comes
  from days 2–3.
- Project cleanup: stale outputs, provider pilots and caches → `_archive/`.

## 2026-09-27/28
- Annualisation bug (B/C equity per trade close) fixed with daily equity.
- Strategy B scale-out exits, confirmation entries, C close entry; in-sample
  sweeps (`sweep_strategy_b.py`, `sweep_new_strategies.py`).
- Output files named by scorer/variant so runs no longer overwrite each other.
- `run_both_strategies.py` finds the package without `PYTHONPATH`.
- Bugs 6–8 fixed (`portfolio.py`, `build_event_table`).

## 2026-08-26 → 2026-08-30
- Full LLM scoring with local Ollama llama3.2:3b (~42h incl. outages): 35,974
  headlines, train period only.
- Strategy C implemented. Specialist-agent prompt softened on analyst
  opinions. Google/Groq/NVIDIA pilots; NVIDIA dropped.

## 2026-07 → 2026-08
- Data pipeline (Bloomberg prices, Benzinga news, IEX minute bars),
  newsdrift engine, Strategies A and B, bugs 1–5. See
  `context/project_playbook_2026-07.md` for the original plan.
