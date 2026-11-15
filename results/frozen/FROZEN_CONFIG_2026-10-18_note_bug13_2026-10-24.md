# Note to FROZEN_CONFIG_2026-10-18 — Bug 13 fix (Strategy C price basis), dated 24 October 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written 2026-10-24 15:49 CEST, BEFORE the fix is implemented or any corrected
result is computed.

## The bug

Strategy C enters at a 1-minute IEX bar price (Alpaca, `adjustment="split"`:
split- but not dividend-adjusted) and exits, with its stop/target checks, on
Bloomberg daily bars (split- and dividend-adjusted). Daily prices sit below the
entry by the dividends paid after the trade date. Effect (all scorers, every
year 2020–2024): shorts +0.25 to +0.68R, longs −0.17 to −0.47R.

## Method (no refetch)

One price basis: Bloomberg's split- and dividend-adjusted daily basis. For each
C trade, the minute-bar entry price is multiplied by the entry day's ratio
r = (Bloomberg daily close of the entry day) / (close of the last 1-minute bar
at or before 16:00 New York time on the entry day). Stop distance, stops,
targets and exits are already on the daily basis. If the entry day has no
minute bar within 10 minutes before 16:00 New York time, no reliable ratio
exists and the trade is dropped (counted). Applies to every C variant that
enters on minute bars (C baseline, C2, C3); C1 enters at the daily close and is
unchanged.

## Checks before anything is relied on

- Unit test: entry and exit on the same basis.
- **Placebo on TRAINING:** C with randomly assigned signal directions
  (`numpy.random.default_rng(20261024)`) must lose roughly its costs, with no
  significant long/short difference. If it does not, stop and report.
  Bug 13 is logged as closed only after the placebo passes.

## Correction run (disclosed)

C is re-run for all rungs (keyword, LLM, embeddings), training and test, with
its risk scale recalibrated on training with the fixed engine (same procedure,
`calibrate_risk.py`); A and B keep their official scales and results. The
corrected C engine also includes the Bug 12 fix. The invalid 18 October C rows
stay in the record, marked invalid; the corrected rows replace them in
`results.md`. Every C test-period run is logged in `outputs/test_period_runs.csv`.

## Fingerprint of the engine before the fix

| file | sha256 |
|---|---|
| `src/newsdrift/strategy_c.py` | `3d0849359136acf564b6a35bf6d07d75c6f4554e4d1d4dfbc05a372c7f15f024` |
