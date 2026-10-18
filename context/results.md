# Results (current as of 18 Oct 2026)

> **Official evaluation = training period + test period** (the single frozen
> runs of 18 Oct 2026). The holdout was dropped by decision before any holdout
> return was computed (`outputs/FROZEN_CONFIG_2026-10-18_note_holdout_dropped.md`);
> H1–H3 and the holdout power figures below are records, not results.

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
  t->close +6.1 (t 2.0); keyword ~0 everywhere.
- Files: `outputs/event_study_*_2026-10-18.*`, `outputs/intraday_description_2026-10-18.csv`.
- Everything below this section predates Bug 10/11 where marked.

## 18 Oct 2026 — strategies, TEST period (single frozen run per scorer)

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
