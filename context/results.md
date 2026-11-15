# Results (current as of 18 Oct 2026)

> **Bug 13 (24 Oct, unresolved by decision): every Strategy C number in this
> file is INVALID** (minute vs daily price basis; `bugs.md`); C is not rerun.
> **C1 (entry at the news-day close, daily bars only) replaces C as the hybrid
> strategy** (note `…note_bug13_decision_2026-10-24.md`); C1 has in-sample
> results only (keyword −4.2%, LLM +0.6% p.a.); a test run needs its own note.
>
> **Bug 14 (gap fills) — A and B CORRECTED 24 Oct** (section below; note
> `…note_c1_and_ab_correction_2026-10-24.md`). The 18 Oct A and B rows are
> SUPERSEDED. C1 failed its placebo (2.30 SE) and stays not validated.
> **Strategy C reopened once (25 Oct) as a minute-bar-only implementation**
> (note `…note_c_minute_2026-10-24.md`): placebo PASSED under the harmonised
> criterion (disclosed as decided after C's earlier result); results below.
> The 18 Oct C rows stay INVALID (Bug 13).
> **Known limitation:** no point-in-time NDX membership (static 193-ticker
> union; note `…note_membership_2026-10-24.md`) → universe look-ahead
> favouring longs; affects every result.
>
> **Official evaluation = training period + test period** (the single frozen
> runs of 18 Oct 2026). The holdout was dropped by decision before any holdout
> return was computed (`outputs/FROZEN_CONFIG_2026-10-18_note_holdout_dropped.md`);
> H1–H3 and the holdout power figures below are records, not results.

## 24 Oct 2026 — descriptive runs (no new tests; `outputs/descriptive_runs.csv`)

- **1(a) by year** (`descriptive_event_study_by_year_2026-10-24.csv`/`.png`;
  reproduces the official all-events rows exactly): the day-0 move is positive
  and t > 5 in every year for both scorers (+42 to +109 bps). Days 1–3 are
  mostly negative and |t| < 2 in each training year; exceptions 2018 (day 3
  +16 keyword, +15 LLM, t ≈ 2.2) and LLM 2021 (day 3 −17, t −2.1). Test 2026
  (Jan–May only) is the one positive cell set: LLM day 1 +22.0 (t 3.2), day 3
  +27.0 (t 1.9); keyword day 3 +26.5 (t 1.9). Descriptive, partial year.
- **1(c) |strength| vs R by year** (`descriptive_strength_vs_outcome_by_year_2026-10-24.csv`,
  from the exactly reproduced 18 Oct runs, `outputs/repro_frozen_runs_2026-10-18/`):
  keyword uninformative (|s| = 1 for 92–100% of trades). LLM A: corr +0.012
  (t 1.7) training with signs flipping by year (2018 −0.049, 2019 +0.078,
  2022 −0.050); test +0.048 (t 4.3), positive in 2024, 2025 and 2026. LLM B
  ≈ 0 (corr +0.009). Plain t, trades overlap in time; Bug 14 applies to R.
- **3 news sample** (`descriptive_news_sample_2026-10-24.csv`): 319,927 unique
  headlines 2016 → 2026-06-01 (17k–43k a year, rising from 2020); 21.6% name
  ≥ 2 tickers; 46.9% inside RTH; 64,352 pass the Tier-0 pre-filter
  (the LLM-scored set); rows per ticker median 1,296 (IQR 774–2,211), top
  TSLA 37,104, AAPL 30,865, AMZN 24,735.
- **4 subgroups** (`descriptive_subgroups_train_2026-10-24.csv`): reshape of
  the official training event study. No subgroup has a significant positive
  post-entry return; the few cells above 4.86 bps have t < 1 (LLM small caps
  day 5 +7.3, LLM duration ≠ 2 day 5 +10.5). The significant cells are
  negative (keyword corporate_event day 5 −29.9, t −2.7; LLM importance 1–3
  day 3 −66.1, t −2.2, N = 207).

## 18 Oct 2026 — current valid numbers (event studies; gross of costs)

Signed returns in bps, t clustered by entry date; round-trip cost 4.86 bps.

| | day 0 (news) | day 1 | day 2 | day 3 | day 5 |
|---|---|---|---|---|---|
| keyword, training, mkt-adj (N ~ 26,900) | +57.8 (21.2) | -2.8 | -5.2 (-2.0) | -5.6 | -7.2 |
| LLM anon, training, mkt-adj (N ~ 26,000) | +60.6 (25.0) | -2.0 | -4.4 (-1.8) | -2.4 | -2.4 |
| keyword, TEST, mkt-adj (N ~ 13,100) | +62.7 (15.8) | +0.6 | -1.7 | -0.8 | +6.4 (1.0) |
| LLM anon, TEST, mkt-adj (N ~ 10,180) | +78.2 (17.6) | +6.2 (2.1) | -0.3 | -0.4 | +0.2 |

- TEST runs: `event_study_test_keyword+llm_anon_2026-10-18.*` (frozen
  configuration, logged in `outputs/test_period_runs.csv`).
- EXPLORATORY, not confirmed: LLM importance 7-10 in the TEST period, mkt-adj
  day 1 +20.2 (t 3.2), day 2 +27.3 (t 2.9), day 3 +28.2 (t 2.4), day 5 +41.7
  (t 2.6), N = 1,929 -- but -3.4 / -4.7 / -0.9 / +0.4 (all |t| < 1) in
  training. Found among ~100 test cells; not part of H1/H2.

- Keyword corporate_event reversal: training day 3 -21.5 (t -2.5); test day 2
  -33.5 (t -3.0), day 3 -34.3 (t -2.5).
- Intraday (training, RTH, raw): LLM -30m->t +12.5 (t 2.3), t->+30m +2.9,
  t->close +6.1 (t 2.0); keyword ~0 everywhere. **Reconciled 24 Oct with the
  speed bound** (`outputs/reconcile_intraday_2026-10-24.csv`; same events, same
  price at or before the moment, both raw): the +2.9 is on the "common" sample
  (all of −30/+30/+60/close available: 10:00–15:00 headlines, 7,054 events,
  pre-gap LLM file); on every event with a +30 price (current file, 11,308) it
  is +0.02 (t 0.01) — the speed-bound number. Sample explains ~2.7 bps, the
  file version ~0.2. **One number for the thesis:** headline -> +30 min
  +0.0 bps (t 0.0, N 11,308; +2.7, t 1.5 on the common sample) — never above
  the 4.86 bps cost, never significant. The pre-news move is robust: −30 -> t
  +11.5 to +12.5 (t 2.3–2.4) in every combination.
- Files: `outputs/event_study_*_2026-10-18.*`, `outputs/intraday_description_2026-10-18.csv`.
- Everything below this section predates Bug 10/11 where marked.

## 25 Oct 2026 — SENSITIVITY: 20% drawdown target (DESCRIPTIVE; official results stay at 5%)

Note `…note_sensitivity_dd20_2026-10-25.md` (bef29da5…);
`outputs/sensitivity_dd20_summary_2026-10-25.csv`. Scales recalibrated on
training to ~20% maxDD (achieved 19–21% for all 40 configurations), governor
scaled x4 (full size < 12%, taper 12–20%, probe beyond), caps unchanged. All
five 5% repeats reproduce the official 5% results exactly.

- **Momentum at 20%** (scale 2.90): test **+4.5% p.a.**, Sharpe 0.71, maxDD 7.3%.
- **News strategies at 20%, test:** almost all lose 2–11% p.a. (test maxDD up
  to 22%; Haiku C fixed 31%). Best: Sonnet C Kelly +3.6% / Sharpe 0.45 (vs
  momentum −0.19, p 0.86); LLM A Kelly +0.8% / 0.08 (was 1.4% / 0.75 at 5%).
  **No strategy beats momentum; most are significantly worse.**
- **Do Sharpe ratios stay close to 5%?** For 28 of 40 configurations yes
  (|change| ≤ 0.2). The 12 material changes have two causes:
  1. **Metric, not economic** — fixed-size B rows (+0.17 to +0.34): same trades,
     same cap binding; the reported Sharpe is CAGR / vol, which compounding
     shifts at 4x size; the mean/std Sharpe is unchanged (keyword B t+5 fixed
     −8.488 vs −8.491).
  2. **Caps binding under Kelly** — Kelly sizes up after wins, so at 4x scale
     the single-position (20%) and gross (100%) caps bind and trades are skipped
     or clipped: LLM A Kelly 0.75 -> 0.08 (cap days 0% -> 35%, trades 8,093 ->
     6,719; mean/std Sharpe 0.76 -> 0.13), keyword A Kelly 0.03 -> −0.28 (0% ->
     15%), Haiku C Kelly 0.76 -> 0.09 (trades 740 -> 684), keyword/LLM C Kelly,
     Sonnet A/C (cap days 7% -> 18%). Signal ordering matters only through
     these caps (Bug 12's deterministic order is unchanged).
- B/C cap binding (concurrent-risk admission on reference risk) is the same at
  5% and 20% (keyword B 76%, C 93% of test days) — it does not depend on size.
- **Reading:** the best 5% results (LLM A Kelly, Haiku C Kelly) do not survive
  realistic sizing; at 20% momentum earns +4.5% while the news strategies lose.

## 25 Oct 2026 — thesis-audit items

- **Strategy B placebo PASSED** (note `…note_placebo_b_2026-10-25.md`, f0e695ce…;
  `outputs/placebo_b_2026-10-25.csv`; training, keyword B-fixed scales, seed
  20261024): t+5 mean R −0.249 vs cost −0.281 (1.76 SE); t+15 −0.152 vs −0.162
  (0.55 SE); long−short t 0.5 / 1.2 (descriptive). Every engine (A, B,
  minute-bar C, momentum) now passes its placebo. B's costs alone are
  0.16–0.28R per trade (tight intraday stops) — why B loses.
- **FF6 vs official training LLM event count** (26,297 vs 26,209): different
  counts and files. The official log counts signal rows (26,209) with the
  training score file as of 18 Oct 07:35; the FF6 study counts events with a
  price bar (26,297) with the current file, which includes the 1,098 rows of
  2024-03-26 -> 04-29 scored later. Like for like: 18 Oct file 26,209 signals ->
  25,980 events; current file 26,527 -> 26,297 (+317 events, 327 vs 9 signal rows
  from news >= 2024-03-26). The FF6 training LLM numbers include ~1.2% late-scored events.
- **1(b) with the continuous momentum benchmark:**
  `outputs/descriptive_yearly_performance_contmom_2026-10-25.csv` (descriptive):
  test 2024 +0.3% (Sharpe 0.23) instead of +2.1% (1.85) — the per-period
  benchmark skipped the losing May–Sep 2024 stretch; 2025 +1.6% (0.74), 2026
  Jan–May +1.4% (1.41).
- Data description with sources: `for_claude/data_description_2026-10-25.md`.

## 25 Oct 2026 — Phase 4: the cost ladder (`outputs/cost_ladder_2026-10-25.csv`)

| rung | API cost total | latency / headline | test news day (bps, t) | best test strategy (Sharpe; vs momentum p; DSR) | look-ahead |
|---|---|---|---|---|---|
| 0 keyword | $0 | 0.002 ms | +62.7 (15.8) | A Kelly 0.03; p 0.40; 0.005 (N 139) | none |
| 1 Llama 3.2 3B | $0 (local; 27 min/1,000 sequential) | 1.57 s | +78.2 (17.6) | A Kelly **0.75**; p 0.98; 0.055 (N 139) | test clean |
| 1b MiniLM | $0 | 3 ms | −24.9 (−5.6)* | A Kelly −0.63; p 0.20; 0.000 (N 155) | test clean |
| 2 Haiku 5.5 | $2.25 ($0.04/1,000) | 0.94 s | +120.1 (17.6) | C Kelly **0.76**; p 0.96; 0.045 (N 155) | EXPOSED |
| 3 Sonnet 5.5 | $29.30 ($0.49/1,000) | 0.98 s | +158.8 (13.5) | C Kelly 0.23; p 0.67; 0.011 (N 163) | EXPOSED |

Continuous momentum test Sharpe 0.72. *Rung 1b is ~99% short (always-short
model), so its signed news-day return is negative. Data cost $0 for every rung.
Days 1/3/5 after entry: |t| < 2.2 everywhere (only Llama day 1 +6.2, t 2.1).
Speed bound best per rung ≤ +11.2 bps (Sonnet, close, t 1.4); none significant.
Best strategies are chosen ex post (highest test Sharpe of A/B/C × sizing).
Memorisation (named vs anonymised): Haiku corr 0.86 / sign 78%; Sonnet 0.82 / 82%.
Llama latency measured 25 Oct (`outputs/rung1_llama_latency_2026-10-25.json`, 200 calls):
median 1.57 s, all parsed; live sign matches the stored score 93.5% (T 0.2).

**Rung comparisons — DESCRIPTIVE, added after the results, not pre-registered**
(`outputs/rung_comparisons_2026-10-25.csv`; adjacent rungs, test period):
- A Kelly Sharpe difference (JKM): Llama − keyword +0.72 ± 0.88 (p 0.42);
  MiniLM − Llama −1.39 ± 1.03 (p 0.18); Haiku − MiniLM −0.58 (p 0.55);
  Sonnet − Haiku +0.28 (p 0.74). No adjacent difference is significant.
- News-day mean difference (date-clustered SE): Llama − keyword +15.4 bps
  (t 3.5); MiniLM − Llama −103.0 (t −14.0); Haiku − MiniLM +145.0 (t 17.3);
  Sonnet − Haiku +38.7 (t 3.8). Better language models describe the news day
  significantly better; none trades better.

## 25 Oct 2026 — Strategy C (minute-bar only) for Haiku and Sonnet (EXPOSED TO LOOK-AHEAD)

Note `…note_c_minute_rungs2_3_2026-10-25.md`; delta fetch 173 ticker-days (21
ranges with IEX data; existing hold days untouched); one run per rung; A/B rows
reproduce the rung 2 and rung 3 summaries exactly.
`outputs/c_minute_rungs2_3_summary_2026-10-25.csv`.

| C minute, test: return p.a. / Sharpe / maxDD | Haiku | Sonnet |
|---|---|---|
| fixed | −2.8% / −0.91 / 9.4% | −0.0% / −0.00 / 3.8% |
| Kelly | **+2.7% / 0.76 / 3.2%** | +0.3% / 0.23 / 1.3% |

- vs continuous momentum (0.72): Haiku Kelly +0.06 ± 1.0 (p 0.96) — level,
  not better; Haiku fixed −1.65 (p 0.09); Sonnet fixed −0.66, Kelly −0.44 (n.s.).
- DSR: Haiku Kelly 0.045 (N 155), others < 0.02. Haiku Kelly − fixed +1.67
  (p 0.013, single unadjusted test): the same signals give −2.8% or +2.7%
  depending on sizing, and the fixed version breached the 5% drawdown design
  (9.4%) — fragile, not an edge. ~440–740 test trades.

## 30 Oct 2026 — descriptive item 2 recomputed against the continuous momentum benchmark

`outputs/descriptive_correlations_contmom_2026-10-30.csv` (descriptive; the 24 Oct
matrix file is kept): daily-return correlation of every corrected run (A and B
after Bug 14, minute-bar C; keyword, llm, embed_minilm, haiku, sonnet) with
the continuous momentum series, training and test, on each run's own days;
the superseded per-period benchmark is kept as a reference column. See the
file for the cells.

## 30 Oct 2026 — live layer: shadow run empty, parity test not performable, paper trading cancelled

No live result exists. The 26–27 Oct shadow run captured 0 items (the scheduler
slept through both sessions; `outputs/parity_report_2026-10-30.md`, log in
`outputs/logs/live_shadow_2026-10-26_27.log`), so the parity test of the 24 Oct
decisions note (item 6d) was not run. Paper trading was cancelled on 30 Oct
before any order (`…note_paper_trading_cancelled_2026-10-30.md`). Latency is
measured only from headline to score (Llama 1.57 s, Sonnet 0.98 s median,
25 Oct); publication-to-fill latency and slippage are not measured.

## 26 Oct 2026 — duration split of the Rung 2 / Rung 3 event studies (read-only extract)

The frozen event-study specification's duration split ("2 vs not 2", event
level: ticker-day events after the |strength| ≥ 0.20 gate, duration = max over
the day's headlines, `event_study.py` line 197) WAS run for Haiku and Sonnet on
25 Oct. Cells below are extracted from the existing files
`outputs/event_study_{train,test}_{haiku,sonnet}_2026-10-25.csv` (already in
`for_claude/`); nothing was re-run. NDX-adjusted signed bps, date-clustered t.
Because a day with any duration-2 headline is grouped as "2", the "not 2" group
is small even for Haiku (50% one-day rows). Exposed to look-ahead like the rest
of rungs 2–3.

| model | period | duration | N (day 1) | day 1 | day 2 | day 3 | day 5 |
|---|---|---|---|---|---|---|---|
| Haiku | train | 2 | 11,193 | +0.7 (t 0.3) | −3.1 (−0.8) | −3.3 (−0.8) | −9.2 (−1.7) |
| Haiku | train | not 2 | 1,288 | −9.6 (−1.2) | **−39.9 (−2.3)** | **−40.6 (−2.4)** | −38.3 (−1.9) |
| Haiku | test | 2 | 4,662 | +2.9 (0.7) | +0.3 (0.1) | −3.8 (−0.5) | −5.3 (−0.5) |
| Haiku | test | not 2 | 719 | −4.7 (−0.4) | −10.8 (−0.7) | −21.7 (−1.1) | −27.1 (−1.0) |
| Sonnet | train | 2 | 4,972 | +0.1 (0.0) | −9.2 (−1.3) | −6.3 (−0.8) | −5.4 (−0.6) |
| Sonnet | train | not 2 | 404 | +2.6 (0.1) | −26.4 (−1.2) | −22.9 (−0.9) | −40.6 (−1.5) |
| Sonnet | test | 2 | 2,017 | +5.4 (0.7) | −2.6 (−0.2) | −2.0 (−0.2) | −1.4 (−0.1) |
| Sonnet | test | not 2 | 138 | −6.3 (−0.2) | +39.5 (0.8) | +12.4 (0.3) | +20.4 (0.3) |

News-day (day 0) cells: Haiku 2 / not 2 +110 (t 27) / +112 (t 8) training,
+116 (t 16) / +144 (t 7) test; Sonnet +121 (t 18) / +88 (t 3) training, +159
(t 13) / +153 (t 3) test. Reading: no duration group of either model shows a
positive post-entry drift; the only |t| > 2 cells are the negative Haiku
training "not 2" days 2–3 (reversal, N ≈ 1,290), not replicated in the test
period (same sign, |t| ≈ 1). Raw (unadjusted) rows are in the same CSVs.
Llama comparison: `descriptive_subgroups_train_2026-10-24.csv` and the
18 Oct test file (duration ≠ 2 day 5 −75.6, t −2.3, N 357).

## 25 Oct 2026 — Rung 3: Claude Sonnet 5.5 (ALL NUMBERS EXPOSED TO LOOK-AHEAD)

Note `…note_rung3_sonnet_2026-10-25.md` + amendment ($60 hard stop). Same
headline set, prompt, parser, max_tokens 300, default sampling, effort low.
- **Scoring:** 57,637 / 57,665 (99.95%), 80 retried, 28 unscored; 1 reply used
  thinking; 118 hit the cap. **Cost $28.14** (+ $1.16 extras = $29.30; stop at $60
  not reached). Usage `outputs/rung3_sonnet_usage_2026-10-25.json`.
- Most selective scorer: 10.9% of rows pass |strength| ≥ 0.20 (19% exactly 0),
  sd 0.115 — event study N 5,376 training / 2,155 test.
- **Duration output** (share of scored headline-ticker rows, training file
  `news_scored_sonnet_anon.csv`, n = 60,229, same basis as Llama's 5.7% / 94.3%
  / 0.0% on 60,252 rows): **1 / 2 / 3 days = 61.6% / 37.7% / 0.8%**; test rows
  (n = 32,476) 68.7% / 30.7% / 0.6%. On distinct headline texts (training,
  43,448) 53.2% / 45.8% / 1.0%. Computed 26 Oct from the existing score files,
  no re-scoring.
- **Event study** (NDX-adj.): news day +118.9 (t 17) training, **+158.8 (t 14)
  test** — the strongest of all rungs; after entry ≈ 0 (training −10.5 day 2,
  t −1.6; test +4.6 / +0.1 / −1.1 / −0.1, all |t| < 1). No tradable drift.
- **Speed bound:** test +30 min **+10.5 bps (t 1.94)** — the only cell of any
  rung above the 4.86 bps cost, but training +30 min is −5.8 (t −1.0) and N ≈ 700:
  **not replicated, exploratory, treated as noise**.
- **Strategies, test** (N = 161, `outputs/rung3_summary_2026-10-25.csv`): A
  fixed −1.4% / Sharpe −1.09, A Kelly −1.9% / −0.93 (vs continuous momentum
  p 0.054 / 0.073); every B row loses. Training A Kelly +1.0% / 0.40 (the only
  positive training cell). DSR ≈ 0; Kelly − fixed n.s. (p_holm 1.0).
- **Memorisation:** anonymised vs named corr 0.82, sign agreement 82%, mean
  |change| 0.04. **Latency** median 0.98 s.
- **Ladder:** the strongest model gives the sharpest news-day sort and still no
  edge after costs; A loses more than with the 3B Llama (+1.4% / 0.75).

## 25 Oct 2026 — Rung 2: Claude Haiku 5.5 (ALL NUMBERS EXPOSED TO LOOK-AHEAD)

Ladder notes of 24 Oct + rung-2 note. Haiku's knowledge cutoff (June 2026)
covers the whole sample: anonymisation does not remove the look-ahead risk.

- **Scoring** (`src/haiku_batch.py` via `score_news_llm.py --providers haiku`):
  the identical 57,665 representative headlines as Llama (same pre-filter,
  template dedup, anonymised prompt, parser); Message Batches, max_tokens 300,
  default sampling (deviation: Llama used T 0.2), effort `low`. 57,411 scored
  (99.6%), 610 retried once, 254 unscored. 34% of replies used thinking; 905
  hit the 300-token cap. **Cost $2.16** (+ $0.09 extras; cap $30).
  Usage log `outputs/rung2_haiku_usage_2026-10-25.json`.
- Haiku is more selective: 30% of rows pass |strength| ≥ 0.20 (20% exactly
  0), strength sd 0.185 — about half Llama's event count.
- **Duration output** (share of scored headline-ticker rows, training file
  `news_scored_haiku_anon.csv`, n = 59,999, same basis as Llama's 5.7% / 94.3%
  / 0.0% on 60,252 rows): **1 / 2 / 3 days = 49.9% / 47.6% / 2.5%**; test rows
  (n = 32,407) 48.1% / 49.0% / 3.0%. On distinct headline texts (training,
  43,274) 43.5% / 53.5% / 3.0%. Unlike Llama, the duration output is not
  collapsed to 2 days. Computed 26 Oct from the existing score files, no
  re-scoring.
- **Event study** (NDX-adjusted, signed bps): news day +110.2 (t 27) training,
  +120.1 (t 18) test — the strongest news-day sort of any rung; after entry
  training −0.3 / −6.9 / −7.1 / −12.2 (day 5 t −2.2), test +1.9 / −1.1 /
  −6.1 / −8.2 (all |t| < 1). **No tradable drift**; it describes better, it
  does not predict better.
- **Speed bound:** max +2.9 bps (test, +30 min, t 1.4) — below the 4.86 bps cost.
- **Strategies A/B, test** (training scales, N = 155,
  `outputs/rung2_summary_2026-10-25.csv`): A fixed −1.6% / Sharpe −1.17,
  A Kelly −1.6% / −1.21 — both worse than continuous momentum (p 0.048 /
  0.050); every B row loses (Sharpe −0.47 to −3.75). DSR ≈ 0. Kelly − fixed:
  A n.s. (p_holm 0.96); B t+5 / t+15 Kelly better (p_holm 0.003, losing less).
- **Memorisation check** (1,000 test headlines, anonymised vs named): strength
  correlation 0.86, sign agreement 78% (zeros count as disagreement), mean
  |change| 0.07. **Latency** (200 real-time calls): median 0.94 s, p90 1.75 s.
- **Ladder conclusion:** the most capable scorer (and the only one exposed to
  look-ahead) does no better after costs than the keyword dictionary or the
  3B Llama; none beats momentum.

## 25 Oct 2026 — Strategy C, minute-bar-only (reopened once; disclosed correction)

Note `…note_c_minute_2026-10-24.md` (281afbb2…). One price basis by
construction: entry, stops, targets, exits on full-session IEX minute bars
(`data_sources/bars_c_hold.csv`, fetched for C only, 7,173 ranges, from
2020-07-27); stop distance = entry × max(2 × mean daily (high−low)/close,
0.4%); regular session only; Bug 14 fills; time exit at the last bar ≤ 16:00
New York; no dividend credit. Unit tests 11/11 (`tests/test_c_minute.py`).

- **Placebo (training, seed 20261024, 13,257 trades): PASSED** — mean R
  −0.0120 vs expected cost −0.0116 (−0.09 SE). Long − short +0.114R (t 12.4),
  descriptive; follows the market by year (longs 2020/2023, shorts 2022) —
  drift + universe look-ahead. Ex-dividend effect −0.0001R (below the
  estimator's noise). 18 stale exits.
- **Test period** (one run per rung, scales recalibrated on training;
  `outputs/c_minute_summary_2026-10-24.csv`):

| C minute, test: return p.a. / Sharpe / maxDD | keyword | LLM | rung 1b |
|---|---|---|---|
| fixed | −0.5% / −0.42 / 2.1% | −0.5% / −0.26 / 4.4% | −1.2% / −1.27 / 2.6% |
| Kelly | −0.6% / −0.54 / 2.2% | +0.9% / 0.42 / 4.0% | −0.8% / −1.03 / 1.7% |

- vs continuous momentum (JKM, test): keyword fixed −1.15 (p 0.20), Kelly
  −1.28 (p 0.19); LLM fixed −0.98 (p 0.29), Kelly −0.29 (p 0.77); rung 1b
  fixed −2.03 (p 0.048, worse), Kelly −1.78 (p 0.08). None beats momentum.
- Deflated Sharpe ≈ 0 everywhere (best LLM Kelly 0.018). Kelly − fixed: Holm
  family of 2 (keyword, LLM) p_holm 0.83 / 0.55; rung 1b p 0.72 — none
  significant. ~850–950 test trades per rung (as the old C: one position per
  ticker, concurrent-risk cap).
- **Conclusion:** the hybrid strategy (intraday news entry, 1–3 day hold) does
  not beat momentum and loses money for keyword and rung 1b; rung 1b's earlier
  "+21%" was the Bug 13 artefact. A and B in these runs equal the Bug 14
  correction exactly (checked).

## OFFICIAL intraday timing figure (thesis number, training, RTH, LLM, raw)

**Headline -> +30 min: +0.0 bps (t 0.0, N 11,308)** — the full sample of
trading-hours LLM events with a +30-minute price (price = last 1-minute bar
ending at or before the moment; current training score file). **Pre-news,
−30 min -> headline: about +12 bps** (+11.5, t 2.4, N 7,898 events with a −30 price,
same file and convention; +11.5 to +12.5 in every sample). The earlier **+2.9** (t 1.5)
came from a 7,054-event sub-sample requiring all of −30/+30/+60/close
(10:00–15:00 headlines) and the pre-gap score file; it is not the official
figure (`outputs/reconcile_intraday_2026-10-24.csv`).

## 24 Oct 2026 — momentum benchmark check (code review + placebo)

- Matches the specification: lookback 90 trading days with a 5-day skip
  (return t−90 -> t−5), 20-day vol estimate, rebalance every 5 trading days,
  weights applied to the next day's return (one-day lag), costs on turnover at
  the empirical 2.43 bps per side.
- **Deviations** (recorded in `bugs.md`, not changed): (1) the 10% target is
  per name and divided by all 193 tickers (including not-yet-listed ones), so
  realised portfolio vol is 2–3% p.a., not 10% — Sharpe is unaffected
  (scale-free), return p.a. and maxDD are not comparable in level; (2) the
  runner restarts momentum in each period, so it holds nothing for the first
  90 trading days of the TEST period (2024-04-30 -> 09-10, 17% of days): test
  Sharpe 1.07 over all days vs 1.18 after the warm-up. **Corrected below:**
  the 1.18 is a sub-period figure; run continuously, momentum's full test
  Sharpe is 0.72 — the warm-up had skipped a losing stretch, so the frozen
  benchmark OVERSTATED momentum (the earlier "understates" was wrong);
  (3) between rebalances weights are held constant (drift rebalancing not
  costed); rebalance every 5 rows, not calendar weeks. Minor.
- Placebo (training, random ±1 per ticker-day, seed 20261024,
  `outputs/placebo_momentum_2026-10-24.csv`): net −0.198 bps/day vs expected
  cost −0.180 (gap −0.15 SE) — random positions lose about their costs.
  Long minus short +0.8 bps/day per unit held (t 1.2), descriptive. The
  refactored engine reproduces the archived one exactly.
- Universe look-ahead likely favours momentum more than the news strategies
  (`…note_membership_addendum_2026-10-24.md`).

## 24 Oct 2026 — momentum benchmark CORRECTED (continuous + scaled)

Note `…note_momentum_2026-10-24.md`; `src/momentum_continuous.py`;
`outputs/momentum_continuous_2026-10-24.csv`, comparisons
`outputs/comparison_vs_continuous_momentum_2026-10-24.csv`.

| momentum, return p.a. / Sharpe / maxDD / vol | training | test |
|---|---|---|
| per period (frozen, SUPERSEDED) | +0.9% / 0.30 / 6.8% / 3.1% | +2.5% / 1.08 / 3.2% / 2.3% |
| **continuous** (from 2015-01-07) | +0.5% / 0.17 / 6.9% / 3.1% | **+1.6% / 0.72 / 2.6% / 2.2%** |
| continuous, scaled k = 0.726 (training maxDD 5%) | +0.4% / 0.17 / 5.0% / 2.3% | +1.1% / 0.73 / 1.9% / 1.6% |

- Continuous = one series on the runner's 171 tickers; the test period starts
  with its 90-day history. Truncation check (cut 2025-04-30): identical up to
  the cut — no look-ahead.
- Scaled: mean/std Sharpe identical by construction (checked to 1e-9); the
  reported Sharpe (CAGR / vol) moves only by volatility drag (0.725 vs 0.726).
- **Sharpe difference vs the continuous benchmark, test (JKM):** LLM A Kelly
  **+0.02 ± 0.95 (p 0.98)** — level with momentum; keyword A Kelly −0.70
  ± 0.84 (p 0.41); LLM A fixed −0.84 (p 0.34); keyword A fixed −1.95
  (p 0.015, worse); rung 1b A fixed −2.93 (p 0.007, worse), A Kelly −1.37
  (p 0.20); every B row worse (p ≤ 0.007). **No news strategy beats momentum;
  the best (LLM A Kelly, Sharpe 0.75) matches it (0.72).** The old benchmark
  reproduces the earlier comparison exactly (checked); those rows are superseded.
- Disclosed limitations (not changed): weights held constant between
  rebalances (drift back to target weights not priced); rebalance every 5
  trading days, not calendar weeks; 10% vol target applied per name / ticker
  count (realised 2–3%; the scaled series addresses comparability).

## 24 Oct 2026 — CORRECTED strategies A and B (Bug 14 fixed engine), TEST period

Disclosed correction run (note `…note_c1_and_ab_correction_2026-10-24.md`):
risk scales recalibrated on training (same 5% rule,
`outputs/risk_calibration_<rung>_bug14fix_2026-10-24.csv`), one run per rung,
`outputs/results_both_strategies_<rung>_calibrated_bug14fix_2026-10-24*.csv`,
logs `outputs/logs/test_run_strategies_<rung>_bug14fix_2026-10-24.log`. Net of
costs, 2024-04-30 -> 2026-06-01. Engine includes the Bug 12 and Bug 14 fixes.

| test period: return p.a. / Sharpe / maxDD | keyword | LLM | rung 1b (MiniLM) |
|---|---|---|---|
| A fixed | -0.7% / -1.22 / 2.0% | -0.1% / -0.11 / 1.7% | -1.0% / -2.18 / 2.2% |
| A Kelly | +0.1% / 0.03 / 2.8% | **+1.4% / 0.75 / 2.2%** | -0.5% / -0.63 / 1.2% |
| B t+5 fixed / Kelly | -2.6% / -2.0% | -1.9% / -1.9% | -2.0% / -1.4% |
| B t+15 fixed / Kelly | -2.5% / -1.9% | -1.4% / -1.7% | -1.4% / -1.8% |
| Momentum, per period (SUPERSEDED) | +2.5% / 1.08 / 3.2% | (same) | (same) |
| **Momentum, continuous** | +1.6% / 0.72 / 2.6% | (same) | (same) |

- **No news strategy beats momentum.** Against the continuous benchmark
  (section above): LLM A Kelly +0.02 ± 0.95 (p 0.98). [SUPERSEDED, per-period
  benchmark: LLM A Kelly −0.32 ± 0.96 (p 0.74); keyword A Kelly −1.04 ± 0.81
  (p 0.20); keyword A fixed −2.29 ± 0.83 (p 0.006); rung 1b A fixed −3.26
  (p 0.002); every B row worse (p ≤ 0.002).]
- Deflated Sharpe: LLM A Kelly 0.055 at N = 139 (0.18 / 0.11 / 0.07 at
  N = 25 / 50 / 100); keyword A Kelly 0.005; rung 1b (N = 155) ≈ 0.
- Kelly − fixed, Holm (`outputs/holm_kelly_vs_fixed_bug14fix_2026-10-24.csv`):
  family of 6 (keyword + LLM): A keyword +1.26 (p 0.044, p_holm 0.088), A LLM
  +0.86 (p 0.16, p_holm 0.16) — not significant; all four B rows p_holm ≤
  0.001. Rung 1b family of 3: A +1.56 (p_holm 0.021), B t+5 p_holm 0.0003,
  B t+15 p_holm 0.043 — Kelly loses less on a losing strategy.
- Effect of the fix (test Sharpe, old → new): LLM A Kelly 1.80 → 0.75, LLM A
  fixed 0.83 → −0.11, keyword A Kelly 0.61 → 0.03; B rows move by < 0.9 and
  stay strongly negative. The 18 Oct A edge was largely the optimistic gap fills.
- Descriptive 1(b) (`descriptive_yearly_performance_bug14fix_2026-10-24.csv`):
  LLM A Kelly is positive in every test year (2024 +0.6%, 2025 +1.1%, 2026
  Jan–May +1.1%) but negative in 2016–17 and 2020 training years; B is
  negative in every year. Descriptive 2 (`descriptive_correlations_bug14fix_2026-10-24.csv`):
  daily-return correlations are low (|ρ| ≤ 0.45; momentum vs any strategy
  −0.21 to +0.32); keyword A vs LLM A 0.30 (train) / 0.20 (test).

## 18 Oct 2026 — strategies, TEST period (single frozen run per scorer) — SUPERSEDED for A and B (Bug 14: optimistic gap fills, entry day/bar unchecked); C INVALID (Bug 13)

`FROZEN_CONFIG_2026-10-18_note_strategies.md`; logs
`outputs/logs/test_run_strategies_{keyword,llm}_2026-10-18.log`; comparisons
`outputs/results_both_strategies_*_comparison.csv`. Net of costs,
2024-04-30 -> 2026-06-01, designed governor, training risk scales.

| test period | keyword: return p.a. / Sharpe / maxDD | LLM: return p.a. / Sharpe / maxDD |
|---|---|---|
| A fixed | -0.4% / -0.64 / 1.8% | +1.0% / 0.83 / 1.2% |
| A Kelly | +1.4% / 0.61 / 2.4% | **+4.0% / 1.80 / 2.0%** |
| B t+5 fixed / Kelly | -2.7% / -2.1% | -1.9% / -2.0% |
| B t+15 fixed / Kelly | -2.9% / -1.7% | -1.5% / -1.6% |
| C fixed / Kelly | -0.3% / -0.9% | +0.3% / -0.2% |
| Momentum | +2.5% / 1.08 / 3.2% | (same) |

- vs momentum (Jobson-Korkie-Memmel, Sharpe difference +- SE): LLM A Kelly
  +0.70 +- 0.96 (p 0.47); keyword A Kelly -0.45 +- 0.81 (p 0.58); keyword A
  fixed -1.71 +- 0.82 (p 0.04, worse); all B significantly worse; C n.s.
- Deflated Sharpe (N = 139): LLM A Kelly 0.46 (N 25/50/100: 0.72/0.61/0.51);
  keyword A Kelly 0.04. No strategy is significant after multiple testing.
- Kelly - fixed: A keyword +1.26 +- 0.62 (p 0.04), A LLM +0.94 +- 0.60
  (p 0.12); B Kelly better (p < 0.001) WITH LOWER exposure (t+15 keyword
  0.19 vs 0.29); A Kelly holds MORE exposure (keyword 0.16 vs 0.08, LLM 0.18
  vs 0.13) -- A's Kelly advantage is not from holding less risk.
- LLM A test: |strength| predicts R (t +4.3), unlike training (t +1.7).
- Kelly - fixed with Holm across the 8 comparisons (A, B t+5, B t+15, C x 2
  scorers; `outputs/h2b_kelly_vs_fixed_holm_2026-10-19.csv`): A keyword
  p_adj 0.165, A LLM 0.353 (not significant); all four B rows p_adj <= 0.006;
  C n.s. (the 6-comparison family with B = t+15 gives the same p_adj).
- Bug 12 (fixed 18 Oct; official runs unchanged): training order-noise floor,
  Sharpe sd across 20 random orders -- A fixed 0, A Kelly 0.09 (keyword) /
  0.04 (LLM), B 0.05-0.27, C 0.10-0.28, D 0.21 (`order_robustness_2026-10-19.csv`).
- H3 pre-registered 18 Oct (LLM day-3 slope on |strength|): test-period slope
  +121 bps (t 1.79); holdout ~1,924 events on 99 dates -> power ~0.19
  (0.10 at half the effect).

## 18 Oct 2026 — strategies, TRAINING period, fixed engine (Bugs 10+11), anonymised LLM

Net of costs (2.43 bps/side), 2016-01-04 -> 2024-04-29, risk scaled to ~5%
maxDD (designed throttle). `outputs/risk_calibration_{keyword,llm}.csv`.

| | keyword: return p.a. / Sharpe | LLM: return p.a. / Sharpe |
|---|---|---|
| A daily 1-3d, fixed | -0.6% / -0.57 | -0.1% / -0.09 |
| A daily 1-3d, Kelly | +0.2% / +0.11 | +1.4% / +0.61 |
| B intraday t+5, fixed / Kelly | -1.4% / -4.78 ; -1.3% / -2.54 | -1.3% / -6.98 ; -1.3% / -3.21 |
| B intraday t+15, fixed / Kelly | -1.3% / -2.39 ; -1.2% / -1.55 | -1.4% / -4.92 ; -1.3% / -2.34 |
| C hybrid, fixed / Kelly | -1.2% / -1.57 ; -1.2% / -0.65 | -1.2% / -1.09 ; -1.4% / -1.40 |
| Momentum benchmark | +0.9% / 0.30 (SE 0.35), maxDD 6.8% | (same) |

Sharpe SE ~0.35 for every row (8.3 years), so no row differs significantly
from zero or from momentum. Raw size (scale 1): A keyword -5.4% p.a.,
maxDD 53%; A LLM fixed -4.1%. D/N sweeps (raw size): keyword N -5.3%;
LLM D -0.3%, N -4.3% (single arbitrary orders). Keyword D is dominated by
order noise (Bug 12): -1.7% deterministic, -6.3% to +0.3% across 20 orders.
D and N are training-only.


Source files are in `outputs/`. IS = in-sample 2016-01-04 → 2024-04-29,
OOS = out-of-sample 2024-04-30 → 2026-06-01. Format: return p.a. / Sharpe /
maxDD / trades.

> **13 Oct 2026 — ALL STRATEGY A NUMBERS BELOW ARE INVALID (Bug 10, ATR on
> the wrong rows).** Fixed engine, A raw scale 1, in-sample: keyword −3.7% /
> Sharpe −0.29 / maxDD 39.5% / 21,669 trades; LLM −3.7% / −0.30 / 39.7% /
> 13,632. At ~5% in-sample maxDD: keyword fixed −0.6% / −0.59 (scale 0.0047),
> keyword Kelly +0.6% / +0.31 (0.0106); LLM fixed −0.1% / −0.04 (0.0154), LLM
> Kelly +1.1% / +0.46 (0.0367). OOS not rerun. B/C/D/N numbers unaffected.

**Read before quoting anything:**
1. **LLM OOS is unusable** (`bugs.md`, Bug 1): the test period was never
   scored, so LLM OOS rests on 89–175 trades from recycled template headlines.
   Only keyword OOS is meaningful.
2. **24 in-sample variants** have been tried for B/C/D/N; none is profitable
   on both scorers. Report this count.
3. **Keyword OOS is not a pristine single look:** it has been run several
   times during development.

## Headline: calibrated to ~5% in-sample maxDD (frozen 11 Oct 2026)

`outputs/results_both_strategies_{keyword,llm}_calibrated.csv`

| Keyword | IS | OOS |
|---|---|---|
| **A fixed** | 10.2% / 1.92 / 4.9% / 18,568 | **10.8% / 2.58 / 2.8% / 2,797** |
| A Kelly | 7.6% / 1.31 / 4.9% / 17,411 | 9.2% / 1.98 / 2.7% / 2,613 |
| Momentum benchmark | 0.9% / 0.30 / 6.8% | 2.5% / 1.08 / 3.2% |
| B (t+5, t+15) | −1.2% to −1.4% / 5.1–5.2% | −1.7% to −2.9% / 3.9–6.3% |
| C | −1.2% / 5.0–5.1% | −0.3% to −0.9% / 1.4–3.7% |

| LLM (IS only) | |
|---|---|
| A fixed | 4.4% / 1.29 / 5.1% / 12,627 |
| A Kelly | 5.3% / 1.29 / 5.1% / 12,336 |
| B, C | −1.3% / 5.0–5.2% |

- The 5% target **held out of sample** for A (2.8% realised) with the
  in-sample scale. B overshoots slightly (up to 6.3%): negative edge.
- A OOS Sharpe (2.58) above IS (1.92) is NOT yet checked: only ~2 years and
  ~2,800 trades. Check year by year and the long/short split before writing up.

## Full size (risk scale 1.0)

`outputs/results_both_strategies_{keyword,llm}.csv`

| | Keyword IS | Keyword OOS | LLM IS |
|---|---|---|---|
| A fixed | 14.5% / 1.07 / 17.1% / 13,851 | 13.6% / 0.89 / 9.7% / 2,410 | 15.2% / 1.16 / 15.8% / 9,266 |
| A Kelly | 10.9% / 0.81 / 20.6% / 13,361 | 22.0% / 1.41 / 9.3% / 2,261 | 9.0% / 0.72 / 20.3% / 10,278 |
| B t+5 fixed | −16.0% / −3.27 / 49.8% | −25.1% / −3.57 / 46.7% | −15.0% / −2.44 / 48.2% |
| B t+15 fixed | −10.4% / −0.90 / 35.3% | −17.5% / −2.97 / 34.3% | −10.9% / −1.17 / 37.6% |
| C fixed | −7.6% / −0.92 / 31.9% / 1,626 | −5.2% / −0.57 / 19.3% / 949 | −11.1% / −1.88 / 38.5% / 1,578 |
| C Kelly | −4.9% / −0.47 / 23.4% / 1,534 | −3.5% / −0.30 / 17.5% / 850 | −9.0% / −1.66 / 32.1% / 1,568 |

**Why A improves when sized down:** at full size the 100% gross-exposure cap
skipped about half of A's 28,391 in-sample signals; at the calibrated size it
trades 18,568, so diversification raises Sharpe. The original sizing was too
large for the caps (a methodology point worth a sentence).

## Keyword vs LLM

- **Same headlines** (`--tier0`, keyword on the LLM's headline set, full size,
  IS): A fixed 12.1% / 0.99 / 15.3% / 8,011; A Kelly 11.0% / 0.91; B t+15
  −5.8% / −0.61; C −6.4% / −0.74. Versus LLM: A fixed LLM better, A Kelly
  keyword better, B/C keyword better. **No clear winner on the same
  headlines** — most of the calibrated gap comes from coverage (keyword reads
  more headlines → more trades → more diversification), not scoring quality.
  Keyword-tier0 OOS (valid): A fixed 14.7% / 1.10, Kelly 16.9% / 1.36.
- The LLM trades more on the same headlines (9,266 vs 8,011): it gives almost
  every headline a non-zero score.
- **Pilot diagnostics (200 headlines):** Ollama 3B strength std 0.236 (keyword
  0.238), 0% neutral, duration collapsed to 2 days. Google Gemini pilot: std
  0.335, 24% neutral, real duration spread — a stronger model is the obvious
  next test (`skills/score_news.md`).
- These are findings about a **small 3B local model** (the "free" rung of the
  cost-of-alpha ladder), not about LLMs in general.

## Where A's edge comes from (in-sample, 9 variants per scorer)

`outputs/sweep_new_strategies_{keyword,llm}{,_daily}.csv`

| | Keyword | LLM |
|---|---|---|
| A: next open, hold 1–3 days | +14.5% / 1.07 | +15.2% / 1.16 |
| D: first session only (next open → close) | −1.7% deterministic; −6.3% to +0.3% by order (Bug 12) | −6.2% / −0.80 (one order) |
| N: first night only (first close after news → next open) | −5.3% / −0.84 | −3.9% / −0.55 |

D and N each make ≈ −0.01R per trade ≈ the round-trip cost (≈ zero before
costs). **A's profit comes from days 2–3 after entry**, not the first session
or first night. This explains why B, C and D fail: they exit before the part
that pays. Slower than the literature's "absorbed in ~2 days".

## Strategy B and C variants (in-sample, none profitable on both scorers)

- `outputs/sweep_strategy_b_*.csv` (13 variants): later entry (t+30/60),
  half at 1R + runner, trailing stop, wider stop. Best: keyword t+15 half+trail
  −7.8% / −0.59; LLM t+60 half+runner −3.7% / −0.28 — best variant flips
  between scorers → mostly noise. Wider stop cut stop-outs ~61% → ~46%; loss
  per trade roughly halved (−0.2R → −0.05 to −0.09R). B appears roughly
  breakeven before costs (~0.15R per trade at a ~35 bps stop).
- `outputs/sweep_new_strategies_*.csv`: B1 confirmation entry (keyword −11.4%,
  LLM −6.2%), B2 hold to close (−11.2%, −7.1%), C1 entry at news-day close
  (−4.2%, +0.6%), C2 confirmation (−6.1%, −8.3%), C3 no target (−0.5%, −5.4%).

## R² (does |strength| predict the size of the move?)

- Keyword: ~0.0000 (90.9% of trades have |strength| = 1.0).
- LLM, Strategy C, current code: 0.0276 IS / 0.0869 OOS (OOS unusable,
  Bug 1). Pre-fix numbers were 0.0053 IS / 0.0488 OOS. For scale, Gu/Kelly/Xiu
  (2020) report ~0.004 for monthly returns.
- **Do not write up as confirmed** until Bug 1 is fixed. A 31-ticker slice
  after the Sept fix gave ~0.006 on ~560 trades (t ≈ 1.8, not significant).
- Hit rates: B 28–35%, C 40–49%; breakeven for a 2R target is 33.3%.

## Historical: pre-fix LLM run (27 Sept 2026), kept as a record

B/C rows INVALID (no governor in B/C, same-day look-ahead, duplicated
trades). In-sample:

| Strategy | Return p.a. | Sharpe | maxDD | Trades | Hit rate | R² |
|---|---|---|---|---|---|---|
| A daily 1-3d, fixed | 15.2% | 1.16 | 15.8% | 9,266 | 47.5% | 0.00014 |
| A daily 1-3d, Kelly | 9.0% | 0.72 | 20.3% | 10,278 | 47.2% | 0.00006 |
| Momentum benchmark | 0.9% | 0.30 | 6.8% | — | — | — |
| B intraday t+5min | −42.8% | −2.50 | 100% | 18,703 | 28.7% | 0.00019 |
| B intraday t+15min | −26.5% | −1.47 | 100% | 18,402 | 32.9% | 0.00090 |
| C hybrid, fixed | −37.0% | −2.52 | 78.6% | 1,738 | 42.3% | 0.00528 |
| C hybrid, Kelly | −33.2% | −2.51 | 75.6% | 11,906 | 42.0% | 0.00263 |

---

## Appended 10 November 2026 — Bug 15 CORRECTION of Strategy A (all ten A rows) and corrections to statements above (appended; nothing above is edited)

> **Bug 15 (same-day information in A's position sizing; `bugs.md`) — every Strategy A row above, fixed and Kelly,
> training and test, 5% and 20%, is SUPERSEDED by this section.** B, C, the momentum benchmark, the event studies,
> the within-day description and the speed bound are unchanged.

Disclosed correction run of 10 Nov 2026 (notes `…note_bug15_2026-11-10.md`, `…note_bug15_addendum_testD2_2026-11-10.md`,
`…note_bug15_results_2026-11-10.md`): fixed engine (all sizing inputs at the previous close), scales recalibrated on
training, one run per rung at 5% and one at 20%, Strategy A only, against the stored continuous momentum series of
24 Oct. Files `outputs/results_both_strategies_<rung>_calibrated_bug15fix_2026-11-10*.csv`,
`risk_calibration_<rung>[_dd20]_bug15fix_2026-11-10.csv`, `a_rows_old_vs_new_bug15fix_2026-11-10.csv`; logged in
`outputs/test_period_runs.csv`. Trial counts unchanged (139 / 155 / 161 / 163).

| A, test period, 5%: return p.a. / Sharpe / maxDD | keyword | Llama | MiniLM | Haiku (exposed) | Sonnet (exposed) |
|---|---|---|---|---|---|
| fixed (was) | −0.7% / −1.22 / 2.0% | −0.1% / −0.11 / 1.7% | −1.0% / −2.18 / 2.2% | −1.6% / −1.17 / 3.7% | −1.4% / −1.09 / 3.4% |
| **fixed (corrected)** | −0.7% / −1.22 / 2.1% | −0.1% / −0.11 / 1.7% | −1.0% / −2.18 / 2.2% | −1.6% / −1.17 / 3.7% | −1.4% / −1.09 / 3.5% |
| Kelly (was) | +0.1% / 0.03 / 2.8% | +1.4% / 0.75 / 2.2% | −0.5% / −0.63 / 1.2% | −1.6% / −1.21 / 3.6% | −1.9% / −0.93 / 4.8% |
| **Kelly (corrected)** | **−1.7% / −1.36 / 4.3%** | **+0.8% / 1.08 / 1.0%** | −0.4% / −1.19 / 0.8% | −1.7% / −1.55 / 3.7% | −2.9% / −1.39 / 6.5% |
| Kelly, training Sharpe (was → corrected) | +0.09 → −0.75 | +0.24 → −0.54 | −0.38 → −0.84 | −0.39 → −0.49 | +0.40 → +0.05 |

- Scales (5%): keyword fixed 0.0039 → 0.0041, Kelly 0.0082 → 0.0033; Llama Kelly 0.0228 → 0.0096; MiniLM Kelly
  0.0031 → 0.0015; Haiku Kelly 0.0454 → 0.0362; Sonnet fixed 0.0359 → 0.0361, Kelly 0.1307 → 0.1294 (training
  drawdown 4.32%: the search alternated around 5%). Fixed rows: Sharpe within 0.002, trade counts unchanged.
- **No news strategy beats momentum (0.72).** Sharpe difference, test (JKM): Llama A Kelly **+0.34 ± 0.95
  (p 0.72)**; keyword A Kelly −2.10 ± 0.92 (p 0.023); MiniLM A Kelly −1.93 (p 0.067); Haiku A Kelly −2.30 (p 0.017);
  Sonnet A Kelly −2.14 (p 0.019); fixed rows as before (keyword p 0.015, Llama 0.34, MiniLM 0.007, Haiku 0.048,
  Sonnet 0.054). `comparison_vs_continuous_momentum_bug15fix_2026-11-10.csv` (forty configurations).
- **Llama A Kelly rose (0.75 → 1.08) when the look-ahead was removed**, the only Kelly row that did. Same trades and
  R-multiples as before, sizes verified from previous-close information; deflated Sharpe 0.131 at N = 139 (0.32 /
  0.23 / 0.16 at N = 25 / 50 / 100); training Sharpe −0.54; positive in each test year (+0.2%, +0.5%, +0.9%). Not
  significant on any test; one draw of five.
- Kelly − fixed, Holm re-adjusted (`holm_kelly_vs_fixed_bug15fix_2026-11-10.csv`): keyword A −0.15 (p 0.81; was
  +1.26, p 0.044); Llama A +1.18 ± 0.62 (p 0.056, p_holm 0.11); MiniLM A +1.00 (p_holm 0.093; was 0.021); Haiku A
  −0.39 (p 0.56); Sonnet A −0.31 (p 0.62). No A difference is significant; MiniLM B t+15 p_holm 0.043 → 0.086 (rank).
- **Forty configurations, test period:** 36 lose (was 35); 24 significantly worse than momentum at 5% (was 22);
  best per rung: keyword C fixed −0.42 (was A Kelly 0.03), Llama A Kelly 1.08 (DSR 0.131), MiniLM C Kelly −1.03
  (was A Kelly −0.63), Haiku C Kelly 0.76, Sonnet C Kelly 0.23 (`cost_ladder_bug15fix_2026-11-10.csv`,
  `recounts_forty_configurations_bug15fix_2026-11-10.csv`).
- Adjacent rungs, A Kelly (descriptive, `rung_comparisons_bug15fix_2026-11-10.csv`): Llama − keyword +2.44 ± 0.88
  (p 0.006; was +0.72, p 0.42); MiniLM − Llama −2.27 ± 1.04 (p 0.030); Haiku − MiniLM −0.37 (p 0.71); Sonnet − Haiku
  +0.16 (p 0.84).
- **20% sensitivity** (`sensitivity_dd20_summary_bug15fix_2026-11-10.csv`, descriptive): A Sharpe ratios stay within
  0.04 of their 5% values except Sonnet A Kelly (−1.39 → −1.04; cap days 0.4% → 11.3%). Llama A Kelly 1.08 → 1.06
  (+3.3% p.a., maxDD 4.1%, 8,091 trades). **The statement above that Llama A Kelly falls from 0.75 to 0.08 at 20%
  because caps bind under Kelly no longer holds**: it came from the inflated scale (0.2034; now 0.0415).
- Checks: acceptance tests A–E and D2 (results note); strict sizing assertion 0 violations in 474,557 trades; A
  placebo unchanged; harness rerun 204 / 204 files, 268 / 272 assertions (`for_claude/verification_summary_2026-11-10.md`).
  **A random-direction placebo cannot detect a look-ahead in position size, with any sizer; the strict assertion and
  the common-direction placebo are the checks that detect it.**

**Corrections to statements above (the data files are right; these sentences were not):**

1. Line 90, "achieved 19–21% for all 40 configurations": the minimum in `sensitivity_dd20_summary_2026-10-25.csv` is
   18.8% (Haiku C Kelly). After the correction the ten A rows lie between 18.5% (Haiku A Kelly) and 20.9%.
2. Lines 97 and 107, "0.08" and "p 0.86": the file has 0.0746 and 0.8547 (0.07 and 0.85). The Llama figure is
   superseded by Bug 15 in any case.
3. Line 256, "the only cell of any rung above the 4.86 bps cost": four speed-bound cells are above the cost
   (`above_cost` True): Haiku training close +5.31 (t 1.07); Sonnet training close +13.86 (t 1.03); Sonnet test
   +30 min +10.46 (t 1.94); Sonnet test close +11.20 (t 1.44). None is significant.
4. Line 359, "divided by all 193 tickers (including not-yet-listed ones)": the divisor is the number of price
   columns, 171 (`baseline.py` l. 36; `momentum_continuous_2026-10-24.log` l. 3).

---

## Appended 10 November 2026 (later) — Bug 16 CORRECTION of Strategy A (all ten A rows) (appended; nothing above is edited)

> **Bug 16 (positions in tickers that stop trading were never closed; `bugs.md`) — every Strategy A row above,
> including the Bug 15 section, is SUPERSEDED by this section.** B, C, the momentum benchmark, the event studies,
> the within-day description and the speed bound are unchanged.

Disclosed correction run of 10 Nov 2026 (notes `…note_bug16_2026-11-10.md`, `…note_bug16_results_2026-11-10.md`):
fixed engine (Bug 15 and Bug 16 rules), scales recalibrated on training, one run per rung at 5% and one at 20%,
Strategy A only, against the stored continuous momentum series. Files
`outputs/results_both_strategies_<rung>_calibrated_bug16fix_2026-11-10*.csv`,
`risk_calibration_<rung>[_dd20]_bug16fix_2026-11-10.csv`, `a_rows_old_vs_new_bug16fix_2026-11-10.csv` (previous =
Bug 15 rows); logged in `outputs/test_period_runs.csv`. Trial counts unchanged (139 / 155 / 161 / 163).

| A, test period, 5%: return p.a. / Sharpe / maxDD | keyword | Llama | MiniLM | Haiku (exposed) | Sonnet (exposed) |
|---|---|---|---|---|---|
| fixed (Bug 15 run) | −0.7% / −1.22 / 2.1% | −0.1% / −0.11 / 1.7% | −1.0% / −2.18 / 2.2% | −1.6% / −1.17 / 3.7% | −1.4% / −1.09 / 3.5% |
| **fixed (corrected)** | −1.4% / −1.22 / 4.0% | −0.2% / −0.12 / 3.3% | −1.3% / −2.10 / 2.7% | −1.6% / −1.17 / 3.7% | −1.4% / −1.09 / 3.5% |
| Kelly (Bug 15 run) | −1.7% / −1.36 / 4.3% | +0.8% / 1.08 / 1.0% | −0.4% / −1.19 / 0.8% | −1.7% / −1.55 / 3.7% | −2.9% / −1.39 / 6.5% |
| **Kelly (corrected)** | −2.1% / −1.36 / 5.3% | **+1.0% / 1.08 / 1.2%** | −0.7% / −1.18 / 1.5% | −1.7% / −1.55 / 3.7% | −2.9% / −1.39 / 6.5% |
| fixed, training Sharpe (Bug 15 run → corrected) | −0.76 → −0.74 | −0.48 → −0.17 | −1.22 → −1.13 | −0.53 → −0.59 | −0.23 → −0.23 |
| Kelly, training Sharpe (Bug 15 run → corrected) | −0.75 → −0.59 | −0.54 → −0.44 | −0.84 → −0.77 | −0.49 → −0.50 | +0.05 → +0.05 |

- **Test-period Sharpe ratios move by at most 0.013**, one row excepted (MiniLM fixed −2.18 → −2.10: the one stuck
  test position, ANSS). Returns and drawdowns are larger in size where the scale rose: keyword fixed 0.0041 →
  0.0079, Kelly 0.0033 → 0.0041; Llama fixed 0.0072 → 0.0145, Kelly 0.0096 → 0.0122; MiniLM fixed 0.0028 → 0.0037,
  Kelly 0.0015 → 0.0027; Haiku and Sonnet unchanged. Keyword A Kelly's test drawdown is now 5.3%.
- **No news strategy beats momentum (0.72).** Sharpe difference, test (JKM): Llama A Kelly +0.34 ± 0.95 (p 0.72);
  keyword fixed −1.96 (p 0.015), Kelly −2.10 (p 0.023); Llama fixed −0.85 (p 0.34); MiniLM fixed −2.84 (p 0.009),
  Kelly −1.91 (p 0.069); Haiku −1.91 (p 0.048), −2.30 (p 0.017); Sonnet −1.82 (p 0.054), −2.14 (p 0.019).
  Llama A Kelly: deflated Sharpe 0.131 at N = 139 (0.32 / 0.23 / 0.16 at N = 25 / 50 / 100); training Sharpe −0.44.
- Kelly − fixed, Holm (`holm_kelly_vs_fixed_bug16fix_2026-11-10.csv`): keyword A −0.15 (p 0.81); Llama A +1.19 ±
  0.62 (p 0.056, p_holm 0.11); MiniLM A +0.93 (p 0.11); Haiku A −0.39 (p 0.56); Sonnet A −0.31 (p 0.62).
- **Forty configurations, test period: unchanged** — 36 lose, 24 significantly worse than momentum; best per
  rung unchanged (keyword C fixed −0.42, Llama A Kelly 1.08, MiniLM C Kelly −1.03, Haiku C Kelly 0.76, Sonnet C
  Kelly 0.23). Training drawdowns of the forty: 4.32% to 5.25%.
- Adjacent rungs, A Kelly (descriptive): Llama − keyword +2.44 ± 0.88 (p 0.006); MiniLM − Llama −2.26 ± 1.04
  (p 0.031); Haiku − MiniLM −0.38 (p 0.70); Sonnet − Haiku +0.16 (p 0.84).
- **20% sensitivity** (`sensitivity_dd20_summary_bug16fix_2026-11-10.csv`, descriptive), test Sharpe 5% → 20%:
  keyword −1.22 → −1.21, −1.36 → −1.33; Llama −0.12 → −0.15, **1.08 → 0.92** (+3.4% p.a., maxDD 4.9%); MiniLM
  −2.10 → −2.07, −1.18 → −1.18; Haiku −1.17 → −1.16, −1.55 → −1.29 (material; cap days 3.4%); Sonnet −1.09 →
  −1.04, −1.39 → −1.19 (cap days 14%, test maxDD 24.1%).
- Checks: acceptance tests of the note (old logs fail on exactly the listed positions; fixed engine reconciles;
  strict sizing assertion; B, C, momentum reconcile); post-run reconciliation 40/40 and strict assertion 80/80;
  placebos pass; harness rerun (`for_claude/verification_summary_2026-11-10_bug16.md`).

## Appended 10 November 2026 (evening) — EXPLORATORY: Strategy F (news fade), training run and ONE test-period run (appended; nothing above is edited)

Not part of the official evaluation. Code and files only in `review_2026-11-10/exploration/fade/` (notes
`FADE_note_2026-11-10.md`, addendum 1, `FADE_note_test_2026-11-10.md` written before the test run, a472af76…;
results `FADE_results_train_2026-11-10.md`, `FADE_results_test_2026-11-10.md`). Strategy F trades against keyword
corporate-event headlines: entry at the next open, exit at the close of the third trading day, index hedge of equal
notional, fixed-fractional size at the previous close, one configuration. Net of costs (2.43 bps per side, hedge
1 bp per side). **Trial 164** (163 + 1).

| F | scale | return p.a. | Sharpe | max drawdown | trades | mean net per trade (clustered t) |
|---|---|---|---|---|---|---|
| training, 5% calibration | 0.1380 | +0.55% | 0.24 | 5.03% | 1,816 | +9.5 bps (1.04) |
| training, 20% calibration | 2.7079 | +6.02% | 0.55 | 17.43% | 1,510 | +17.6 bps (1.73) |
| **test, 5% scale (one run)** | 0.1380 | **+3.61%** | **1.11** | 2.67% | 746 | +30.2 bps (2.09) |
| test, 5% scale, hedge off (decomposition) | 0.1380 | +3.43% | 0.94 | 3.46% | 746 | +33.0 bps (1.91) |
| test, 20% scale (descriptive) | 2.7079 | +22.54% | 1.62 | 13.35% | 536 | +39.2 bps (2.38) |

- Test period against continuous momentum (0.73 on the same days): +0.38 ± 0.98, p 0.70 (5% scale); deflated
  Sharpe ratio at N = 164: 0.13. By year: 2024 +3.6%, 2025 +4.1%, 2026 to 1 June −0.2% (−44.6 bps per trade).
- **Not a blind test and not a confirmation.** The test-period reversal of this subgroup (day 3 −34.3 bps, t −2.5,
  above) was known when F was specified on 10 Nov 2026; the run shows only that the known gross effect survives
  costs, hedge and sizing. By the rule written before the run the result is "consistent with the hypothesis".
- Fragile: the five best trades carry half of the profit (mean +11.6 bps without the best 7 of 746 trades); five
  tickers (META, WBD, CSCO, LCID, RIVN) carry 80%; fading negative headlines earns +53.1 bps per trade, fading
  positive headlines +7.4; training is weak (losing years 2018 and 2021); the last five months lose.
- Checks: the engine's mean per trade (+30.22 bps) equals minus the event-study day-3 return of the traded events
  less costs (+30.24); equity reconciles with the trade log; placebos passed on training (random and common
  direction). F's test period is used; no tuning of F on it is admissible. A confirmation needs data after
  2026-06-01.

## Appended 14 November 2026 — DESCRIPTIVE: event-study standard errors under wider clusters, training period only (appended; nothing above is edited)

Specification `review_2026-11-14/CLUSTERING_note_2026-11-14.md` (a595eddc…, written before the reviewer's check).
Script `src/descriptive_event_study_clustering.py`; file
`outputs/descriptive_event_study_clustering_train_2026-11-14.csv` (39dfb338…, copy in `for_claude/`). The official
training event study of 18 Oct (all events, market-adjusted, signed, basis points; Llama scores as on 18 Oct,
59,154 rows) with the same cluster-robust variance and three cluster definitions: entry date (official, about 2,080
clusters), ISO week (434), calendar month (100). Validity: the eight official cells are reproduced (mean and t to
1e-6, N exact). No strategy run, nothing tuned, no other number changes. Test period not read.

| scorer | day | mean | SE entry date | SE week | SE month | bound entry date | bound week | bound month |
|---|---|---|---|---|---|---|---|---|
| keyword | 1 | −2.83 | 1.60 | 1.64 | 1.69 | −0.20 | −0.14 | −0.05 |
| keyword | 2 | −5.19 | 2.61 | 3.00 | 2.81 | −0.88 | −0.26 | −0.56 |
| keyword | 3 | −5.61 | 3.29 | 3.72 | 3.37 | −0.20 | +0.52 | −0.06 |
| keyword | 5 | −7.21 | 4.13 | 5.18 | 5.10 | −0.41 | +1.31 | +1.19 |
| Llama | 1 | −2.05 | 1.56 | 1.71 | 1.64 | +0.52 | +0.76 | +0.65 |
| Llama | 2 | −4.44 | 2.51 | 2.60 | 2.30 | −0.32 | −0.17 | −0.66 |
| Llama | 3 | −2.43 | 2.98 | 3.02 | 2.72 | +2.47 | +2.54 | +2.04 |
| Llama | 5 | −2.37 | 3.81 | 3.99 | 4.17 | +3.91 | +4.20 | +4.49 |

Bound = mean + 1.645 × SE (one-sided 95%). Reading by the rule fixed in the note:
- (i) no bound crosses the round-trip cost of 4.86 bps: all eight stay below it under all three definitions
  (largest: Llama day 5, 3.91 / 4.20 / 4.49);
- (ii) one standard error rises by 25% or more: keyword day 5, +25.2% by week (+23.5% by month); every other cell
  at days 2 to 5 rises by 15% or less, and two fall under month clustering. Material by the rule, narrowly;
- bounds below zero: five of eight by entry date, three by week, four by month. The statement "five of the eight
  bounds sit below zero" holds for entry-date clustering only.
- Limits: 100 month clusters make that variance estimate noisy; training period only.

## Appended 14 November 2026 (later) — Bug 17 CORRECTION of Strategy A (all ten A rows) (appended; nothing above is edited)

Bug 17 (`bugs.md`, appended note of 14 Nov): the entry step admitted positions on the book after the day's exits
(re-entry on the exit day; gross cap judged after the exits). Fixed in `src/newsdrift/backtest.py`; admission now
uses the book of the previous close. Pre-run note `outputs/FROZEN_CONFIG_2026-10-18_note_bug17_2026-11-14.md`,
addendum `…_addendum_testC_2026-11-14.md` (one stop at test C, fixture of the Bug 15 test, author's decision),
results note `…_note_bug17_results_2026-11-14.md`. Strategy A only; scales recalibrated on training by the
unchanged rule; one run; B, C and momentum not run. **Every Strategy A number of the Bug 16 section above is
SUPERSEDED by this section.** Files: `outputs/*_bug17fix_2026-11-14*`. Trial counts unchanged (139 / 155 / 161 /
163).

Training period, 5% target, Bug 16 run → Bug 17 run:

| rung | sizer | scale | return p.a. | Sharpe | max drawdown | trades |
|---|---|---|---|---|---|---|
| keyword | fixed | 0.0079 → 0.0104 | -0.523% → -0.535% | -0.736 → -0.653 | 5.09% → 5.03% | 25,089 → 20,599 |
| keyword | kelly | 0.0041 → 0.0062 | -0.460% → -0.404% | -0.594 → -0.418 | 5.08% → 5.23% | 25,089 → 20,599 |
| Llama | fixed | 0.0145 → 0.0187 | -0.216% → -0.187% | -0.174 → -0.131 | 5.04% → 5.01% | 21,869 → 19,088 |
| Llama | kelly | 0.0122 → 0.0204 | -0.407% → -0.121% | -0.437 → -0.092 | 5.23% → 4.86% | 21,869 → 19,088 |
| MiniLM | fixed | 0.0037 → 0.0049 | -0.590% → -0.586% | -1.133 → -0.982 | 5.10% → 5.09% | 21,217 → 18,188 |
| MiniLM | kelly | 0.0027 → 0.0033 | -0.613% → -0.608% | -0.765 → -0.750 | 5.25% → 5.20% | 21,217 → 18,188 |
| Haiku | fixed | 0.0201 → 0.0198 | -0.560% → -0.571% | -0.593 → -0.640 | 5.04% → 5.03% | 10,999 → 10,222 |
| Haiku | kelly | 0.0363 → 0.0274 | -0.529% → -0.597% | -0.498 → -0.798 | 5.02% → 4.98% | 10,999 → 10,222 |
| Sonnet | fixed | 0.0361 → 0.0384 | -0.259% → -0.236% | -0.233 → -0.202 | 5.07% → 5.06% | 5,039 → 4,892 |
| Sonnet | kelly | 0.1294 → 0.1333 | +0.107% → +0.163% | +0.048 → +0.071 | 4.32% → 5.08% | 5,028 → 4,857 |

Test period, 5% target (one run):

| rung | sizer | scale | return p.a. | Sharpe | max drawdown | trades |
|---|---|---|---|---|---|---|
| keyword | fixed | 0.0079 → 0.0104 | -1.385% → -1.554% | -1.218 → -1.255 | 4.02% → 4.32% | 12,076 → 9,281 |
| keyword | kelly | 0.0041 → 0.0062 | -2.144% → -2.493% | -1.362 → -1.454 | 5.33% → 6.07% | 12,076 → 9,281 |
| Llama | fixed | 0.0145 → 0.0187 | -0.191% → +0.017% | -0.119 → +0.010 | 3.31% → 2.93% | 8,093 → 6,815 |
| Llama | kelly | 0.0122 → 0.0204 | +0.990% → +1.792% | +1.075 → +1.298 | 1.22% → 1.47% | 8,093 → 6,815 |
| MiniLM | fixed | 0.0037 → 0.0049 | -1.289% → -1.197% | -2.097 → -1.778 | 2.68% → 2.47% | 8,201 → 6,662 |
| MiniLM | kelly | 0.0027 → 0.0033 | -0.676% → -0.436% | -1.179 → -0.790 | 1.45% → 1.03% | 8,201 → 6,662 |
| Haiku | fixed | 0.0201 → 0.0198 | -1.558% → -1.355% | -1.173 → -1.115 | 3.67% → 3.19% | 4,366 → 3,901 |
| Haiku | kelly | 0.0363 → 0.0274 | -1.742% → -0.721% | -1.553 → -0.899 | 3.70% → 1.81% | 4,366 → 3,901 |
| Sonnet | fixed | 0.0361 → 0.0384 | -1.370% → -1.292% | -1.089 → -0.976 | 3.45% → 3.14% | 1,908 → 1,824 |
| Sonnet | kelly | 0.1294 → 0.1333 | -2.948% → -3.253% | -1.393 → -1.446 | 6.45% → 7.33% | 1,907 → 1,818 |

Test period against the stored continuous momentum series:

| rung | sizer | Sharpe | difference to momentum ± SE | p | DSR (N) | difference in the Bug 16 run |
|---|---|---|---|---|---|---|
| keyword | fixed | -1.255 | -1.993 ± 0.824 | 0.0156 | 0.0000 (139) | -1.956 (p 0.0152) |
| keyword | kelly | -1.454 | -2.198 ± 0.933 | 0.0185 | 0.0000 (139) | -2.103 (p 0.0229) |
| Llama | fixed | +0.010 | -0.716 ± 0.893 | 0.4224 | 0.0045 (139) | -0.845 (p 0.3397) |
| Llama | kelly | +1.298 | +0.559 ± 0.959 | 0.5600 | 0.2020 (139) | +0.340 (p 0.7209) |
| MiniLM | fixed | -1.778 | -2.520 ± 1.080 | 0.0196 | 0.0000 (155) | -2.842 (p 0.0086) |
| MiniLM | kelly | -0.790 | -1.524 ± 1.043 | 0.1440 | 0.0001 (155) | -1.915 (p 0.0686) |
| Haiku | fixed | -1.115 | -1.851 ± 0.971 | 0.0567 | 0.0000 (155) | -1.910 (p 0.0482) |
| Haiku | kelly | -0.899 | -1.632 ± 0.939 | 0.0820 | 0.0000 (155) | -2.295 (p 0.0167) |
| Sonnet | fixed | -0.976 | -1.710 ± 0.943 | 0.0699 | 0.0000 (161) | -1.825 (p 0.0540) |
| Sonnet | kelly | -1.446 | -2.193 ± 0.902 | 0.0150 | 0.0000 (161) | -2.138 (p 0.0188) |

- **Best configuration: Llama A Kelly, test-period Sharpe 1.30 (+1.79% p.a.), was 1.08**; against momentum
  +0.56 ± 0.96 (p 0.56), DSR(139) 0.20; training Sharpe −0.09 (was −0.44). Not significant.
- **35 of the 40 configurations lose (was 36); 22 are significantly worse than momentum at 5% (was 24).** Llama A
  fixed is now at +0.02% p.a.; Haiku A fixed (p 0.057) and Haiku A Kelly (p 0.082) are no longer significantly
  worse. No configuration beats momentum significantly.
- Kelly against fixed, Holm: Llama +1.28 ± 0.64, p 0.045, Holm 0.091; keyword −0.21 (0.74); MiniLM +1.00 (0.091);
  Haiku +0.22 (0.74); Sonnet −0.48 (Holm 1.00). None significant after Holm.
- Rung comparisons on A Kelly (descriptive): Llama − keyword +2.76 ± 0.87 (p 0.002); MiniLM − Llama −2.08 ± 1.04
  (p 0.045); Haiku − MiniLM −0.11 (p 0.91); Sonnet − Haiku −0.56 (p 0.44).
- The correction removes 13% to 18% of the training trades of the free rungs and 16% to 23% of their test-period
  trades (Haiku 7% / 11%, Sonnet 3% / 4–5%). In the superseded run the removed trades were worse than the rest in
  the test period in every rung, which is the direction in which most rows move.

20% sensitivity (descriptive), test period:

| rung | sizer | Sharpe 5% → 20% | cap-binding days 5% / 20% | p vs momentum 5% / 20% | material |
|---|---|---|---|---|---|
| keyword | fixed | -1.255 → -1.229 | 0.00% / 1.53% | 0.0156 / 0.0165 | no |
| keyword | kelly | -1.454 → -1.029 | 0.00% / 11.11% | 0.0185 / 0.0562 | yes |
| Llama | fixed | +0.010 → +0.366 | 0.00% / 9.00% | 0.4224 / 0.7061 | yes |
| Llama | kelly | +1.298 → +0.741 | 0.00% / 15.33% | 0.5600 / 0.9826 | yes |
| MiniLM | fixed | -1.778 → -1.758 | 0.00% / 0.00% | 0.0196 / 0.0194 | no |
| MiniLM | kelly | -0.790 → -0.797 | 0.00% / 0.00% | 0.1440 / 0.1430 | no |
| Haiku | fixed | -1.115 → -1.054 | 0.00% / 2.11% | 0.0567 / 0.0637 | no |
| Haiku | kelly | -0.899 → -0.666 | 0.00% / 6.13% | 0.0820 / 0.1513 | yes |
| Sonnet | fixed | -0.976 → -1.028 | 0.00% / 3.45% | 0.0699 / 0.0610 | no |
| Sonnet | kelly | -1.446 → -1.620 | 0.57% / 8.05% | 0.0150 / 0.0122 | no |

- Four rows are material by the rule of 25 Oct (Sharpe change above 0.20): keyword Kelly, Llama fixed, Llama
  Kelly (1.30 → 0.74) and Haiku Kelly; before only Haiku Kelly. Two 20% Kelly calibrations did not converge in the
  six steps of the search (Haiku 14.9% and Sonnet 17.5% training drawdown in the run); reported as they are.
- Checks after the run: admission assertion 80 of 80 on the 40 logs (0 of 402,283 positions opened in a ticker
  held or closed that day; no entry above the gross cap); Bug 15 strict assertion 80 of 80; reconciliation 40 of
  40; placebos pass (fixed 0.62 SE; Kelly random; common direction +0.91 / −3.09 bps, 0.18 / −0.45 clustered SE);
  harness 204 of 204 files, 17 of 17 test files, 457 of 461 assertions (four calibration-band findings).
- Appended 14 Nov 2026 (later), descriptive, training only — signal-order robustness on the Bug 17 engine
  (`for_claude/order_robustness_bug17fix_2026-11-14.csv`, efc2d079…; note beside it; script
  `src/order_robustness_bug17fix_2026-11-14.py`; the October file `order_robustness_2026-10-19.csv` is unchanged):
  standard deviation of the training Sharpe ratio over 20 random orderings of same-day signals, Strategy A at the
  Bug 17 scales: keyword fixed 0.000 (October 0.000), keyword Kelly 0.038 (0.090), Llama fixed 0.000 (0.000),
  Llama Kelly 0.029 (0.041). B, C and D are identical on the engine before and after the Bug 17 fix; against
  October, D is identical and B and C differ because their engines were changed on 24 Oct (Bugs 13 and 14).
