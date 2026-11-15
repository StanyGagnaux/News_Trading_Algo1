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

**Bug 13 — Strategy C mixes two price bases (found 24 Oct; daily-bar C INVALID; RESOLVED 25 Oct by a minute-bar-only reimplementation, note `…note_c_minute_2026-10-24.md`: placebo passed, C reported from it).** C
enters at a 1-minute IEX bar price (Alpaca, `adjustment="split"`: split- but
NOT dividend-adjusted) and exits, with stop/target checks, on Bloomberg daily
bars (split- AND dividend-adjusted). Daily prices therefore sit below the
entry by the dividends paid after the trade date (MSFT 2023 ratio 1.02, AAPL
2021 1.03), more so the further back. Effect, all scorers, every year
2020–2024: C shorts +0.25 to +0.68R, longs −0.17 to −0.47R, shrinking towards
2026. Consequences: all Strategy C results, including the official 18 Oct C
rows (keyword and LLM, ~65% long → biased down) and the ladder's rung 1b C
(99% short → spuriously +21% p.a. in test), are NOT valid. Unaffected: A, D,
N, C1 (daily only), B (minute only), event studies, intraday analysis, speed
bound. Fix (note `…note_bug13_2026-10-24.md`, 8a537056…): minute entries scaled
by the entry day's daily/minute close ratio; unit test `tests/test_bug13_basis.py`
passes (fails on the old engine). Placebo on training (random directions, seed
20261024, 12,410 trades): mean R −0.003 vs cost −0.012 (2.04 SE) and longs
+0.027R vs shorts −0.032R (t 6.8) -> FAILED on both pre-registered criteria;
gap ~1/10 of the bug's, shorts win in the 2022 bear year; NDX-adjusting halves
it (t 4.4). C1 diagnostic (addendum ecd30b37…, same seed and events):
long−short +0.0063R (t 0.76) vs C's +0.0590R -> outside the ±0.0086R band, so
under the frozen rule a basis error remains in C (caveat: C1 skips the rest of
the news day, so the rule cannot separate basis error from news-day drift).
C1 mean R +0.0017 vs cost −0.0103 (2.88 SE). **Decision 24 Oct** (note
`…note_bug13_decision_2026-10-24.md`, f1218fd9…): Bug 13 unresolved within the
project; Strategy C reported invalid and not rerun; C1 replaces it as the hybrid
strategy (in-sample results only; a test run needs its own dated note); no
further C diagnostics.

**Bug 14 — stop/target fills ignore gaps (found 24 Oct; FIXED for A and B —
placebo passed, corrected run done; C1 NOT validated).** Daily-bar engines fill a stop at the stop price
and a target at the target price whenever the bar's low/high crosses them, even
when the bar OPENS beyond the level (`backtest.py` 163–173 for A;
`strategy_c.py` walk-forward loop for C/C1). Correct fill when the open is
already beyond the level: the open (worse than the stop, better than the
target). Second part: the entry day is never checked — A enters at the open and
checks from the next bar; C checks from the day after its intraday entry. A
stop crossed on the entry day is then filled at the stop price on the next bar,
however far the price has moved. Net effect is optimistic: stops (1R) are
crossed far more often than targets (2–2.5R), and gap losses beyond 1R are
never booked. This explains why C1's random-direction placebo earns more than
minus its cost (mean R +0.0017 vs −0.0103). Affects A, C, C1 (daily bars,
overnight gaps); B less (minute bars, but sparse IEX bars and the entry bar is
unchecked); D, N, the event studies and the speed bound have no stops and are
unaffected. Time exits are at the close (correct).
Fix (note `…note_bug14_2026-10-24.md`, 5f2ce391…; shared `risk.barrier_exit`):
gap through stop or target fills at the open; stop first if both touched; A
checked from the entry day, B from the entry bar; C1 unchanged on its entry
day (entry at the close, its range lies before the entry). Unit test
`tests/test_bug14_fills.py` 15/15 (the old engine fails every gap/entry-bar
check); all other tests pass. Placebo on training (seed 20261024, plain SE):
**A PASSED** (25,098 trades, mean R −0.0073 vs cost −0.0090, 0.48 SE; long
+0.0060 vs short −0.0206, t 3.9, descriptive); **C1 FAILED** (12,410 trades,
mean R −0.0001 vs cost −0.0103, 2.30 SE; before the fix 2.88 SE; long−short
t 1.0). Per the note: stopped; no recalibration, no rerun. The fixed engine is
in `src/` (backup `_archive/_backup_2026-10-24_before_bug14_fix/`).
Decision 24 Oct (note `…note_c1_and_ab_correction_2026-10-24.md`, 24a9940a…):
criterion not amended; C1 not validated, hybrid strategy not evaluated; A and B
rerun as a disclosed correction (keyword, LLM, rung 1b; scales recalibrated on
training). LLM A Kelly test Sharpe 1.80 -> 0.75; 18 Oct A/B rows SUPERSEDED.

**Universe selection — no point-in-time index membership (found 24 Oct by code
inspection; KNOWN LIMITATION, note `…note_membership_2026-10-24.md`, 11c352cd…; no further work).** `nasdaq100.txt` is the static union of 193
tickers that were NDX members at any time 2015–2026, with no dates. Signals,
trades (A–D, N) and event-study events use every ticker in it on every date;
nothing checks membership on the event date. Membership dates are not on disk:
`bloomberg_to_csv.py` can read `MEMBERS_YYYY` sheets (`INDX_MWEIGHT_HIST`), but
none were exported. Effect: firms that joined the index later (selected because
they grew) are traded before they joined, and leavers after they left, so there
is look-ahead in the universe selection, favouring longs. Counting events
outside membership needs the membership history (Bloomberg export).

**Momentum benchmark deviations (found 24 Oct by code review; RECORDED, not
changed — the frozen benchmark stays).** (1) Vol target per name / 193
tickers incl. not-yet-listed -> realised vol 2–3% p.a., not 10% (Sharpe
unaffected). (2) Momentum restarts per period: flat for the first 90 trading
days of the test period (17%) — FIXED 24 Oct by the continuous series (note
`…note_momentum_2026-10-24.md`, 5b6c210b…): full test Sharpe 0.72, not 1.07;
the warm-up had skipped a losing stretch, so the frozen benchmark OVERSTATED
momentum (the first reading, "understates", was wrong). (3) Constant weights between weekly rebalances,
drift not costed; 5-row, not calendar-week, rebalance — DISCLOSED LIMITATIONS.
(1) stays; a scaled series (k 0.726, training maxDD 5%) gives comparable
return and drawdown. Placebo passes (random
positions lose about their costs, −0.15 SE).

**Placebo coverage (25 Oct):** A (Bug 14 engine) passed, B passed (note
`…note_placebo_b_2026-10-25.md`), minute-bar C passed, momentum passed; C (daily
basis) and C1 failed and are not validated.

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

---

## Appended 10 November 2026 — Bug 15 and corrections to statements above (appended; nothing above is edited)

**Bug 15 — same-day information in the position sizing of Strategy A (found 10 Nov 2026 by the reviewer's code
review; FIXED 10 Nov; all ten A rows rerun as a disclosed correction).** In `backtest.py` (`NewsDriftBacktest.run`)
one loop iteration for date d booked the day's exits (using day d's high, low and CLOSE) and passed each result to
the sizer, marked equity at the close of d and updated the governor, and only then opened the new positions "at
day d's open" — sized with a Kelly window containing trades closed on day d (87–99.9% of training sizing calls),
with the equity and throttle of that close, and with entry-day stops of earlier tickers of the same day. Direction,
entry, stop, target and exit were unaffected; position SIZE used information that did not exist at the open (hard
rule 1). With a long-biased book the Kelly fraction rose on days that went the book's way, which inflated the A
Kelly rows; the fixed rows moved only through equity and throttle (≤ 0.002 Sharpe at 5%). The order of steps is
older than the Bug 14 fix. Not caught earlier because the random-direction placebo's statistic does not depend on
size, the A placebo ran with the fixed sizer, and the 8 Nov assertion tested "exit date ≤ entry date", which
same-day closes satisfy.
Fix (notes `…note_bug15_2026-11-10.md` 7a66229b…, addendum `…note_bug15_addendum_testD2_2026-11-10.md` e1532c0f…,
results `…note_bug15_results_2026-11-10.md`): every sizing input of day d is that of the close of d−1 (Kelly window:
trades with exit date strictly before d; sizing equity; governor throttle); day d's results reach the sizer after
the day's last entry; runtime assertions on every sizing call. Backup `_archive/_backup_2026-11-10_before_bug15_fix/`.
Checks: unit test `tests/test_bug15_sizing_lag.py` 19/19 (the old code fails 10 of 18); the engine equals the
reviewer's reference variant V2 on all ten training cells (difference 0.0); strict assertion: 0 violations in
474,557 trades and 476,550 sizing calls of the official dumps (5% and 20%, both periods), 97.3–99.9% violations on
the old training dumps; common-direction placebo (test D2, keyword, Kelly, training): excess of the size-weighted
over the equal-weighted entry-day return +1.72 bps (0.33 clustered SE) all long and −2.21 (−0.34) all short on the
new code, +37.07 (7.77) and +42.21 (6.93) on the old code.
**A random-direction placebo cannot detect a look-ahead in position size, with any sizer**: with directions drawn
independently per signal the direction of an entry is independent of its size, so the size-weighted return has
expectation zero under either code (test D, Kelly sizer, random directions: new code −0.54 SE, old code −0.81 SE —
both pass). **The strict assertion on every sizing call and the common-direction placebo are the checks that detect
it**; both are now in `tests/` and in the harness. The fixed-sizer A placebo rerun is unchanged (0.48 SE).
Effect (5% target, test Sharpe old → new): keyword A Kelly 0.03 → −1.36; Llama A Kelly 0.75 → 1.08 (training +0.24
→ −0.54; vs momentum +0.34 ± 0.95, p 0.72; DSR 0.13 — not significant); MiniLM −0.63 → −1.19; Haiku −1.21 → −1.55;
Sonnet −0.93 → −1.39; fixed rows unchanged to the third decimal. Scales recalibrated on training
(`outputs/risk_calibration_<rung>_bug15fix_2026-11-10.csv`). The A rows of 24/25 Oct are SUPERSEDED (Bug 15); B, C,
the benchmark, event studies and speed bound are unaffected (`portfolio.py` closes trades with `exit_ts <= entry_ts`
before each sizing call). Trial counts unchanged (139 / 155 / 161 / 163). Other callers of the A engine
(`order_robustness.py`, `sweep_new_strategies.py`, `calibrate_scorer.py`) were not rerun; their recorded training
outputs predate the fix. Disclosed, not changed: a ticker whose position exits on day d can be re-entered at the
open of d (admission on the book after day d's exits).

**Placebo coverage (10 Nov):** A fixed sizer passed (rerun, unchanged); A Kelly sizer with random directions
passed; A Kelly common-direction placebo: new code within, old code above two clustered SE.

**Corrections to statements above (the code and the data files are right; these sentences were not):**

1. Line 4, "none by reading code": Bugs 13 and 14 were found by code inspection prompted by a placebo, the universe
   limitation and the benchmark deviations by code review, and Bug 15 by reading code.
2. Lines 16–17 (entry 3), "Fixed: `max(2×ATR, 8×round-trip cost, 40bps)`": the fix that exists, in the code of
   18 October and today, is the skip of candidates whose stop is below 3 × the round-trip base cost (`intraday.py`
   `min_stop_to_cost_ratio`, l. 117 and 268–270); the stop itself is 3 × the standard deviation of the last 30
   one-minute returns × price (l. 95–96, 259–263).
3. Line 150, "C1 FAILED (12,410 trades": `placebo_c1_bug14fix_2026-10-24.csv` has 12,873 trades; 12,410 is the trade
   count of the daily-bar C placebo (correctly given at line 114).
4. Line 171, "Vol target per name / 193 tickers incl. not-yet-listed": the divisor is the number of price columns,
   171 (`baseline.py` l. 36, `n = close.shape[1]`; `momentum_continuous_2026-10-24.log` l. 3).

---

## Appended 10 November 2026 (later) — Bug 16 (appended; nothing above is edited)

**Bug 16 — Strategy A never closed a position in a ticker that stops trading (found 10 Nov 2026, after the
freeze, in the course of the external review, while the exploratory Strategy F in `review_2026-11-10/` was
reconciled; FIXED 10 Nov; all ten A rows rerun as a disclosed correction).** In `backtest.py` a held position
whose ticker had no bar on day d was skipped in the exit loop and left out of the mark-to-market, while its
notional kept counting against the gross cap. A position opened in the last bars of a stock that stops trading
(acquisitions) was never closed: its whole value left equity on the next trading day and no trade was booked.
Always against the strategy; not a look-ahead. These positions were also large, because a stock pinned to a deal
price has a very small ATR. A one-day gap in a ticker's bars made a one-day hole in equity (extra volatility).
Training, Bug 15 dumps: keyword 3 stuck positions (ATVI, ESRX, SPLK), Llama 5 (ESRX, MXIM, MYL, SHPG, WFM),
MiniLM 6 (the same and XLNX), Haiku and Sonnet none; 26% to 77% of a row's training loss, and about half of the
"five percent" drawdown of keyword fixed and Llama fixed, so their scales were about half of what the rule gives.
Test period: one position (MiniLM, ANSS). Not caught earlier: every assertion and placebo worked on booked
trades; nothing compared the equity curve with the trade log.
Fix (notes `…note_bug16_2026-11-10.md` c17fce3f…, results `…note_bug16_results_2026-11-10.md`; diagnosis
`review_2026-11-10/BUG16_note_2026-11-10.md` d6577a76… and its addendum 2d054c04…): positions are marked at
their last available close; the holding period is counted on the trading calendar; a time exit on a day without
a bar fills at the last available close (reason `stale`) and is booked like any other trade. Runtime assertion
every day: equity change = booked results + open positions. Backup `_archive/_backup_2026-11-10_before_bug16_fix/`.
Checks: unit test `tests/test_bug16_stopped_ticker.py` 9/9 (the old code fails 5 of 6); the old logs fail the
reconciliation on exactly the listed positions (40/40 checks); the fixed engine reconciles on every row and day
(training at the old scales 10/10; official dumps of the run 40/40, largest residual 2e-9); the Bug 15 strict
sizing assertion still passes (0 violations in 474,521 trades); Strategies B and minute-bar C reconcile
unchanged (60/60) and the stored momentum series equals its recomputation (5e-16) — the mechanism does not exist
there. Placebos on the new engine: fixed sizer 0.48 SE; Kelly with random directions passes; Kelly with common
directions +2.66 bps (0.53 clustered SE) long, −1.77 (−0.28) short.
Effect (5% target): **test-period Sharpe ratios move by at most 0.013** except MiniLM fixed
(−2.18 → −2.10); test returns and drawdowns are larger in size where the scale rose (keyword fixed 0.0041 →
0.0079, Llama fixed 0.0072 → 0.0145, MiniLM fixed 0.0028 → 0.0037, Kelly 0.0033 → 0.0041, 0.0096 → 0.0122,
0.0015 → 0.0027; Haiku, Sonnet unchanged). Training Sharpe: keyword fixed −0.76 → −0.74, Kelly −0.75 → −0.59;
Llama fixed −0.48 → −0.17, Kelly −0.54 → −0.44; MiniLM fixed −1.22 → −1.13, Kelly −0.84 → −0.77; Haiku fixed
−0.53 → −0.59 (the one-day holes are gone). Counts of the forty configurations unchanged (36 lose, 24
significantly worse than momentum). The Bug 15 A rows are SUPERSEDED (Bug 16). Trial counts unchanged
(139 / 155 / 161 / 163). `order_robustness.py`, `sweep_new_strategies.py` and `calibrate_scorer.py` were not
rerun; their recorded training outputs predate the fix.

**Check added to the harness (10 Nov):** the equity reconciliation for A, B, minute-bar C and momentum
(`bughunt/bh_reconciliation.py`). It is the check that detects this class of error.

## Appended 14 November 2026 — Bug 17 (appended; nothing above is edited)

**Bug 17 — the entry step of Strategy A admitted positions on the book as it stood after the day's exits (found
after the freeze by the external review, by reading the code; disclosed but not corrected on 10 Nov; FIXED
14 Nov; all ten A rows rerun as a disclosed correction).** In `backtest.py` one day d ran: exits of d (with d's
high, low and close), mark to market, then the entries "at the open of d", which were tested against `open_pos`
as left by the exits. Three consequences: a ticker held at the open of d and closed during d was entered again
at that day's open; the gross-exposure cap was judged on the book after the day's exits; an entry closed on its
entry day did not count for the later tickers of the same open. Bug 17 is two things under one rule:
- **a double position on scheduled exit days.** 71% to 91% of the re-entries follow a time exit, which is known
  at the open: no future information, but two positions in one ticker from the open to the close of d, against
  the rule of one position per ticker, and the old one left out of the gross figure;
- **a look-ahead in admission on stop and target days** (hard rule 1). 9% to 29% follow a stop or a target hit
  during d (training: keyword 551 trades, Llama 729, MiniLM 1,090, Haiku 204, Sonnet 53).
Size in the official runs of 10 Nov, trades entered on the exit day of the previous trade in the ticker —
training: keyword 6,150 of 25,089 (24.5%), Llama 4,241 (19.4%), MiniLM 5,351 (25.2%), Haiku 1,046 (9.5%), Sonnet
184 (3.7%); test period: keyword 4,105 of 12,076 (34.0%), Llama 2,053 (25.4%), MiniLM 3,071 (37.4%), Haiku 715
(16.4%), Sonnet 108 (5.7%). Direction, entry price, stop, target, size and exit of every admitted trade were
correct; wrong was which trades were admitted. Not caught earlier: the Bug 15 assertion covers the sizing inputs,
not the book; the Bug 16 reconciliation holds whatever is admitted; the placebos do not depend on which tickers
are free. B and C (`portfolio.py` closes by timestamp before each admission), momentum, the event study and the
exploratory Strategy F are not affected.
Fix (notes `…note_bug17_2026-11-14.md` e96e94d7…, addendum `…note_bug17_addendum_testC_2026-11-14.md` 705714f1…,
results `…note_bug17_results_2026-11-14.md`; diagnosis `review_2026-11-14/BUG17_note_2026-11-14.md` 964ad2d4… and
`BUG17_reference_2026-11-14.md` d56f0993…): the entry step sees a snapshot of the book taken at the close of
d−1, before the exits of d, plus its own orders of this open. A ticker in the snapshot is not entered at d (it
is eligible again from d+1); gross = notional in the snapshot + notional admitted earlier at this open, still
open or not. Three runtime assertions; sizing-log column `gross_at_decision`. Engine `fbf1e857…` → `424ae4ef…`;
backup `_archive/_backup_2026-11-14_before_bug17_fix/`.
Checks: unit test `tests/test_bug17_admission_snapshot.py` 13/13 (the old engine fails each of its three cases);
perturbation test on real training data (day d's high, low, close replaced by the open; keyword and Llama, both
sizers, 150 days each): the old engine changes its entries on 31 (keyword) and 55 (Llama) of 150 days, the new
one on 0 of 600; the ten training cells of the reviewer's independent reference reproduced with a difference of
exactly 0; the old training logs fail the trade-log check with exactly the reviewer's counts; on the 40 logs of
the run no position is opened in a ticker held or closed that day (0 of 402,283) and no entry exceeds the gross
cap on the previous close's book; Bug 15 strict assertion 0 violations in 401,447 trades; reconciliation 0 failing
days; three placebos pass; harness 204/204 files, 457/461 assertions (the four are calibration-band findings).

**Fixture change in an existing test (author's decision of 14 Nov, addendum).** The correction was stopped at
acceptance test C because `tests/test_bug15_sizing_lag.py` failed on the corrected engine. Its section 2 fixture
held five positions (87,531 notional) that all closed on day d and needed 17,506 more for the entry of d against a
gross cap of 100,000: it relied on capacity freed during day d, i.e. on Bug 17, not on the Bug 15 rule. Changed:
`max_gross_exposure=2.0` in `fixed_case` only (file 93427590… → a8c00760…). The changed test passes 19/19 on the
corrected engine and on the engine of 10 Nov, and fails 10 of 18 on the engine before the Bug 15 fix, as the
unchanged test did. No acceptance criterion was changed.

Effect (5% target; scales recalibrated, free rungs up by a fifth to two thirds, Haiku Kelly down): 13% to 18%
fewer training trades in the free rungs (7% Haiku, 3% Sonnet), 16% to 23% fewer test-period trades (11% Haiku,
4–5% Sonnet). **Test-period Sharpe ratios move by −0.09 to +0.65**: keyword fixed −1.22 → −1.25, Kelly −1.36 →
−1.45; Llama fixed −0.12 → +0.01, **Kelly 1.08 → 1.30** (+1.8% p.a.; vs momentum +0.56 ± 0.96, p 0.56; DSR(139)
0.20); MiniLM fixed −2.10 → −1.78, Kelly −1.18 → −0.79; Haiku fixed −1.17 → −1.12, Kelly −1.55 → −0.90; Sonnet
fixed −1.09 → −0.98, Kelly −1.39 → −1.45. Training Sharpe: keyword −0.74 → −0.65 and −0.59 → −0.42; Llama −0.17 →
−0.13 and −0.44 → −0.09; MiniLM −1.13 → −0.98 and −0.77 → −0.75; Haiku −0.59 → −0.64 and −0.50 → −0.80; Sonnet
−0.23 → −0.20 and +0.05 → +0.07. The forty configurations: **35 lose (was 36), 22 significantly worse than
momentum (was 24)**; none beats momentum significantly. The Bug 16 A rows are SUPERSEDED (Bug 17). Trial counts
unchanged (139 / 155 / 161 / 163; Strategy F is trial 164); counting the reruns would be stricter.
`order_robustness.py`, `sweep_new_strategies.py`, `sensitivity_dd20.py` and `calibrate_scorer.py` were not rerun;
their recorded outputs predate the fix.

**Checks added to the harness (14 Nov):** the admission assertion from dumped logs
(`bughunt/bh_bug17_admission.py`): no entry in a ticker held or closed that day, gross cap on the previous
close's book. The perturbation test (flatten day d's range, compare day d's entries) is the test that detects a
look-ahead in admission; it does not detect the double position on scheduled exit days, the trade-log check does.
