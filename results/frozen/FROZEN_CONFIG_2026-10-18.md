# Frozen configuration — 18 October 2026

Frozen: **2026-10-18**, before any LLM score for the test period or the holdout
exists. Nothing is added to this file afterwards; corrections go in a separate
dated note (`outputs/FROZEN_CONFIG_2026-10-18_note_<date>.md`).

## 1. Scorers

**Keyword dictionary** — `KeywordScorer` with `SignalConfig` in
`src/newsdrift/config.py` as of today: Loughran-McDonald-style word lists
`lm_positive` (15 words) and `lm_negative` (20 words), strength =
(pos − neg) / (pos + neg).

**LLM** — `llama3.2:3b` via Ollama (OpenAI-compatible endpoint), temperature
0.2, `max_tokens` 300, `think: false`, Ollama only (no Google/Groq fallback:
`--providers ollama`). Prompt: `PROMPT` in `src/score_news_llm.py` as of today,
with anonymisation ON (the scored company's names and ticker masked as "the
company", `src/anonymize.py`, names in `data_sources/company_names.csv`).
Pre-processing as in `score_news_llm.py` today: exact-repeat dedup, Tier-0
filter (`tier0_keep`), template dedup (`normalize_template`; one
representative scored per template, its score reused). Output fields:
strength ∈ [−1, 1], duration ∈ {1, 2, 3}, importance 1–10.

**Universe** — restricted when the news is downloaded: all 191 tickers in
`data_sources/news_history_clean.csv` are among the 193 tickers of
`data_sources/nasdaq100.txt` (checked 2026-10-18, 0 outside). The Tier-0
watchlist check is inactive when run from the project root and redundant.

## 2. Splits

| | from | to | status |
|---|---|---|---|
| Training | 2016-01-04 | 2024-04-29 | backtest calendar, 80% (`src/splits.py`) |
| Test | 2024-04-30 | 2026-06-01 | |
| Holdout | 2026-06-02 | 2026-10-31 | **not yet downloaded** |

LLM scoring of training news: timestamps before 2024-04-30 00:00 UTC
(`news_scored_llm_ollama_anon.csv`, 60,252 rows). The test period is scored
once with `--include-test-period` into `news_scored_llm_ollama_anon_incl_test.csv`.

## 3. Signal gate (Bug 11 rule)

Per headline: |strength| ≥ 0.20. Per ticker and entry day, strengths are
averaged (duration = max); a day whose average is 0 or has |average| < 0.20
produces **no trade** (`build_signal_table`; engine guard in `backtest.py`).
Entry day (effective date) = first trading day strictly after the news date
(UTC calendar date). Direction = sign of the daily average.

## 4. Event study specification (`src/event_study.py`, as run today)

- One event per (ticker, entry day) from the gated daily signal table above.
- Signed returns (× sign of the daily average), in bps, **gross** of costs:
  - day 0 = close-to-close return of the last trading day before entry (the
    news day; never traded);
  - day k = entry-day open → close of the k-th trading day of that ticker,
    k ∈ {1, 2, 3, 5} (day 1 = entry-day close).
- Raw and market-adjusted (minus the NDX return over the same window, NDX
  daily open/close from `prices.csv`).
- Mean, t-statistic clustered by entry date (cluster-robust variance of the
  mean with G/(G−1) correction), N.
- Splits: all events; |strength| terciles; market-cap terciles (prior-day
  market cap, terciles pooled within scorer and period); news category
  (`headline_type`, fixed regex rules, first match wins, from the day's
  strongest headline: earnings_guidance, analyst, corporate_event, other);
  LLM only: importance (1–3, 4–6, 7–10) and duration (2 vs not 2).
- Reference line: round-trip cost 2 × 2.43 bps = 4.86 bps.

## 5. Pre-registered holdout hypotheses

Written before the holdout exists. Evaluated once on the holdout
(2026-06-02 → 2026-10-31) with sections 1–4 unchanged.

**H1.** For keyword AND LLM, the mean market-adjusted signed return from entry
to the close of day 1, 2, 3 and 5 is not distinguishable from zero.

**H2.** Keyword signals in category "corporate_event" show a reversal: the
mean market-adjusted signed return to the close of day 3 is negative.
One-sided test, single evaluation, no other categories tested.

Decision rules (t clustered by entry date, as in section 4):
- H1 holds for a scorer and horizon if |t| < 1.96 (two-sided 5%); 8 cells
  (2 scorers × 4 horizons), each reported; no multiplicity adjustment.
- H2 is supported if t < −1.645 (one-sided 5%).

## 6. Fingerprints (SHA-256) of the frozen files

| file | sha256 |
|---|---|
| `src/newsdrift/config.py` | `4058a18c941597906041f05ff3ecf465a443776f9d39407b12772aea08e9df7a` |
| `src/newsdrift/signals.py` | `bca0e5f8e5c26e7e5528ac77deaa2e4a50f8c28a35bac2172dd89f29a5d49c1a` |
| `src/newsdrift/backtest.py` | `6311effbf980c74f2cceda6a2722894ae2f776bdafb9fb2ba921fd1d361c5464` |
| `src/score_news_llm.py` | `04f55f48143f0648ece6dba7f33dfb0cdded1124e9be1ceb7a623f3c46f9ae44` |
| `src/anonymize.py` | `da37396e5109c551260e2ab7b0d2bde8525a78bef63ea9ba69c50d09eed598b2` |
| `data_sources/company_names.csv` | `8f68c97ce52615aedfc5ab7abbc53a7c495041caf37873d6b43a089b9e2804cc` |
| `src/event_study.py` | `879acfcc968e6b4bb8d2e6e313ac5ea6fd3a76065e0af54f6fd8fc4f4102d020` |
| `src/splits.py` | `2a81df54d60315c784afeca0d51489901f91386445bafe96974d2013599e3152` |
| `src/calibrate_scorer.py` | `83fadc8f28f26e9dd47654e30753a5e557f4dbff151871a7efcc0804a1d97470` |
| `src/paths.py` | `ef6feb8316e9d8e6a0d96e1f46367dfed45f27705976ec797f8ef1c8c3198f68` |
| `data_sources/nasdaq100.txt` | `030a4692406e5e0e68d8f7e4e670fca4d53a3646a8e2c338d302fb00c1b82987` |

Commands:
```
echo y | python3 src/score_news_llm.py --providers ollama --include-test-period
python3 src/event_study.py --period test --scorers keyword llm_anon
```
