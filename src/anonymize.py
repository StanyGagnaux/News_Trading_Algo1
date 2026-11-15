"""
Glasserman-Lin headline anonymization for LLM scoring.

Masks the scored company's names and ticker so the model cannot recall how
that particular stock moved after a historical headline (look-ahead through
training-data memory). Only the company being scored is masked; other
companies in the headline stay visible.

Names come from data_sources/company_names.csv (ticker, aliases separated by
'|'). Matching is case-sensitive with word boundaries, longest alias first,
and swallows a trailing legal suffix ("Apple Inc." -> "the company").
"""
from __future__ import annotations
import csv
import re

MASK = "the company"
# Bare ticker symbols that are also everyday abbreviations are not masked.
BARE_TICKER_STOPLIST = frozenset({"CA"})
_SUFFIX = r"(?:,?\s+(?:Inc|Corp|Corporation|Co|Ltd|Plc|PLC|plc|Holdings|Group|N\.V|SE|AG)\.?)?"


def load_aliases(path) -> dict[str, list[str]]:
    """{ticker: [alias, ...]} from the company-names CSV."""
    with open(path, newline="") as f:
        return {row["ticker"]: [a.strip() for a in row["aliases"].split("|") if a.strip()]
                for row in csv.DictReader(f)}


def anonymize(headline: str, ticker: str, aliases: list[str]) -> str:
    out = str(headline)
    for name in sorted(aliases, key=len, reverse=True):
        out = re.sub(rf"(?<![\w.]){re.escape(name)}{_SUFFIX}(?![\w])", MASK, out)
    if ticker and ticker not in BARE_TICKER_STOPLIST:
        out = re.sub(rf"\$?(?<![\w.]){re.escape(ticker)}(?![\w])", MASK, out)
    return out
