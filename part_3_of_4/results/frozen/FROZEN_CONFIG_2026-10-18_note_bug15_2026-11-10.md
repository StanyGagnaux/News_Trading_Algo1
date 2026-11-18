# Bug 15 — same-day information in the position sizing of Strategy A: fix rule, acceptance tests and disclosed correction run, dated 10 November 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written 2026-11-10 08:40 CET (Zurich) BEFORE any change to `src/` or `tests/` and
before any run, by decision of the author of the same day. It implements the
specification, which is not edited:

    fbea000b7c5aea292611fcad2b7c87c92310495d4ab85eedd710cbbdb7e4216f  review_2026-11-10/BUG15_note_2026-11-10.md
    01c8d87f835fca787248569a01437a439d26487881fa6886ce5eae5076affef0  review_2026-11-10/BUG15_decisions_and_handoff_2026-11-10.md
    8e860bf944fc537de97ac7ff4c85ea07df4c3e6b16b843c109a46fc02d5b9291  review_2026-11-10/sizing_lag/engine_variants.py  (reference "V2")

Results are NOT in this note (it predates them); they go into a second dated
note, `…note_bug15_results_2026-11-10.md`, registered the same way.

## 1. Diagnosis (found by code review, 10 Nov 2026; `context/bugs.md`)

`src/newsdrift/backtest.py`, `NewsDriftBacktest.run` (SHA-256 before the change
`db6d438f419dfa2e5c43079fb690ec164c63ec1b22b4b9f964ce20bad78099c3`). Inside one
iteration for date d the engine (1) books the exits of day d from that day's
open, high, low and CLOSE and passes each result to the sizer (l. 134, called
from l. 186 and l. 250); (2) marks equity at the close of d and updates the
drawdown governor with it (l. 193–199); (3) only then opens the new positions
"at day d's open" (l. 201–252), sized with the Kelly window of step 1
(l. 221), the equity and throttle of step 2 (l. 222–223) and caps on that
equity (l. 228, 235). An entry-day stop or target is also recorded before the
next ticker of the same day is sized.

Direction, entry price, stop, target and exit of every trade are unaffected.
Position SIZE at 09:30 depends on outcomes at 16:00 of the same day. This
breaks hard rule 1 (no look-ahead). Channels: (a) Kelly window (decisive;
87–99.9% of training sizing calls contain a trade closed on the entry day);
(b) sizing equity and governor throttle from the close of d (small); (c)
entry-day exits recorded before the next ticker is sized (part of a).
Not caught earlier because the random-direction placebo's statistic (mean R
per trade) does not depend on size, the A placebo ran with the fixed sizer,
and the 8 Nov assertion tested "exit date <= entry date", which same-day
closes satisfy. Affected: every Strategy A row (Kelly materially; fixed
through channel b). Not affected: event studies, speed bound, Strategies B
and C (`portfolio.py` closes trades with `exit_ts <= entry_ts` before each
sizing call), the momentum benchmark.

## 2. Fix rule (author's decision 1: all sizing inputs at the previous close)

For every position opened at the open of day d:

| Input | After the fix |
|---|---|
| Kelly window (`sizer.risk_fraction`) | trades with exit date strictly before d. Results of day d, including entry-day stops and targets, are held back and passed to the sizer after the last entry of day d |
| Sizing equity (`risk_amount`) | equity at the close of d−1 (initial equity on the first day) |
| Position cap (20% of equity) and gross cap (100%) | on the equity at the close of d−1 |
| Governor throttle | the value returned by `governor.update` at the close of d−1 (1.0 on the first day); the governor is still updated once per day with that day's close |

Unchanged on purpose: direction, entry price, stop, target, exits, costs, the
order of same-day signals, the equity curve's definition, and admission on the
book after day d's exits (a ticker whose position exits on day d can still be
re-entered at the open of d; disclosed in the thesis, no code change). The
end-of-day hand-over to the sizer runs on every path, including days without
signals and days on which the lagged throttle is not positive.

Implementation follows `run_variant(lag_kelly=True, lag_equity=True)` of the
reference file statement for statement, except that the engine keeps its
`size_weight` branch and its `cap_days` record, and does NOT add a
`risk_amount` column to the trade log (`newsdrift/exposure.py` uses that
column to tell A from B/C logs). Added, reporting only: a per-call sizing log
(date, ticker, base fraction, sizing equity, throttle, window size, newest
exit date in the window, risk amount, opened yes/no), dumped next to the
trade logs.

**Runtime checks added to the engine** (hard rule 1): before every call of
the sizer on date d, `max(exit date of the trades in the Kelly window) < d`
(strict); the sizing equity equals the equity-curve value of the previous
trading day (initial equity on the first day).

Files to be changed (SHA-256 before the change; backup of `src/` and `tests/`
in `_archive/_backup_2026-11-10_before_bug15_fix/`):

| file | before | change |
|---|---|---|
| `src/newsdrift/backtest.py` | `db6d438f419dfa2e5c43079fb690ec164c63ec1b22b4b9f964ce20bad78099c3` | the fix, the runtime checks, the sizing log |
| `src/run_both_strategies.py` | `65b4778a9abbf0b046475cfd88e1b0d355fad0c505a30bd97ed70fcf21d2572e` | additive options only, defaults unchanged: `--only-a` (Strategies B and C are not run), `--benchmark-equity FILE` (the stored continuous momentum series replaces the per-period benchmark; momentum is not rerun); sizing log added to `--dump-dir` |
| `src/calibrate_risk.py` | `23be3cd56a01e6ebc0f2456eaa42ae828bc16f3cedfdbe2b5554fc1722be9a47` | additive option `--only-a` |
| `src/placebo_a.py` | `5b187d1cb5ad3d740163a216b3778e2235df9d6269a7f9f99ade1a8a35a7b1ed` | additive options `--sizer`, `--scales`, `--out` (defaults = the 24 Oct placebo); size-weighted statistic of test D |
| `tests/test_bug15_sizing_lag.py` | new | unit test (test C) |
| `src/bug15_report.py` | new | derived tables from stored files (no strategy is run) |

Not changed: `risk.py` (`c3c32817…`), `portfolio.py` (`cd426423…`), `stats.py`
(`0c3c34c0…`), every B, C and momentum file. Other callers of the A engine
(`order_robustness.py`, `sweep_new_strategies.py`, `calibrate_scorer.py`) are
not rerun; their recorded outputs predate the fix and are training-only.
Interpreter for every command below (the project's `python3`, not Anaconda):
`/Library/Frameworks/Python.framework/Versions/3.13/bin/python3` (3.13.7,
pandas 2.3.3, numpy 2.3.4). All 14 existing test files pass with it before the
change (checked 10 Nov, 08:30).

## 3. Acceptance tests (order fixed here; **if any fails: stop, report, no test-period run; no criterion is amended after its result is seen**)

**C. Unit test, synthetic data** (`tests/test_bug15_sizing_lag.py`). The risk
amount of a position opened at the open of day d is identical (1e-9 relative)
whether another position closes on day d at its target or at its stop (Kelly
window channel), and whether equity and the governor at the close of d are
higher or lower (fixed sizer, a day-d loss large enough to move the throttle);
an entry-day stop of an earlier ticker does not change the size of a later
ticker of the same day; the day-d result DOES change sizes on day d+1; results
of a day without signals reach the sizer. Must FAIL on the code of 10 Nov
(backup) and PASS on the new code. All 14 existing test files must still pass.

**A. Cross-check against the reference implementation, training period, OLD
scales.** The fixed engine, driven by the official pipeline
(`run_both_strategies.load_inputs`, the score files of the official runs,
designed governor, training slice 2016-01-04 → 2024-04-29), at the A scales of
`risk_calibration_{keyword,llm,embed_minilm}_bug14fix_2026-10-24.csv` and
`risk_calibration_{haiku,sonnet}_2026-10-25.csv`, must return the ten cells of
the specification, Section 3 A (reference `results_train.jsonl`, variant V2):
return p.a., Sharpe and maximum drawdown to 1e-9, trades exactly. Any
difference is explained in the results note before the run proceeds.

**E. Reference harness on a fresh copy of the new `src/`**
(`review_2026-11-10/sizing_lag/stage2_run.py` and `engine_variants.py`, copied
unchanged; the cached training inputs of the reference): for every rung and sizer the
copy of the engine ("SRC") equals variant V2 at the same scale (metrics 1e-9,
trades exact, equity curves 1e-6 absolute); V0 (old logic) differs from SRC
for the Kelly rows.

**B. Strict assertion.** For every sizing call on date d: (1) the newest exit
date in the Kelly window is strictly earlier than d; (2) the sizing equity
equals the equity-curve value of the previous trading day; (3) the throttle
equals the governor's value at the previous close. Checked two ways: the
engine's runtime checks and sizing log, and independently of the engine from
the dumped trade log and equity curve alone (risk amount recovered as
pnl / R-multiple; Kelly fraction recomputed from the trades with exit date
< d; governor replayed on the dumped equity curve; position cap applied).
Expected 0 violations. Pre-run: training period, old scales, ten
configurations; the independent version must FAIL on the official Kelly dumps
of 24/25 October (old code). Post-run: the official dumps of the correction
run, every rung, both sizers, both periods, 5% and 20% — a violation there
voids the run (reported, not repaired silently).

**D. Kelly-sizer placebo at the portfolio level** (training period only).
Keyword daily signals, directions random exactly as in the A placebo of
24 Oct (`numpy.random.default_rng(20261024)` on the sign, |strength|
unchanged), **Kelly sizer**, designed governor, the keyword A Kelly scale of
the 5% recalibration of Section 4 (calibration is training-only and precedes
this test; the test-period run comes after it).
  (i) existing criterion: |mean R − mean expected cost in R| < 2 plain SE,
  expected cost per trade −(2 × per-side cost) / stop distance;
  (ii) per trade i: oc_i = direction × (close / open − 1) of the entry day;
  size s_i = risk amount = pnl_i / R_i from the trade log (trades with R = 0
  dropped and counted); w_i = s_i / mean(s); excess = mean((w_i − 1) × oc_i)
  = size-weighted minus equal-weighted signed entry-day return. PASS if
  excess ≤ 2 SE, SE = plain standard error of (w_i − 1) × oc_i (the same kind
  of SE as criterion (i); with independent random directions the terms are
  uncorrelated across trades). The SE clustered by entry date is reported
  beside it, not used.
Requirement of the specification: the new code passes (i) and (ii); the old code
(backup of 10 Nov, same script, same seed, same scale; additionally at its own
official scale 0.0082, descriptive) fails (ii).
*Remark written before the test is run:* with directions drawn independently
per signal, the direction of an entry is independent of its size and of the
entry day's raw return under either code, so the expected excess is zero for
the old code as well. The requirement "the old code fails (ii)" may therefore
not be met by this design; the mechanism of Bug 15 needs the common direction
of a long-biased book. If the requirement is not met, that is reported and
the procedure stops before the test-period run, as for any other failed test;
the design is not changed on my own.

## 4. Disclosed correction run (only if A to E pass)

1. **5% recalibration on TRAINING**, unchanged rule (`calibrate_risk.py`,
   proportional search, 5% ± 0.25 pp, mechanical), A fixed and A Kelly, five
   rungs: `calibrate_risk.py [--llm-scores <training score file>] --only-a
   --out outputs/risk_calibration_<rung>_bug15fix_2026-11-10.csv`. Training
   score files as on 24/25 Oct: none (keyword);
   `news_scored_llm_ollama_anon.csv`; `news_scored_embed_minilm.csv`;
   `news_scored_haiku_anon.csv`; `news_scored_sonnet_anon.csv`.
2. **One run per rung, training + test**, the frozen command otherwise
   unchanged: `run_both_strategies.py [--llm-scores <…_incl_test.csv>]
   --risk-scales <1.> --dd-governor designed --n-trials N --only-a
   --benchmark-equity outputs/momentum_continuous_equity_2026-10-24.csv
   --out-name <rung>_calibrated_bug15fix_2026-11-10 --dump-dir
   outputs/correction_bug15fix_2026-11-10/dd05/<rung>`; N = 139 (keyword),
   139 (Llama), 155 (MiniLM), 155 (Haiku), 161 (Sonnet). The benchmark is the
   stored continuous series of 24 Oct (SHA-256 `83df7421…af3c98`), not rerun.
3. **20% sensitivity, once** (descriptive, design of the note of 25 Oct):
   calibration with `--target-dd 0.20 --dd-cap 0.20 --dd-throttle-start 0.12
   --only-a`, run with `--dd-cap 0.20 --dd-throttle-start 0.12 --only-a`,
   N = 139 / 139 / 155 / 155 / 163 as on 25 Oct; names `…_dd20_bug15fix_2026-11-10`.
4. Derived tables from the stored files only (`src/bug15_report.py`): Holm for
   Kelly minus fixed (same families as 24/25 Oct: six for keyword + Llama; three
   each for MiniLM, Haiku, Sonnet; new A rows, unchanged B rows), comparison
   against continuous momentum, 20% summary, yearly performance and
   correlations for the A rows, adjacent-rung differences, cost ladder (best
   strategy per rung re-selected by the same ex-post rule), equity charts of
   the Llama and Haiku rungs with the corrected A curves.
5. A placebo (fixed sizer) rerun; the 8 Nov verification harness rerun on the
   new files with assertion B added.
6. Every run is logged in `outputs/test_period_runs.csv`. **Strategies B and C
   and the momentum benchmark are not run.** The driver is
   `outputs/correction_bug15fix_2026-11-10/run.sh`.

## 5. Trial counts (author's decision 3)

The counts stay **139 / 155 / 161 / 163**. The ten corrected A configurations
replace the earlier ones and are not counted as new trials (precedent: the
Bug 14 correction run of 24 Oct). Counting them would be the stricter choice
(+10 per count); stated here so the reader can judge.

## 6. Superseded by this run (files stay in place, marked SUPERSEDED (Bug 15))

The A rows (fixed and Kelly, training and test) of:
`results_both_strategies_{keyword,llm,embed_minilm}_calibrated_bug14fix_2026-10-24*.csv`,
`…_calibrated_cminute_2026-10-24*.csv`, `results_both_strategies_{haiku,sonnet}_calibrated_2026-10-25*.csv`,
`…_calibrated_cminute_2026-10-25*.csv`, `rung2_summary_2026-10-25.csv`, `rung3_summary_2026-10-25.csv`,
`comparison_vs_continuous_momentum_2026-10-24.csv`, `holm_kelly_vs_fixed_bug14fix_2026-10-24.csv`,
`sensitivity_dd20_summary_2026-10-25.csv`, `descriptive_yearly_performance_*`,
`descriptive_correlations_*`, `rung_comparisons_2026-10-25.csv` (A Kelly column),
`cost_ladder_2026-10-25.csv` (best-strategy cells), the A rows of every
`risk_calibration_*` file, the equity charts, and `placebo_a_bug14fix_2026-10-24.csv`
(rerun). The B and C rows and the benchmark in those files are unchanged.
