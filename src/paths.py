"""Project locations, resolved from this file so every script runs the same
from any working directory. Change a location here, once."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data_sources"
OUTPUTS = ROOT / "outputs"
LOGS = OUTPUTS / "logs"

PRICES = DATA / "prices.csv"
NEWS_RAW = DATA / "news_history.csv"
NEWS_CLEAN = DATA / "news_history_clean.csv"
BARS = DATA / "bars_intraday.csv"
TICKERS = DATA / "nasdaq100.txt"
LLM_SCORES = DATA / "news_scored_llm_ollama.csv"
LLM_CACHE = DATA / "llm_score_cache.json"
CONTEXT_TABLE = DATA / "context_table.csv"
COMPANY_NAMES = DATA / "company_names.csv"
