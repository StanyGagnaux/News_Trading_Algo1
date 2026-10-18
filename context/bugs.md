# Bugs: fixed (do not reintroduce) and open

Every bug here was found by testing or by checking a suspicious number —
none by reading code. Regression checks live in `tests/test_portfolio_fixes.py`.

## Fixed

1. **Kelly absorbing condition** — when f* hit 0 the sizer stopped trading,
   so it never received new closed trades to recover from. Fixed with a probe
   floor.
2. **Drawdown governor death spiral** — exposure hit exactly 0 at the cap;
   with no trades equity could not rise, so drawdown could never shrink. One
   config stopped trading Nov 2018 and stayed dead four years, which was
   initially misread as a signal-quality difference. Fixed with a 5% probe
   floor + decaying peak (60-day half-life).
3. **Intraday stops narrower than costs** — stop was 24 bps, round-trip cost
   17 bps (71% of the stop). Fixed: `max(2×ATR, 8×round-trip cost, 40bps)`.
4. **Intraday equity compounding 35k OVERLAPPING trades sequentially** —
   produced −100% as an accounting artifact. Fixed: daily portfolio
   aggregation with per-day risk cap.
5. **Freshness guard failing open** — the live pusher discarded stale news but
   let items through when the timestamp was missing or unparseable. Fixed to
   fail-safe (discard when unverifiable).
6. **Sizing changed WHICH signals traded** (Sept) — B/C checked the
   concurrent-risk cap against the sizer's own risk, so Kelly's probe size
   (~0.1% vs ~0.7% fixed) let many more trades fit: C Kelly 11,906 vs fixed
   1,738. Fixed in `portfolio.py`: admission uses a sizer-independent
   reference risk; actual risk is still capped (scaled down to fit). Current
   real data: C 1,626 fixed vs 1,534 Kelly (gap = Kelly positions scaled to
   zero when the cap is nearly full).
7. **No drawdown governor in B and C** (Sept) — only Strategy A called
   `DrawdownGovernor`. Fixed: same governor, updated once per day on realised
   equity. Oct: `--dd-governor` also switched only B/C, so A always ran
   "designed" — fixed, it now applies to all strategies.
8. **Same-day look-ahead + duplicated trades in B and C** (27 Sept) — the
   runner merged `build_signal_table`'s daily average back onto every headline
   timestamp. A 14:55 entry used headlines published later that day; every
   headline that day became its own trade — up to 366 on one ticker-day. Fixed
   with `build_event_table()` + one open position per ticker. Violated Hard
   Rule 1; found by checking an implausible number (168 average open positions
   on 31 tickers).
9. **B/C annualised on the wrong time axis** (Oct) — their equity curve had
   one point per trade close instead of one per trading day, while
   `performance_metrics` assumes 252 points = 1 year. A 1-year synthetic run
   was read as 3.9 years, understating B/C losses (B t+5 IS: −3.5% → −15.0%
   p.a.). Fixed in `portfolio.daily_equity`. Only B/C return and Sharpe
   changed.

10. **Strategy A ATR on the wrong rows + same-day look-ahead** (13 Oct) —
   `backtest.py` computed ATR in ticker order, then `reset_index(level=0,
   drop=True)` dropped the row labels, so values were assigned BY POSITION to
   a date-filtered table: 0% of rows got their own ATR, 8% got NaN, and the
   result depended on how the table happened to be indexed. The ATR also
   included the entry day's own high/low (look-ahead, Hard Rule 1). Fixed:
   `attach_atr()` (index-preserving, shifted one day); `standalone.py` uses the
   same function. Test `tests/test_atr_alignment.py` (200 rows; fails on the
   old code, passes on the new). Found because the calibration layer's
   standalone simulator disagreed with the engine. Effect, A raw scale 1,
   in-sample: keyword +14.5% / Sharpe 1.07 / maxDD 17.1% → −3.7% / −0.29 /
   39.5%; LLM +15.2% / 1.16 / 15.8% → −3.7% / −0.30 / 39.7%. All earlier
   Strategy A numbers (incl. the OOS Sharpe 2.58 headline) are INVALID. B/C/D/N
   unaffected (verified: their calibrated scales reproduce exactly).

11. **Strategy A traded net-zero and weak days** (found 13 Oct, fixed 18 Oct)
   — `build_signal_table` gated |strength| >= 0.20 per HEADLINE, then averaged
   per (ticker, day). Opposite headlines netted to 0.0 and the engine traded
   that as a SHORT (`direction = 1 if s > 0 else -1`) at 1% risk (991 of
   21,669 in-sample keyword trades); weak averages (0 < |mean| < 0.20) also
   traded (4,382 LLM-anonymised days). Fixed: the gate is re-applied to the
   netted value in `build_signal_table` (as `build_event_table` already did
   for B/C), plus an engine guard and the same gate in
   `calibrate_scorer.build_features`. Test `tests/test_signal_gate.py` (fails
   on the old code, passes on the new). Affects A and the D/N sweeps; B/C
   unaffected. The 13 Oct frozen A risk scales predate this fix.

12. **Results depended on the row order of same-time signals** (found 18 Oct,
   fixed 18 Oct, files labelled 19 Oct) — when caps bind, the engines admitted same-day (A) or
   same-time (replay: B, C, D, N) signals in input row order, which was not
   deterministic across equivalent inputs (two LLM score files with identical
   content gave different orders). For Kelly the order also changes the
   sequence of recorded R-multiples, so sizes change even with identical trades.
   Fix: stable sort with a content tie-break (`backtest.py`, `portfolio.py`,
   `signals.py`; `tie_rank` hook in `open_close.py`); test
   `tests/test_order_invariance.py` (fails on the old code). Dated note
   `FROZEN_CONFIG_2026-10-18_note_bug12_2026-10-19.md`; the 18 Oct test runs
   stay official. Training robustness check (20 random orders,
   `outputs/order_robustness_2026-10-19.csv`): Sharpe sd 0 for A fixed, 0.04–0.09
   A Kelly, 0.05–0.27 B, 0.10–0.28 C, 0.21 D. It explains the keyword D
   discrepancy: 8,040 trades in every order but returns −6.3% to +0.3%;
   deterministic −1.7% (pre-Bug-11 table −1.7%, same trades count).

Pre-fix backups: `_archive/_backup_2026-09-27_before_bugfix/` and
`_archive/_backup_2026-10-13_before_restructure/`,
`_archive/_backup_2026-10-13_before_atr_fix/`,
`_archive/_backup_2026-10-18_before_bug11_fix/`,
`_archive/_backup_2026-10-19_before_bug12_fix/`.

## Open

**Bug 1 — LLM out-of-sample near-empty — RESOLVED 18 Oct 2026.** The test
period was scored once with the frozen setup (`FROZEN_CONFIG_2026-10-18.md`):
32,485 test rows, 100% of pre-filtered test headlines; logged in
`outputs/test_period_runs.csv`. The scoring cutoff now follows the backtest
calendar (`src/splits.py`), which also closed a one-month unscored gap at the
end of training (2024-03-26 -> 04-29).

**Bug 4 — LLM Strategy A OOS Sharpe below keyword** (overfit 0.52 vs 0.83).
Probably an artifact of Bug 1; recheck afterwards.

**Anonymization — implemented 13 Oct, IN USE since 17 Oct.** All current LLM
results use the anonymised scores (`news_scored_llm_ollama_anon*.csv`); the
older `news_scored_llm_ollama.csv` (raw headline and ticker, Glasserman-Lin
look-ahead risk) is kept only for the named-vs-anonymised comparison.
Still open: the 3 rows marked CHECK in `company_names.csv` (SPCX, HONA
unknown; WTW ticker history) -- frozen as they are on 18 Oct.

**Watchlist file not found by two scripts -- SETTLED 18 Oct (no change).**
`score_news_llm.py` (Tier-0 filter) and `raw_news_pusher.py` look for
`nasdaq100.txt` in the current directory, so the watchlist step is skipped.
It is redundant: the universe restriction is applied when the news is
downloaded (all 191 news tickers are among the 193 universe tickers), as
recorded in `FROZEN_CONFIG_2026-10-18.md`.

**`--with-context` arm cannot run:** `context_table.csv` and
`outcome_feedback.py` are missing (`systems.md`).

**Minor:** B/C session filters use fixed UTC hours (14:30–19:30 entry, B
forced exit 20:00 UTC) and ignore US daylight saving, so in winter B exits ~1h
before the real close.

## Decision status

**What "5% drawdown cap" means:** resolved in practice by calibrated sizing
(`methodology.md`); the thesis still needs the wording. Strict mode is a
reported finding, not the operating rule.
