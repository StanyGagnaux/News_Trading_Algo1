# Strategy note to FROZEN_CONFIG_2026-10-18 — dated 18 October 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_strategies.txt`).
Frozen before any trading strategy is run on the test period with the fixed
engine. Amends nothing in the earlier frozen files (all 11 fingerprints
re-verified unchanged at freezing time).

## 1. Test-period run (2024-04-30 → 2026-06-01): what is run

- Runner `src/run_both_strategies.py` (fingerprint below), engine with the
  Bug 10 and Bug 11 fixes. One run per scorer, each logged in
  `outputs/test_period_runs.csv`; no parameter changes after seeing results.
- Strategies, every row reported, none selected: A daily 1–3d; B intraday
  t+5 and t+15; C hybrid — each with the fixed AND the Kelly sizer.
- **D and N: training-only**, not in the test run. Keyword D is not quoted
  anywhere until its open trade-count discrepancy is explained.
- Benchmark: time-series momentum (`newsdrift.baseline.momentum_backtest`),
  same universe and costs.
- Scorers: keyword (`KeywordScorer`); LLM =
  `news_scored_llm_ollama_anon_incl_test.csv` (fingerprint below).
- Costs: 2.43 bps per side (empirical half-spread 1.43 + commission 1.00).
- Risk scales: `outputs/risk_calibration_{keyword,llm}.csv` (training only,
  18 Oct 2026; ~5% training maxDD per strategy and sizer).
- **Drawdown governor: "designed" only** (5% probe floor, 60-day decaying
  peak). Realised maxDD is reported; 5% is a training target, not a guarantee.

## 2. Reported metrics (net of costs; training shown as a consistency check)

Annual return, Sharpe with Lo (2002) SE, maxDD, trades, hit rate.

**Deflated Sharpe ratio.** Number of trials = every configuration tried in
training, including runs on the pre-fix engines, counted per scorer from the
project records: runner rows (8 per scorer) in the August–September pre-fix
runs (16), the strict-governor runs (16), the 11 October full-size (16) and
calibrated runs (16), the keyword Tier-0 runs (8), the 13 October fixed-engine
recalibration of A (4) and the 18 October rerun (A and the LLM B/C rows with
anonymised scores: 10); Strategy B sweep (13 × 2 = 26); new-strategy sweep
of 13 October (7 × 2 = 14) and its 18 October rerun (9); the calibration
layer (4). **Total N = 139.** This is a documented lower bound: unlogged
exploratory runs in August–September are not countable. Primary DSR at
N = 139; **sensitivity at N = 25, 50 and 100**; null luck variance (1/T).

## 3. Benchmark comparison (pre-registered)

Each news strategy vs momentum on the **Sharpe difference**, with the
standard error of the difference: Jobson-Korkie (1981) with Memmel's (2003)
correction (`newsdrift.stats.sharpe_diff_test`), on daily returns over the
dates both series share; two-sided p. Assumes IID normal returns (no
autocorrelation correction; stated as a limitation). Each strategy's own
Sharpe SE is not used for the comparison.

## 4. H2b — Kelly vs fixed (pre-registered)

For each strategy and scorer: the Sharpe difference Kelly − fixed with the
same Jobson-Korkie-Memmel test as item 3, plus a paired t-test on the mean
daily return difference (Kelly − fixed) (`newsdrift.stats.paired_mean_diff`).
Average gross exposure for both sizers (`newsdrift.exposure`): sum of open
position notionals / equity per day (entry day through exit day), averaged
over all days of the period — to show whether a Kelly advantage comes from
holding less risk after losses. Validated on training only
(`outputs/validation_2026-10-18/`, training split 80/20, no test data).

## 5. Holdout

**No strategy is evaluated on the holdout.** The holdout (2026-06-02 →
2026-10-16) evaluates only the pre-registered H1 and H2
(`FROZEN_CONFIG_2026-10-18_note_2026-10-18.md`).

## 6. Commands

```
python3 src/run_both_strategies.py --risk-scales outputs/risk_calibration_keyword.csv --dd-governor designed --n-trials 139
python3 src/run_both_strategies.py --llm-scores data_sources/news_scored_llm_ollama_anon_incl_test.csv --risk-scales outputs/risk_calibration_llm.csv --dd-governor designed --n-trials 139
```

## 7. Fingerprints (SHA-256) at freezing time

| file | sha256 |
|---|---|
| `src/run_both_strategies.py` | `0e552bf72821da57f5ddfa24492e9dc1832502ca603232e962ae2accc6507b3a` |
| `src/newsdrift/stats.py` | `0c3c34c09203212ef9bec22754c7af16033bcbd63a76b2ae65cef1e8c0a9e012` |
| `src/newsdrift/exposure.py` | `5ce7f8bd8273212295c49141204df3626ddfbd5f714dd04c586ce64f71fad077` |
| `src/newsdrift/backtest.py` | `6311effbf980c74f2cceda6a2722894ae2f776bdafb9fb2ba921fd1d361c5464` |
| `src/newsdrift/portfolio.py` | `3740611d8f2203f1d659bbe3ec832baec5c58586c3165084eba34cf71250f4a1` |
| `src/newsdrift/intraday.py` | `219b1eec38e04dbdf1417086b5bbe2e28464f2ca5dde240e77985ab8447b3669` |
| `src/newsdrift/strategy_c.py` | `3d0849359136acf564b6a35bf6d07d75c6f4554e4d1d4dfbc05a372c7f15f024` |
| `src/newsdrift/risk.py` | `90d20ee15b207df8bcaa5c6e15046bfe8fbc580ea0090037d019594d938fa9af` |
| `src/newsdrift/config.py` | `4058a18c941597906041f05ff3ecf465a443776f9d39407b12772aea08e9df7a` |
| `src/newsdrift/signals.py` | `bca0e5f8e5c26e7e5528ac77deaa2e4a50f8c28a35bac2172dd89f29a5d49c1a` |
| `src/newsdrift/baseline.py` | `50a6eade2c38cd276dffc51a02e5a45d2e2f7c40c84e655b472c3a64b448dc0c` |
| `outputs/risk_calibration_keyword.csv` | `da42a1ff2a05e6ff1c6ba0f87d97762e7525a385a0330992441b8631daf5db5b` |
| `outputs/risk_calibration_llm.csv` | `131665fe5794ba209e986d4cc64dbf495bb7c673539fa942ae8b2ed35b02e285` |
| `data_sources/news_scored_llm_ollama_anon_incl_test.csv` | `802ca65246888e157bee826293616435dc05d27f70b5702e0bd4a706fc397071` |
