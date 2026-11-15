## Current state (18 Oct 2026; Strategy A corrected 10 Nov 2026 for Bugs 15 and 16)

**Official evaluation = training period + test period** (single frozen runs of
18 Oct 2026). The holdout was dropped by decision (2026-10-19) before any
holdout return was computed; H1–H3 are not evaluated.

- **No tradable post-news drift.** Event study: large signed news-day move
  (+57 to +78 bps, t > 15) but from the next open market-adjusted returns of
  about 0 to −7 bps (training) and −2 to +6 bps (test), below the 4.86 bps
  round-trip cost. Headlines describe more than they predict (intraday).
- **Strategies, test period (A corrected 10 Nov for Bugs 15 and 16; A and B corrected
  24 Oct for Bug 14; net of costs):** best is LLM A Kelly +1.0% p.a., Sharpe
  1.08 vs continuous momentum 0.72 (corrected 24 Oct; was 1.08); difference
  +0.34 ± 0.95 (p 0.72, n.s.), DSR(139) 0.13; its training Sharpe is −0.44.
  Every other A row loses (keyword A Kelly −1.36, MiniLM −1.18); 36 of the 40
  configurations lose and 24 are significantly worse than momentum. B loses.
  C (minute-bar-only reimplementation, 25 Oct): best LLM Kelly Sharpe 0.42,
  none beats momentum; C1 not validated (placebo). The A rows of 24/25 Oct
  (LLM A Kelly 0.75) and of the Bug 15 run (`*_bug15fix_*`) are superseded;
  numbers in the last appended section of `context/results.md` and
  `outputs/*_bug16fix_2026-11-10*`.
- **Rung 2 (Claude Haiku 5.5, 25 Oct; exposed to look-ahead):** strongest
  news-day sort (+110/+120 bps) but no post-entry drift; A test Sharpe −1.2
  (fixed) and −1.6 (Kelly), both worse than momentum; B loses. Scoring cost $2.16.
- **Rung 3 (Claude Sonnet 5.5, 25 Oct; exposed to look-ahead):** news day
  +159 bps (test) but no drift; A test Sharpe −1.1 (fixed) and −1.4 (Kelly),
  B loses. Cost $29.30. 18 Oct A/B rows (LLM A Kelly 1.80) superseded.
- **Exploratory, unconfirmed:** keyword corporate_event reversal (training and
  test); LLM importance 7–10 drift (test only).
- **Exploratory Strategy F (news fade, 10 Nov; not official, trial 164):** fades
  keyword corporate-event headlines, 3-day hold, index hedge; only in
  `review_2026-11-10/exploration/fade/`. Training Sharpe 0.24; one test run:
  +3.6% p.a., Sharpe 1.11, vs momentum +0.38 ± 0.98 (p 0.70), DSR(164) 0.13.
  Not blind (the test-period reversal was known) and carried by a few trades:
  not a confirmed finding; its test period is used, do not tune F on it.
- **Bugs 1–12 fixed** (`context/bugs.md`); Bug 12 order noise ~0.1–0.3 Sharpe
  for B/C/D, small for A.
- **Bug 15 fixed 10 Nov** (same-day information in A's position sizing; notes
  `outputs/FROZEN_CONFIG_2026-10-18_note_bug15*_2026-11-10.md`): A sizes use
  the previous close's Kelly window, equity and throttle, asserted at runtime.
  A random-direction placebo cannot detect a sizing look-ahead; the strict
  assertion and the common-direction placebo do
  (`tests/test_bug15_sizing_lag.py`, `src/placebo_a.py --directions`).
- **Bug 16 fixed 10 Nov** (A never closed a position whose ticker stopped
  trading and its margin vanished from equity; notes
  `outputs/FROZEN_CONFIG_2026-10-18_note_bug16*_2026-11-10.md`): positions are
  marked at the last available close, holding days run on the trading calendar,
  a missing exit-day bar exits at the last close (`stale`). Equity = booked
  trades + open positions is asserted every day in A and checked for B, C and
  momentum by the harness (`tests/test_bug16_stopped_ticker.py`,
  `bughunt/bh_reconciliation.py`). Test Sharpe ratios move by at most 0.013
  (MiniLM fixed −2.18 → −2.10); the fixed scales of keyword and Llama about
  double, and with them their test returns and drawdowns.

- **Bug 17 fixed 14 Nov** (A's entry step admitted on the book after the day's exits:
  re-entry in a ticker on its exit day, 4% to 37% of the trades, and the gross cap judged
  after the exits; notes `outputs/FROZEN_CONFIG_2026-10-18_note_bug17*_2026-11-14.md`):
  admission uses a snapshot of the book at the previous close plus the entries of the same
  open, asserted at runtime. Checked by a perturbation test (flatten day d's range, the
  entries of d must not change), the reviewer's independent reference (ten training cells,
  difference 0) and a dump-based assertion (`tests/test_bug17_admission_snapshot.py`,
  `bughunt/bh_bug17_admission.py`). One stop at acceptance test C: the fixture of
  `tests/test_bug15_sizing_lag.py` relied on the defect and was changed on the author's
  decision (addendum). **Current A numbers (`outputs/*_bug17fix_2026-11-14*`): LLM A Kelly
  test +1.8% p.a., Sharpe 1.30, vs momentum +0.56 ± 0.96 (p 0.56), DSR(139) 0.20, training
  Sharpe −0.09; keyword A Kelly −1.45, MiniLM −0.79, Haiku −1.12 / −0.90, Sonnet −0.98 /
  −1.45; 35 of 40 configurations lose, 22 significantly worse than momentum.** The A
  numbers in the bullets above (1.08, 36 of 40, 24) are those of the Bug 16 run and are
  superseded. 20%: four rows material (Llama A Kelly 1.30 → 0.74).
