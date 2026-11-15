# Bug 15 — results of the acceptance tests and of the disclosed correction run, dated 10 November 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written 2026-11-10 (Zurich) AFTER the single correction run. Follows, and does not edit, the pre-run note
`…note_bug15_2026-11-10.md` (`7a66229b…cf6676a`) and its addendum `…note_bug15_addendum_testD2_2026-11-10.md`
(`e1532c0f…bb7dd3`). Net of costs; training 2016-01-04 → 2024-04-29, test 2024-04-30 → 2026-06-01.
SHA-256 of every output file: `for_claude/FROZEN_RUN_outputs_hashes_bug15fix_2026-11-10.txt`.

## 1. Diagnosis and fix (as specified)

A Strategy A position opened at the open of day d was sized with the Kelly window, the equity and the governor
throttle of day d's CLOSE. Fixed in `src/newsdrift/backtest.py` (`db6d438f…` → `50fc92f6…4585a651`), reference
variant V2: all three inputs are those of the close of d−1; results of day d reach the sizer after the day's last
entry; runtime assertions on every sizing call. Direction, entry, stop, target, exit and costs are untouched: in
18 of the 20 trade logs the trades, exits and R-multiples equal those of 24/25 October exactly (difference ≤ 2e-15);
Sonnet A Kelly differs by 6 / 4 trades in training and 1 in the test period (size-dependent admission).
**The correction changed sizes only.**

## 2. Acceptance tests (training period only)

| Test | Result |
|---|---|
| A — ten training cells at the old scales against the reference V2 | PASS, difference 0.0, trades equal |
| B — strict assertion, training part | PASS, 0 violations in 168,703 sizing calls; fails on the old dumps (97.3–99.9% of trades) |
| C — unit test `tests/test_bug15_sizing_lag.py` | PASS 19/19; the old code fails 10 of 18 |
| E — reviewer's `stage2_run.py` on a fresh copy of the new `src/` | PASS, engine = V2 in 10 of 10 |
| D — Kelly placebo, random directions (as run) | new code passes (i) 0.48 SE and (ii) −1.11 bps (−0.54 SE). Requirement "old code fails (ii)": **not met and not meetable by this design** (old code −1.58 bps, −0.81 SE) |
| D2 — Kelly placebo, common direction (addendum) | **both criteria met**: new code +1.72 bps (0.33 clustered SE) long, −2.21 (−0.34) short; old code +37.07 (7.77) and +42.21 (6.93); equal to the reviewer's reference to 2e-14; trades 25,084 / 25,090 |
| B — post-run part, every official dump | PASS, 0 violations in 474,557 trades and 476,550 sizing calls (5% and 20%, both periods) |

**A random-direction placebo cannot detect a look-ahead in position size, with any sizer** (the direction of an
entry is independent of its size). The strict assertion on every sizing call and the common-direction placebo are
the checks that detect it; both are now in the test suite and the harness.

## 3. Recalibrated scales (training, unchanged mechanical rule)

| Rung | 5% fixed old → new | 5% Kelly old → new | 20% fixed old → new | 20% Kelly old → new |
|---|---|---|---|---|
| keyword | 0.0039 → **0.0041** | 0.0082 → 0.0033 | 0.0173 → 0.0173 | 0.0363 → 0.0139 |
| Llama | 0.0072 → 0.0072 | 0.0228 → 0.0096 | 0.0307 → 0.0307 | 0.2034 → 0.0415 |
| MiniLM | 0.0028 → 0.0028 | 0.0031 → 0.0015 | 0.0124 → 0.0124 | 0.0131 → 0.0065 |
| Haiku | 0.0201 → 0.0201 | 0.0454 → 0.0362 | 0.0874 → 0.0842 | 0.2097 → 0.1898 |
| Sonnet | 0.0359 → **0.0361** | 0.1307 → 0.1294 | 0.1625 → 0.1582 | 0.5860 → 0.7495 |

Training drawdown of the runs at 5%: 4.32% to 5.23%. **Sonnet A Kelly sits at 4.32%**: the proportional search
alternated between 3.9% and 5.8% and the rule keeps the largest scale under 5.25% (as Haiku C Kelly on 25 Oct).
Keyword A fixed is at 5.23% (inside the ±0.25 pp tolerance). At 20%: 18.5% (Haiku A Kelly) to 20.9%.

## 4. The ten corrected rows at 5% (return p.a. / Sharpe / maximum drawdown / trades), old → new

| A | training old | training new | test old | test new |
|---|---|---|---|---|
| keyword fixed | −0.60% / −0.762 / 4.98% / 25,086 | −0.63% / −0.762 / 5.23% / 25,086 | −0.68% / −1.218 / 2.00% / 12,076 | −0.72% / −1.219 / 2.10% / 12,076 |
| keyword Kelly | +0.14% / +0.09 / 5.04% / 25,086 | −0.55% / −0.75 / 5.17% / 25,086 | +0.07% / +0.03 / 2.80% / 12,076 | **−1.73% / −1.36 / 4.31%** / 12,076 |
| Llama fixed | −0.45% / −0.480 / 5.09% / 21,863 | −0.45% / −0.480 / 5.09% / 21,863 | −0.09% / −0.113 / 1.65% / 8,093 | −0.09% / −0.114 / 1.65% / 8,093 |
| Llama Kelly | +0.44% / +0.24 / 5.02% / 21,863 | −0.43% / −0.54 / 5.02% / 21,863 | +1.37% / +0.75 / 2.22% / 8,093 | **+0.78% / +1.08 / 0.96%** / 8,093 |
| MiniLM fixed | −0.60% / −1.215 / 5.13% / 21,211 | −0.60% / −1.215 / 5.13% / 21,211 | −1.04% / −2.181 / 2.17% / 8,200 | −1.04% / −2.182 / 2.17% / 8,200 |
| MiniLM Kelly | −0.51% / −0.38 / 5.05% / 21,211 | −0.60% / −0.84 / 5.05% / 21,211 | −0.45% / −0.63 / 1.20% / 8,200 | −0.38% / −1.19 / 0.81% / 8,200 |
| Haiku fixed | −0.56% / −0.529 / 5.04% / 10,998 | −0.56% / −0.530 / 5.04% / 10,998 | −1.56% / −1.173 / 3.67% / 4,366 | −1.56% / −1.173 / 3.67% / 4,366 |
| Haiku Kelly | −0.57% / −0.39 / 4.98% / 10,998 | −0.52% / −0.49 / 5.01% / 10,998 | −1.61% / −1.21 / 3.56% / 4,366 | −1.74% / −1.55 / 3.69% / 4,366 |
| Sonnet fixed | −0.26% / −0.226 / 5.04% / 5,039 | −0.26% / −0.228 / 5.07% / 5,039 | −1.36% / −1.089 / 3.43% / 1,908 | −1.37% / −1.089 / 3.45% / 1,908 |
| Sonnet Kelly | +0.97% / +0.40 / 5.02% / 5,030 | +0.11% / +0.05 / 4.32% / 5,028 | −1.86% / −0.93 / 4.83% / 1,908 | −2.95% / −1.39 / 6.45% / 1,907 |

File: `a_rows_old_vs_new_bug15fix_2026-11-10.csv` (all cells, 5% and 20%, with the mean-over-standard-deviation
Sharpe). The positive training Kelly cells of 24/25 Oct (keyword, Llama, Sonnet) were produced by the look-ahead.

### Movement of the five fixed rows

| A fixed | target | scale | training: return / Sharpe / maxDD / trades | test: return / Sharpe / maxDD / trades |
|---|---|---|---|---|
| keyword | 5% | 0.0039 → 0.0041 | −0.598 → −0.629% / −0.762 → −0.762 / 4.98 → 5.23% / 25,086 = | −0.684 → −0.719% / −1.218 → −1.219 / 2.00 → 2.10% / 12,076 = |
| Llama | 5% | 0.0072 = | −0.452 → −0.452% / −0.480 → −0.480 / 5.09 → 5.09% / 21,863 = | −0.090 → −0.091% / −0.113 → −0.114 / 1.65 → 1.65% / 8,093 = |
| MiniLM | 5% | 0.0028 = | −0.602 → −0.602% / −1.215 → −1.215 / 5.13 → 5.13% / 21,211 = | −1.041 → −1.042% / −2.181 → −2.182 / 2.17 → 2.17% / 8,200 = |
| Haiku | 5% | 0.0201 = | −0.558 → −0.559% / −0.529 → −0.530 / 5.04 → 5.04% / 10,998 = | −1.557 → −1.558% / −1.173 → −1.173 / 3.67 → 3.67% / 4,366 = |
| Sonnet | 5% | 0.0359 → 0.0361 | −0.256 → −0.259% / −0.226 → −0.228 / 5.04 → 5.07% / 5,039 = | −1.362 → −1.370% / −1.089 → −1.089 / 3.43 → 3.45% / 1,908 = |
| keyword | 20% | 0.0173 = | −2.674 → −2.681% / −0.768 → −0.768 / 20.58 → 20.63% / 25,086 = | −3.020 → −3.031% / −1.213 → −1.217 / 8.61 → 8.63% / 12,076 = |
| Llama | 20% | 0.0307 = | −1.974 → −1.985% / −0.491 → −0.494 / 20.33 → 20.39% / 21,863 = | −0.428 → −0.445% / −0.126 → −0.130 / 6.90 → 6.93% / 8,093 = |
| MiniLM | 20% | 0.0124 = | −2.656 → −2.662% / −1.210 → −1.213 / 20.90 → 20.95% / 21,211 = | −4.547 → −4.557% / −2.151 → −2.156 / 9.28 → 9.30% / 8,200 = |
| Haiku | 20% | 0.0874 → 0.0842 | −2.471 → −2.382% / −0.538 → −0.538 / 20.38 → 19.73% / 10,996 → 10,997 | −6.731 → −6.475% / −1.165 → −1.163 / 15.23 → 14.69% / 4,366 = |
| Sonnet | 20% | 0.1625 → 0.1582 | −1.362 → −1.443% / −0.269 → −0.291 / 20.70 → 20.83% / 5,022 → 5,028 | −6.094 → −5.833% / −1.077 → −1.058 / 14.70 → 14.12% / 1,902 → 1,903 |

At 5% no fixed-row Sharpe moves by more than 0.002 and no trade count changes; the keyword and Sonnet rows also
carry the slightly larger scale. At 20% the largest Sharpe movement is 0.02 (Sonnet).

## 5. Tests on the corrected rows (test period)

**Against continuous momentum (0.72; Jobson-Korkie-Memmel), old → new:** keyword fixed −1.95 → −1.95 (p 0.015);
keyword Kelly −0.70 (p 0.40) → **−2.10 ± 0.92 (p 0.023)**; Llama fixed −0.84 (p 0.34); Llama Kelly +0.02 (p 0.98) →
**+0.34 ± 0.95 (p 0.72)**; MiniLM fixed −2.93 (p 0.007); MiniLM Kelly −1.37 (p 0.20) → −1.93 ± 1.05 (p 0.067); Haiku
fixed −1.91 (p 0.048); Haiku Kelly −1.94 (p 0.0498) → −2.30 ± 0.96 (p 0.017); Sonnet fixed −1.82 (p 0.054); Sonnet
Kelly −1.66 (p 0.073) → −2.14 ± 0.91 (p 0.019). **No news strategy beats momentum.**

**Deflated Sharpe:** Llama A Kelly 0.131 at N = 139 (0.32 / 0.23 / 0.16 at N = 25 / 50 / 100; was 0.055); every other
A row ≤ 0.003.

**Kelly minus fixed, Holm re-adjusted** (`holm_kelly_vs_fixed_bug15fix_2026-11-10.csv`; B rows unchanged): keyword A
+1.26 (p 0.044) → **−0.15 ± 0.60 (p 0.81)**; Llama A +0.86 → +1.18 ± 0.62 (p 0.056, p_holm 0.11); MiniLM A +1.56
(p_holm 0.021) → +1.00 ± 0.59 (p 0.093, p_holm 0.093); Haiku A −0.39 (p 0.56); Sonnet A −0.31 (p 0.62). No A
difference is significant after adjustment. In the MiniLM family B t+15 moves from p_holm 0.043 to 0.086 because
A's p changed its rank. Gross exposure Kelly / fixed: keyword 0.07 / 0.07, Llama 0.06 / 0.08, MiniLM 0.01 / 0.04,
Haiku 0.07 / 0.13, Sonnet 0.09 / 0.09.

**Llama A Kelly rose from 0.75 to 1.08 when the look-ahead was removed; the other four Kelly rows fell.** Checked
under hard rule 5 before reporting: same trades and R-multiples as on 24 Oct; every size in that log reproduced from
previous-close information (assertion B); the engine equals the reference on training. It is one draw of five and
not significant on any test above; its training Sharpe is −0.54. By year (descriptive): test 2024 +0.2%, 2025 +0.5%,
2026 Jan–May +0.9%; training negative in 2016, 2017, 2020, 2021, 2022 and Jan–Apr 2024. |strength| predicts R in the
test period (t +3.9) but not in training (t +1.9), which Kelly's strength-proportional size loads on.

**Recounts of the forty configurations** (`comparison_vs_continuous_momentum_…` with unchanged B and C rows;
`recounts_forty_configurations_…`): losing in the test period **36 of 40** (was 35; the four that do not lose: Llama A
Kelly, Llama C Kelly, Haiku C Kelly, Sonnet C Kelly); significantly worse than momentum at 5% **24 of 40** (was 22;
A 6, B 17, C 1; largest p among them 0.0484, smallest p not significant 0.0540); standard errors of the Sharpe
differences 0.81 to 1.08; training drawdowns 4.32% to 5.25% (was 4.49% to 5.25%). Best configuration per rung
(ex post, same rule): keyword **C fixed −0.42** (DSR 0.0006; was A Kelly 0.03); Llama A Kelly 1.08 (DSR 0.131);
MiniLM **C Kelly −1.03** (DSR 0.000; was A Kelly −0.63); Haiku C Kelly 0.76 (0.045) and Sonnet C Kelly 0.23 (0.011)
unchanged.

**Adjacent rungs, A Kelly (descriptive, not pre-registered):** Llama − keyword +0.72 (p 0.42) → **+2.44 ± 0.88
(p 0.006)**; MiniLM − Llama −1.39 (p 0.18) → **−2.27 ± 1.04 (p 0.030)**; Haiku − MiniLM −0.37 (p 0.71); Sonnet − Haiku
+0.16 (p 0.84). The news-day column is unchanged.

## 6. 20% sensitivity (descriptive)

Test Sharpe 5% → 20%: keyword fixed −1.22 → −1.22, Kelly −1.36 → −1.35; Llama fixed −0.11 → −0.13, **Kelly 1.08 →
1.06** (+3.3% p.a., maximum drawdown 4.1%, 8,091 trades, cap days 0.2%); MiniLM −2.18 → −2.16, −1.19 → −1.19; Haiku
−1.17 → −1.16, −1.55 → −1.51; Sonnet −1.09 → −1.06, **Kelly −1.39 → −1.04** (the only material change: cap days
0.4% → 11.3%, trades 1,907 → 1,821). The earlier statement that Llama A Kelly falls from 0.75 to 0.08 at 20% because
caps bind was an artefact of the inflated scale (0.2034; now 0.0415) and no longer holds. The Sharpe test against
momentum uses the stored series; it is scale-free and reproduces the 25 Oct cells from the old dumps to 4e-14.

## 7. Placebos and verification

A placebo, fixed sizer, rerun: unchanged (mean R −0.0073 against −0.0090, 0.48 SE). Harness of 8 November rerun
(`verification_summary_2026-11-10.md`): 204 of 204 files reproduce; 15 of 15 test files pass; 272 assertions, 268
pass; the 4 that fail are calibration bookkeeping (drawdown bands, record against run) and change no number.

## 8. Trial counts

Unchanged at **139 / 155 / 161 / 163**; the ten corrected configurations replace the earlier ones (precedent:
24 Oct). Counting them as new trials would be the stricter choice.

## 9. Scope, deviations, superseded files

- Strategies B and C and the momentum benchmark were **not run**. In the new result files the row
  `BENCHMARK_momentum` and the `strategy_minus_momentum` comparisons are the stored continuous series of 24 Oct
  (`83df7421…`), not the per-period benchmark of earlier files.
- Additive options only, defaults unchanged: `run_both_strategies.py` `--only-a`, `--benchmark-equity`;
  `calibrate_risk.py` `--only-a`; `placebo_a.py` `--sizer`, `--scales`, `--out`, `--directions`. New:
  `src/bug15_report.py` (derived tables from stored files; each re-applied rule first reproduces the earlier
  official file), `tests/test_bug15_sizing_lag.py`, harness scripts `bh_bug15_sizing.py`, `bug15_harness.*`.
- Not rerun, recorded outputs predate the fix (training only): `order_robustness.py`, `sweep_new_strategies.py`,
  `calibrate_scorer.py`; the 18 Oct and 13 Oct A rows (already superseded).
- The equity charts of the Llama and Haiku rungs show the corrected A curves; B, C and the per-period benchmark
  line are those of the official minute-bar-C runs.
- **SUPERSEDED (Bug 15), files left in place:** the A rows of every file listed in the pre-run note, Section 6.
