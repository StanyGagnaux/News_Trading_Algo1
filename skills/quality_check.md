# Skill: quality check (run after every code change and every result)

## After any code change

```bash
python3 tests/test_portfolio_fixes.py     # must end "ALL N CHECKS PASSED"
python3 tests/test_freshness_guard.py     # must end "All cases behaved as expected."
```

Add a test with a hand-calculated answer for every new feature or fix (see
the existing scale-out, D and N checks). A change to defaults must reproduce
earlier results exactly: compare the output CSV with the previous one
(`shasum`), not by eye.

## Before believing a result (Hard Rule 5: too good → hunt the bug)

- **Trade counts plausible?** Compare with the number of signals available.
  Unexpected jumps found bugs 6 and 8.
- **Look-ahead:** any new time-touching code needs a runtime assertion that
  entry happens strictly after the information it uses.
- **Out-of-sample beats in-sample?** Possible, but check year by year, the
  long/short split and the trade count first.
- **Annualisation:** equity curves must have one point per trading day.
- **LLM OOS:** meaningless until Bug 1 is fixed.
- **Costs:** results are net of costs; a strategy that is ~breakeven before
  costs will look like a loss of about one round trip per trade.
- **Overfitting:** report how many variants were tried, not just the best one.

## Before sharing results

- Update `context/results.md` (numbers + caveats) and `context/changelog.md`.
- Never include `data_sources/`, `.env` or `ALPACA_KEY.py` in anything shared.
