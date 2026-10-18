# Note to FROZEN_CONFIG_2026-10-18 — Bug 12 fix, dated 19 October 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).

## What changed and why

Bug 12 (`context/bugs.md`): when portfolio caps bind, the engines admitted
same-day (Strategy A) or same-time (replay: B, C, D, N) signals in input row
order, and that order was not deterministic across equivalent inputs. Fix:
a stable sort with an explicit tie-break — Strategy A by (date, ticker,
strength); the replay by (entry time, ticker, news time, strength,
R-multiple); signal and event tables sorted by (time, ticker). An optional
`tie_rank` column overrides the tie-break, for robustness checks only.
Regression test: `tests/test_order_invariance.py` (fails on the old code,
passes on the new).

## What this does NOT change

- **The 18 October test-period strategy runs remain the official results**
  (run with the previous code, fingerprinted in
  `FROZEN_CONFIG_2026-10-18_note_strategies.md`). The test period is not
  rerun as an official run.
- **The event study, and therefore H1, H2 and any H3, is unaffected:** it
  averages over all events with no caps, so its results do not depend on row
  order. Only the file fingerprints of `signals.py` and `backtest.py` in
  `FROZEN_CONFIG_2026-10-18.md` change, as listed below.
- Risk scales are not recalibrated.

## Robustness check (training only)

20 random orderings of tied signals (`tie_rank`), per strategy and scorer, on
the training period at the 18 October risk scales; the spread of Sharpe is
reported as the order noise floor of the official test results. Also checked:
whether Bug 12 explains the keyword D discrepancy.

## Fingerprints (SHA-256)

| file | before (used by the 18 Oct runs) | after (19 Oct fix) |
|---|---|---|
| `src/newsdrift/backtest.py` | `6311effbf980c74f2cceda6a2722894ae2f776bdafb9fb2ba921fd1d361c5464` | `8b3dd822883f3c8563d4adf94cb9d1ba3a69e1afde11c0ad45ca47854dd0330b` |
| `src/newsdrift/portfolio.py` | `3740611d8f2203f1d659bbe3ec832baec5c58586c3165084eba34cf71250f4a1` | `4ee88b1087dfab774473bd554314665b2afa25dbfa510bb6745e33f71cc2c4c1` |
| `src/newsdrift/signals.py` | `bca0e5f8e5c26e7e5528ac77deaa2e4a50f8c28a35bac2172dd89f29a5d49c1a` | `d5bdcaa9c787bf3de48c176eaa6a80ab8e75350c23bdaa3d2f014ffff5cfd043` |
| `src/newsdrift/open_close.py` | `9903377c3859b1731842349778482f7f6a7e5b304d20883df49b4aa0aabcd506` | `356197397c6528081689b00a1433fcb27aea391bc54f63a7d5fe6e1f56a35584` |
| `tests/test_order_invariance.py` | — | `a1e0527bcaf9d45d6c6a87dbce0466895410407e91577bdef7b791650bf993c9` |
