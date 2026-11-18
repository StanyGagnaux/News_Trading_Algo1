# Decision note — paper trading cancelled (30 October 2026)

Record of a decision taken by the author on 30 October 2026, written the same
day. Read-only: no code, data or result was changed. Supersedes item 6e of the
decisions note of 24 October 2026 (`…note_ladder_decisions_2026-10-24.md`).

## Decision

Paper trading — planned for Wednesday 28 October to Friday 6 November 2026 on
the paper endpoint only, after explicit approval — is **cancelled**. It was
never started: approval was never given, no paper endpoint was connected, and
**no order was placed at any time**.

## What exists and what does not (checked 30 Oct 2026)

- **Order code: none.** `src/live_pipeline.py` is shadow-mode only and contains
  no order, fill or broker code (by design, see its header). `src/raw_news_pusher.py`
  forwards headlines to Telegram and places no orders.
- **Paper-trading data: none.** No order, fill, position, latency-to-fill or
  slippage record exists in `outputs/`, `data_sources/` or the logs of any copy
  of the project.
- **Shadow run of 26–27 October (item 6c): no data either.** The scheduled
  process (PID 34811, started 24 Oct 13:48 UTC) logged the 26 Oct session as
  closed at 2026-10-30 03:46 UTC with 0 news ids and 0 revisions and skipped
  27 Oct; `outputs/live/` is empty; the LLM cache was re-saved unchanged
  (61,288 `ollama_anon_` entries before and after). Evidence and diagnosis in
  `outputs/parity_report_2026-10-30.md`.
- **Parity test (item 6d): not performable** — there is no live side to
  compare. Not run.

## Consequences for the thesis

- Latency is measured only from headline to score (off-line, 25 Oct: Llama 3.2
  3B median 1.57 s, Sonnet 5.5 median 0.98 s). Latency from publication to
  order and to fill, and slippage against the mid at receipt, are **not
  measured**; the speed clause of SQ4 reads accordingly.
- Sections affected in the thesis: Table 3.1
  execution row, 3.1.2, 3.8 (now "The live signal layer"), register 3.7,
  Tables 4.1 and 4.7, 5.1, 5.12, 5.13 ("Live parity"), Table 5.16. The parity
  placeholders are to be filled from `parity_report_2026-10-30.md`.
- The hard rule "signals only — no live money" was never at risk: nothing
  beyond signals was ever connected.
- The analysis freeze stands: no re-run of the shadow run, no new fetch, no
  further analyses, models or news sources.
