# Bug 14 — gap fills: fix, checks and disclosed correction run, dated 24 October 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written 2026-10-24 BEFORE any code change, by decision of the author.

## Defect (found by code inspection, `context/bugs.md`)

Stops filled at the stop price and targets at the target price whenever the
bar's range crossed them, even when the bar OPENED beyond the level; and the
entry day/bar was never checked (A from the next day; B from the bar after the
entry bar). Net effect optimistic: losses beyond 1R through gaps never booked.

## Fix (one rule, one shared helper)

a) Gaps. Per bar, the open is checked first: a bar that opens beyond the stop
   fills the stop at the OPEN (the worse of stop and open); a bar that opens
   beyond the target fills the target at the OPEN (symmetric rule: a resting
   limit order fills at the open, here the better price). Otherwise a range
   that crosses the level fills at the level.
b) A bar that touches both stop and target (without a gap) exits at the stop.
c) Stops/targets are checked from the entry bar onward:
   - A: the entry day's bar (entered at its open; no gap is possible on it).
     The time exit is unchanged (close of the `duration`-th day after entry).
   - B: the entry minute bar is included.
   - C1 (entry at the news-day close): **no bar of the entry day lies after the
     entry**; checking that day's high/low would use prices from before the
     entry (look-ahead). C1's first checked bar stays the next day, where rule a)
     covers the overnight gap. This deviates from the instruction as written
     ("entry day for C1"), for the stated reason.
   Same rule applied in `standalone.py` (scorer calibration only) and B's
   scale-out exits (sweeps only); neither is in an official run. C (intraday
   entry) shares the C1 loop; C stays INVALID (Bug 13) and is not rerun.

Files changed (SHA-256 before the change):

| file | before |
|---|---|
| `src/newsdrift/risk.py` (helper) | `90d20ee15b207df8bcaa5c6e15046bfe8fbc580ea0090037d019594d938fa9af` |
| `src/newsdrift/backtest.py` (A) | `8b3dd822883f3c8563d4adf94cb9d1ba3a69e1afde11c0ad45ca47854dd0330b` |
| `src/newsdrift/intraday.py` (B) | `219b1eec38e04dbdf1417086b5bbe2e28464f2ca5dde240e77985ab8447b3669` |
| `src/newsdrift/strategy_c.py` (C1) | `7e97c3932b614354771ecaeeefa890a3e2dd3365df2326be5b0fd5b52443701a` |
| `src/newsdrift/standalone.py` | `5e11cac000935a1ceed8462e172831ca718c12c82e410350252786dd3cc35052` |
| `src/run_both_strategies.py` (additive options only) | `0e552bf72821da57f5ddfa24492e9dc1832502ca603232e962ae2accc6507b3a` |
| `src/calibrate_risk.py` (additive options only) | `1b07c18e8362429b1281ea3872ff6341f6284e1a058432bc9f58d22022775d05` |

Runner/calibration options added, defaults unchanged: `--c-variant C|C1`,
an output-name option (official 18 Oct files are never overwritten), and a
dump of trade logs and daily equity (for descriptive items 1(b) and 2).

## Checks before anything is relied on

d) Unit tests: gap through the stop, gap through the target, stop and target
   in the same bar, stop on the entry day (A) / entry bar (B), C1 overnight gap.
e) Placebo on TRAINING, random directions (`numpy.random.default_rng(20261024)`
   applied to the sign of |strength|): A (keyword daily signals, fixed sizer,
   designed governor, keyword A-fixed scale of 18 Oct so caps rarely bind) and
   C1 (same 12,410-event set as the Bug 13 placebo). **PASS for each if mean R
   lies within 2 SE (plain) of minus the expected cost in R**, per trade
   −(2 × 2.43 bps) / stop distance in bps. Long-minus-short reported as
   descriptive. If either fails: stop and report; nothing else changes.

## Disclosed correction run (only if both placebos pass)

1. Risk scales recalibrated on TRAINING with the fixed engine, same 5% maxDD
   rule (`calibrate_risk.py`, mechanical), for A, B (t+5, t+15) and C1, fixed
   and Kelly; keyword, LLM (anonymised) and rung 1b (MiniLM). Recorded in
   `outputs/risk_calibration_<rung>_bug14fix_2026-10-24.csv`.
2. One run per rung over training + test with the frozen command otherwise
   unchanged (designed governor; deflated Sharpe at N = 139 for keyword and
   LLM, N = 155 for rung 1b; same Jobson-Korkie-Memmel Sharpe difference vs
   momentum). Holm for Kelly vs fixed: the H2b family of 8 (keyword + LLM ×
   A, B t+5, B t+15, C1), rung 1b as its own family of 4. Each run logged in
   `outputs/test_period_runs.csv`. **This note covers C1's test run.**
3. The engine also carries the Bug 12 (deterministic order) and Bug 13 (basis,
   irrelevant to C1) fixes. The 18 October A, B and C rows stay in the record,
   marked SUPERSEDED (A, B: Bug 14 correction) or INVALID (C: Bug 13).
4. Then descriptive items 1(b) and 2 on the corrected runs.
