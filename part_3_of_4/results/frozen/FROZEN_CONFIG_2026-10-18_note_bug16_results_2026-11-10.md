# Bug 16 — results of the acceptance tests and of the disclosed correction run, dated 10 November 2026

Written 2026-11-10 (Zurich) after the run specified in `FROZEN_CONFIG_2026-10-18_note_bug16_2026-11-10.md`
(SHA-256 `c17fce3f…53e486f`, written and registered before the run). Specification notes:
`review_2026-11-10/BUG16_note_2026-11-10.md` (`d6577a76…`) and `BUG16_addendum_1_test_period_2026-11-10.md`
(`2d054c04…`). Bug 16 was found by the external review after the freeze of 18 October 2026, on 10 November 2026,
while an exploratory strategy was reconciled against its trade log. One run per configuration; every result is
reported regardless of outcome. Trial counts unchanged: 139 / 155 / 161 / 163.

## 1. Diagnosis and fix (as specified)

Strategy A (`src/newsdrift/backtest.py`) skipped a position whose ticker had no bar that day, both in the exit loop
and in the daily mark to market. A position open when its ticker stops trading (acquisition, delisting) was
therefore never closed, its holding days were never counted, and its margin (shares × entry price) disappeared from
equity for good; on a one-day gap in the price file the margin disappeared for that day. The equity curve did not
equal the booked trades plus the open positions. Fix, three rules: (1) an open position is marked at its last
available close; (2) holding days are counted on the trading calendar, bar or no bar; (3) when the exit day has no
bar the position exits at its last available close, exit cost applied, reason `stale`. A runtime assertion checks
every day that equity − initial equity = booked trade results + unrealised result of the open positions (1e-9 of
initial equity). Engine hash before `50fc92f6…` (Bug 15 version), after `fbf1e857…`. B, C and the momentum
benchmark are separate engines and are unchanged.

Size of the error, keyword A fixed, training, same scale 0.0041: final equity 94,890.51 (before) against 97,769.91
(after); the difference of 2,879 is the margin of three positions that were never closed — ESRX 172
(21 Dec 2018), ATVI 886 (13 Oct 2023), SPLK 1,830 (18 Mar 2024). Acquisition targets trade in a narrow range, so
twice their ATR is small and the position is large for a given risk amount. At that scale the training drawdown
falls from 5.23% to 2.67%, which is why the recalibrated fixed scales of the keyword and Llama rungs roughly double.

## 2. Acceptance tests (all passed before the run)

| test | result |
|---|---|
| R-old: logs of the Bug 15 run must fail the reconciliation on exactly the stuck positions of the specification note | 40 of 40 as expected: 24 of the 40 logs have failing days, and the never-closed tickers are exactly WFM, SPLK, ATVI, MXIM, SHPG, ESRX, MYL, XLNX (training) and ANSS (test, MiniLM); no other ticker |
| R-new: fixed engine, training, at the Bug 15 scales | reconciliation 10 of 10 on every day (largest residual 1.8e-9 on 100,000) |
| Bug 15 strict sizing assertion on the fixed engine | 20 of 20, 0 violations |
| B (40 logs) and minute-bar C (20 logs): equity change = sum of trade results | 40 of 40 and 20 of 20 (largest residual 9.7e-10); files unchanged |
| continuous momentum: stored daily returns recomputed from prices | largest difference 5.5e-16 |
| unit tests | 16 of 16 files; `tests/test_bug16_stopped_ticker.py` 9 of 9 (the engine before the fix fails 5 of its 6 behavioural checks) |

## 3. The ten rows at 5%, Bug 15 run → Bug 16 run

Training period (calibration to a 5% training drawdown, ±0.25 pp, unchanged mechanical rule):

| rung | sizer | scale | return p.a. | Sharpe | max drawdown | trades |
|---|---|---|---|---|---|---|
| keyword | fixed | 0.0041 → 0.0079 | -0.629% → -0.523% | -0.762 → -0.736 | 5.23% → 5.09% | 25,086 → 25,089 |
| keyword | kelly | 0.0033 → 0.0041 | -0.550% → -0.460% | -0.749 → -0.594 | 5.17% → 5.08% | 25,086 → 25,089 |
| Llama | fixed | 0.0072 → 0.0145 | -0.452% → -0.216% | -0.480 → -0.174 | 5.09% → 5.04% | 21,863 → 21,869 |
| Llama | kelly | 0.0096 → 0.0122 | -0.431% → -0.407% | -0.543 → -0.437 | 5.02% → 5.23% | 21,863 → 21,869 |
| MiniLM | fixed | 0.0028 → 0.0037 | -0.602% → -0.590% | -1.215 → -1.133 | 5.13% → 5.10% | 21,211 → 21,217 |
| MiniLM | kelly | 0.0015 → 0.0027 | -0.602% → -0.613% | -0.839 → -0.765 | 5.05% → 5.25% | 21,211 → 21,217 |
| Haiku | fixed | 0.0201 → 0.0201 | -0.559% → -0.560% | -0.530 → -0.593 | 5.04% → 5.04% | 10,998 → 10,999 |
| Haiku | kelly | 0.0362 → 0.0363 | -0.525% → -0.529% | -0.494 → -0.498 | 5.01% → 5.02% | 10,998 → 10,999 |
| Sonnet | fixed | 0.0361 → 0.0361 | -0.259% → -0.259% | -0.228 → -0.233 | 5.07% → 5.07% | 5,039 → 5,039 |
| Sonnet | kelly | 0.1294 → 0.1294 | +0.107% → +0.107% | +0.048 → +0.048 | 4.32% → 4.32% | 5,028 → 5,028 |

Test period (one run):

| rung | sizer | scale | return p.a. | Sharpe | max drawdown | trades |
|---|---|---|---|---|---|---|
| keyword | fixed | 0.0041 → 0.0079 | -0.719% → -1.385% | -1.219 → -1.218 | 2.10% → 4.02% | 12,076 → 12,076 |
| keyword | kelly | 0.0033 → 0.0041 | -1.726% → -2.144% | -1.363 → -1.362 | 4.31% → 5.33% | 12,076 → 12,076 |
| Llama | fixed | 0.0072 → 0.0145 | -0.091% → -0.191% | -0.114 → -0.119 | 1.65% → 3.31% | 8,093 → 8,093 |
| Llama | kelly | 0.0096 → 0.0122 | +0.779% → +0.990% | +1.075 → +1.075 | 0.96% → 1.22% | 8,093 → 8,093 |
| MiniLM | fixed | 0.0028 → 0.0037 | -1.042% → -1.289% | -2.182 → -2.097 | 2.17% → 2.68% | 8,200 → 8,201 |
| MiniLM | kelly | 0.0015 → 0.0027 | -0.380% → -0.676% | -1.192 → -1.179 | 0.81% → 1.45% | 8,200 → 8,201 |
| Haiku | fixed | 0.0201 → 0.0201 | -1.558% → -1.558% | -1.173 → -1.173 | 3.67% → 3.67% | 4,366 → 4,366 |
| Haiku | kelly | 0.0362 → 0.0363 | -1.737% → -1.742% | -1.553 → -1.553 | 3.69% → 3.70% | 4,366 → 4,366 |
| Sonnet | fixed | 0.0361 → 0.0361 | -1.370% → -1.370% | -1.089 → -1.089 | 3.45% → 3.45% | 1,908 → 1,908 |
| Sonnet | kelly | 0.1294 → 0.1294 | -2.948% → -2.948% | -1.393 → -1.393 | 6.45% → 6.45% | 1,907 → 1,907 |

Reading: test-period Sharpe ratios move by at most 0.013 in nine rows; MiniLM fixed moves from −2.18 to −2.10 (the
one stuck test-period position, ANSS). Returns and drawdowns scale with the recalibrated size: about ×2 for keyword
fixed and Llama fixed. Training rows improve where a stuck position had been written off (Llama fixed −0.48 →
−0.17, keyword Kelly −0.75 → −0.59). Haiku fixed moves the other way (−0.53 → −0.59) at an unchanged return: Haiku
and Sonnet have no stale exit, but two one-day gaps in the price file (DXCM, 21 July 2016; BIIB, 9 June 2023) had
made the margin of an open position vanish for one day and return the next (daily equity moves of −0.57% / +0.60%
and −0.74% / +0.70%); without them the daily standard deviation is 10% lower and the same loss gives a more
negative Sharpe ratio. Two exits move by a day (BIIB, DXCM) and one BIIB trade is added. No training row turns
positive that was negative; Sonnet Kelly stays the only positive one (+0.048). Stale exits in the run: keyword 4 in
training (ESRX, BIIB, ATVI, SPLK; BIIB is the one-day gap), Llama 5 (WFM, ESRX, SHPG, MYL, MXIM), MiniLM 6
(+ XLNX) and 1 in the test period (ANSS); Haiku and Sonnet none.

## 4. Tests on the corrected rows (test period, 5%)

Against the stored continuous momentum series (`outputs/momentum_continuous_equity_2026-10-24.csv`, Sharpe 0.72):

| rung | sizer | Sharpe | difference to momentum ± SE | p | DSR (N) | difference in the Bug 15 run |
|---|---|---|---|---|---|---|
| keyword | fixed | -1.218 | -1.956 ± 0.806 | 0.0152 | 0.0000 (139) | -1.955 (p 0.0153) |
| keyword | kelly | -1.362 | -2.103 ± 0.924 | 0.0229 | 0.0000 (139) | -2.103 (p 0.0229) |
| Llama | llm | -0.119 | -0.845 ± 0.885 | 0.3397 | 0.0025 (139) | -0.844 (p 0.3404) |
| Llama | llm | +1.075 | +0.340 ± 0.952 | 0.7209 | 0.1314 (139) | +0.340 (p 0.7209) |
| MiniLM | llm | -2.097 | -2.842 ± 1.081 | 0.0086 | 0.0000 (155) | -2.926 (p 0.0069) |
| MiniLM | llm | -1.179 | -1.915 ± 1.052 | 0.0686 | 0.0000 (155) | -1.927 (p 0.0669) |
| Haiku | llm | -1.173 | -1.910 ± 0.967 | 0.0482 | 0.0000 (155) | -1.910 (p 0.0482) |
| Haiku | llm | -1.553 | -2.295 ± 0.959 | 0.0167 | 0.0000 (155) | -2.295 (p 0.0167) |
| Sonnet | llm | -1.089 | -1.825 ± 0.947 | 0.0540 | 0.0000 (161) | -1.825 (p 0.0540) |
| Sonnet | llm | -1.393 | -2.138 ± 0.910 | 0.0188 | 0.0000 (161) | -2.138 (p 0.0188) |

Kelly against fixed, Holm within the families of 18 October:

| family | rung | Kelly − fixed ± SE | p | Holm p | gross exposure Kelly / fixed |
|---|---|---|---|---|---|
| H2b_family_6 | keyword | -0.147 ± 0.600 | 0.8060 | 0.8060 | 0.089 / 0.127 |
| H2b_family_6 | Llama | +1.186 ± 0.620 | 0.0558 | 0.1115 | 0.071 / 0.169 |
| rung1b_family_3 | MiniLM | +0.927 ± 0.584 | 0.1126 | 0.1126 | 0.024 / 0.051 |
| rung2_family_3 | Haiku | -0.385 ± 0.656 | 0.5571 | 0.5571 | 0.073 / 0.130 |
| rung3_family_3 | Sonnet | -0.313 ± 0.640 | 0.6249 | 1.0000 | 0.086 / 0.090 |

Rung comparisons on A Kelly (descriptive):

- rung 1 (llm_anon) minus rung 0 (keyword): +2.443 ± 0.883 (p 0.0056); Bug 15 run +2.443 (p 0.0057)
- rung 1b (embed_minilm) minus rung 1 (llm_anon): -2.255 ± 1.043 (p 0.0306); Bug 15 run -2.268 (p 0.0297)
- rung 2 (haiku) minus rung 1b (embed_minilm): -0.380 ± 0.973 (p 0.6959); Bug 15 run -0.368 (p 0.7054)
- rung 3 (sonnet) minus rung 2 (haiku): +0.157 ± 0.767 (p 0.8375); Bug 15 run +0.157 (p 0.8375)

Recounts over the forty configurations (A rows new; B and C carried over unchanged):

| item | Bug 15 run | Bug 16 run |
|---|---|---|
| configurations | 40 | 40 |
| losing_in_test | 36 | 36 |
| significantly_worse_than_momentum_5pct | 24 | 24 |
| largest_p_among_significantly_worse | 0.0484 | 0.0484 |
| smallest_p_not_significant | 0.0540 | 0.0540 |
| better_than_momentum_point_estimate | 2 | 2 |
| se_sharpe_diff_min | 0.8057 | 0.8058 |
| se_sharpe_diff_max | 1.0829 | 1.0813 |
| training_maxDD_min | 0.0432 | 0.0432 |
| training_maxDD_max | 0.0525 | 0.0525 |
| best_keyword | C_minute_multiday_fixed; Sharpe -0.4208; DSR 0.000606 (N 139); vs momentum -1.1514, p 0.2047 | C_minute_multiday_fixed; Sharpe -0.4208; DSR 0.000606 (N 139); vs momentum -1.1514, p 0.2047 |
| best_llm | A_daily_1-3d_kelly_llm; Sharpe 1.0751; DSR 0.131337 (N 139); vs momentum +0.3402, p 0.7209 | A_daily_1-3d_kelly_llm; Sharpe 1.0753; DSR 0.131359 (N 139); vs momentum +0.3403, p 0.7209 |
| best_embed_minilm | C_minute_multiday_kelly_llm; Sharpe -1.0302; DSR 0.000000 (N 155); vs momentum -1.7785, p 0.0759 | C_minute_multiday_kelly_llm; Sharpe -1.0302; DSR 0.000000 (N 155); vs momentum -1.7785, p 0.0759 |
| best_haiku | C_minute_multiday_kelly_llm; Sharpe 0.7577; DSR 0.044688 (N 155); vs momentum +0.0559, p 0.9554 | C_minute_multiday_kelly_llm; Sharpe 0.7577; DSR 0.044688 (N 155); vs momentum +0.0559, p 0.9554 |
| best_sonnet | C_minute_multiday_kelly_llm; Sharpe 0.2303; DSR 0.010672 (N 163); vs momentum -0.4353, p 0.6653 | C_minute_multiday_kelly_llm; Sharpe 0.2303; DSR 0.010672 (N 163); vs momentum -0.4353, p 0.6653 |

## 5. 20% sensitivity (descriptive)

Training:

| rung | sizer | scale | return p.a. | Sharpe | max drawdown | trades |
|---|---|---|---|---|---|---|
| keyword | fixed | 0.0173 → 0.0335 | -2.681% → -2.244% | -0.768 → -0.744 | 20.63% → 20.11% | 25,086 → 25,089 |
| keyword | kelly | 0.0139 → 0.0187 | -2.359% → -2.066% | -0.762 → -0.587 | 20.39% → 20.90% | 25,082 → 25,032 |
| Llama | fixed | 0.0307 → 0.0606 | -1.985% → -1.035% | -0.494 → -0.200 | 20.39% → 20.09% | 21,863 → 21,869 |
| Llama | kelly | 0.0415 → 0.0496 | -1.892% → -1.666% | -0.554 → -0.454 | 20.34% → 19.65% | 21,850 → 21,825 |
| MiniLM | fixed | 0.0124 → 0.016 | -2.662% → -2.552% | -1.213 → -1.134 | 20.95% → 20.45% | 21,211 → 21,217 |
| MiniLM | kelly | 0.0065 → 0.0112 | -2.623% → -2.567% | -0.843 → -0.772 | 20.36% → 20.38% | 21,211 → 21,216 |
| Haiku | fixed | 0.0842 → 0.0845 | -2.382% → -2.408% | -0.538 → -0.606 | 19.73% → 19.79% | 10,997 → 10,998 |
| Haiku | kelly | 0.1898 → 0.1763 | -1.985% → -2.583% | -0.399 → -0.558 | 18.47% → 20.69% | 10,731 → 10,780 |
| Sonnet | fixed | 0.1582 → 0.1577 | -1.443% → -1.438% | -0.291 → -0.298 | 20.83% → 20.76% | 5,028 → 5,028 |
| Sonnet | kelly | 0.7495 → 0.8404 | +0.344% → +0.596% | +0.040 → +0.067 | 19.19% → 20.57% | 4,710 → 4,689 |

Test:

| rung | sizer | scale | return p.a. | Sharpe | max drawdown | trades |
|---|---|---|---|---|---|---|
| keyword | fixed | 0.0173 → 0.0335 | -3.031% → -5.859% | -1.217 → -1.213 | 8.63% → 16.15% | 12,076 → 12,076 |
| keyword | kelly | 0.0139 → 0.0187 | -7.166% → -8.685% | -1.345 → -1.334 | 17.08% → 20.78% | 12,071 → 12,028 |
| Llama | fixed | 0.0307 → 0.0606 | -0.445% → -1.018% | -0.130 → -0.151 | 6.93% → 13.39% | 8,093 → 8,092 |
| Llama | kelly | 0.0415 → 0.0496 | +3.325% → +3.413% | +1.063 → +0.923 | 4.09% → 4.87% | 8,091 → 8,082 |
| MiniLM | fixed | 0.0124 → 0.016 | -4.557% → -5.496% | -2.156 → -2.068 | 9.30% → 11.16% | 8,200 → 8,201 |
| MiniLM | kelly | 0.0065 → 0.0112 | -1.646% → -2.806% | -1.192 → -1.179 | 3.50% → 5.92% | 8,200 → 8,201 |
| Haiku | fixed | 0.0842 → 0.0845 | -6.475% → -6.498% | -1.163 → -1.163 | 14.69% → 14.74% | 4,366 → 4,366 |
| Haiku | kelly | 0.1898 → 0.1763 | -8.179% → -6.798% | -1.514 → -1.288 | 16.68% → 14.03% | 4,299 → 4,319 |
| Sonnet | fixed | 0.1582 → 0.1577 | -5.833% → -5.740% | -1.058 → -1.044 | 14.12% → 13.94% | 1,903 → 1,903 |
| Sonnet | kelly | 0.7495 → 0.8404 | -9.426% → -11.777% | -1.045 → -1.193 | 19.48% → 24.12% | 1,821 → 1,808 |

| rung | sizer | Sharpe 5% → 20% | cap-binding days 5% / 20% | p vs momentum 5% / 20% | material |
|---|---|---|---|---|---|
| keyword | fixed | -1.218 → -1.213 | 0.00% / 0.00% | 0.0152 / 0.0150 | no |
| keyword | kelly | -1.362 → -1.334 | 0.00% / 2.30% | 0.0229 / 0.0232 | no |
| Llama | llm | -0.119 → -0.151 | 0.00% / 0.19% | 0.3397 / 0.3356 | no |
| Llama | llm | +1.075 → +0.923 | 0.00% / 0.77% | 0.7209 / 0.8413 | no |
| MiniLM | llm | -2.097 → -2.068 | 0.00% / 0.00% | 0.0086 / 0.0084 | no |
| MiniLM | llm | -1.179 → -1.179 | 0.00% / 0.00% | 0.0686 / 0.0681 | no |
| Haiku | llm | -1.173 → -1.163 | 0.00% / 0.38% | 0.0482 / 0.0483 | no |
| Haiku | llm | -1.553 → -1.288 | 0.00% / 3.45% | 0.0167 / 0.0327 | yes |
| Sonnet | llm | -1.089 → -1.044 | 0.00% / 0.96% | 0.0540 / 0.0595 | no |
| Sonnet | llm | -1.393 → -1.193 | 0.38% / 13.98% | 0.0188 / 0.0399 | no |

## 6. Checks after the run

- Reconciliation on the new logs: 40 of 40 (ten configurations × two periods × two targets), 0 failing days, largest
  residual 1.8e-9; 475,546 positions, 474,521 booked trades, 64 stale exits, 1,025 open at a period end, none left
  open in a ticker that stopped trading.
- Bug 15 strict assertion: 80 of 80, 0 violations (474,521 trades; 476,568 sizing calls).
- Placebos, training, keyword signals, seed 20261024, scale 0.0041 (0.0049 for the fixed sizer, as on 24 Oct): fixed
  sizer mean R −0.0073 against −0.0090 expected, 0.48 SE; Kelly with random directions (i) 0.48 SE, (ii) −1.12 bps
  (−0.55 SE, −0.45 clustered); Kelly with a common direction +2.66 bps (0.53 clustered SE) all long, −1.77 (−0.28)
  all short. All pass.
- Harness rerun (`exploratory_B_exit/verification/`, fresh sandbox `sandbox_bug16_2026-11-10/`): 204 of 204 files
  reproduce with 0 differing cells; 16 of 16 test files; 381 assertions, 378 pass. The three that fail are the known
  calibration findings and change no reported number: training drawdown outside the 4.5–5.2% band for Llama Kelly
  5.23%, MiniLM Kelly 5.25% and Sonnet Kelly 4.32% (training drawdowns of the ten rows: 4.32% to 5.251%; the search
  tolerance is 5.25% on the unrounded scale), and the calibration record against the run at 5% and at 20% (record
  taken at the unrounded search scale; finding 4 of 8 Nov). See `verification_summary_2026-11-10_bug16.md`.

## 7. Trial counts

Unchanged: the A rows are deflated at N = 139 / 139 / 155 / 155 / 161 (keyword, Llama, MiniLM, Haiku, Sonnet), as in
the Bug 15 run; the project's counts stay 139 / 155 / 161 / 163. The ten reruns are corrections of the
same ten configurations, not new trials; counting them would be stricter and would lower every deflated Sharpe ratio.

## 8. Scope, deviations, superseded files

- Only Strategy A was rerun. B, minute-bar C, momentum and the event study are unchanged and were only reconciled.
- The stale rule also fires on a one-day gap in the price file when that day is the position's exit day (BIIB,
  9 June 2023, keyword rung): the position exits at the previous close. This follows the written rule.
- Deviation in wording only: the harness log ends with "BUG 15 HARNESS RERUN COMPLETE" (script adapted from the
  Bug 15 harness); the run is the Bug 16 rerun.
- Superseded: the Strategy A rows and curves of every `…_bug15fix_2026-11-10` file (left in place, marked in
  `outputs/summary/README.md`). Current A files: `…_bug16fix_2026-11-10`; hashes in `FROZEN_RUN_outputs_hashes_bug16fix_2026-11-10.txt`.
- Thesis text: the statement that the best configuration is Llama A Kelly with Sharpe 1.08 against momentum 0.72
  (difference +0.34 ± 0.95, p 0.72, DSR(139) 0.13), with a training Sharpe of −0.44 (was −0.54), stands; 36 of 40
  configurations lose and 24 are significantly worse than momentum, unchanged.
