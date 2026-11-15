# Note to FROZEN_CONFIG_2026-10-18 — cost ladder and extensions, dated 24 October 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written 2026-10-24 14:58 CEST, BEFORE any result of the analyses below is
computed. The 18 October runs remain the official results; everything here is
an additional, pre-registered analysis. Every new test-period run is logged in
`outputs/test_period_runs.csv`, one run per rung and analysis.

## a) Factor robustness (event study)

- Factors: Fama-French five factors + momentum (UMD), daily, Kenneth French
  data library; risk-free rate from the same files. Record download date and
  file checksums.
- Per event: betas from OLS of the ticker's daily excess return
  (close-to-close, `prices.csv`) on the six factors over the 250 trading days
  ending 10 trading days before the news date (days −259 … −10 relative to the
  news date's trading day). Events with fewer than 200 valid returns in that
  window are dropped and counted.
- Abnormal return over each frozen window = ticker return − Σ over the
  window's trading days of (rf + β'f). Day 0 is close-to-close (exact). For
  windows starting at the entry OPEN, the first day's factor return is
  close-to-close (the French data are daily); this approximation is stated.
- Same windows (day 0; entry open → close of day 1, 2, 3, 5), signing,
  date-clustered t-statistics, splits and both periods as the frozen event
  study. Reported beside, not replacing, the NDX-adjusted results.

## b) Rung 1b — sentence embeddings + ridge

- Model `sentence-transformers/all-MiniLM-L6-v2`; record the exact model
  revision (commit hash) and package versions. Input: the SAME anonymised
  headline texts as the Llama runs (`anonymize.py` with `company_names.csv`),
  i.e. the Tier-0/template-dedup headline set Llama scored.
- Target y: the market-adjusted return from the entry open to the close of
  day 3 (frozen spec; unsigned, NDX-adjusted) of the (ticker, entry day) event
  the headline belongs to; every headline of an event carries that event's y.
- Ridge with intercept on the 384-dim embedding. Fit: events with entry day
  2016-01-04 … and day-3 close ≤ 2021-12-31. Penalty λ chosen by validation
  MSE on events with entry ≥ 2022-01-01 and day-3 close ≤ 2024-04-29, from the
  fixed grid λ ∈ {0.01, 0.1, 1, 10, 100, 1 000, 10 000}. The model fitted on
  2016–2021 with that λ is applied once to the test period; NO refit.
- Prediction → strength: s = clip(ŷ / q95, −1, 1), q95 = 95th percentile of
  |ŷ| over the fit sample. Direction = sign(s). Duration fixed at 2 days
  (the Llama modal value); no importance output. Events then built exactly
  as for the other rungs (per-headline gate 0.20, daily netting, Bug 11 gate).
- Training-period results of this rung are in-sample (2016–2021 is the fit
  sample); stated in every table.
- Risk scales calibrated on training only with `calibrate_risk.py`, exactly as
  for the other rungs.

## c) Rung 2 — Claude Haiku

- Model `claude-haiku-5-5` via the Message Batches API; prompt text
  (`PROMPT` in `score_news_llm.py`), anonymisation, output format and parsing
  (`parse_reply`), temperature 0.2 and max_tokens 300 identical to the Llama
  runs; same headline set (training and test). Separate cache namespace.
  Unparseable replies are retried once, identically, then left unscored and
  counted. No prompt or parameter change after any result is seen.
- Cost control: estimate with the token-counting endpoint first; stop if the
  estimate exceeds **$30**.
- **Look-ahead caveat:** if Haiku's training data extend beyond 2024-04-29,
  its test-period scores may embed knowledge of later events despite
  anonymisation. The published knowledge cutoff is recorded before Phase 3 and
  the caveat reported with every Haiku result. (Llama 3.2's cutoff is
  December 2023; MiniLM was trained before 2022.)
- Risk scales calibrated on training only.

## d) Cost ladder

Rungs: 0 keyword, 1 Llama 3.2 3B (local), 1b embeddings (local), 2 Haiku
(API). Each through the identical frozen event study and strategies A/B/C
(`run_both_strategies.py`, designed governor, its own training risk scales).
Per rung: data cost (Benzinga via Alpaca: $0; Bloomberg: university terminal,
$0 marginal), compute wall-clock time per 1,000 headlines (measured), API cost
per 1,000 headlines and in total (from usage logs), and median latency to
score one headline (real-time call, measured on 200 headlines; for Haiku via
the standard Messages API, cost counted).

## e) Speed bound

Trading-hours news only; per rung the headline's own direction (event table
as in `intraday_description.py`). Signed return from the price AT the headline
timestamp (close of the last 1-minute bar ending at or before it, at most 10
minutes stale, same session) to +1, +5, +15, +30 minutes and the session close;
mean, date-clustered t, N; both periods; against the 4.86 bps round trip. Raw
returns (no intraday index). Coverage per horizon is reported (IEX bars are
sparse at +1 minute).

## f) Paper trading (descriptive only)

- Dates 2026-10-26 → 2026-11-06, US regular trading hours. Alpaca **paper**
  endpoint only (hard-coded; the logger refuses non-paper keys).
- One market order (fixed notional $1,000, day order) per signal that passes
  the filters: universe ticker, fresh (freshness guard), trading hours, rung-1
  (Llama, the frozen LLM) |strength| ≥ 0.20; direction = sign. Each position
  is closed with a market order 30 minutes after the fill, or at 15:55 ET if
  earlier. The other rungs score every headline and their score times are
  logged; they trigger no orders.
- Logged per signal: newswire timestamp, receipt time, score time per rung,
  order submission time, fill time, quote (bid/ask) at receipt, fill price.
  Reported: latency distributions and slippage (fill vs mid at receipt,
  signed, bps). Not a performance test; not in the trial count.

## g) Trial count

New strategy configurations: rungs 1b and 2 × 8 strategy rows = 16. Deflated
Sharpe ratios of the ladder use **N = 139 + 16 = 155** (sensitivity 25 / 50 /
100 unchanged). Factor robustness, speed bound and paper trading are not
strategy trials.

## Fingerprints of the frozen code these analyses reuse (SHA-256)

| file | sha256 |
|---|---|
| `src/event_study.py` | `b26425672d1f89e6fa440881c37906cf2a3b0fa14de892901a909a8a723882cb` |
| `src/intraday_description.py` | `fee4c4897af5afc8d06953f8f83094fe7ad8b1d088a767aaca06648f692f78d0` |
| `src/run_both_strategies.py` | `0e552bf72821da57f5ddfa24492e9dc1832502ca603232e962ae2accc6507b3a` |
| `src/calibrate_risk.py` | `1b07c18e8362429b1281ea3872ff6341f6284e1a058432bc9f58d22022775d05` |
| `src/score_news_llm.py` | `04f55f48143f0648ece6dba7f33dfb0cdded1124e9be1ceb7a623f3c46f9ae44` |
| `src/anonymize.py` | `da37396e5109c551260e2ab7b0d2bde8525a78bef63ea9ba69c50d09eed598b2` |
| `data_sources/company_names.csv` | `8f68c97ce52615aedfc5ab7abbc53a7c495041caf37873d6b43a089b9e2804cc` |
| `src/newsdrift/signals.py` | `d5bdcaa9c787bf3de48c176eaa6a80ab8e75350c23bdaa3d2f014ffff5cfd043` |
| `src/newsdrift/backtest.py` | `8b3dd822883f3c8563d4adf94cb9d1ba3a69e1afde11c0ad45ca47854dd0330b` |
| `src/newsdrift/portfolio.py` | `4ee88b1087dfab774473bd554314665b2afa25dbfa510bb6745e33f71cc2c4c1` |
| `src/newsdrift/stats.py` | `0c3c34c09203212ef9bec22754c7af16033bcbd63a76b2ae65cef1e8c0a9e012` |
