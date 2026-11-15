#!/bin/bash
# score_two_models.sh -- unattended model comparison for the thesis:
# scores the TRAINING period (default; test period excluded) with each Ollama
# model in turn, anonymized, Ollama only (no Google/Groq fallback, so every
# score comes from the named model). Fastest model first.
#
# Each model has its own cache namespace and output file:
#   llama3.2:3b  -> data_sources/news_scored_llm_ollama_anon.csv
#   qwen3.8:27b  -> data_sources/news_scored_llm_ollama-qwen3.8-27b_anon.csv
# Failed headlines are not cached, so each pass resumes where the last ended.
# Before each pass it waits (up to 24h) for the server to answer; the scorer
# stops a pass after 20 errors in a row. A model is finished when nothing is
# left, or after 2 passes in a row that made no progress.
#
# USAGE (from the project root):  caffeinate -i bash src/score_two_models.sh
cd "$(dirname "$0")/.." || exit 1
LOG="outputs/logs/score_two_models_$(date +%F).log"
MAX_PASSES=30
PAUSE_SEC=120
WAIT_MAX_SEC=86400          # give up if the server stays unreachable for 24h
OLLAMA_URL=$(grep '^OLLAMA_BASE_URL=' .env | cut -d= -f2- | tr -d "\"'" | sed -E 's#/v1/?$##')

wait_for_server() {         # poll every minute until Ollama answers
  local waited=0
  until curl -s -m 10 -o /dev/null "$OLLAMA_URL/api/tags"; do
    if [ $waited -eq 0 ]; then echo "=== $(date '+%F %T') server unreachable, waiting ===" | tee -a "$LOG"; fi
    if [ $waited -ge $WAIT_MAX_SEC ]; then
      echo "=== $(date '+%F %T') server down for 24h, giving up ===" | tee -a "$LOG"; exit 1
    fi
    sleep 60; waited=$((waited + 60))
  done
  if [ $waited -gt 0 ]; then echo "=== $(date '+%F %T') server back after ${waited}s ===" | tee -a "$LOG"; fi
}

for MODEL in "llama3.2:3b" "qwen3.8:27b"; do
  prev=-1; stuck=0
  for pass in $(seq 1 $MAX_PASSES); do
    wait_for_server
    echo "=== $(date '+%F %T') $MODEL pass $pass ===" | tee -a "$LOG"
    PASS_LOG=$(mktemp)
    echo y | python3 -u src/score_news_llm.py --providers ollama \
        --ollama-model "$MODEL" 2>&1 | tee -a "$LOG" > "$PASS_LOG"
    left=$(grep -o '[0-9,]* need scoring' "$PASS_LOG" | head -1 | tr -dc '0-9')
    rm -f "$PASS_LOG"
    echo "=== $(date '+%F %T') $MODEL pass $pass: ${left:-?} needed scoring at start ===" | tee -a "$LOG"
    if [ "${left:-1}" = "0" ]; then break; fi
    if [ "$left" = "$prev" ]; then stuck=$((stuck + 1)); else stuck=0; fi
    if [ $stuck -ge 2 ]; then
      echo "=== $MODEL: no progress in 2 passes, moving on ===" | tee -a "$LOG"; break
    fi
    prev=$left
    sleep $PAUSE_SEC
  done
done
echo "=== $(date '+%F %T') ALL DONE ===" | tee -a "$LOG"
