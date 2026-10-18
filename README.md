# News-Driven Automated Trading versus Traditional Systematic Strategies

MSc Banking & Finance thesis, ZHAW — code and results repository.
Supervisor: Prof. Martin Schnauss. State: 18 October 2026 (final evaluation:
training period + test period).

## What the thesis tests

Can company news be turned into a systematic trading strategy that survives
transaction costs, position sizing, stops and a drawdown limit — and does a
large language model (LLM) read news better than a keyword dictionary?

The target is the post-news **drift** (from the first tradable price after
the news), not the initial spike, which high-frequency traders own.

- **Universe:** every Nasdaq-100 member 2015–2026 (193 tickers,
  survivorship-controlled).
- **News:** Benzinga via Alpaca, 476,916 headline-ticker rows, 2015-09 → 2026-06.
- **Scorers:** a Loughran-McDonald-style keyword dictionary vs `llama3.2:3b`
  (local Ollama, temperature 0.2, company names anonymised). Each scorer
  outputs a strength in [−1, 1], a duration of 1–3 days and (LLM) an importance.
- **Splits:** training 2016-01-04 → 2024-04-29, test 2024-04-30 → 2026-06-01.
  A holdout was pre-registered but dropped by decision before any holdout
  return was computed; the official evaluation is training plus test.

## Main results so far

Event study on the daily signals (one event per ticker and entry day).
Signed returns in basis points, market-adjusted (minus Nasdaq-100), gross of
costs, t-statistics clustered by date. Round-trip cost 4.86 bps.

| | news day (not traded) | day 1 | day 2 | day 3 | day 5 |
|---|---|---|---|---|---|
| keyword, training | +57.8 (t 21.2) | −2.8 | −5.2 | −5.6 | −7.2 |
| LLM, training | +60.6 (t 25.0) | −2.0 | −4.4 | −2.4 | −2.4 |
| keyword, test | +62.7 (t 15.8) | +0.6 | −1.7 | −0.8 | +6.4 |
| LLM, test | +78.2 (t 17.6) | +6.2 (t 2.1) | −0.3 | −0.4 | +0.2 |

**Trading strategies, net of costs** (annual return / Sharpe; risk scaled to
~5% max drawdown in training, so training figures are in-sample):

| strategy | keyword: training | keyword: test | LLM: training | LLM: test |
|---|---|---|---|---|
| A daily drift, fixed | −0.6% / −0.57 | −0.4% / −0.64 | −0.1% / −0.09 | +1.0% / 0.83 |
| A daily drift, Kelly | +0.2% / 0.11 | +1.4% / 0.61 | +1.4% / 0.64 | +4.0% / 1.80 |
| B intraday (4 variants) | −1.2% to −1.4% | −1.7% to −2.9% | −1.3% to −1.4% | −1.5% to −2.0% |
| C hybrid, fixed / Kelly | −1.2% / −1.2% | −0.3% / −0.9% | −1.0% / −1.4% | +0.3% / −0.2% |
| Momentum benchmark | +0.9% / 0.30 | +2.5% / 1.08 | (same) | (same) |

1. **The price reaction happens on the news day; from the next open there is
   no drift above trading costs** for either scorer, in training or test.
2. **Headlines describe more than they predict:** intraday, the LLM-signed
   move in the 30 minutes *before* a headline (+12.5 bps, t 2.3) exceeds the
   move in the 30 minutes after (+2.9 bps).
3. **The LLM does not clearly beat the keyword dictionary.** The 3B model
   uses a few fixed scores; neither strength, importance nor duration sorts
   returns in training.
4. **Trading strategies, test period (one frozen run per scorer, net of
   costs):** the best is LLM-scored daily drift with Kelly sizing, +4.0% p.a.,
   Sharpe 1.80, against momentum's 1.08 — but the Sharpe difference
   (+0.70 ± 0.96, Jobson-Korkie-Memmel) is not significant and the deflated
   Sharpe at 139 trials is 0.46. Keyword A fixed is significantly worse than
   momentum (−1.71 ± 0.82). Intraday strategy B loses; C is about zero. After
   a Holm correction, Kelly sizing beats fixed sizing only for B.
5. **Two leads, both not yet confirmed:** keyword "corporate event" news
   reverses (test day 2 −33.5 bps, t −3.0; pre-registered for a holdout that was later dropped, so unconfirmed); and
   high-importance LLM news drifts in the test period (+20 to +42 bps) but not
   in training (exploratory).

## Research discipline

- **No look-ahead:** signal and event tables assert it at runtime.
- **Frozen configuration before any test look:**
  `results/frozen/FROZEN_CONFIG_2026-10-18.md` and its dated note, both with
  SHA-256 fingerprints. Holdout hypotheses H1 (no tradable drift, Holm-
  corrected) and H2 (corporate-event reversal) were written before the holdout
  data existed; the holdout was later dropped unevaluated.
- **Every test-period run is logged** (`results/test_period_runs.csv`); every
  configuration tried in training is logged (`results/experiments_log.csv`).
- **Bugs are documented, not hidden:** `context/bugs.md` lists twelve found
  and fixed, including one that had produced a spurious +14.5% p.a. backtest.

## Repository layout

| folder | contents |
|---|---|
| `src/newsdrift/` | engine: signals, risk and sizing, backtests for strategies A–D/N, portfolio replay, statistics |
| `src/` | runners and analyses: `event_study.py`, `intraday_description.py`, `score_news_llm.py` (LLM scoring), `run_both_strategies.py`, calibration, data download and checks |
| `tests/` | regression tests for the fixed bugs and the statistics (`python3 tests/<file>.py`) |
| `context/` | thesis framing, methodology, system map, results, bug log, changelog |
| `skills/` | step-by-step procedures used to run the project |
| `results/` | frozen configuration, event studies (csv, charts, logs), sweeps, checks |
| `data_sources/` | only the public ticker list and company names (see below) |
| `CLAUDE.md` | working rules for the AI coding assistant used in the project |

## Running it

```
pip install -r requirements.txt
cp .env.example .env              # Alpaca keys, Ollama address
python3 tests/test_portfolio_fixes.py
python3 src/event_study.py        # needs the data below
```

**Data are not included.** Prices come from Bloomberg (terms prohibit
redistribution), news and minute bars from Alpaca (re-downloadable with
`src/fetch_historical_news.py` and `src/fetch_intraday_bars.py`). Expected files and their locations are in
`src/paths.py`.

## Status of the result files

Everything in `results/` is current (rerun 18 Oct 2026 on the training
period with all bug fixes), with two caveats: the keyword D row in
`results/sweeps/sweep_new_strategies_keyword.csv` is under an open check (same
trade count as before the Bug 11 fix but a different return) and should not
be quoted yet; and the "before" rows in
`results/atr_fix_before_after_2026-10-13.csv` are the buggy numbers, kept on
purpose as a record.

**Test-period strategy runs:** `results/strategies_test/` (frozen in
`results/frozen/FROZEN_CONFIG_2026-10-18_note_strategies.md`). Bug 12 (fixed
after these runs, which stay official): when exposure caps bind, results
depended on the row order of same-day signals; across 20 random orders in
training the Sharpe moves by about 0.04–0.09 for A Kelly and 0.05–0.28 for
B/C (`results/order_robustness_2026-10-19.csv`).

**Unused (kept as a record):** `src/holdout_eval.py`, `src/h3.py` and their
tests, and `results/holdout_unused/` — the holdout and its hypothesis H3 were
dropped before any holdout return was computed.

**Holdout:** not evaluated — dropped by decision (low power with the
available prices); no holdout return was ever computed
(`results/frozen/FROZEN_CONFIG_2026-10-18_note_holdout_dropped.md`).
