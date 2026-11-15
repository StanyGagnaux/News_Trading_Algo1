# Rung 2 (Claude Haiku) — strategy layer for the run, dated 24 October 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written 2026-10-24 BEFORE any rung-2 scoring or run (the API key is not yet in
`.env`). Amends the strategy layer of `…note_ladder_2026-10-24.md` (4b26f9e1…)
for rung 2 only; scoring, sampling, look-ahead label, memorisation check and
spend cap stay as in that note and `…note_ladder_decisions_2026-10-24.md`.

When the key arrives, rung 2 runs through:

1. **The corrected engine** (Bug 14 fix, `…note_bug14_2026-10-24.md`; plus the
   Bug 12 and Bug 13 fixes), the same code as the 24 Oct A/B correction run
   (`…note_c1_and_ab_correction_2026-10-24.md`).
2. **Strategies A and B only** (A; B t+5 and t+15; fixed and Kelly).
   **C and C1 are excluded** (C invalid, Bug 13; C1 not validated, placebo).
3. **Risk scales calibrated on training by the same rule** (5% maxDD,
   designed throttle, `calibrate_risk.py --skip-c`) from the training score
   file `data_sources/news_scored_haiku_anon.csv`; output
   `outputs/risk_calibration_haiku_<date>.csv`.
4. One run over training + test with the frozen command otherwise unchanged:
   `run_both_strategies.py --llm-scores data_sources/news_scored_haiku_anon_incl_test.csv
   --risk-scales <calibration> --dd-governor designed --n-trials 155 --skip-c
   --out-name haiku_calibrated_<date> --dump-dir outputs/rung2_<date>/`.
   N = 155 is kept as pre-registered (conservative: fewer rows now run).
5. Same comparison tests as the A/B correction run: Jobson-Korkie-Memmel
   Sharpe difference vs momentum, deflated Sharpe, Kelly − fixed with Holm
   (rung 2 as its own family of 3). Logged in `outputs/test_period_runs.csv`.
   Event study and speed bound for rung 2 as in the ladder note (unchanged).
