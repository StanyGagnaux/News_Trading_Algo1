# Skill: run a backtest

Run everything from the project root with `python3` (not Anaconda `python`).
Runs take ~5–10 min (the minute-bar file is 1.3 GB); run them in the
background and do not start two scoring or backtest jobs that write the same
output at once.

## Main comparison (A, B, C + momentum, 80/20 split)

```bash
python3 src/run_both_strategies.py                                  # keyword, full size
python3 src/run_both_strategies.py --llm-scores data_sources/news_scored_llm_ollama.csv
python3 src/run_both_strategies.py --risk-scales outputs/frozen_risk_scales_2026-10-11_keyword.csv
python3 src/run_both_strategies.py --llm-scores data_sources/news_scored_llm_ollama.csv \
        --risk-scales outputs/frozen_risk_scales_2026-10-11_llm.csv
python3 src/run_both_strategies.py --tier0                          # keyword on the LLM's headlines
python3 src/run_both_strategies.py --dd-governor strict             # hard-cap finding
```

Output: `outputs/results_both_strategies_<variant>.csv` and
`outputs/equity_both_strategies_<variant>.png`. The suffix records the
variant (`keyword`/`llm`, `_strict`, `_scaleX`, `_calibrated`, `_tier0`), so
runs never overwrite each other.

## In-sample experiments (never touch out-of-sample)

```bash
python3 src/calibrate_risk.py [--llm-scores ...]        # risk scale for ~5% IS maxDD
python3 src/sweep_strategy_b.py [--llm-scores ...]      # 13 Strategy B exit variants
python3 src/sweep_new_strategies.py [--llm-scores ...]  # B/C variants, D, N
python3 src/sweep_new_strategies.py --daily-only        # A vs D vs N only (fast)
```

## Rules while doing it

- Tune ONLY on in-sample numbers. Freeze a configuration in writing (dated
  file in `outputs/`) before looking at out-of-sample with it.
- Count every variant tried and update the count in `context/results.md`.
- LLM out-of-sample numbers are meaningless until Bug 1 is fixed
  (`context/bugs.md`).
- After the run, apply `skills/quality_check.md`, then update
  `context/results.md` and `context/changelog.md`.
