# C1 decision and the A/B correction run (Bug 14), dated 24 October 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written 2026-10-24 BEFORE the correction run, by decision of the author. Adds
to `…note_bug14_2026-10-24.md` (5f2ce391…), which is not edited.

## 1. C1 decision

- C1 FAILED the pre-registered Bug 14 placebo criterion: mean R −0.0001 vs
  expected cost −0.0103, gap 2.30 plain SE (limit 2).
- **The criterion is NOT amended.** A date-clustered SE might reduce the gap
  (C1's yearly placebo means swing by about ±0.07R), but changing the rule
  after seeing the result would be a post-hoc choice.
- **C1 is reported as not validated, like C. The hybrid strategy (intraday
  news, multi-day hold) is therefore not evaluated.** No C1 test run.
- A's placebo passed (0.48 SE). Its long-minus-short gap (+0.0060R vs
  −0.0206R, t 3.9) is recorded as descriptive and consistent with the
  membership limitation (`…note_membership_2026-10-24.md`): a universe chosen
  with hindsight from later index members drifts up, so random longs beat
  random shorts.

## 2. Correction run — A and B only (Bug 14 fixed engine)

Scope narrowed from the Bug 14 note: C1 excluded (section 1).

1. Risk scales recalibrated on TRAINING with the same 5% maxDD rule
   (`calibrate_risk.py`, mechanical) for A, B t+5, B t+15, fixed and Kelly:
   - keyword: no score file;
   - LLM: `data_sources/news_scored_llm_ollama_anon.csv` (as on 18 Oct);
   - rung 1b: `data_sources/news_scored_embed_minilm.csv`.
   Output `outputs/risk_calibration_<rung>_bug14fix_2026-10-24.csv`.
2. One run per rung, training + test, the frozen command otherwise unchanged
   (designed governor; LLM `…_anon_incl_test.csv`; rung 1b
   `…embed_minilm_incl_test.csv`). Deflated Sharpe N = 139 for keyword and LLM,
   N = 155 for rung 1b; Jobson-Korkie-Memmel Sharpe difference vs momentum; the
   Kelly − fixed test. Runner option `--skip-c` (C invalid, C1 not validated),
   outputs `results_both_strategies_<rung>_calibrated_bug14fix_2026-10-24*`.
   Each run logged in `outputs/test_period_runs.csv`.
3. Holm for Kelly vs fixed (test period): family of 6 = keyword + LLM × (A,
   B t+5, B t+15), the H2b family without C; rung 1b as its own family of 3.
4. The 18 October A and B rows stay in the record, marked SUPERSEDED (Bug 14:
   optimistic gap fills, entry day/bar unchecked). The ladder's rung-1b A/B
   rows of 24 Oct likewise. C rows stay INVALID (Bug 13).
5. Then descriptive items 1(b) (yearly return and Sharpe) and 2 (correlation
   matrices of daily returns, training and test) on the corrected A and B runs
   plus momentum.

Code (SHA-256 before the additive runner/calibration options; engines as fixed under Bug 14):
    0e552bf72821da57f5ddfa24492e9dc1832502ca603232e962ae2accc6507b3a  src/run_both_strategies.py
    1b07c18e8362429b1281ea3872ff6341f6284e1a058432bc9f58d22022775d05  src/calibrate_risk.py
    833b85dddaacb6844458a2128970c5ef3b2d1768448cb8710d4ef73f4dfe09ae  src/newsdrift/backtest.py
    39ca652ce84839d9d54411109fca404aff09b10938de02a1238cd75ee5d43876  src/newsdrift/intraday.py
    c3c328171d2bfea152e8089c44037dad160417ba87d90c08ebabc9a86c01aded  src/newsdrift/risk.py
    4ee88b1087dfab774473bd554314665b2afa25dbfa510bb6745e33f71cc2c4c1  src/newsdrift/portfolio.py
    0c3c34c09203212ef9bec22754c7af16033bcbd63a76b2ae65cef1e8c0a9e012  src/newsdrift/stats.py
