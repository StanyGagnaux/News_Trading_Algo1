# Changelog

Newest first. Bug details in `bugs.md`; results in `results.md`.

## 2026-10-18 (22:20, decision dated 2026-10-19) — Holdout dropped
- Dated note `FROZEN_CONFIG_2026-10-18_note_holdout_dropped.md` (read-only,
  SHA-256 ffc101cf... in `FROZEN_CONFIG_hashes_notes_2026-10-19.txt`):
  "Holdout not evaluated; dropped by decision on 2026-10-19. No holdout
  returns were ever computed." Official evaluation = training + test (18 Oct).
- Holdout files and `src/holdout_eval.py` marked unused in README.md (kept).

## 2026-10-18 (night) — Holdout switched to Bloomberg prices (Phase 1, frozen; not run)
- Dated note `FROZEN_CONFIG_2026-10-18_note_holdout_bloomberg_2026-10-18.md`
  (read-only, SHA-256 31d2e6fa... in `FROZEN_CONFIG_hashes_notes_2026-10-19.txt`):
  Bloomberg `prices.csv` (ends 2026-07-14) replaces Yahoo; holdout news
  2026-06-02 .. 2026-07-07 (day-5 rule); 22,564 later rows excluded; events
  keyword 579, LLM 411, corporate 46 (24 / 24 / 19 entry dates); power low for
  every hypothesis (H1 cells 1-11%, H2 9-15%, H3 7-10%). Date-label correction
  for the notes labelled 19 Oct.
- `event_study.load_window` (shared loader; `load_test` output verified
  identical); `src/holdout_eval.py` (--counts / --validate / --run);
  `tests/test_holdout_eval.py` (6 checks). Holdout NOT run (awaiting review).

## 2026-10-18 (late) — Bug 12 fixed; H2b Holm; H3 pre-registered
(Files from this step carry the label 2026-10-19 by mistake; written 18 Oct, 20:50–21:15.)
- Bug 12 fixed (deterministic tie-break) with dated note
  `FROZEN_CONFIG_2026-10-18_note_bug12_2026-10-19.md`; 18 Oct test runs stay
  official. Training robustness (20 orders): see `results.md`. Explains the
  keyword D discrepancy (order noise: -6.3% to +0.3% at a constant 8,040 trades).
- H2b Holm (8 comparisons): Kelly beats fixed only for B; A not significant.
- H3 pre-registered before holdout prices: dated note
  `FROZEN_CONFIG_2026-10-18_note_H3_2026-10-19.md` (SHA-256 in
  `FROZEN_CONFIG_hashes_notes_2026-10-19.txt`), code `src/h3.py`
  (`tests/test_h3.py`); ex-ante power ~0.19. Test-period effect-size run logged.

## 2026-10-18 (night) — Strategy layer frozen; test-period strategy runs
- `outputs/FROZEN_CONFIG_2026-10-18_note_strategies.md` (read-only, SHA-256 in
  `FROZEN_CONFIG_hashes_strategies.txt`): decisions D/N training-only,
  designed governor, N = 139 trials (+25/50/100), Jobson-Korkie-Memmel vs
  momentum, H2b Kelly vs fixed with exposure; no strategy on the holdout.
- New: `newsdrift.stats.sharpe_diff_test`, `paired_mean_diff`;
  `newsdrift/exposure.py`; runner comparison section; tests (19 stats checks).
  Validated on training only (`outputs/validation_2026-10-18/`).
- Test runs (logged): best LLM A Kelly +4.0% p.a., Sharpe 1.80 vs momentum
  1.08 -- difference +0.70 +- 0.96, DSR(139) 0.46; nothing significant.
- Bug 12 found (signal row order changes trades when caps bind).
- Holdout headlines scored (6,723 rows, no prices), `outputs/holdout_runs.csv`.

## 2026-10-18 (evening) — Training-period rerun of all strategies
- `calibrate_risk.py` (keyword, anonymised LLM), `sweep_new_strategies.py`,
  momentum: training only, fixed engine, Bug 11 rule. Table in `results.md`.
  Best training row: A LLM Kelly +1.4% p.a., Sharpe 0.61 (SE ~0.35); momentum
  +0.9%, Sharpe 0.30. Old outputs in `_archive/_backup_2026-10-18_before_training_rerun/`.
- Open check: keyword D has the same trade count (8,040) before and after the
  Bug 11 fix but a different return; not yet explained. Keyword D is not
  quoted anywhere until it is.

## 2026-10-18 (evening) — Test period scored; test-period event study, both scorers
- LLM test period scored once with the frozen setup: 32,485 rows (100% of
  pre-filtered test headlines), `news_scored_llm_ollama_anon_incl_test.csv`
  (SHA-256 in `outputs/FROZEN_RUN_outputs_hashes.txt`). Bug 1 resolved.
- `event_study.py --period test --scorers keyword llm_anon` (logged): LLM
  mkt-adj day 1 +6.2 (t 2.1), days 2-5 ~0; keyword unchanged. Exploratory:
  LLM importance 7-10 +20 to +42 bps (t 2.4-3.2) in test, ~0 in training.
- Holdout news downloaded (29,919 clean rows) and being scored (no prices);
  `fetch_historical_news.py --progress` added.

## 2026-10-18 — Configuration frozen; holdout hypotheses pre-registered
- `outputs/FROZEN_CONFIG_2026-10-18.md` + final note
  `outputs/FROZEN_CONFIG_2026-10-18_note_2026-10-18.md` (both read-only;
  SHA-256 in `outputs/FROZEN_CONFIG_hashes.txt`). Holdout 2026-06-02 ->
  2026-10-16, Yahoo prices; H1 = Holm-corrected one-sided 95% upper bound
  below 4.86 bps in each of 8 cells; H2 = keyword corporate_event day-3
  reversal, one-sided 5%.
- Scoring cutoff aligned to the backtest (`src/splits.py`); training gap
  2024-03-26..04-29 scored (1,098 rows). Test period scoring started with the
  frozen setup (`--include-test-period` -> `*_anon_incl_test.csv`).
- `src/source_consistency.py`: Yahoo vs Bloomberg returns corr 0.9994,
  mean |diff| 0.94 bps; Yahoo cannot supply 27/193 universe tickers.

## 2026-10-18 — Bug 11 fixed; intraday description test; first logged test-period run
- Bug 11 fixed (`bugs.md` #11): daily netted strength re-gated at 0.20; engine
  guard; `tests/test_signal_gate.py` (6 checks; fails on old code).
- `src/intraday_description.py` (training, RTH news, raw minute returns):
  LLM signed move -30m->t +12.5 bps (t 2.3) vs t->+30m +2.9 (1.5),
  t->close +6.1 (2.0); keyword ~0 in every window. Pre window is 30 min
  (bars were fetched from 30 min before the news).
- `src/event_study.py --period test --scorers keyword` = FIRST entry in the new
  `outputs/test_period_runs.csv` (earlier keyword OOS looks predate the log).
  Test period: day 0 +62.7 bps mkt-adj; days 1-5 +0.6 / -1.7 / -0.8 / +6.4
  (all |t| < 1). Keyword corporate_event reversal replicates (day 2 -33.5 bps,
  t -3.0; training -13.0, t -1.9).
- Training event study rerun with the fix: keyword unchanged (27,042 events);
  LLM 30,591 -> 26,209 events, market-adjusted days 1-5 still -2.0 to -4.4 bps.

## 2026-10-18 — Diagnostics on anonymised LLM scores + event study (training only)
- `src/event_study.py` -> `outputs/event_study_2026-10-18.{csv,png}`, log
  `outputs/logs/event_study_2026-10-18.log`. Zero-netting days excluded in the
  study only (engine issue still open).
- Main finding: signed day-0 (news day) return +57 bps market-adjusted for
  both scorers (t > 20); from the entry open on, market-adjusted returns are
  0 to -7 bps for both, below the 4.86 bps round-trip cost. The LLM's positive
  raw day-5 return (+10.6 bps) is market exposure (62% of its signals long).

## 2026-10-18 — Anonymized 3B scoring complete; 27B dropped
- llama3.2:3b, anonymized, training period: all 39,649 headlines scored
  -> `data_sources/news_scored_llm_ollama_anon.csv` (59,154 rows, 187 tickers,
  2016-01-03 -> 2024-03-25). Strength std 0.27; 0.0% neutral (flag: the model
  almost never says 0); duration 94% = 2 (carries little information).
- qwen3.8:27b cancelled by user decision: mostly CPU on the Ollama host, first
  request timed out after ~20 min, 0 headlines scored. No 27B outputs exist.
- `score_news_llm.py`: stops a run after 20 consecutive errors (was: timed out
  on every remaining headline when the server dropped).

## 2026-10-16 — Two-model Ollama scoring started (llama3.2:3b, then qwen3.8:27b)
- Ollama now reached via Tailscale (`OLLAMA_BASE_URL` = 100.75.252.66).
- `score_news_llm.py --ollama-model <name>`: non-default models get their own
  cache namespace and output (`news_scored_llm_ollama-<model>_anon.csv`);
  default (3B) unchanged. Ollama calls send `think: false`.
- `src/score_two_models.sh`: training period, anonymized, Ollama only (no
  Google/Groq fallback), 3B first, then 27B; resumes across passes. Log:
  `outputs/logs/score_two_models_2026-10-16.log`.
- 27B caveat: only 1.7 of 18.3 GB fits in GPU memory on the Ollama host, so it
  runs mostly on CPU; a first test call gave no reply within 10 minutes.

## 2026-10-13 — Bug 10 fixed: Strategy A ATR alignment + same-day look-ahead
- `newsdrift/backtest.py`: new `attach_atr()` (index-preserving, ATR up to the
  previous bar); trades now record `reason` (stop/target/time).
  `newsdrift/standalone.py` uses `attach_atr`. New `tests/test_atr_alignment.py`.
- Strategy A turns from profitable to slightly negative in-sample (raw size);
  see `bugs.md` #10 and `results.md`. All earlier A results invalid.
- New `outputs/frozen_risk_scales_2026-10-13_{keyword,llm}.csv` supersede the
  11 Oct files (kept); note in `frozen_risk_scales_2026-10-13_NOTE.md`.
  B/C scales unchanged. Before/after table:
  `outputs/logs/atr_fix_before_after_2026-10-13.csv`.
- Calibration layer (`src/calibrate_scorer.py`, `newsdrift/standalone.py`,
  `tests/test_calibration.py`) built; its 4 logged runs used the buggy engine
  and must be rerun.

## 2026-10-13 — Headline anonymization added
- `src/anonymize.py` + `data_sources/company_names.csv` (191 tickers) +
  `tests/test_anonymize.py` (11 checks). `score_news_llm.py` masks the scored
  company's names + ticker by default, separate cache namespace, output
  `*_anon.csv`; `--no-anonymize` keeps the old behaviour. Existing scores
  unchanged; needs a re-score to take effect.
- Full post-restructure verification: 7 main outputs byte-identical; 4 of 6
  sweeps byte-identical, the other 2 identical row-for-row plus the new
  Strategy N row (added after they were last generated).

## 2026-10-13 — Project restructured
- New layout: `context/`, `skills/`, `data_sources/` (was `data/` + LLM scores
  + cache), `outputs/` (was `results/` + `logs/` + `for_claude/`), `src/`
  (all code; the `newsdrift` package moved out of `newsdrift_system/`),
  `tests/`. All paths centralised in `src/paths.py`; scripts run from the root
  as `python3 src/<script>.py`.
- `fetch_historical_news.py` and `raw_news_pusher.py` now load `.env` from the
  project root (they looked next to the script, which would have broken after
  the move).
- CLAUDE.md rewritten as a navigator; its detailed content moved to
  `context/`. Old CLAUDE.md and all code backed up in
  `_archive/_backup_2026-10-13_before_restructure/`.
- Verified: 41 tests + freshness guard pass; all 7 main outputs reproduced
  byte-for-byte against pre-move checksums.

## 2026-10-11/12
- `--tier0`: keyword scorer on the LLM's headline set → no clear winner on
  the same headlines.
- Anonymization gap found (scores in use were not anonymized).
- Per-strategy risk scales calibrated in-sample (`calibrate_risk.py`, A/B/C),
  frozen in `outputs/frozen_risk_scales_2026-10-11_*.csv`; runner
  `--risk-scales`. Keyword A OOS at frozen scale: 10.8% / Sharpe 2.58 / maxDD
  2.8%.
- `--dd-governor` now applies to Strategy A too; new `risk_scale` lever.
- Strategies D (open → close) and N (close → next open) added: A's edge comes
  from days 2–3.
- Project cleanup: stale outputs, provider pilots and caches → `_archive/`.

## 2026-09-27/28
- Annualisation bug (B/C equity per trade close) fixed with daily equity.
- Strategy B scale-out exits, confirmation entries, C close entry; in-sample
  sweeps (`sweep_strategy_b.py`, `sweep_new_strategies.py`).
- Output files named by scorer/variant so runs no longer overwrite each other.
- `run_both_strategies.py` finds the package without `PYTHONPATH`.
- Bugs 6–8 fixed (`portfolio.py`, `build_event_table`).

## 2026-08-26 → 2026-08-30
- Full LLM scoring with local Ollama llama3.2:3b (~42h incl. outages): 35,974
  headlines, train period only.
- Strategy C implemented. Specialist-agent prompt softened on analyst
  opinions. Google/Groq/NVIDIA pilots; NVIDIA dropped.

## 2026-07 → 2026-08
- Data pipeline (Bloomberg prices, Benzinga news, IEX minute bars),
  newsdrift engine, Strategies A and B, bugs 1–5. See
  `context/project_playbook_2026-07.md` for the original plan.
