# Skill: score news with an LLM

Script: `src/score_news_llm.py`. Output: `data_sources/news_scored_llm_<provider>.csv`.
Cache: `data_sources/llm_score_cache.json` (never delete it: it saves up to
~42h of re-scoring; scores are keyed by headline hash, so a changed PROMPT
needs its old cache entries purged first).

## Order of operations (always)

1. **Estimate (free):** `python3 src/score_news_llm.py --estimate --providers <p>`
2. **Pilot (200 headlines):** `python3 src/score_news_llm.py --pilot 200 --providers <p>`
   Check the pilot report: strength std dev (keyword baseline 0.238), %
   neutral (should be well above 0), duration spread, and spot-check sample
   scores for direction errors.
3. **Full run, train period only** (default excludes the test period).
4. **Test period, ONCE**, only after the final configuration is written down
   and dated: add `--include-test-period`. Report the result whatever it is.

## Providers

- `ollama`: local llama3.2:3b on the LAN machine (`OLLAMA_BASE_URL`), free,
  ~1.6 s/headline. Both machines must stay awake (`caffeinate -i -w <pid>`
  here; disable sleep there). Full run ≈ 18h of uptime.
- `google`: Gemini Flash-Lite, 500 free requests/day, then falls back.
- `groq`: gpt-oss-20b, cheap, fast.
- Arms: `--agents` (macro vs company specialist prompt), `--with-context`
  (needs `context_table.csv`, currently missing).

## Comparing Ollama models

`--ollama-model <name>` (e.g. `qwen3.8:27b`) scores with another Ollama model
in its own cache namespace and output file. `bash src/score_two_models.sh`
runs 3B then 27B unattended (wrap in `caffeinate -i`).

## Background runs

Full runs ask for a y/N confirmation; in the background pipe it:
`echo y | python3 src/score_news_llm.py ...`. Progress prints are buffered —
check progress by counting cache entries for the provider prefix instead.

## Anonymization (on by default)

The scored company's names and ticker are replaced by "the company"
(`src/anonymize.py`, names in `data_sources/company_names.csv`). Anonymized
scores use their own cache namespace and are written to
`news_scored_llm_<provider>_anon.csv`; point backtests at that file with
`--llm-scores`. `--no-anonymize` reproduces the old (unmasked) behaviour.
After editing `company_names.csv`, run `python3 tests/test_anonymize.py`.

## Before the final scoring run (open items, `context/bugs.md`)

- Pick the model with a pilot comparison (a stronger model than the 3B is the
  obvious first test).
- Review the 3 rows marked CHECK in `company_names.csv`.
- Decide the watchlist path behaviour of the Tier-0 filter.

Typical next Ollama run (train period, anonymized, resumable):
`echo y | python3 src/score_news_llm.py --providers ollama` → then
`python3 src/run_both_strategies.py --llm-scores data_sources/news_scored_llm_ollama_anon.csv`.
