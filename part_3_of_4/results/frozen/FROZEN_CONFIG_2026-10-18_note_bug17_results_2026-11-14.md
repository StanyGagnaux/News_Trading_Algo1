# Bug 17 — results of the acceptance tests and of the disclosed correction run, dated 14 November 2026

Written 2026-11-14 (Zurich) after the run specified in `FROZEN_CONFIG_2026-10-18_note_bug17_2026-11-14.md`
(SHA-256 `e96e94d7…526c72cc`, written and registered before any change) and its addendum
`…_note_bug17_addendum_testC_2026-11-14.md` (`705714f1…7f1298b`, written on the author's decision before the tests
continued). Specification files: `review_2026-11-14/BUG17_note_2026-11-14.md` (`964ad2d4…`) and
`BUG17_reference_2026-11-14.md` (`d56f0993…`). Bug 17 was found by the external review after the freeze of
18 October 2026. One run per configuration; every result is reported regardless of outcome. Trial counts
unchanged: 139 / 155 / 161 / 163 (the exploratory Strategy F is trial 164).

## 1. Diagnosis and fix (as specified)

Strategy A (`src/newsdrift/backtest.py`) ran, for each day d, the exits of d, then the mark to market, then the
entries at the open of d, and it tested those entries against the book as it stood after the exits. A ticker held
at the open of d and closed during d was entered again at the open of d; the gross-exposure cap was judged on the
book after the day's exits; an entry closed on its entry day did not count for the later tickers of the same open.
In the official runs of 10 November, 3.7% to 25.2% of the training trades and 5.7% to 37.4% of the test-period
trades were entered on the exit day of the previous trade in the same ticker. Most follow a scheduled time exit
(a double position in one ticker for one day, no future information); 9% to 29% in training follow a stop or a
target hit during d (a look-ahead in admission). Fix, one rule: the entry step sees a snapshot of the book taken
at the close of d−1, before the exits of d, plus its own orders of this open. A ticker in the snapshot is not
entered at d; gross = notional in the snapshot + notional admitted earlier at this open, still open or not.
Three runtime assertions; new sizing-log column `gross_at_decision`. Direction, entry price, stop, target, size,
fills, stale exits and costs are unchanged. Engine hash before `fbf1e857…` (Bug 16 version), after `424ae4ef…`.
B, C and the momentum benchmark are separate engines and are unchanged.

One detail beyond the five reference lines of the specification: a ticker already ordered at this open is skipped (the
reference asserts instead). Signals are unique per day and ticker; the ten reference cells are reproduced exactly
(Section 2, test A).

## 2. Acceptance tests

The correction was **stopped once**, at test C, and resumed on the author's decision (addendum): the fixture of
section 2 of `tests/test_bug15_sizing_lag.py` held five positions (87,531 notional) that all closed on day d and
needed 17,506 more for the entry of d, against a gross cap of 100,000; it relied on the defect and failed on the
corrected engine. The fixture was given room under the cap (`max_gross_exposure=2.0` in `fixed_case`; file
`93427590…` → `a8c00760…`); the changed test passes 19 of 19 on the corrected engine and on the engine of
10 November and still fails 10 of 18 on the engine before the Bug 15 fix. Record:
`outputs/correction_bug17fix_2026-11-14/STOP_at_test_C_2026-11-14.md`.

| test | result |
|---|---|
| C, unit test `tests/test_bug17_admission_snapshot.py` | engine of 10 November: each of the three cases fails (6 of 12 checks); corrected engine: 13 of 13 |
| C, all test files | first attempt 15 of 16 existing files (stop, see above); with the approved fixture 17 of 17 |
| D, perturbation (high, low, close of every ticker on day d replaced by the open), keyword and Llama, fixed and Kelly, 100 stop-or-target days + 50 random days each | engine of 10 November: keyword 25 of 100 and 6 of 50 days with different entries, Llama 44 of 100 and 11 of 50, the same for both sizers; corrected engine: 0 of 600 days (6,526 entries compared) |
| A, ten training cells of the reference implementation at the Bug 16 scales, official pipeline | 10 of 10: return, Sharpe and maximum drawdown differ by exactly 0, trades exact, including Haiku Kelly and Sonnet Kelly where the gross cap binds (1 and 6 days) |
| B (1) on the official training logs of 10 November: trades entered on the exit day of the previous trade in the ticker | fails as required with exactly the reference counts: keyword 6,150; Llama 4,241; MiniLM 5,351; Haiku 1,046; Sonnet 184 (fixed) and 183 (Kelly) |
| B (1) and (2) on the ten training logs of the corrected engine | 0 such entries; 0 entries above the gross cap judged on the previous close's book; the engine's logged gross equals the recomputed one (largest difference 7e-11) |
| E, Bug 15 strict sizing assertion, corrected engine, training | 20 of 20, 0 violations (146,229 sizing calls) |
| E, Bug 16 reconciliation, corrected engine, training | 10 of 10, 0 failing days (largest residual 1.4e-9 on 100,000) |
| E, placebos on the corrected engine, training, keyword signals, before the run (Kelly scale 0.0041) | fixed sizer 0.62 SE from the expected cost: pass; Kelly, random directions: (i) 0.62 SE, (ii) −1.04 bps (−0.45 SE): pass; common direction +1.16 bps (0.23 clustered SE) long, −3.10 (−0.45) short: within +2 clustered SE |

Correction to the checker of B, made before the run and disclosed here: its first version compared the reference
counts with all opened positions, which include those still open at the end of training (entered on 26 and
29 April 2024: 11, 3, 14, 3 for keyword, Llama, MiniLM, Haiku), and flagged four rungs as not matching. The
criterion is written on trades; the checker now compares the trades of the trade log with the reference and
reports the wider count beside it. The criterion was not changed; the first output is kept
(`acceptance/acceptance_results_first_checker_version.jsonl`).

## 3. The ten rows at 5%, Bug 16 run → Bug 17 run

Training period (calibration to a 5% training drawdown, ±0.25 pp, unchanged mechanical rule):

| rung | sizer | scale | return p.a. | Sharpe | max drawdown | trades |
|---|---|---|---|---|---|---|
| keyword | fixed | 0.0079 → 0.0104 | -0.523% → -0.535% | -0.736 → -0.653 | 5.09% → 5.03% | 25,089 → 20,599 |
| keyword | kelly | 0.0041 → 0.0062 | -0.460% → -0.404% | -0.594 → -0.418 | 5.08% → 5.23% | 25,089 → 20,599 |
| Llama | fixed | 0.0145 → 0.0187 | -0.216% → -0.187% | -0.174 → -0.131 | 5.04% → 5.01% | 21,869 → 19,088 |
| Llama | kelly | 0.0122 → 0.0204 | -0.407% → -0.121% | -0.437 → -0.092 | 5.23% → 4.86% | 21,869 → 19,088 |
| MiniLM | fixed | 0.0037 → 0.0049 | -0.590% → -0.586% | -1.133 → -0.982 | 5.10% → 5.09% | 21,217 → 18,188 |
| MiniLM | kelly | 0.0027 → 0.0033 | -0.613% → -0.608% | -0.765 → -0.750 | 5.25% → 5.20% | 21,217 → 18,188 |
| Haiku | fixed | 0.0201 → 0.0198 | -0.560% → -0.571% | -0.593 → -0.640 | 5.04% → 5.03% | 10,999 → 10,222 |
| Haiku | kelly | 0.0363 → 0.0274 | -0.529% → -0.597% | -0.498 → -0.798 | 5.02% → 4.98% | 10,999 → 10,222 |
| Sonnet | fixed | 0.0361 → 0.0384 | -0.259% → -0.236% | -0.233 → -0.202 | 5.07% → 5.06% | 5,039 → 4,892 |
| Sonnet | kelly | 0.1294 → 0.1333 | +0.107% → +0.163% | +0.048 → +0.071 | 4.32% → 5.08% | 5,028 → 4,857 |

Test period (one run):

| rung | sizer | scale | return p.a. | Sharpe | max drawdown | trades |
|---|---|---|---|---|---|---|
| keyword | fixed | 0.0079 → 0.0104 | -1.385% → -1.554% | -1.218 → -1.255 | 4.02% → 4.32% | 12,076 → 9,281 |
| keyword | kelly | 0.0041 → 0.0062 | -2.144% → -2.493% | -1.362 → -1.454 | 5.33% → 6.07% | 12,076 → 9,281 |
| Llama | fixed | 0.0145 → 0.0187 | -0.191% → +0.017% | -0.119 → +0.010 | 3.31% → 2.93% | 8,093 → 6,815 |
| Llama | kelly | 0.0122 → 0.0204 | +0.990% → +1.792% | +1.075 → +1.298 | 1.22% → 1.47% | 8,093 → 6,815 |
| MiniLM | fixed | 0.0037 → 0.0049 | -1.289% → -1.197% | -2.097 → -1.778 | 2.68% → 2.47% | 8,201 → 6,662 |
| MiniLM | kelly | 0.0027 → 0.0033 | -0.676% → -0.436% | -1.179 → -0.790 | 1.45% → 1.03% | 8,201 → 6,662 |
| Haiku | fixed | 0.0201 → 0.0198 | -1.558% → -1.355% | -1.173 → -1.115 | 3.67% → 3.19% | 4,366 → 3,901 |
| Haiku | kelly | 0.0363 → 0.0274 | -1.742% → -0.721% | -1.553 → -0.899 | 3.70% → 1.81% | 4,366 → 3,901 |
| Sonnet | fixed | 0.0361 → 0.0384 | -1.370% → -1.292% | -1.089 → -0.976 | 3.45% → 3.14% | 1,908 → 1,824 |
| Sonnet | kelly | 0.1294 → 0.1333 | -2.948% → -3.253% | -1.393 → -1.446 | 6.45% → 7.33% | 1,907 → 1,818 |

Reading. The correction removes the re-entries: 13% to 18% of the training trades of the free rungs (7% Haiku,
3% Sonnet) and 16% to 23% of their test-period trades (11% Haiku, 4% to 5% Sonnet). With fewer positions the
training drawdown at the old scales falls, so the recalibrated scales of the free rungs rise by a fifth to two thirds
(keyword fixed 0.0079 → 0.0104, Llama Kelly 0.0122 → 0.0204); Haiku Kelly falls (0.0363 → 0.0274).
Test-period Sharpe ratios move by −0.09 to +0.65. In the superseded run the removed trades were worse than the
rest in the test period in every rung (mean R-multiple of the re-entries against the other trades: keyword
−0.022 / −0.013, Llama −0.021 / −0.000, MiniLM −0.068 / −0.041, Haiku −0.051 / −0.020, Sonnet −0.060 / −0.027),
which is the direction in which most rows move. Llama A Kelly rises from 1.08 to 1.30 (+0.99% → +1.79% p.a.) and
Llama A fixed from −0.12 to +0.01; Haiku A Kelly from −1.55 to −0.90; MiniLM Kelly from −1.18 to −0.79; keyword
fixed and Kelly and Sonnet Kelly become slightly worse. The best row became better after a correction, so it was
checked before being reported: the engine equals an independent reference implementation to the last digit on the
training period, and assertion B, the Bug 15 assertion and the reconciliation hold on the test-period logs
(Section 6). The result remains statistically indistinguishable from momentum (Section 4) and its training
Sharpe ratio is −0.09. No training row turns positive that was negative; Sonnet Kelly stays the only positive
one (+0.07).

## 4. Tests on the corrected rows (test period, 5%)

Against the stored continuous momentum series (`outputs/momentum_continuous_equity_2026-10-24.csv`):

| rung | sizer | Sharpe | difference to momentum ± SE | p | DSR (N) | difference in the Bug 16 run |
|---|---|---|---|---|---|---|
| keyword | fixed | -1.255 | -1.993 ± 0.824 | 0.0156 | 0.0000 (139) | -1.956 (p 0.0152) |
| keyword | kelly | -1.454 | -2.198 ± 0.933 | 0.0185 | 0.0000 (139) | -2.103 (p 0.0229) |
| Llama | fixed | +0.010 | -0.716 ± 0.893 | 0.4224 | 0.0045 (139) | -0.845 (p 0.3397) |
| Llama | kelly | +1.298 | +0.559 ± 0.959 | 0.5600 | 0.2020 (139) | +0.340 (p 0.7209) |
| MiniLM | fixed | -1.778 | -2.520 ± 1.080 | 0.0196 | 0.0000 (155) | -2.842 (p 0.0086) |
| MiniLM | kelly | -0.790 | -1.524 ± 1.043 | 0.1440 | 0.0001 (155) | -1.915 (p 0.0686) |
| Haiku | fixed | -1.115 | -1.851 ± 0.971 | 0.0567 | 0.0000 (155) | -1.910 (p 0.0482) |
| Haiku | kelly | -0.899 | -1.632 ± 0.939 | 0.0820 | 0.0000 (155) | -2.295 (p 0.0167) |
| Sonnet | fixed | -0.976 | -1.710 ± 0.943 | 0.0699 | 0.0000 (161) | -1.825 (p 0.0540) |
| Sonnet | kelly | -1.446 | -2.193 ± 0.902 | 0.0150 | 0.0000 (161) | -2.138 (p 0.0188) |

Kelly against fixed, Holm within the families of 18 October:

| family | rung | Kelly − fixed ± SE | p | Holm p | gross exposure Kelly / fixed |
|---|---|---|---|---|---|
| H2b_family_6 | keyword | -0.205 ± 0.619 | 0.7404 | 0.7404 | 0.101 / 0.130 |
| H2b_family_6 | Llama | +1.275 ± 0.637 | 0.0454 | 0.0909 | 0.100 / 0.185 |
| rung1b_family_3 | MiniLM | +0.996 ± 0.589 | 0.0907 | 0.0907 | 0.023 / 0.055 |
| rung2_family_3 | Haiku | +0.218 ± 0.646 | 0.7354 | 0.7354 | 0.052 / 0.115 |
| rung3_family_3 | Sonnet | -0.483 ± 0.628 | 0.4414 | 1.0000 | 0.080 / 0.092 |

Rung comparisons on A Kelly (descriptive):

- rung 1 (llm_anon) minus rung 0 (keyword): +2.757 ± 0.867 (p 0.0015); Bug 16 run +2.443 (p 0.0056)
- rung 1b (embed_minilm) minus rung 1 (llm_anon): -2.083 ± 1.038 (p 0.0448); Bug 16 run -2.255 (p 0.0306)
- rung 2 (haiku) minus rung 1b (embed_minilm): -0.109 ± 0.984 (p 0.9120); Bug 16 run -0.380 (p 0.6959)
- rung 3 (sonnet) minus rung 2 (haiku): -0.561 ± 0.728 (p 0.4414); Bug 16 run +0.157 (p 0.8375)

Recounts over the forty configurations (A rows new; B and C carried over unchanged):

| item | Bug 16 run | Bug 17 run |
|---|---|---|
| configurations | 40 | 40 |
| losing_in_test | 36 | 35 |
| significantly_worse_than_momentum_5pct | 24 | 22 |
| largest_p_among_significantly_worse | 0.0484 | 0.0484 |
| smallest_p_not_significant | 0.0540 | 0.0567 |
| better_than_momentum_point_estimate | 2 | 2 |
| se_sharpe_diff_min | 0.8058 | 0.8238 |
| se_sharpe_diff_max | 1.0813 | 1.0798 |
| training_maxDD_min | 0.0432 | 0.0449 |
| training_maxDD_max | 0.0525 | 0.0525 |
| best_keyword | C_minute_multiday_fixed; Sharpe -0.4208; DSR 0.000606 (N 139); vs momentum -1.1514, p 0.2047 | C_minute_multiday_fixed; Sharpe -0.4208; DSR 0.000606 (N 139); vs momentum -1.1514, p 0.2047 |
| best_llm | A_daily_1-3d_kelly_llm; Sharpe 1.0753; DSR 0.131359 (N 139); vs momentum +0.3403, p 0.7209 | A_daily_1-3d_kelly_llm; Sharpe 1.2981; DSR 0.201982 (N 139); vs momentum +0.5591, p 0.5600 |
| best_embed_minilm | C_minute_multiday_kelly_llm; Sharpe -1.0302; DSR 0.000000 (N 155); vs momentum -1.7785, p 0.0759 | A_daily_1-3d_kelly_llm; Sharpe -0.7904; DSR 0.000055 (N 155); vs momentum -1.5237, p 0.1440 |
| best_haiku | C_minute_multiday_kelly_llm; Sharpe 0.7577; DSR 0.044688 (N 155); vs momentum +0.0559, p 0.9554 | C_minute_multiday_kelly_llm; Sharpe 0.7577; DSR 0.044688 (N 155); vs momentum +0.0559, p 0.9554 |
| best_sonnet | C_minute_multiday_kelly_llm; Sharpe 0.2303; DSR 0.010672 (N 163); vs momentum -0.4353, p 0.6653 | C_minute_multiday_kelly_llm; Sharpe 0.2303; DSR 0.010672 (N 163); vs momentum -0.4353, p 0.6653 |

Changes in the counts: 35 of 40 configurations lose (36 before; Llama A fixed is now at +0.02% p.a.), and 22 are
significantly worse than momentum at 5% (24 before; Haiku A fixed moves from p 0.048 to 0.057 and Haiku A Kelly
from 0.017 to 0.082). Llama Kelly against fixed has p 0.045 unadjusted and 0.091 after Holm: not significant.
The best MiniLM configuration is now A Kelly (−0.79) instead of minute-bar C Kelly (−1.03).

## 5. 20% sensitivity (descriptive)

Training:

| rung | sizer | scale | return p.a. | Sharpe | max drawdown | trades |
|---|---|---|---|---|---|---|
| keyword | fixed | 0.0335 → 0.046 | -2.244% → -2.375% | -0.744 → -0.655 | 20.11% → 20.43% | 25,089 → 20,582 |
| keyword | kelly | 0.0187 → 0.0261 | -2.066% → -1.884% | -0.587 → -0.497 | 20.90% → 20.03% | 25,032 → 19,950 |
| Llama | fixed | 0.0606 → 0.077 | -1.035% → -1.197% | -0.200 → -0.209 | 20.09% → 20.12% | 21,869 → 18,783 |
| Llama | kelly | 0.0496 → 0.1059 | -1.666% → -1.167% | -0.454 → -0.204 | 19.65% → 20.91% | 21,825 → 17,933 |
| MiniLM | fixed | 0.016 → 0.0211 | -2.552% → -2.534% | -1.134 → -0.986 | 20.45% → 20.37% | 21,217 → 18,188 |
| MiniLM | kelly | 0.0112 → 0.0135 | -2.567% → -2.489% | -0.772 → -0.751 | 20.38% → 20.07% | 21,216 → 18,175 |
| Haiku | fixed | 0.0845 → 0.0832 | -2.408% → -2.463% | -0.606 → -0.658 | 19.79% → 20.00% | 10,998 → 10,190 |
| Haiku | kelly | 0.1763 → 0.1755 | -2.583% → -1.700% | -0.558 → -0.380 | 20.69% → 14.85% | 10,780 → 9,814 |
| Sonnet | fixed | 0.1577 → 0.1594 | -1.438% → -1.404% | -0.298 → -0.297 | 20.76% → 20.43% | 5,028 → 4,806 |
| Sonnet | kelly | 0.8404 → 0.6028 | +0.596% → -0.031% | +0.067 → -0.004 | 20.57% → 17.53% | 4,689 → 4,422 |

Test:

| rung | sizer | scale | return p.a. | Sharpe | max drawdown | trades |
|---|---|---|---|---|---|---|
| keyword | fixed | 0.0335 → 0.046 | -5.859% → -6.747% | -1.213 → -1.229 | 16.15% → 17.81% | 12,076 → 9,263 |
| keyword | kelly | 0.0187 → 0.0261 | -8.685% → -5.967% | -1.334 → -1.029 | 20.78% → 15.49% | 12,028 → 8,882 |
| Llama | fixed | 0.0606 → 0.077 | -1.018% → +2.524% | -0.151 → +0.366 | 13.39% → 8.27% | 8,092 → 6,650 |
| Llama | kelly | 0.0496 → 0.1059 | +3.413% → +4.501% | +0.923 → +0.741 | 4.87% → 7.23% | 8,082 → 6,426 |
| MiniLM | fixed | 0.016 → 0.0211 | -5.496% → -5.092% | -2.068 → -1.758 | 11.16% → 10.26% | 8,201 → 6,662 |
| MiniLM | kelly | 0.0112 → 0.0135 | -2.806% → -1.799% | -1.179 → -0.797 | 5.92% → 4.17% | 8,201 → 6,662 |
| Haiku | fixed | 0.0845 → 0.0832 | -6.498% → -5.424% | -1.163 → -1.054 | 14.74% → 12.44% | 4,366 → 3,871 |
| Haiku | kelly | 0.1763 → 0.1755 | -6.798% → -3.048% | -1.288 → -0.666 | 14.03% → 6.42% | 4,319 → 3,780 |
| Sonnet | fixed | 0.1577 → 0.1594 | -5.740% → -5.658% | -1.044 → -1.028 | 13.94% → 12.22% | 1,903 → 1,769 |
| Sonnet | kelly | 0.8404 → 0.6028 | -11.777% → -11.338% | -1.193 → -1.620 | 24.12% → 22.53% | 1,808 → 1,736 |

| rung | sizer | Sharpe 5% → 20% | cap-binding days 5% / 20% | p vs momentum 5% / 20% | material |
|---|---|---|---|---|---|
| keyword | fixed | -1.255 → -1.229 | 0.00% / 1.53% | 0.0156 / 0.0165 | no |
| keyword | kelly | -1.454 → -1.029 | 0.00% / 11.11% | 0.0185 / 0.0562 | yes |
| Llama | fixed | +0.010 → +0.366 | 0.00% / 9.00% | 0.4224 / 0.7061 | yes |
| Llama | kelly | +1.298 → +0.741 | 0.00% / 15.33% | 0.5600 / 0.9826 | yes |
| MiniLM | fixed | -1.778 → -1.758 | 0.00% / 0.00% | 0.0196 / 0.0194 | no |
| MiniLM | kelly | -0.790 → -0.797 | 0.00% / 0.00% | 0.1440 / 0.1430 | no |
| Haiku | fixed | -1.115 → -1.054 | 0.00% / 2.11% | 0.0567 / 0.0637 | no |
| Haiku | kelly | -0.899 → -0.666 | 0.00% / 6.13% | 0.0820 / 0.1513 | yes |
| Sonnet | fixed | -0.976 → -1.028 | 0.00% / 3.45% | 0.0699 / 0.0610 | no |
| Sonnet | kelly | -1.446 → -1.620 | 0.57% / 8.05% | 0.0150 / 0.0122 | no |

Four rows are flagged material by the rule of 25 October (change of the Sharpe ratio above 0.20): keyword Kelly
(−1.45 → −1.03), Llama fixed (+0.01 → +0.37), Llama Kelly (+1.30 → +0.74) and Haiku Kelly (−0.90 → −0.67); in the
Bug 16 run only Haiku Kelly was. At 20% the exposure caps bind on 6% to 15% of the test days for the Kelly rows of
keyword, Llama and Haiku. Two 20% calibrations ended away from the target because the search (six steps, unchanged)
did not converge for the Kelly sizer, whose drawdown is not monotone in the scale: Haiku Kelly 14.2% at the search
scale (14.9% in the run, at the scale rounded to four decimals) and Sonnet Kelly 17.5%. Both are reported as they
are.

## 6. Checks after the run

- Assertion B on the logs of the run (ten configurations × two periods × two targets): 40 of 40 for (1) and 40 of
  40 for (2); 402,283 positions, none opened on a day on which an earlier position in its ticker was held or
  closed; no entry above the gross cap (largest use 99.997% of the cap); 408,142 logged gross figures equal the
  recomputed ones.
- Bug 15 strict assertion: 80 of 80, 0 violations (401,447 trades; 408,142 sizing calls).
- Reconciliation: 40 of 40, 0 failing days, largest residual 1.6e-9; 401,447 booked trades, 64 stale exits, 836
  positions open at a period end, none left open in a ticker that stopped trading.
- Placebos as official files at the recalibrated keyword Kelly scale 0.0062 (fixed sizer 0.0049, as on 24 Oct):
  fixed sizer mean R −0.0067 against −0.0091 expected, 0.62 SE; Kelly with random directions (i) 0.62 SE,
  (ii) −1.04 bps (−0.44 SE, −0.40 clustered); common direction +0.91 bps (0.18 clustered SE) all long, −3.09
  (−0.45) all short. All pass.
- Harness rerun (`exploratory_B_exit/verification/`, fresh sandbox `sandbox_bug17_2026-11-14/`): 204 of 204 files
  reproduce with 0 differing cells; 17 of 17 test files; 461 assertions, 457 pass. The four that fail are
  calibration findings of the known kind and change no reported number: training drawdown outside the 4.5–5.2%
  band for keyword Kelly (5.23%) and MiniLM Kelly (5.20%); outside the 19–21% band for Haiku Kelly (14.85%) and
  Sonnet Kelly (17.53%), see Section 5; and the calibration record against the run at 5% and at 20% (record
  taken at the unrounded search scale; finding 4 of 8 Nov; at 20% the largest gap is 0.66 pp, Haiku Kelly). See
  `verification_summary_2026-11-14_bug17.md`.

## 7. Trial counts

Unchanged, as the author has decided so far: the A rows are deflated at N = 139 / 139 / 155 / 155 / 161 (keyword,
Llama, MiniLM, Haiku, Sonnet); the project's counts stay 139 / 155 / 161 / 163, the exploratory Strategy F is
trial 164. The reruns are corrections of the same ten configurations. Counting the thirty reruns of the Bug 15,
16 and 17 corrections as trials would be stricter and would lower every deflated Sharpe ratio, including the 0.20
of Llama A Kelly.

## 8. Scope, deviations, superseded files, registers

- Only Strategy A was rerun. B, minute-bar C, momentum and the event study are unchanged.
- Deviations from the pre-run note: the stop at test C and the approved fixture change (addendum); the corrected
  comparison in the checker of B (Section 2). No criterion or tolerance was changed.
- `order_robustness.py`, `sweep_new_strategies.py`, `sensitivity_dd20.py` and `calibrate_scorer.py` were not
  rerun; their recorded outputs predate the fix.
- Superseded: the Strategy A rows and curves of every `…_bug16fix_2026-11-10` file (left in place, marked in
  `outputs/summary/README.md`). Current A files: `…_bug17fix_2026-11-14`; hashes in
  `FROZEN_RUN_outputs_hashes_bug17fix_2026-11-14.txt`.
- Hash registers: after the run the registers of the Bug 15, Bug 16 and Bug 17 runs are regenerated in that
  order, so that every line of each verifies against the files in `outputs/summary/`. The digests of the three
  registers before and after are recorded in `outputs/correction_bug17fix_2026-11-14/REGISTER_DIGESTS_2026-11-14.txt`,
  a file that no register lists (a register cannot hold its own digest, and this note is itself registered).
- Thesis text: the best configuration is still Llama A Kelly, now with a test-period Sharpe ratio of 1.30
  (+1.8% p.a.) against continuous momentum (difference +0.56 ± 0.96, p 0.56, DSR(139) 0.20); its training Sharpe
  ratio is −0.09 (was −0.44). 35 of the 40 configurations lose and 22 are significantly worse than momentum
  (were 36 and 24). No configuration beats momentum significantly; the conclusion of the thesis does not change.
  The 20% paragraph needs rewriting from `sensitivity_dd20_summary_bug17fix_2026-11-14.csv` (four rows material;
  Llama A Kelly 1.30 → 0.74).
