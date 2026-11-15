# Methodology (as implemented in `src/`)

## Signals

- **Keyword scorer** (`KeywordScorer`): Loughran-McDonald-style dictionary.
  `strength = (pos − neg)/(pos + neg)` → ±1 for any single-polarity headline
  (90.9% of trades had |strength| = 1.0), duration = keyword density.
- **LLM scorer**: `src/score_news_llm.py` scores headlines once and writes a
  CSV; backtests read it through `PrecomputedScorer` (lookup by exact
  `(headline, ticker)` text). Only headlines passing the free **Tier-0
  filter** (`tier0_keep`: drops template noise, keeps headlines with trigger
  words) are scored. Current scores: local Ollama `llama3.2:3b`, train period
  only, NOT anonymized. From Oct 2026 the scorer masks the scored company's
  names and ticker by default (Glasserman-Lin); the next re-score will use it.
- **Noise gate:** |strength| < 0.20 is dropped (`config.min_abs_strength`).
- **Look-ahead control:** `build_signal_table()` (daily aggregate, Strategy A
  and D) trades at the first trading day strictly after the news;
  `build_event_table()` (point-in-time, one event per headline, Strategies B,
  C and N). Both assert their invariant at runtime.

## Strategies

| | Entry | Exit | Engine |
|---|---|---|---|
| **A** daily drift | Open of first trading day after news | Stop (2×ATR) / 2R target / close after `duration` (1–3) days | `backtest.py` |
| **B** intraday | First minute bar at news + 5/15 min (configurable) | Stop (3× recent minute vol) / 2R / same-session close | `intraday.py` |
| **C** hybrid | First minute bar at news + 15 min | Stop 2× mean daily range (floor 0.4%) / 2R / close after `duration` daily bars | `strategy_c.py` |
| **D** open-to-close | Next-day open (same as A) | Same-day close, no stop/target | `open_close.py` |
| **N** overnight | First daily close strictly after the headline | Next day's open, no stop/target | `open_close.py` |

B/C/D/N only trade in-session news where bars exist (B/C: 14:30–19:30 UTC
entry window, fixed UTC hours ignoring US daylight saving — in winter B exits
~1h before the real close). D and N need daily bars only.

Optional variants (all off by default, in-sample experiments): B scale-out
(`--partial-exit-r`, `--trail-r`, `--no-breakeven`), B/C confirmation entry
(`confirm_move_bps`), C entry at the news-day close (`entry_mode="close"`),
keyword scorer restricted to the LLM's headline set (`--tier0`).

## Costs

All results net of costs, calibrated from the empirical bid/ask in
`prices.csv`: median half-spread 1.43 bps + commission → 2.43 bps per side.
Intraday entries pay a latency-decaying cost: `3 + 15·exp(−t/5)` bps
(~3.7 bps at t+15 min); exits pay the normal per-side rate.

## Sizing and drawdown control

- **Sizers:** fixed-fractional (control) vs fractional Kelly (0.25×, rolling
  40 closed trades, probe floor against the f* = 0 deadlock).
- **Portfolio replay** (B, C, D, N — `portfolio.py`): admission under a 4%
  concurrent-risk cap uses a sizer-independent reference risk, so both sizers
  see the same signals; one open position per ticker; equity recorded once per
  trading day.
- **Drawdown governor** (`--dd-governor`, applies to ALL strategies):
  `designed` = throttle (de-risks from 3% to 5% drawdown, 5% probe floor,
  60-day decaying peak — realised maxDD can exceed 5%); `strict` = hard cap
  (no probe, all-time peak — holds ~5% but strategies nearly stop trading);
  `off`.
- **Position scale** (`risk_scale`, Oct 2026): multiplies every position's
  risk. The 5% drawdown target is met by SIZING, calibrated in-sample only
  (`src/calibrate_risk.py`), frozen in
  `outputs/frozen_risk_scales_2026-10-11_{keyword,llm}.csv`, with the
  designed governor kept as a second line of defence. Calibrated scales are
  ~0.03–0.10 of the original size.

**Thesis wording:** describe the drawdown control as "sizing calibrated
in-sample to a 5% target, plus a continuous throttle" — not a hard cap. Report
realised maxDD, and report the strict-mode result (C collapses from ~1,500 to
96–262 trades) as the measured cost of a hard cap — evidence for the
Grossman-Zhou argument that exposure should shrink continuously rather than
switch off.

## Split and evaluation

80/20 chronological split, fixed before tuning: in-sample 2016-01-04 →
2024-04-29, out-of-sample 2024-04-30 → 2026-06-01. Reported: annualised
return, Sharpe, maxDD, trades, hit rate, R² (does |strength| explain trade
R-multiple), overfit score (OOS Sharpe / IS Sharpe). Benchmark: time-series
momentum.
