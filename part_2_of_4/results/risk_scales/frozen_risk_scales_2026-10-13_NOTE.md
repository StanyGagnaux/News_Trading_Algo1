# Frozen risk scales, 13 October 2026

`frozen_risk_scales_2026-10-13_{keyword,llm}.csv` SUPERSEDE
`frozen_risk_scales_2026-10-11_{keyword,llm}.csv`.

Reason: Bug 10 (context/bugs.md). Strategy A's engine (newsdrift/backtest.py)
assigned ATR values by position to a filtered price table, so stops, targets
and sizes used other rows' / tickers' ATR, and the ATR included the entry
day's own high/low. Fixed 13 Oct 2026 (index-preserving, shifted one day);
test: tests/test_atr_alignment.py.

- Only the A_daily_1-3d rows changed. B and C rows are byte-identical to
  11 Oct (their engines compute volatility from prior bars and were unaffected).
- Calibrated on the training period only (2016-01-04 -> 2024-04-29), designed
  throttle, target in-sample maxDD 5%, with calibrate_risk.py.
- The 11 Oct files are kept unchanged (also copied to
  _archive/_backup_2026-10-13_before_atr_fix/). Do not use them.
