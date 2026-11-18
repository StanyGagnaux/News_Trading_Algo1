# Sensitivity analysis — 20% drawdown target, dated 25 October 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Written 2026-10-25 BEFORE any code change or run, by decision of the author.

**This is a DESCRIPTIVE sensitivity analysis added after the results. The
official results remain those at the 5% drawdown target.** Purpose: show
returns and drawdowns at a realistic risk level.

## Design (mechanical scaling of the 5% procedure by x4)

1. **Risk scales recalibrated on TRAINING** to a maximum drawdown of about
   20% (`calibrate_risk.py`, same proportional search; tolerance and maximum
   scale scaled with the target: ±1.0 pp, max scale 8.0 — the 5% values ±0.25 pp
   and 2.0 are unchanged): all rungs (keyword, Llama, MiniLM, Haiku, Sonnet),
   strategies A, B (t+5, t+15) and minute-bar C, fixed and Kelly.
   **Continuous momentum** scaled to a 20% training drawdown the same way.
2. **Drawdown governor scaled proportionally:** full size below 12%, linear
   taper 12% -> 20%, probe size (5% floor, 60-day peak half-life, unchanged)
   beyond. Single-position (20% of equity), gross-exposure (100%) and
   concurrent-risk (4%) caps **unchanged**.
3. **One test-period run per configuration** (rung x target). The 5% runs are
   repeated with an added cap-binding counter to measure cap binding at 5%;
   they must reproduce the existing 5% results exactly (A/B: Bug 14
   correction; C: minute-bar runs) or the comparison is not reported.
   Reported side by side at 5% and 20%: test return p.a., Sharpe, maximum
   drawdown, **share of test days on which an exposure cap binds** (A: an
   entry clipped by the position cap or skipped by the gross cap; B/C: an
   entry skipped or scaled down by the concurrent-risk cap), and the
   Jobson-Korkie-Memmel Sharpe difference vs continuous momentum (scaled
   momentum at 20%; the test is scale-invariant) with its p-value.
4. Whether Sharpe ratios stay close to the 5% values is checked, and material
   differences are explained (caps, governor, signal ordering).

Runs are sequential and **paused Mon 26 and Tue 27 Oct 14:00–21:30
Europe/Zurich** so they cannot affect the shadow run. Code changes are
additive: options `--target-dd`, `--dd-cap`, `--dd-throttle-start` (defaults
unchanged) and cap-day counters that do not alter any trade.

| file | SHA-256 before |
|---|---|
| `src/calibrate_risk.py` | `e1b685822d28aa464080837190f74d91ed566eefc655a5682b66e3f948cc2758` |
| `src/run_both_strategies.py` | `157172117704a729577ab7aced419fa984b736ee7a59e7f0c2b890382dd6a22a` |
| `src/newsdrift/backtest.py` | `833b85dddaacb6844458a2128970c5ef3b2d1768448cb8710d4ef73f4dfe09ae` |
| `src/newsdrift/portfolio.py` | `4ee88b1087dfab774473bd554314665b2afa25dbfa510bb6745e33f71cc2c4c1` |
| `src/newsdrift/intraday.py` | `39ca652ce84839d9d54411109fca404aff09b10938de02a1238cd75ee5d43876` |
| `src/newsdrift/strategy_c.py` | `dac8cfa7a1a18c9f57f53d976d1538638f29b3092df5934bee5b64130977dd96` |
