# Momentum benchmark corrections, dated 24 October 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written 2026-10-24 BEFORE any change or run, by decision of the author.

## Reason (code review of 24 Oct, `context/bugs.md`)

The runner restarts momentum in each period, so the benchmark holds nothing for
the first 90 trading days of the TEST period (2024-04-30 -> 09-10, 17% of
days; test Sharpe 1.07 over all days, 1.18 after the warm-up). Its 10% vol
target is per name divided by the ticker count, so realised vol is 2–3% p.a.,
which makes return and drawdown not comparable in level with the news
strategies (sized to a 5% training maxDD).

## Corrections

1. **Continuous momentum.** One momentum series from the first price date
   (2015-01-07) to 2026-06-01 on the runner's universe (the 171 tickers with
   prices and news), engine and parameters unchanged (90/5 lookback, 20-day
   vol, rebalance every 5 trading days, one-day lag, 2.43 bps per side on
   turnover). Training and test returns are slices of this one series, so the
   test period starts with its 90-day history (prices before the test start
   only). A truncation check asserts no look-ahead: the series computed on data
   cut at a date inside the test period is identical up to that date.
   Its test-period Sharpe is reported.
2. **Scaled momentum.** Positions multiplied by a scale k chosen on TRAINING by
   the same rule as the news strategies (`calibrate_risk.calibrate`: maxDD
   about 5%, same tolerance and search). Reported for return and drawdown on a
   comparable scale. Sharpe is unchanged by construction (daily returns scale
   by k); confirmed numerically.
3. **Comparisons rerun — momentum only.** Jobson-Korkie-Memmel Sharpe
   difference vs the continuous benchmark for every A and B strategy of the
   corrected 24 Oct runs (keyword, LLM, rung 1b), training and test, with the
   runner's `compare_strategies`; first checked to reproduce the existing
   comparison exactly with the old benchmark. The earlier strategy-vs-momentum
   rows (18 Oct and the 24 Oct Bug 14 correction) stay in the record, marked
   SUPERSEDED (benchmark flat for 90 days of the test period). Kelly − fixed,
   Holm and deflated Sharpe do not involve momentum and are unchanged.
   Logged in `outputs/test_period_runs.csv`.
4. **Disclosed limitations (not changed):** (a) weights are held constant
   between rebalances, i.e. the drift back to target weights is not priced;
   (b) rebalancing every 5 trading days, not on calendar weeks. The per-name
   vol scaling also stays; item 2 addresses comparability.

Code: `src/newsdrift/baseline.py` (before: `14842506f4acbb7685f07194e0072c03a26ae9679281aa6878019aef73487fb2`) gains an additive
`risk_scale` argument (default 1.0, unchanged); new `src/momentum_continuous.py`.
