# Systems: data, code, environment

## Data (`data_sources/`)

| File | What | Status |
|---|---|---|
| `prices.csv` | Bloomberg daily OHLCV + bid/ask + mktcap, 171 tickers, 2015-01 → 2026-07, 428k rows | audited, adjustments verified |
| `news_history.csv` | Raw Benzinga via Alpaca, before dedup | source of the clean file |
| `news_history_clean.csv` | Benzinga via Alpaca, 476,916 rows, 2015-09 → 2026-06 | deduped (33% exact repeats removed) |
| `bars_intraday.csv` | Alpaca IEX 1-min bars around events, 19.6M rows (1.3 GB), 2020-07 → 2026-06 | 91% entry coverage during market hours |
| `nasdaq100.txt` | 193 tickers = every NDX member at any point 2015-2026 | survivorship-controlled |
| `wb6_prices_D.xlsx` | Bloomberg export for the 20 missing tickers | needs refreshing |
| `news_scored_llm_ollama.csv` | LLM scores (local Ollama llama3.2:3b), 46,485 rows, 2016-01 → 2024-03 | **TRAIN PERIOD ONLY** |
| `llm_score_cache.json` | Permanent scoring cache (all providers/arms tried) | keep: avoids up to ~42h of re-scoring |
| `company_names.csv` | Ticker → company-name variants for anonymization (191 tickers) | 3 rows marked CHECK need review |

`context_table.csv` (point-in-time drift context for the `--with-context`
scoring arm) is referenced by `score_news_llm.py` but no longer exists, and
`outcome_feedback.py`, which built it, is missing.

**Open data gaps:**
- 20 tickers have news but no prices — refresh `wb6_prices_D.xlsx` at the
  Bloomberg terminal, then `python3 src/bloomberg_to_csv.py convert`.
- News ends 2026-06-01, prices run to 2026-07-14 (~6 week gap).
- IEX = ~2-3% of US volume; 42% of news breaks outside market hours (no bar
  can exist — normal, not a failure). Coverage during RTH is 91%.

## Code (`src/`)

All scripts are run from the project root as `python3 src/<script>.py`.
Locations live in one place: `src/paths.py`.

**`src/newsdrift/` package (engine):**
- `config.py` — all tunable parameters. Start here for changes.
- `signals.py` — scorers, `build_signal_table()`, `build_event_table()`.
- `risk.py` — `KellySizer`, `FixedFractionSizer`, `DrawdownGovernor`, stops.
- `backtest.py` — Strategy A engine + `performance_metrics`.
- `intraday.py` — Strategy B engine (+ scale-out and confirmation options).
- `strategy_c.py` — Strategy C engine.
- `open_close.py` — Strategies D (open → close) and N (close → next open).
- `portfolio.py` — shared replay for B/C/D/N: governor, sizer-independent
  admission, risk scale, one position per ticker, daily equity. Change risk
  logic HERE, once.
- `baseline.py` — momentum benchmark, split helpers.
- `data.py` — loaders.

**Scripts:**
- `run_both_strategies.py` — A, B, C + benchmark, 80/20 split. Flags:
  `--llm-scores`, `--dd-governor`, `--risk-scale`, `--risk-scales <csv>`,
  `--tier0`, `--allow-stacking`, B exit options. Output name says which
  variant ran (`_llm`, `_calibrated`, `_tier0`, `_strict`, …).
- `calibrate_risk.py` — in-sample risk scale per strategy/sizer for a 5% maxDD.
- `sweep_strategy_b.py`, `sweep_new_strategies.py` — in-sample variant sweeps.
- `score_news_llm.py` — LLM scoring: providers ollama/google/groq, 4 arms
  (plain, `--agents`, `--with-context`, both), permanent cache, template
  dedup, `--estimate`, `--pilot`. Excludes the test period unless
  `--include-test-period`. Anonymizes headlines by default
  (`--no-anonymize` for the old behaviour).
- `anonymize.py` — masks the scored company's names + ticker.
- `fetch_historical_news.py`, `fetch_intraday_bars.py` — Alpaca downloads.
- `bloomberg_to_csv.py` — Bloomberg xlsx → CSV + data audit.
- `audit_intraday_coverage.py` — bar coverage diagnostics.
- `raw_news_pusher.py` — live pipeline: Alpaca websocket → Telegram, no scoring.

Listed in older notes but not in the project: `filtered_news_pusher.py`,
`improve_strategy_b.py` (replaced by `sweep_strategy_b.py`),
`outcome_feedback.py`.

**Tests (`tests/`):** `test_portfolio_fixes.py` (41 adversarial checks; run
after any change to the engines, `portfolio.py` or `signals.py`) and
`test_freshness_guard.py` (live pusher) and `test_anonymize.py` (11 checks).

## Environment

- Use `python3` (Framework Python 3.13), which has all packages installed —
  not the Anaconda `python`, which lacks `google-genai`.
- Secrets live in `.env` (`ALPACA_KEY`, `ALPACA_SECRET`, `TELEGRAM_TOKEN`,
  `TELEGRAM_CHAT_ID`, `GROQ_API_KEY`, `GOOGLE_API_KEY`, `OLLAMA_BASE_URL`) and
  `ALPACA_KEY.py`, both at the project root. Never print or commit them.
- **Ollama** runs on a second machine on the LAN (`OLLAMA_BASE_URL`, model
  `llama3.2:3b`). Long scoring runs need BOTH machines awake: the scoring
  script runs on this Mac, inference on the other. Use `caffeinate -i -w
  <pid>` here and disable sleep on the Ollama machine. A sleep breaks the TCP
  connection silently; restart the run (it resumes from the cache).
- NVIDIA NIM was tried and dropped (rate limits, multi-minute latency).

## GitHub rules

**Three things must NEVER be committed:**
1. **API keys** — `.env` and `ALPACA_KEY.py` hold live credentials.
   Committing them exposes them permanently in git history; bots scrape public
   repos for exactly this.
2. **Large files** — `bars_intraday.csv` is 1.3 GB (GitHub's limit is 100 MB
   per file). `news_history_clean.csv` (59 MB) and `prices.csv` (34 MB) fit
   but bloat the repo.
3. **Bloomberg-derived data** — Bloomberg's terms prohibit redistribution.
   `prices.csv` stays out regardless of size or visibility.

`.gitignore` must cover these (the project is not currently a git repo).
Verify `git status` shows no CSV, xlsx or key files before every commit.
Claude via the GitHub integration sees code only and cannot run backtests;
anything touching real data stays local.
