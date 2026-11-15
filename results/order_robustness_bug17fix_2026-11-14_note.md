# Signal-order robustness on the Bug 17 engine — note of 14 November 2026

Descriptive, training period only (4 January 2016 to 29 April 2024); no test-period data read; nothing tuned. Run on
the author's instruction of 14 November 2026, after the Bug 17 correction run.

**File:** `order_robustness_bug17fix_2026-11-14.csv` (SHA-256 `efc2d079…e822b3c1`), log `order_robustness_bug17fix_2026-11-14.log`.
**Script:** `src/order_robustness_bug17fix_2026-11-14.py`, a dated copy of `src/order_robustness.py`. The October
script was not run and `order_robustness_2026-10-19.csv` (`cb2a6d4a…`) is unchanged and stays in place.

**What it does:** as in October, for each row the deterministic result and 20 random orderings of same-day signals
(seed 20261019 + k). Differences to October: Strategy A uses the scales of the Bug 17 run, read from
`for_claude/risk_calibration_{keyword,llm}_bug17fix_2026-11-14.csv` (keyword 0.0104 / 0.0062, Llama 0.0187 / 0.0204);
B, C and D use the 18 October scale files the October run read (`outputs/risk_calibration_{keyword,llm}.csv`,
SHA-256 pinned in the script: `da42a1ff…`, `131665fe…`; there is no copy of them in `for_claude/`); one added
column, `risk_scale`.

## Strategy A (the cells Section 4.10 cites): standard deviation of the training Sharpe ratio over 20 orderings

| rung | sizer | October (engine and scales of 18 Oct) | Bug 17 engine and scales | range over the orderings, Bug 17 | deterministic, Bug 17 |
|---|---|---|---|---|---|
| keyword | fixed | 0.000 | 0.000 | −0.653 to −0.653 | −0.653 |
| keyword | Kelly | 0.090 | 0.038 | −0.467 to −0.317 | −0.418 |
| Llama | fixed | 0.000 | 0.000 | −0.131 to −0.131 | −0.131 |
| Llama | Kelly | 0.041 | 0.029 | −0.217 to −0.077 | −0.092 |

The fixed rows do not depend on the order (standard deviation below 1e-13). The Kelly rows still do, less than in
October. The cause was not isolated here; it is consistent with the order in which trades closed on the same day
enter the Kelly window of 40 trades, which still follows the signal order (the sizes of day d themselves no longer
use results of day d since Bug 15). The deterministic results equal the training cells of the Bug 17 run
(−0.6535, −0.4183, −0.1314, −0.0920).

## Strategies B, C and D

- **Not touched by Bug 17:** the same script was run on the engine as it stood before the Bug 17 fix (backup of
  14 November). All 13 B, C and D rows are identical between the two engines (largest difference over all cells 0.0).
- **Against the October file:** D (keyword) is identical in every cell. **B and C are not**, and cannot be: their
  engines were changed on 24 October, after the October check (Bug 14 fill rule in `intraday.py` and `risk.py`;
  Bug 13 in `strategy_c.py`). Example: keyword B t+5 fixed −5.38 now against −4.85 in October; the standard
  deviations over the orderings are of the same size as in October (B 0.05 to 0.31, was 0.05 to 0.27; C 0.14 to
  0.31, was 0.10 to 0.28). The C rows are those of the daily-bar engine that Bug 13 invalidated; they are kept for
  comparison only and are not the minute-bar C of the thesis.

The control file and its log are in `outputs/correction_bug17fix_2026-11-14/order_robustness/`.
