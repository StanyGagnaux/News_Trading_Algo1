# Note to FROZEN_CONFIG_2026-10-18 — holdout on Bloomberg prices, dated 18 October 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written before any holdout return has been computed. Earlier frozen files
are not edited; this note supersedes them only where stated.

## 1. Price source and window (supersedes the Yahoo source and the 2026-10-16 end)

- **Holdout prices: Bloomberg `prices.csv` only**, which ends **2026-07-14**
  (NDX included). Yahoo is not used for the holdout.
- **Holdout window:** news dated 2026-06-02 through **2026-07-07**, the last
  news date whose full day-5 window (entry open → close of day 5, frozen
  event-study spec) ends on or before 2026-07-14 on the prices.csv trading
  calendar (holidays 19 June and 3 July removed): news on 2026-07-07 enters
  on 2026-07-08, whose day 5 is 2026-07-14. Computed by
  `holdout_eval.last_news_date` (tested in `tests/test_holdout_eval.py`).
- **One event set for all horizons:** an event enters every horizon (day 0,
  1, 2, 3, 5) or none (complete cases on the ticker's own bars).
- **Excluded holdout news:** 22,564 of 29,919 cleaned holdout rows are dated
  after 2026-07-07, plus 2 rows dated 2026-06-01; they were downloaded (and
  the LLM scored them) but are excluded and never evaluated. 7,353 rows fall
  in the window.
- **Expected events (counted from bar dates only, no prices):** keyword 579
  (24 entry dates); LLM 411 (24 entry dates); keyword corporate_event 46
  (19 entry dates).

## 2. Disclosures

- Bloomberg prices for June–July 2026 were downloaded in July 2026 and have
  **never been used to evaluate any news event**: every test-period analysis
  stopped at 2026-06-01, and the 18 October Yahoo/Bloomberg consistency check
  compared prices only, with no news or signals.
- The Phase-1 counts above read the June–July price file only to see which
  dates each ticker has a row for; no price value or return was computed.
- No Yahoo holdout loader was ever written. `src/source_consistency.py`
  (Yahoo, consistency check only) and `newsdrift.data.load_prices_yfinance`
  remain in the repository and are **not used** by the holdout.
- **Date correction:** the notes `FROZEN_CONFIG_2026-10-18_note_bug12_2026-10-19.md`
  and `..._note_H3_2026-10-19.md` (and the hashes file `..._hashes_notes_2026-10-19.txt`,
  `h2b_kelly_vs_fixed_holm_2026-10-19.csv`, `order_robustness_2026-10-19.csv`,
  `h3_power_2026-10-19.csv`) carry the label 19 October but were written on
  **18 October 2026, 20:50–21:15 CEST** (file timestamps). Their content
  stands; only the date label is wrong.

## 3. Code path

The holdout runs through the same event-study code and price loader as the
official test-period run: `event_study.load_window` (the former `load_test`
logic, now parameterised; `load_test()` verified to return identical data
before and after), `event_study.event_returns` and `clustered_mean`, with
`src/holdout_eval.py --run` applying only the holdout date window. The full
`--run` code path was exercised once on a TRAINING window (news 2023-06-02 to
2023-07-09) as a code check (`outputs/validation_2026-10-18/`).

## 4. Hypotheses and tests: unchanged

H1 (Holm across the 8 keyword/LLM × day 1/2/3/5 cells, one-sided bound
against 4.86 bps, inconclusive otherwise), H2 (keyword corporate_event, day
3, one-sided 5%) and H3 (LLM day-3 slope on |strength|, one-sided 5%, CR1
date-clustered) exactly as in the earlier notes.

## 5. Expected power before any run (`outputs/holdout_power_2026-10-18.csv`)

Effect sizes from the test period; SE scaled from the test period by the
ratio of entry dates (clusters) or of events. H1 "power" = probability of
concluding "below cost" in a cell, at the first Holm step (0.05/8) and at
0.05.

| test | assumed truth | alpha | power (date basis) | power (event basis) |
|---|---|---|---|---|
| H1 keyword day 1 | test-period mean | 0.0063 | 0.02 | 0.02 |
| H1 keyword day 1 | true mean 0 | 0.0063 | 0.02 | 0.02 |
| H1 keyword day 1 | test-period mean | 0.0500 | 0.10 | 0.10 |
| H1 keyword day 1 | true mean 0 | 0.0500 | 0.11 | 0.11 |
| H1 keyword day 2 | test-period mean | 0.0063 | 0.02 | 0.02 |
| H1 keyword day 2 | true mean 0 | 0.0063 | 0.01 | 0.01 |
| H1 keyword day 2 | test-period mean | 0.0500 | 0.10 | 0.10 |
| H1 keyword day 2 | true mean 0 | 0.0500 | 0.08 | 0.08 |
| H1 keyword day 3 | test-period mean | 0.0063 | 0.01 | 0.01 |
| H1 keyword day 3 | true mean 0 | 0.0063 | 0.01 | 0.01 |
| H1 keyword day 3 | test-period mean | 0.0500 | 0.08 | 0.08 |
| H1 keyword day 3 | true mean 0 | 0.0500 | 0.07 | 0.07 |
| H1 keyword day 5 | test-period mean | 0.0063 | 0.01 | 0.01 |
| H1 keyword day 5 | true mean 0 | 0.0063 | 0.01 | 0.01 |
| H1 keyword day 5 | test-period mean | 0.0500 | 0.05 | 0.05 |
| H1 keyword day 5 | true mean 0 | 0.0500 | 0.07 | 0.07 |
| H1 llm_anon day 1 | test-period mean | 0.0063 | 0.00 | 0.00 |
| H1 llm_anon day 1 | true mean 0 | 0.0063 | 0.02 | 0.02 |
| H1 llm_anon day 1 | test-period mean | 0.0500 | 0.04 | 0.04 |
| H1 llm_anon day 1 | true mean 0 | 0.0500 | 0.10 | 0.09 |
| H1 llm_anon day 2 | test-period mean | 0.0063 | 0.01 | 0.01 |
| H1 llm_anon day 2 | true mean 0 | 0.0063 | 0.01 | 0.01 |
| H1 llm_anon day 2 | test-period mean | 0.0500 | 0.08 | 0.08 |
| H1 llm_anon day 2 | true mean 0 | 0.0500 | 0.08 | 0.07 |
| H1 llm_anon day 3 | test-period mean | 0.0063 | 0.01 | 0.01 |
| H1 llm_anon day 3 | true mean 0 | 0.0063 | 0.01 | 0.01 |
| H1 llm_anon day 3 | test-period mean | 0.0500 | 0.07 | 0.07 |
| H1 llm_anon day 3 | true mean 0 | 0.0500 | 0.07 | 0.07 |
| H1 llm_anon day 5 | test-period mean | 0.0063 | 0.01 | 0.01 |
| H1 llm_anon day 5 | true mean 0 | 0.0063 | 0.01 | 0.01 |
| H1 llm_anon day 5 | test-period mean | 0.0500 | 0.06 | 0.06 |
| H1 llm_anon day 5 | true mean 0 | 0.0500 | 0.07 | 0.06 |
| H2 keyword corporate_event day 3 | half of it | 0.0500 | 0.09 | 0.09 |
| H2 keyword corporate_event day 3 | test-period mean | 0.0500 | 0.14 | 0.15 |
| H3 LLM slope day 3 | half of it | 0.0500 | 0.07 | 0.07 |
| H3 LLM slope day 3 | test-period slope | 0.0500 | 0.10 | 0.10 |

With 24 entry dates the holdout has **low power for every hypothesis**
(H1 cells about 1–11%, H2 about 9–15%, H3 about 7–10%). Non-rejections will
be reported as uninformative, not as evidence for the null.

## 6. Fingerprints (SHA-256)

| file | sha256 |
|---|---|
| `src/event_study.py` (before, in `FROZEN_CONFIG_2026-10-18.md`) | `879acfcc968e6b4bb8d2e6e313ac5ea6fd3a76065e0af54f6fd8fc4f4102d020` |
| `src/event_study.py` (now: `load_window`) | `b26425672d1f89e6fa440881c37906cf2a3b0fa14de892901a909a8a723882cb` |
| `src/holdout_eval.py` | `6ad4fc376b7abee2e018a772ba27e8a4b63895aa2d781e988402b4c311343e50` |
| `tests/test_holdout_eval.py` | `c07e0e7ec4d293e66f91f000836dcf09fa075d06ae322929d20f85eb11bfa255` |
| `src/h3.py` (unchanged) | `d579bfd913c0f73fc2691d7ef8bb59878462e8585f00f255aa0bc8d608c1d162` |
| `outputs/holdout_power_2026-10-18.csv` | `224c4c9624d8da11ac99e24b5b5ac522f9e36260e3b240a6fac368ea28154333` |
| `data_sources/prices.csv` | `fbe780c25a9ad1790e0b26c83ff482bafb869ca9e3bcdf3bea01b716ab05166b` |
| `data_sources/holdout/news_holdout_clean.csv` | `58cb1dd316d20e9a6322143dec5a21e7323b6ebb1203694db95798fbac926a34` |
| `data_sources/holdout/news_scored_llm_ollama_anon_holdout.csv` | `e81afaca0a1c137441ad67829dc4ca4cd4c8c072de4e4390d4a864a8677d3c40` |
