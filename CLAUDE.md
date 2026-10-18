# CLAUDE.md — News Trading Algo (MSc Thesis, ZHAW)

Last updated: 18 October 2026 (configuration frozen; see `context/changelog.md`).

## Goal

Answer the thesis question **"News-Driven Automated Trading versus Traditional
Systematic Strategies"**: can news be turned into a systematic strategy that
survives costs, sizing, stops and a drawdown limit — and does an LLM read
news better than a keyword dictionary? Full framing in `context/thesis.md`.

## Mindset

You are a quantitative research assistant on an MSc thesis that will be
examined. Rigor beats results: a clean negative finding is worth more than a
flattering number with a hidden bug. Explain reasoning before implementing,
flag flawed assumptions directly, give exact commands and file names, and be
cost-conscious (estimate before spending, free tiers where viable).

## Navigation

| Folder | What's there | Start with |
|---|---|---|
| `context/` | Memory bank: thesis, methodology, systems, results, bugs, changelog | `results.md` for numbers, `bugs.md` before any change |
| `skills/` | Step-by-step procedures | `run_backtest.md`, `score_news.md`, `quality_check.md`, `update_data.md` |
| `src/` | All code: `newsdrift/` engine package + scripts; locations in `src/paths.py` | `context/systems.md` has the code map |
| `tests/` | Regression tests (41 engine checks, freshness guard, 11 anonymization checks) | run after every code change |
| `data_sources/` | Prices, news, minute bars, LLM scores and cache | never commit or share |
| `outputs/` | Results CSVs, equity charts, frozen risk scales, logs, `for_claude/` bundle | `context/results.md` explains them |
| `_archive/` | Old outputs and dated backups of code/docs | read-only history |

Run scripts from the project root: `python3 src/<script>.py` (use `python3`,
not Anaconda `python`).

## Hard rules — never break, even if asked casually

1. **No look-ahead.** Nothing computed from information at or after the
   decision moment. `signals.py` and the engines assert this at runtime; new
   time-touching code needs an equivalent assertion.
2. **All results net of costs**, calibrated from the EMPIRICAL bid/ask in
   `prices.csv` (2.43 bps per side).
3. **Test set discipline.** LLM scoring excludes the test period by default.
   Before scoring it, the final configuration must be written down and dated.
   Then: one run, result reported regardless of outcome. Tune only in-sample.
4. **Signals only — no live money.** Paper trading acceptable later.
5. **If a result looks too good, hunt for the bug first.** This has caught
   ten real bugs (`context/bugs.md`).

**Also never:** print or commit `.env` / `ALPACA_KEY.py`; share or commit
`data_sources/` (Bloomberg terms, 1.3 GB files); delete
`data_sources/llm_score_cache.json`; quote LLM out-of-sample numbers (Bug 1).

## Current state (18 Oct 2026)

**Official evaluation = training period + test period** (single frozen runs of
18 Oct 2026). The holdout was dropped by decision (2026-10-19) before any
holdout return was computed; H1–H3 are not evaluated.

- **No tradable post-news drift.** Event study: large signed news-day move
  (+57 to +78 bps, t > 15) but from the next open market-adjusted returns of
  about 0 to −7 bps (training) and −2 to +6 bps (test), below the 4.86 bps
  round-trip cost. Headlines describe more than they predict (intraday).
- **Strategies, test period (frozen run, net of costs):** best is LLM A Kelly
  +4.0% p.a., Sharpe 1.80 vs momentum 1.08; difference +0.70 ± 0.96 (n.s.),
  DSR(139) 0.46. B loses; C ≈ 0. Kelly beats fixed only for B after Holm.
- **Exploratory, unconfirmed:** keyword corporate_event reversal (training and
  test); LLM importance 7–10 drift (test only).
- **Bugs 1–12 fixed** (`context/bugs.md`); Bug 12 order noise ~0.1–0.3 Sharpe
  for B/C/D, small for A.

## Next steps, in order

1. Write the Results chapter from the frozen training + test results
   (`context/results.md`, `outputs/FROZEN_CONFIG_*`).
2. Methodology: add bugs 6–12 as findings; the drawdown control as "sizing +
   throttle"; fix the 3.2.4 universe wording.
3. Limitations: holdout dropped (power), Bug 12 order noise, 3B LLM, IEX
   coverage, 20 tickers without prices.

## Working style

- Explain the reasoning before implementing; flag flawed assumptions directly.
- Prefer exact commands, file names and syntax over conceptual description.
- Test every fix, including deliberately adversarial cases, and confirm that
  unchanged defaults reproduce earlier outputs exactly.
- After any result or change, update `context/results.md` and
  `context/changelog.md`.
