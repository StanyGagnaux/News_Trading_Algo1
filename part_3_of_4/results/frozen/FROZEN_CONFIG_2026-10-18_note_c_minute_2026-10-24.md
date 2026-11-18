# Strategy C reopened once — minute-bar-only implementation, dated 24 October 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written 2026-10-24 BEFORE any fetch, code change or run, by decision of the
author. Adds to the Bug 13, Bug 14 and C1 notes, which are not edited.

## 1. Reason — one placebo criterion for all engines (decided after C's result)

A and C were validated against different criteria (A: mean only; C: mean
plus long-short symmetry). The A, momentum and C placebos all show longs
beating shorts, consistent with the recorded universe look-ahead
(`…note_membership_2026-10-24.md` + addendum), so long-short symmetry cannot
be required of any engine in this universe. **From now on one criterion
applies to every engine: mean R within 2 (plain) SE of minus the expected
cost; long-minus-short is reported as descriptive.** This harmonisation was
decided AFTER C's placebo result and is disclosed as such.

C1 is unaffected: it failed the mean criterion itself (2.30 SE) and stays
not validated.

## 2. Data — refetch for Strategy C only (reverses the earlier no-refetch choice)

The existing minute bars (`data_sources/bars_intraday.csv`, SHA-256
`330e5c78aebb0b73a92ed7e2c4cc775e7ea23873bbb10de9ac856ccc8a5eca2d`) cover only
30 min before to 390 min after each headline; C's hold days are covered for
38–63% of events and partly (selecting covered events would condition on
later news = look-ahead). **For Strategy C only, and reversing the no-refetch
choice made for the Bug 13 fix**, full-session bars are fetched:

- Days: for every C event of any rung (keyword, LLM anonymised, rung 1b),
  training and test (union), the news day and the next 4 trading days of that
  ticker (prices calendar) — covers an entry rolling to the next session plus
  the maximum 3-day hold.
- Source: Alpaca `v2/stocks/{sym}/bars`, 1Min, `feed=iex`,
  `adjustment="split"` (as the existing file); request 09:30 New York of the
  first day to 16:00 of the last day of each merged date range; only bars
  stamped 09:30–15:59 New York are kept. Output to a separate file
  `data_sources/bars_c_hold.csv`; the existing bars file stays untouched.
- Throttle: >= 1 s between requests (<= 60/min, under a third of the account
  limit); **paused Monday 26 and Tuesday 27 October 14:00–21:30
  Europe/Zurich** so it cannot affect the shadow run. Resumable.
- The free IEX feed serves a rolling ~6-year history. Events whose news day
  precedes the first date for which the fetch returns bars are excluded by
  calendar date (not by outcome); that date and the count are recorded.

## 3. Implementation (minute-bar only, Bug 14 engine)

New module `src/newsdrift/strategy_c_minute.py`; additive option
`--c-engine daily|minute` (default daily = unchanged) in
`run_both_strategies.py` and `calibrate_risk.py`; placebo variant in
`placebo_c.py`.

- Events: identical to C (`market_hours_events(build_event_table(...))`).
- Entry: first regular-session minute bar at or after news + 15 min, at its
  open, with C's latency-decayed entry cost.
- **Stop distance as a ratio:** entry × max(2.0 × mean over the 14 daily bars
  before the entry day of (high − low) / close, 0.004). Basis-free (the
  adjustment factor cancels). Target 2R.
- **Regular-session bars only** (09:30–16:00 New York) for entry, stops,
  targets and exits.
- Walk: every regular-session bar from the entry bar (inclusive) to 16:00 New
  York on the exit day = the `duration`-th trading day after the entry day
  (duration clipped to 1–3, as C); Bug 14 fill rule (`risk.barrier_exit`: gaps
  fill at the bar's open; stop first if both touched).
- **Time exit:** close of the last regular-session bar at or before 16:00 New
  York on the exit day; if that day has no bar, the last earlier bar (counted;
  no trade is dropped on later data).
- Exit cost 2.43 bps per side (empirical), as C.
- **Ex-dividend: no adjustment.** Split-adjusted minute prices drop by the
  dividend on the ex-date: a long loses and a short gains about the dividend
  (in reality received / paid). NDX quarterly dividends ~0.1–0.3% of price,
  ~5% of trades expected to span an ex-date; opposite for longs and shorts, so
  the mean-R placebo is unaffected; biases the strategy slightly against
  longs. **Size estimated descriptively** after the run: per trade, the
  implied dividend = change of (daily adjusted close / last minute close at or
  before 16:00) between entry day and exit day; mean effect in R by direction.

## 4. One attempt, time limit

1. Unit tests (minute-only fills, gap through stop, both touched, entry-bar
   stop, time exit, regular-session filter, no look-ahead), then the TRAINING
   placebo: random directions (`numpy.random.default_rng(20261024)`), PASS if
   mean R lies within 2 plain SE of minus the expected cost
   (−(entry cost + exit cost) / stop distance per trade); long-minus-short
   descriptive.
2. **Fail → C stays not validated; no further work on C.**
3. **Pass →** risk scales calibrated on training (5% maxDD rule, A and B
   recomputed alongside and expected to equal the Bug 14 scales); one run per
   rung (keyword, LLM, rung 1b) over training + test as a disclosed
   correction; same comparison tests as A and B: Jobson-Korkie-Memmel vs the
   **continuous momentum benchmark**, deflated Sharpe with **N unchanged
   (139 keyword/LLM, 155 rung 1b; the new C replaces C in the trial count)**,
   Kelly − fixed with Holm (**family of 2: keyword + LLM C; rung 1b C on its
   own**). Logged in `outputs/test_period_runs.csv`. The 18 Oct C rows stay
   INVALID.
4. **Time limit:** if fetch, unit tests and training placebo are not complete
   by **Wednesday 28 October 2026, 23:59 Europe/Zurich**, stop: C stays not
   validated and the reason is recorded.

Code before the change (SHA-256): `run_both_strategies.py` 8bafc0d3…,
`calibrate_risk.py` 374ba2ea…, `newsdrift/strategy_c.py` dac8cfa7…,
`placebo_c.py` a5641768….
