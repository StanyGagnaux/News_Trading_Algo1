# Skill: update the data

All files land in `data_sources/`; progress logs in `outputs/logs/`. Alpaca
keys are read from `.env` at the project root.

## News (Benzinga via Alpaca)

```bash
python3 src/fetch_historical_news.py --start 2016-01-01 --end 2026-06-01
```
Writes `data_sources/news_history.csv` (resumable). Then dedupe into
`news_history_clean.csv` (33% exact repeats removed last time).

## Intraday minute bars (Alpaca IEX)

```bash
python3 src/fetch_intraday_bars.py
python3 src/audit_intraday_coverage.py      # check entry coverage (~91% in RTH)
```

## Daily prices (Bloomberg)

Export at the Bloomberg terminal, then:
```bash
python3 src/bloomberg_to_csv.py convert --xlsx <export>.xlsx
python3 src/bloomberg_to_csv.py audit --prices data_sources/prices.csv --news data_sources/news_history.csv
```
Open gap: refresh `wb6_prices_D.xlsx` for the 20 tickers with news but no
prices; news ends 2026-06-01 while prices run to 2026-07-14.

## After any data update

- Re-run `skills/quality_check.md`, then the backtests (`skills/run_backtest.md`).
- New news headlines need scoring before the LLM arm covers them
  (`skills/score_news.md`).
- Record what changed and when in `context/changelog.md`.
- Bloomberg data must never be redistributed or committed.
