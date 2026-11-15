[README.md](https://github.com/user-attachments/files/34884377/README.md)
# News-Driven Automated Trading versus Traditional Systematic Strategies

MSc Banking & Finance thesis, ZHAW — code and results repository.
Supervisor: Prof. Martin Schnauss. State: 14 November 2026 (final evaluation:
training period + test period; configuration frozen 18 October 2026; Strategy A
corrected last on 14 November 2026, Bug 17).

## What the thesis tests

Can company news be turned into a systematic trading strategy that survives
transaction costs, position sizing, stops and a drawdown limit — and does a
large language model (LLM) read news better than a keyword dictionary?

The target is the post-news **drift** (from the first tradable price after
the news), not the initial spike, which high-frequency traders own.

- **Universe:** every Nasdaq-100 member 2015–2026 (193 tickers,
  survivorship-controlled).
- **News:** Benzinga via Alpaca, 476,916 headline-ticker rows, 2015-09 → 2026-06.
- **Scorers (five rungs):** a Loughran-McDonald-style keyword dictionary;
  `llama3.2:3b` (local Ollama, temperature 0.2, company names anonymised);
  MiniLM sentence embeddings; Claude Haiku and Claude Sonnet. Haiku and Sonnet
  are **exposed to look-ahead** (both models were released after the end of
  the sample, so their training data may cover it); their rows are reported
  for comparison only. Each scorer outputs a strength
  in [−1, 1], a duration of 1–3 days and (LLMs) an importance.
- **Splits:** training 2016-01-04 → 2024-04-29, test 2024-04-30 → 2026-06-01.
  A holdout was pre-registered but dropped by decision before any holdout
  return was computed; the official evaluation is training plus test.

## Main results

Event study on the daily signals (one event per ticker and entry day).
Signed returns in basis points, market-adjusted (minus Nasdaq-100), gross of
costs, t-statistics clustered by date. Round-trip cost 4.86 bps.

| | news day (not traded) | day 1 | day 2 | day 3 | day 5 |
|---|---|---|---|---|---|
| keyword, training | +57.8 (t 21.2) | −2.8 | −5.2 | −5.6 | −7.2 |
| LLM, training | +60.6 (t 25.0) | −2.0 | −4.4 | −2.4 | −2.4 |
| keyword, test | +62.7 (t 15.8) | +0.6 | −1.7 | −0.8 | +6.4 |
| LLM, test | +78.2 (t 17.6) | +6.2 (t 2.1) | −0.3 | −0.4 | +0.2 |

The price reaction happens on the news day; from the next open there is no
drift above trading costs for either scorer, in training or test. With
standard errors clustered by week or month instead of by entry date, all eight
training bounds stay below the cost
(`results/event_study/descriptive_event_study_clustering_train_2026-11-14.csv`).

**Trading strategies, test period, net of costs** (annual return / Sharpe
ratio; one run per configuration; position size scaled on the training period
to a 5% maximum drawdown). Forty configurations: five scorers × eight
strategies.

| strategy | keyword | Llama | MiniLM | Haiku (exposed) | Sonnet (exposed) |
|---|---|---|---|---|---|
| A daily drift, fixed | −1.6% / −1.25 | +0.0% / +0.01 | −1.2% / −1.78 | −1.4% / −1.11 | −1.3% / −0.98 |
| A daily drift, Kelly | −2.5% / −1.45 | **+1.8% / +1.30** | −0.4% / −0.79 | −0.7% / −0.90 | −3.3% / −1.45 |
| B intraday t+5 min, fixed | −2.6% / −8.38 | −1.9% / −8.96 | −1.9% / −8.62 | −1.9% / −3.75 | −1.4% / −1.41 |
| B intraday t+5 min, Kelly | −2.0% / −4.05 | −1.9% / −5.20 | −1.4% / −6.07 | −1.9% / −1.48 | −1.9% / −1.84 |
| B intraday t+15 min, fixed | −2.5% / −4.47 | −1.4% / −4.59 | −1.4% / −4.33 | −2.3% / −2.66 | −0.4% / −0.23 |
| B intraday t+15 min, Kelly | −1.9% / −1.70 | −1.7% / −2.12 | −1.8% / −2.94 | −1.3% / −0.47 | −1.3% / −0.53 |
| C minute bars, multi-day, fixed | −0.4% / −0.42 | −0.5% / −0.26 | −1.2% / −1.27 | −2.8% / −0.91 | −0.0% / −0.00 |
| C minute bars, multi-day, Kelly | −0.6% / −0.54 | +0.9% / +0.42 | −0.8% / −1.03 | +2.7% / +0.76 | +0.3% / +0.23 |

Momentum benchmark (continuous series), test period: **+1.6% / 0.72**.

- **35 of the 40 configurations lose money** in the test period (A 8 of 10,
  B 20 of 20, C 7 of 10); **22 are significantly worse than momentum** at 5%
  (A 4, B 17, C 1). No configuration beats momentum significantly.
- **Best configuration: Llama, A daily drift, Kelly sizing — Sharpe 1.30**
  (+1.8% p.a.). Against momentum the Sharpe difference is +0.56 ± 0.96
  (p 0.56, Jobson-Korkie-Memmel); the deflated Sharpe ratio at 139 trials is
  0.20; its **training Sharpe ratio is −0.09**. Not a confirmed edge.
- Source of every cell:
  `results/strategies_A_bug17fix_2026-11-14/comparison_vs_continuous_momentum_bug17fix_2026-11-14.csv`
  (A rows from the run of 14 November; B and C rows carried over unchanged
  from the files of 24/25 October). Details and the 20% drawdown sensitivity:
  `context/results.md`, appended sections.

## Which result files are official

| strategy | official files | folder |
|---|---|---|
| **A** (daily drift) | `…_calibrated_bug17fix_2026-11-14*` — run of 14 November 2026 (Bugs 15, 16, 17 corrected) | `results/strategies_A_bug17fix_2026-11-14/` |
| **B** (intraday) | `results_both_strategies_{keyword,llm,embed_minilm}_calibrated_bug14fix_2026-10-24*` and `results_both_strategies_{haiku,sonnet}_calibrated_2026-10-25*`, with their `risk_calibration_*` files | `results/strategies_B_C_2026-10-24_25/` |
| **C** (minute bars) | `results_both_strategies_*_calibrated_cminute_2026-10-24*` (keyword, Llama, MiniLM) and `…_cminute_2026-10-25*` (Haiku, Sonnet), with `risk_calibration_*_cminute_*`, `c_minute_summary_2026-10-24.csv`, `c_minute_rungs2_3_summary_2026-10-25.csv` | `results/strategies_B_C_2026-10-24_25/` |

**The A rows inside the 24/25 October files are superseded by the run of
14 November.** Those files are official for their B rows (and, in the
`cminute` files, for their C rows) only.

**Superseded, kept as the record:**
- `results/strategies_A_bug16fix_2026-11-10/` — Strategy A after Bugs 15 and
  16 (10 November); superseded by Bug 17.
- `results/strategies_test/` — the runs of 18 October (all strategies, before
  Bugs 12 to 17; momentum benchmark per period with Sharpe 1.08, replaced by
  the continuous series, 0.72).
- `results/order_robustness_2026-10-19.csv` — order noise on the engines and
  scales of 19 October; for Strategy A see the file of 14 November below.
- `results/risk_scales/`, `results/sweeps/` — training-period records of
  October.

## Bugs 10 to 17 and their correction runs

Seventeen numbered bugs are documented in `context/bugs.md`. The eight found
from 13 October on, each with a dated note in `results/frozen/` written before
its correction run:

| bug | found | what was wrong | correction |
|---|---|---|---|
| 10 | 13 Oct | ATR values assigned to the wrong rows and tickers, and including the entry day | fixed; before/after in `results/atr_fix_before_after_2026-10-13.csv` |
| 11 | 18 Oct | the signal gate was not applied to the netted strength of a ticker-day | fixed; training rerun of 18 Oct |
| 12 | 19 Oct | results depended on the row order of same-day signals when exposure caps bind | deterministic order; order-robustness check |
| 13 | 24 Oct | Strategy C mixed two price bases (daily-bar C invalid) | minute-bar-only reimplementation, runs of 24/25 Oct |
| 14 | 24 Oct | stop and target fills ignored opening gaps | fixed for A and B; runs of 24 Oct |
| 15 | 10 Nov | Strategy A sized positions with information of the same day | sizes from the previous close; A rerun 10 Nov |
| 16 | 10 Nov | Strategy A never closed a position in a ticker that stopped trading | positions marked and closed at the last close; A rerun 10 Nov |
| 17 | 14 Nov | Strategy A admitted entries on the book as it stood after the day's exits (re-entry on the exit day; gross cap judged after exits) | admission on the previous close's book; A rerun 14 Nov |

Each Strategy A correction was one disclosed run of the same ten
configurations with acceptance tests fixed beforehand; the trial counts used
for the deflated Sharpe ratio were left unchanged (139 / 155 / 161 / 163),
which is the less strict choice. B, C and the benchmark were not rerun after
25 October.

## Research discipline

- **No look-ahead:** signal and event tables assert it at runtime; Strategy A
  asserts that sizes (Bug 15) and admissions (Bug 17) use the previous close
  only, and that equity equals booked trades plus open positions (Bug 16).
- **Frozen configuration before any test look:**
  `results/frozen/FROZEN_CONFIG_2026-10-18.md` and its dated notes, with
  SHA-256 fingerprints. Holdout hypotheses H1 (no tradable drift, Holm-
  corrected) and H2 (corporate-event reversal) were written before the holdout
  data existed; the holdout was later dropped unevaluated.
- **Every test-period run is logged** (`results/test_period_runs.csv`); every
  configuration tried in training is logged (`results/experiments_log.csv`).
- **Bugs are documented, not hidden:** `context/bugs.md` lists seventeen found
  and fixed, including one that had produced a spurious +14.5% p.a. backtest.

## Repository layout

| folder | contents |
|---|---|
| `src/newsdrift/` | engine: signals, risk and sizing, backtests for strategies A–D/N, portfolio replay, statistics |
| `src/` | runners and analyses: `event_study.py`, `intraday_description.py`, `score_news_llm.py` (LLM scoring), `run_both_strategies.py`, calibration, correction reports, data download and checks |
| `tests/` | 17 regression test files for the fixed bugs and the statistics (`python3 tests/<file>.py`) |
| `context/` | thesis framing, methodology, system map, results, bug log, changelog |
| `skills/` | step-by-step procedures used to run the project |
| `results/` | frozen configuration and notes, strategy results (see above), event studies, sweeps, checks |
| `data_sources/` | only the public ticker list and company names (see below) |
| `CLAUDE.md` | working rules for the AI coding assistant used in the project |

## Running it

```
pip install -r requirements.txt
cp .env.example .env              # Alpaca keys, Ollama address
python3 tests/test_portfolio_fixes.py
python3 src/event_study.py        # needs the data below
```

**Do not run `src/order_robustness.py`.** It writes
`order_robustness_2026-10-19.csv` and would overwrite the official October
file. Use the dated copy `src/order_robustness_bug17fix_2026-11-14.py`, which
refuses to overwrite its output.

**Data are not included.** Prices come from Bloomberg (terms prohibit
redistribution), news and minute bars from Alpaca (re-downloadable with
`src/fetch_historical_news.py` and `src/fetch_intraday_bars.py`). Expected files and their locations are in
`src/paths.py`.

## Other result files

- **Order noise (Bug 12), training period.** Across 20 random orderings of
  same-day signals the training Sharpe ratio of Strategy A has a standard
  deviation of 0.000 (fixed sizing) and 0.038 (keyword) or 0.029 (Llama) with
  Kelly sizing, on the engine and scales of 14 November
  (`results/order_robustness_bug17fix_2026-11-14.csv` and its note). For B the
  standard deviation is 0.05 to 0.31.
- **Hash registers and verification of the correction runs:**
  `results/frozen/FROZEN_RUN_outputs_hashes_bug15fix_2026-11-10.txt`, `…_bug16fix_2026-11-10.txt` and
  `…_bug17fix_2026-11-14.txt` give the SHA-256 of every file of the three correction runs by file name (the
  files sit in different folders here, so match them by name). The harness rerun of the Bug 17 run is in
  `results/verification_2026-11-14_bug17/`. Registered files not in this folder: the superseded Bug 15 result
  files, the harness reports and placebo logs of 8 and 10 November, and the diagnostic placebos of the code
  before Bug 15; and `README.md`, whose registered version is the index of the project's `for_claude/` bundle,
  not this README.
- **Event studies:** `results/event_study/` (training rerun of 18 October,
  test period, and the clustering check of 14 November).
- The keyword D row in `results/sweeps/sweep_new_strategies_keyword.csv` and
  the "before" rows in `results/atr_fix_before_after_2026-10-13.csv` are kept
  as records and should not be quoted.

**Unused (kept as a record):** `src/holdout_eval.py`, `src/h3.py` and their
tests, and `results/holdout_unused/` — the holdout and its hypothesis H3 were
dropped before any holdout return was computed
(`results/frozen/FROZEN_CONFIG_2026-10-18_note_holdout_dropped.md`).
