# Strategy C (minute-bar only) for rungs 2 and 3, dated 25 October 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written 2026-10-25 by decision of the author, BEFORE any C result for Haiku
or Sonnet exists (rung 2 A/B results are known; rung 3 is still being scored).
Amends `…note_rung2_2026-10-24.md` and `…note_rung3_sonnet_2026-10-25.md`
(+ amendment), which excluded C when the minute-bar C was not yet validated;
it was validated on 25 Oct (`…note_c_minute_2026-10-24.md`, placebo passed).
The engine is validated once for all scorers; no new placebo.

1. **Data.** For every C event of Haiku and Sonnet (same event definition as
   C), the news day and next 4 trading days are fetched exactly as in the
   C-minute note (full-session IEX bars, feed=iex, adjustment="split",
   regular session kept, >= 1 s between requests, paused Mon 26 / Tue 27 Oct
   14:00–21:30 Europe/Zurich, same deadline Wed 28 Oct 23:59). **Only
   ticker-days not already in `data_sources/c_hold_days.csv` are fetched**, from
   a separate range list, and appended to `data_sources/bars_c_hold.csv`; the
   bars of every existing hold day are untouched, so the keyword / LLM / rung 1b
   C results cannot change.
2. **Runs.** One additional run per rung with `--c-engine minute` (risk scales
   recalibrated on training by the 5% rule; A and B recomputed alongside and
   required to reproduce the rung's A/B results exactly; only the C rows are
   new). Rung 2: deflated Sharpe N = 155 (C rows were already counted in the
   ladder's 155). Rung 3: N = 163 for the C rows (161 + 2); its A/B rows keep
   N = 161 as pre-registered.
3. **Tests** as for C elsewhere: Jobson-Korkie-Memmel vs the continuous
   momentum benchmark; Kelly − fixed for C, each rung's C on its own (no Holm
   adjustment, as for rung 1b's C). **Labelled "exposed to look-ahead".**
4. If the delta fetch or the runs cannot finish by the deadline, C for these
   rungs is not evaluated and the reason is recorded.
