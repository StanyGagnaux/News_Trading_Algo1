# Known limitation — no point-in-time index membership, dated 24 October 2026

Status: **FINAL** (read-only; SHA-256 in `outputs/FROZEN_CONFIG_hashes_notes_2026-10-19.txt`).
Recorded by decision of the author; no further work on it.

- The universe (`data_sources/nasdaq100.txt`) is a static list of the 193
  tickers that were Nasdaq-100 members at any time 2015–2026, with no dates.
- Signals, trades (all strategies) and event-study events are NOT restricted
  to the periods in which each ticker was actually an index member: a company
  that joined later is included before it joined, one that left is included
  after it left.
- Direction of the bias: firms that joined were selected because they grew,
  so pre-inclusion periods carry look-ahead in favour of rising stocks; the
  bias favours longs (strategies are ~65% long; event-study signs are mixed).
- No membership history is available in the project (no `MEMBERS_YYYY`
  export from Bloomberg), so the number of events outside membership periods
  is unknown.
- Reported as a limitation of all results; the official results are not changed.
