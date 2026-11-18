# Verification summary, 14 November 2026 — rerun of the 8 November harness on the Bug 17 correction run

Scope: Strategy A (the ten configurations rerun on 14 Nov 2026 with the Bug 17 fix, at the 5% and the 20% drawdown
target), the three placebos and every derived table; the equity reconciliation for A, B, minute-bar C and the
momentum benchmark; and the new admission assertion for A. B, C and the benchmark were not rerun (code and files
unchanged since 8 Nov); they are reconciled from their stored trade logs and equity curves.
`verification_summary_2026-11-08.md` stands for every file not listed below. The A rows verified in
`verification_summary_2026-11-10_bug16.md` (Bug 16 run) are SUPERSEDED (Bug 17).

Method, as on 8 Nov: a fresh sandbox (`sandbox_bug17_2026-11-14/`: byte-identical copy of `src/` and `tests/`, 82
files, `scripts/src_hashes_*_bug17.txt`; `data_sources/` linked; the official files dated before the run linked as
inputs, `scripts/seeded_inputs_bug17.txt`) replays the commands of `outputs/correction_bug17fix_2026-11-14/run.sh`,
the placebos and `src/bug17_report.py` (`scripts/bug17_harness.sh`). Each produced file is compared value by value
with the official one (floats 1e-9, counts exact, PNGs pixel by pixel; `scripts/compare_files.py`). Nothing in
`outputs/summary/`, `outputs/`, `src/` or `data_sources/` was modified by the harness.

Deliverables: `reproduction_2026-11-14_bug17.csv` (204 files), `bug_hunt_2026-11-14_bug17.md` (461 assertions),
this summary.

## 1. Reproduction: 204 of 204 files identical

5% run: the 5 calibrations, 15 result / comparison / deflated-Sharpe files and 5 charts. 20% run: the same 25 files.
140 dump files (trade logs, equity curves, sizing logs; both targets, both periods). The 9 derived tables, the two
equity charts (Llama, Haiku) and the three placebo files. 0 differing cells.

## 2. Unit tests: 17 of 17 files pass

The 16 files of the Bug 16 rerun and `tests/test_bug17_admission_snapshot.py` (13 checks; the engine before the fix
fails each of its three cases). `tests/test_bug15_sizing_lag.py` runs in the version approved on 14 Nov
(`a8c00760…`; section 2 fixture with room under the gross cap; addendum to the pre-run note).

## 3. Assertions: 461 run, 457 pass, 4 fail

Passed:
- **Admission (new, Bug 17), 80 checks** on the 40 logs (ten configurations, both periods, 5% and 20%):
  - no position is opened in a ticker on a day on which an earlier position in it is held or closed: 0 of 402,283
    positions;
  - every admitted entry respects the gross cap judged on the book of the previous close plus the entries admitted
    earlier at the same open (1e-9 relative): 0 violations; 519 entries lie within 1% of the cap, the largest use
    is 99.997%; the engine's logged gross equals the recomputed one on all 408,142 calls.
  - The same check (1) on the official training logs of 10 November fails with exactly the predicted counts
    (keyword 6,150; Llama 4,241; MiniLM 5,351; Haiku 1,046; Sonnet 184 and 183)
    (`outputs/correction_bug17fix_2026-11-14/acceptance/acceptance_results.jsonl`).
- **Equity reconciliation, 101 checks.**
  - Strategy A, 40 logs: on every one of 52,340 days equity − initial equity = booked trade results + unrealised
    result of the open positions at their last available close; 0 failing days, largest residual 1.6e-9 on
    100,000. 402,283 positions = 401,447 booked trades (64 of them stale exits) + 836 open at a period end; no
    position is left open in a ticker that stopped trading.
  - Strategy B, 40 logs, and minute-bar C, 20 logs (stored files, unchanged): largest residual 9.7e-10 (B) and
    4.1e-10 (C).
  - Continuous momentum: the stored daily returns recomputed from prices (171 tickers, 2,866 days), largest
    difference 5.5e-16.
- **Stale exits, 8 checks.**
- **Assertion B of Bug 15 (sizing), 80 checks: 0 violations** on 401,447 trades and 408,142 sizing calls; the
  position cap binds on 352 trades.
- **The 8 Nov Strategy A assertions (`bh_A.py`), 175 checks plus the cost check**, on the new trade logs.
- **Planted drift, 12 of 12.**

Failed, none changes a reported number (calibration findings of the known kind):
1. `calibration.bug17.dd05.training_maxDD_0.045_0.052`: 2 of 10 outside the 4.5–5.2% band — keyword A Kelly 5.23%
   and MiniLM A Kelly 5.20% (the search accepts up to 5.25% at the unrounded scale; the run uses the scale rounded
   to four decimals).
2. `calibration.bug17.dd20.training_maxDD_0.19_0.21`: 2 of 10 outside the 19–21% band — Haiku A Kelly 14.85% and
   Sonnet A Kelly 17.53%. The proportional search (six steps, unchanged) does not converge for these two: the
   drawdown of the Kelly sizer is not monotone in the scale (Haiku 34.1% at 0.377, 25.2% at 0.221, 14.2% at 0.175,
   24.1% at 0.247; Sonnet 17.5% at 0.603, 25.1% at 0.688, 21.6% at 0.548, 12.5% at 0.508), and the rule keeps the
   largest scale under 21%. Descriptive 20% rows only.
3. and 4. `calibration_record_vs_run` (5% and 20%): the drawdown and Sharpe written into `risk_calibration_*.csv`
   are those of the unrounded search scale (largest gap 0.06 pp drawdown at 5%; 0.66 pp at 20%, Haiku A Kelly,
   where the path is sensitive to the fourth decimal of the scale; finding 4 of 8 Nov). The thesis reports the
   run's values.

## 4. Placebos (training period, keyword signals)

- Fixed sizer, random directions: mean R −0.0067 against −0.0091 expected, 0.62 SE (20,631 trades).
- Kelly sizer (scale 0.0062), random directions: (i) 0.62 SE, (ii) −1.04 bps (−0.44 SE; −0.40 clustered). Passes.
- Kelly sizer, common direction: +0.91 bps (0.18 clustered SE) all long, −3.09 (−0.45) all short. Passes.

## Bottom line

Every file of the Bug 17 correction run reproduces from the code and data; no Strategy A position is opened in a
ticker that was held at the previous close, and the gross cap is respected on the previous close's book; the equity
curve of every A, B and C configuration equals its trade log plus its open positions on every day; the sizing of
all ten A configurations still uses previous-close information only; and no failed assertion changes a reported
result.
