"""
score_news_llm.py -- score historical headlines with an LLM.

COST CONTROL IS THE POINT OF THIS SCRIPT. Four mechanisms:

 1. DEDUPE + PERMANENT CACHE. The LLM is stateless -- it will happily score
    the same headline 50 times and charge you 50 times. Deduplication is a
    PIPELINE job, not something the model does for itself. Every score is
    written to llm_score_cache.json keyed by a hash of the headline text, so
    a headline is never paid for twice, even across separate runs, crashes
    or re-runs.

 2. TIER-0 FILTER. A free regex gate drops routine headlines before any API
    call (analyst-note filler, "shares rise 2%", listicles). Typically kills
    60-90% of volume at zero cost.

 3. DRY RUN. --estimate makes NO API calls: it runs the filter, counts what
    would be scored, and prints the projected cost so you approve the spend
    before it happens.

 4. PILOT MODE. --pilot N scores only N headlines, reports the ACTUAL cost
    and shows the scores so you can judge quality before committing.

 Plus: --providers takes an ORDERED CASCADE (free-tier friendly) -- score
 with providers[0] until it hits a rate limit, then fall over to the next
 one for the rest of the run. The test period is refused by default so the
 out-of-sample set stays unscored until the final frozen run.

PROVIDERS (prices verified Aug 2026 -- re-check before a big run):
  ollama -- Llama 3.2 3B on the user's own local machine (LAN), $0, no
            rate limit. DEFAULT PRIMARY. Small model -- verify quality via
            --pilot before trusting it for the full run.
  google -- Gemini 2.5 Flash-Lite, $0.10/$0.40 per MTok, free-tier eligible.
  groq   -- gpt-oss-20b on Groq's own chips, $0.075/$0.30 per MTok.
(Claude/Anthropic and xAI/Grok support were removed -- no working keys for
those at the moment. NVIDIA NIM was tried and dropped Aug 2026 -- eval-tier
rate limits and multi-minute latency made it unusable at pipeline scale.
Re-adding any provider is a small, self-contained change: one PROVIDERS
entry + one _call_<provider> function.)

USAGE (from the project root):
  # 1. free estimate, no API calls
  python3 src/score_news_llm.py --estimate

  # 2. small paid pilot -- check quality and real cost
  python3 src/score_news_llm.py --pilot 200

  # 3. full run, cascading from google to groq on rate limits
  python3 src/score_news_llm.py --providers google groq

OUTPUT: data_sources/news_scored_llm_<provider>.csv with [timestamp, ticker,
headline, strength, duration, importance] -- drop-in replacement for the
keyword scorer. Cache: data_sources/llm_score_cache.json.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import sys
import time

import numpy as np
import pandas as pd
from dotenv import load_dotenv

from splits import backtest_train_end
from paths import DATA, PRICES, NEWS_CLEAN, LLM_CACHE, CONTEXT_TABLE, COMPANY_NAMES
from anonymize import anonymize, load_aliases, MASK

load_dotenv()  # picks up GROQ_API_KEY / GOOGLE_API_KEY from .env automatically

# ----------------------------------------------------------------- pricing
PROVIDERS = {
    "google": {
        # Google AI Studio / Gemini Developer API. Flash-Lite is the
        # cheapest tier and free-tier eligible. gemini-2.5-flash-lite is
        # deprecated for new API keys (confirmed via live 404) -- use 3.5.
        "model": "gemini-3.5-flash-lite",
        "price_in_per_mtok": 0.30,
        "price_out_per_mtok": 2.50,
        "api_key_env": "GOOGLE_API_KEY",
        "supports_batch": False,
        "pricing_note": "Gemini 3.5 Flash-Lite: $0.30/$2.50 per MTok, "
                        "free-tier eligible (ai.google.dev)",
    },
    "groq": {
        # Groq (groq.com) -- NOT xAI's Grok. Serves open models on their own
        # LPU chips via the standard OpenAI Chat Completions endpoint.
        # gpt-oss-20b IS a reasoning model -- reasoning_effort="low" plus a
        # generous max_tokens (see _call_groq) keeps it from burning its
        # budget on hidden chain-of-thought before reaching the JSON answer
        # (gpt-oss-120b at max_tokens=150 did exactly that: empty output).
        "model": "openai/gpt-oss-20b",
        "price_in_per_mtok": 0.075,
        "price_out_per_mtok": 0.30,
        "api_key_env": "GROQ_API_KEY",
        "supports_batch": False,         # no confirmed Groq batch discount
        "pricing_note": "GPT-OSS 20B via Groq: $0.075/$0.30 per MTok (groq.com)",
    },
    "ollama": {
        # Local Ollama instance on the user's own hardware (LAN), reached via
        # Ollama's OpenAI-compatible endpoint. $0 real cost -- no API billing,
        # no rate limit beyond the host machine's own throughput. api_key is
        # a required-but-unchecked placeholder for the OpenAI client.
        # NVIDIA NIM (deepseek-v4-pro / deepseek-v4-flash) was tried first and
        # dropped Aug 2026: pro hit a hard rate-limit cooldown with no
        # confirmed reset time, flash worked but took 3.5-15+ min per call
        # before a 504 -- neither is viable at pipeline scale.
        "model": "llama3.2:3b",
        "price_in_per_mtok": 0.0,
        "price_out_per_mtok": 0.0,
        "api_key_env": None,   # no real key -- OLLAMA_BASE_URL instead
        "base_url_env": "OLLAMA_BASE_URL",
        "supports_batch": False,
        "pricing_note": "Llama 3.2 3B via local Ollama -- $0, runs on the "
                        "user's own hardware over LAN",
    },
}
MAX_CONSECUTIVE_ERRORS = 20    # then assume the provider is down and stop
EST_INPUT_TOKENS = 190          # prompt + headline, measured empirically
EST_OUTPUT_TOKENS = 75          # the JSON reply

CACHE_FILE = str(LLM_CACHE)
OUT_FILE = str(DATA / "news_scored_llm.csv")

# ------------------------------------------------------------ Tier-0 gate
WATCHLIST: set = set()
if os.path.exists("nasdaq100.txt"):
    WATCHLIST = {t.strip().upper() for t in open("nasdaq100.txt") if t.strip()}

# --- recurring TEMPLATE noise -------------------------------------------
# These are wire boilerplate that repeats hundreds of times with only a date
# or number changing. They contain trigger words ("earnings", "upgrades") so
# a naive keyword filter lets them through and you pay for every repeat.
# Measured on the real archive: ~2,300 such headlines survived the old gate.
TEMPLATE_NOISE = re.compile(
    r"earnings scheduled for|"
    r"\bstocks? to watch\b|"
    r"top (ratings )?upgrades?[ /&]*(and )?downgrades?|"
    r"trending stocks on wallstreetbets|"
    r"if you invested|invested \$?[\d,]+ in this stock|"
    r"\bbiggest movers\b|moving news for|"
    r"option alert recap|fast money (picks|halftime)|"
    r"(top|worst) performing industries|"
    r"morning memo|stocks moving in .{0,20}(pre|post).session|"
    r"\bmarket wrap\b|\bmid.?day (movers|report)\b|"
    r"benzinga'?s? (top|daily|weekly)|"
    r"\bwatchlist\b|\bmovers?:? (up|down)\b",
    re.IGNORECASE)


def normalize_template(h: str) -> str:
    """Collapse a headline to its TEMPLATE by stripping the parts that vary
    (numbers, dates, weekdays, quarters). Two headlines with the same
    template are the same recurring story shape -- score one, reuse it."""
    h = str(h).lower()
    h = re.sub(r"\d+[\d,\.]*%?", "#", h)
    h = re.sub(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\b",
               "MON", h)
    h = re.sub(r"\b(mon|tues|wednes|thurs|fri|satur|sun)day\b", "DAY", h)
    h = re.sub(r"\b(q[1-4]|fy|h[12])\b", "PER", h)
    h = re.sub(r"[^a-z# ]", " ", h)
    return re.sub(r"\s+", " ", h).strip()


SKIP_PATTERNS = re.compile(
    r"^\d+\s|\bstocks? to (watch|buy)\b|\btop \d+\b|\bwhat to know\b|"
    r"\bthings to know\b|\bmarket wrap\b|\bpremarket movers\b|"
    r"\b(gainers|losers) of\b|\bdividend stocks\b|\bhere's why\b|"
    r"\bshares? (are )?(up|down|rise|fall|gain|drop)s? \d+", re.IGNORECASE)

KEEP_PATTERNS = re.compile(
    r"\bearnings\b|\bguidance\b|\bupgrade[sd]?\b|\bdowngrade[sd]?\b|"
    r"\bacquir\w*|\bmerger\b|\bbuyout\b|\bprobe\b|\blawsuit\b|\bsettle\w*|"
    r"\brecall\b|\bhalt\w*|\bbankrupt\w*|\blayoff\w*|\bcontract\b|"
    r"\bapprov\w*|\breject\w*|\btariff\w*|\bsanction\w*|\bban\b|"
    r"\bfda\b|\btrial results\b|\bpatent\b|\bceo\b|\bresign\w*|"
    r"\bfomc\b|\bfed\b|\bcpi\b|\binflation\b|\brate (cut|hike|decision)\b|"
    r"\btrump\b|\bpowell\b|\bwarn\w*|\bbeat[s]?\b|\bmiss(es|ed)?\b|"
    r"\bsurge[sd]?\b|\bplunge[sd]?\b|\bsoar[sd]?\b|\brecord\b|\bstake\b",
    re.IGNORECASE)


def tier0_keep(headline: str, ticker: str) -> bool:
    """Free filter. True = worth spending a token on."""
    if len(headline) < 20:
        return False
    if SKIP_PATTERNS.search(headline):
        return False
    if TEMPLATE_NOISE.search(headline):      # recurring wire boilerplate
        return False
    if not KEEP_PATTERNS.search(headline):
        return False
    if WATCHLIST and ticker.upper() not in WATCHLIST:
        return False
    return True


# ------------------------------------------------------------------ prompt
PROMPT = """You are the signal module of a systematic trading system.
Score this financial news headline.

Headline: "{headline}"
Company ticker: {ticker}

Respond ONLY with JSON, no other text:
{{"strength": float in [-1,1] -- sign is the expected direction of the
   stock's DRIFT over the NEXT 1-3 TRADING DAYS, AFTER the initial market
   reaction has already happened. Magnitude is your confidence times the
   economic materiality. Use values across the full range, not just -1/0/1.
   Use 0.0 if the headline is not materially informative for price.
 "duration": 1, 2 or 3 -- trading days you expect the drift to persist,
 "importance": 1-10 -- how market-moving (10 = FOMC shock, presidential
   action on this company; 5 = normal single-stock news; 1-2 = noise)}}"""


PROMPT_WITH_CONTEXT = """You are the signal module of a systematic trading system.
Score this financial news headline.

Headline: "{headline}"
Company ticker: {ticker}

Historical context (computed ONLY from events before this headline's date):
{context}

Use the context as a prior, not as an answer -- a company whose news usually
drifts up does not make this particular headline bullish. Weigh the
headline's own content first.

Respond ONLY with JSON, no other text:
{{"strength": float in [-1,1] -- sign is the expected direction of the
   stock's DRIFT over the NEXT 1-3 TRADING DAYS, AFTER the initial reaction.
   Magnitude is confidence times materiality. Use the full range.
 "duration": 1, 2 or 3,
 "importance": 1-10}}"""



# ============================ SPECIALIST ROUTING ============================
# Two agents, ONE call per headline -- the router picks which prompt to use,
# so this costs the same as the single-agent arm. The two agents reason
# differently because macro and single-stock news transmit to price through
# different mechanisms:
#   MACRO/POLICY  -> transmission is via rates, risk appetite, sector beta
#                    and second-order effects. The headline is rarely ABOUT
#                    the ticker; the question is how it propagates TO it.
#   COMPANY       -> transmission is via revised expectations for that firm.
#                    The question is whether the news changes the earnings
#                    path and how much of it the market has already priced.
MACRO_ROUTER = re.compile(
    r"\bfomc\b|\bfed(eral reserve)?\b|\bpowell\b|\becb\b|\bboj\b|"
    r"\bcpi\b|\bppi\b|\binflation\b|\bpayrolls?\b|\bnonfarm\b|\bgdp\b|"
    r"\bunemployment\b|\bjobless\b|\brate (cut|hike|decision|hold)\b|"
    r"\byield curve\b|\btreasur\w+|\brecession\b|\bstagflation\b|"
    r"\btrump\b|\bbiden\b|\bwhite house\b|\bcongress\b|\bsenate\b|"
    r"\btariff\w*|\bsanction\w*|\btrade war\b|\bexport (ban|control)|"
    r"\bopec\b|\bgeopolit\w*|\bwar\b|\belection\b|"
    r"\bantitrust\b|\bftc\b|\bdoj\b|\bregulat\w+ crackdown",
    re.IGNORECASE)


def route(headline: str) -> str:
    return "macro" if MACRO_ROUTER.search(str(headline)) else "company"


PROMPT_MACRO = """You are the MACRO & POLICY analyst of a systematic trading
desk. You specialise in how economy-wide and political events transmit into
the price of an individual stock.

Headline: "{headline}"
Stock you must score: {ticker}
{context}
Reason in this order before answering:
1. WHAT CHANGED at the macro level -- rates, growth, inflation, trade policy,
   geopolitical risk, regulatory regime? Distinguish a concrete ACTION
   (a rate decision, a signed tariff, a released statistic) from mere TALK
   (a speech, a proposal, an opinion). Talk moves prices far less.
2. SURPRISE vs EXPECTATION -- markets price the expected. A rate cut that
   everyone anticipated is not bullish news. Only the surprise component
   moves prices.
3. TRANSMISSION TO THIS STOCK -- how does this reach {ticker} specifically?
   Consider: rate sensitivity (long-duration growth names fall when yields
   rise), sector exposure (tariffs hit importers and hardware supply chains),
   revenue geography, and whether the firm is a beneficiary or a victim.
   A macro event can be bullish for the index and bearish for this name.
4. SECOND-ORDER EFFECTS -- a weak jobs number can be equity-POSITIVE if the
   market reads it as rate-cut fuel. State the regime logic you are applying.
5. PERSISTENCE -- scheduled macro releases are absorbed fast because everyone
   was watching. Policy shifts with implementation lags drift longer.

Respond ONLY with JSON, no other text:
{{"strength": float in [-1,1] -- expected direction of {ticker}'s DRIFT over
   the NEXT 1-3 TRADING DAYS, AFTER the initial reaction. Magnitude =
   confidence x materiality. 0.0 for talk without action, or if already
   priced. Use the full range.
 "duration": 1, 2 or 3 trading days,
 "importance": 1-10 (10 = FOMC shock, war, sweeping tariffs; 5 = notable
   data print; 1-2 = routine commentary)}}"""


PROMPT_COMPANY = """You are the SINGLE-STOCK analyst of a systematic trading
desk. You specialise in how firm-specific news changes the expected earnings
path of one company.

Headline: "{headline}"
Stock you must score: {ticker}
{context}
Reason in this order before answering:
1. WHAT CHANGED for the business -- revenue, margins, growth, competitive
   position, capital structure, management, legal or regulatory exposure?
   Distinguish a HARD FACT (reported earnings, a signed contract, an FDA
   decision, a completed acquisition) from an OPINION (an analyst note, a
   price-target change, a columnist's view) -- but do not assume opinions
   are automatically weak. Analyst rating changes are a documented source of
   real price drift: weigh the SIZE of the rating change (Sell-to-Buy is a
   far bigger revision than Hold-to-Buy), the size and direction of any
   price-target revision, and the prominence of the analyst or bank. A
   large, surprising rating change from a major bank can carry real
   multi-day drift; a minor target tweak from an obscure shop usually does
   not.
2. VERSUS EXPECTATIONS -- a company can grow revenue 20% and fall if 25% was
   expected. Score the surprise, not the level.
3. MATERIALITY TO THE WHOLE FIRM -- a contract worth 0.1% of revenue is
   noise. Weigh the news against the size of the business.
4. ALREADY PRICED? -- pre-announced events, recycled stories, and news that
   merely confirms a known trend produce little drift. Score those near 0.
5. ASYMMETRY & PERSISTENCE -- bad news historically drifts longer than good
   news, as institutions exit positions gradually. Guidance cuts and legal
   problems tend to persist. For analyst rating changes specifically,
   persistence scales with the SIZE of the revision and how lightly-covered
   the stock is: a large upgrade on a thinly-covered name can drift for
   several days, while a routine target tweak on a heavily-covered mega-cap
   is usually absorbed the same day.

Respond ONLY with JSON, no other text:
{{"strength": float in [-1,1] -- expected direction of {ticker}'s DRIFT over
   the NEXT 1-3 TRADING DAYS, AFTER the initial reaction. Magnitude =
   confidence x materiality -- judge analyst opinions on their own content
   (size of rating change, size of target revision, analyst prominence)
   rather than discounting them by category. 0.0 for recycled news or
   immaterial items only. Use the full range.
 "duration": 1, 2 or 3 trading days,
 "importance": 1-10 (10 = presidential action on this firm, bankruptcy,
   mega-merger; 7-8 = major earnings surprise, big M&A; 5 = normal
   single-stock news; 1-2 = routine coverage)}}"""


def headline_key(headline: str) -> str:
    return hashlib.sha1(headline.strip().lower().encode()).hexdigest()[:20]


def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except Exception:
            print("[warn] cache unreadable, starting fresh")
    return {}


def save_cache(cache: dict):
    tmp = CACHE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cache, f)
    os.replace(tmp, CACHE_FILE)


def parse_reply(text: str) -> dict | None:
    try:
        raw = text[text.find("{"): text.rfind("}") + 1]
        o = json.loads(raw)
        return {
            "strength": round(max(-1.0, min(1.0, float(o["strength"]))), 3),
            "duration": int(max(1, min(3, int(o["duration"])))),
            "importance": int(max(1, min(10, int(o["importance"])))),
        }
    except Exception:
        return None


def money(x: float) -> str:
    return f"${x:,.2f}"


def cost_of(n: int, provider: str) -> float:
    p = PROVIDERS[provider]
    cin = n * EST_INPUT_TOKENS / 1e6 * p["price_in_per_mtok"]
    cout = n * EST_OUTPUT_TOKENS / 1e6 * p["price_out_per_mtok"]
    return cin + cout


def _is_rate_limited(exc: Exception) -> bool:
    """Provider-agnostic 429 sniff -- openai-python and google-genai raise
    different exception types, so match on the common signals instead of
    pinning to either library's exact class name."""
    if getattr(exc, "status_code", None) == 429:
        return True
    if str(getattr(exc, "code", "")) == "429":
        return True
    s = str(exc).lower()
    return ("429" in s or "rate limit" in s or "resource_exhausted" in s
            or "quota" in s)


def _extract_retry_delay(exc: Exception, default: float = 5.0) -> float:
    """Best-effort parse of the provider's suggested retry delay from a
    429 error message (e.g. "Please retry in 22.97s"); falls back to a
    fixed default when the message doesn't include one."""
    m = re.search(r"retry in ([\d.]+)s", str(exc))
    return float(m.group(1)) + 0.5 if m else default


# Proactive pacing: Gemini free tier caps at 15 requests/MINUTE (separate
# from, and far tighter than, its 500/day cap) -- discovered the hard way
# when a run with no pacing burned 866 429s and only converted ~6% of its
# Google attempts into actual scores. Groq hasn't shown this problem at the
# volumes tested, so it's left unthrottled.
MIN_INTERVAL_SEC = {"google": 4.5, "groq": 0.0, "ollama": 0.0}
MAX_RETRIES_PER_HEADLINE = 3


# -------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--news", default=str(NEWS_CLEAN))
    ap.add_argument("--prices", default=str(PRICES))
    ap.add_argument("--train-frac", type=float, default=0.80)
    ap.add_argument("--start", default="2016-01-01",
                    help="backtest calendar start (for the train/test split)")
    ap.add_argument("--end", default="2026-06-01",
                    help="backtest calendar end (for the train/test split)")
    ap.add_argument("--estimate", action="store_true",
                    help="dry run: no API calls, just the projected cost")
    ap.add_argument("--pilot", type=int, default=0,
                    help="score only N headlines, report actual cost")
    ap.add_argument("--include-test-period", action="store_true",
                    help="DANGER: scores the out-of-sample set too")
    ap.add_argument("--agents", action="store_true",
                    help="specialist routing: macro agent vs company agent "
                         "(same cost, one call per headline)")
    ap.add_argument("--with-context", action="store_true",
                    help="inject point-in-time track record into the prompt "
                         "(needs context_table.csv from outcome_feedback.py)")
    ap.add_argument("--context-file", default=str(CONTEXT_TABLE))
    ap.add_argument("--no-anonymize", action="store_true",
                    help="send the raw headline and ticker (pre-Oct-2026 "
                         "behaviour). Default masks the scored company's "
                         "names + ticker (Glasserman-Lin), see src/anonymize.py")
    ap.add_argument("--ollama-model", default=None,
                    help="Ollama model to use instead of the default "
                         f"{PROVIDERS['ollama']['model']}; gets its own cache "
                         "namespace and output file (ollama-<model>)")
    ap.add_argument("--max", type=int, default=0,
                    help="hard cap on headlines to score this run")
    ap.add_argument("--providers", nargs="+", choices=list(PROVIDERS),
                    default=["ollama", "google", "groq"],
                    help="cascade order: score with providers[0] until it "
                         "hits a rate limit, then fall over to the next. "
                         "Default runs on the user's local Ollama box first "
                         "(free, unlimited, but a small 3B model), then "
                         "Google's 500/day free quota, then Groq.")
    args = ap.parse_args()
    primary = args.providers[0]

    # ---------------- load and filter
    print("loading news...")
    nw = pd.read_csv(args.news, parse_dates=["timestamp"], low_memory=False)
    nw["timestamp"] = pd.to_datetime(nw["timestamp"], utc=True)
    print(f"  {len(nw):,} headline-ticker rows")

    # training end on the BACKTEST calendar (splits.py). Until 18 Oct 2026 this
    # used every price date 2015-2026 -> 2024-03-26, leaving the last month of
    # the backtest's training period unscored. News through the end of the
    # last training day (UTC) is training: B/C trade it the same day; for A
    # it enters on the first test day.
    cut = backtest_train_end(args.prices, args.news, args.start, args.end, args.train_frac)
    if not args.include_test_period:
        before = len(nw)
        nw = nw[nw.timestamp < pd.Timestamp(cut, tz="UTC") + pd.Timedelta(days=1)]
        print(f"  TEST PERIOD EXCLUDED (after {cut.date()}): "
              f"{before - len(nw):,} rows held back, {len(nw):,} remain")
        print("  (the out-of-sample set stays unscored until the frozen run)")

    # unique headlines only -- this is where dedupe saves real money
    uniq = nw.drop_duplicates(subset=["headline"]).copy()
    print(f"  {len(uniq):,} UNIQUE headlines "
          f"({1 - len(uniq)/max(len(nw),1):.1%} were repeats -- "
          f"those cost nothing)")

    uniq["keep"] = [tier0_keep(h, t) for h, t in
                    zip(uniq.headline.astype(str), uniq.ticker.astype(str))]
    kept = uniq[uniq.keep]
    print(f"  {len(kept):,} pass the free Tier-0 filter "
          f"({len(kept)/max(len(uniq),1):.1%} of unique)")

    # ---- TEMPLATE DEDUP: many headlines are the same story shape with a
    # different number/date. Score ONE representative per template and reuse
    # the score for the rest, instead of paying for each variant.
    kept = kept.copy()
    kept["template"] = kept.headline.map(normalize_template)
    n_before = len(kept)
    reps = kept.drop_duplicates(subset=["template"])
    saved = n_before - len(reps)
    if saved > 0:
        print(f"  template dedup: {n_before:,} -> {len(reps):,} "
              f"({saved:,} variants reuse a representative's score, "
              f"saving {money(cost_of(saved, primary))})")

    ctx_map = {}
    if args.with_context:
        if not os.path.exists(args.context_file):
            sys.exit(f"missing {args.context_file} -- run outcome_feedback.py")
        cdf = pd.read_csv(args.context_file, low_memory=False)
        ctx_map = dict(zip(cdf.headline.astype(str), cdf.context.astype(str)))
        print(f"  context loaded for {len(ctx_map):,} headlines "
              f"(ARM: WITH CONTEXT, ~45 extra input tokens each)")
        globals()["EST_INPUT_TOKENS"] = 235

    if args.agents:
        reps = reps.copy()
        reps["route"] = reps.headline.map(route)
        vc = reps.route.value_counts().to_dict()
        print(f"  ARM: SPECIALIST AGENTS -- routed {vc} "
              f"({vc.get('macro',0)/max(len(reps),1):.1%} to the macro agent)")

    if args.agents:
        globals()["EST_INPUT_TOKENS"] = (
            globals()["EST_INPUT_TOKENS"] + 330)   # richer specialist prompts

    cache = load_cache()
    reps = reps.copy()
    reps["key"] = reps.headline.map(headline_key)
    if args.agents:
        reps["key"] = "ag_" + reps["key"]       # separate cache namespace
    if args.with_context:
        reps["key"] = "ctx_" + reps["key"]      # separate cache namespace
    if not args.no_anonymize:
        # separate namespace: never reuse scores made from unmasked headlines
        reps["key"] = "anon_" + reps["key"]
    print(f"  anonymization: {'OFF (raw headline + ticker)' if args.no_anonymize else 'ON (company names + ticker masked)'}")
    # namespaced by the PRIMARY provider -- a headline scored via cascade
    # fallback still lands in this namespace (documented simplification,
    # the cascade is a resilience feature, not a per-headline provider log).
    reps["key"] = f"{_provider_tag(args)}_" + reps["key"]
    todo = reps[~reps.key.isin(cache)]
    print(f"  {len(cache):,} already in cache | {len(todo):,} need scoring")

    if args.max and len(todo) > args.max:
        todo = todo.head(args.max)
        print(f"  capped to {len(todo):,} by --max")

    # ---------------- cost estimate
    n = len(todo)
    print("\n" + "=" * 62)
    print("COST ESTIMATE")
    print("=" * 62)
    provider_cfg = PROVIDERS[primary]
    print(f"  providers (cascade): {' -> '.join(args.providers)}")
    print(f"  headlines to score : {n:,}")
    print(f"  model (primary)    : {provider_cfg['model']}")
    print(f"  est tokens/headline: {EST_INPUT_TOKENS} in + "
          f"{EST_OUTPUT_TOKENS} out")
    print(f"  standard API       : {money(cost_of(n, primary))}")
    if args.pilot:
        print(f"  THIS PILOT ({args.pilot}) : "
              f"{money(cost_of(min(args.pilot, n), primary))}")
    print("=" * 62)
    print(f"Prices per {provider_cfg['pricing_note']}.")

    if args.estimate:
        print("\n--estimate: no API calls made. Nothing was charged.")
        print("Next: python score_news_llm.py --pilot 200")
        return

    tmap = dict(zip(reps.template, reps.key))
    if n == 0:
        print("\nnothing to score -- everything is cached already.")
        _write_output(nw, cache, tmap, _out_name(args))
        return

    # ---------------- confirm before spending
    if args.pilot:
        todo = todo.head(args.pilot)
        print(f"\nPILOT MODE: scoring {len(todo)} headlines only.")
    else:
        est = money(cost_of(len(todo), primary))
        resp = input(f"\nScore {len(todo):,} headlines for ~{est}? [y/N] ")
        if resp.strip().lower() != "y":
            print("aborted, nothing charged.")
            return

    # ---------------- build one client per provider in the cascade
    clients, call_fns = {}, {}
    for name in args.providers:
        pcfg = PROVIDERS[name]
        if name == "google":
            key = os.environ.get(pcfg["api_key_env"], "")
            if not key:
                sys.exit(f"set {pcfg['api_key_env']} first (for --providers {name})")
            try:
                from google import genai
            except ImportError:
                sys.exit("pip install google-genai")
            clients[name] = genai.Client(api_key=key)
            call_fns[name] = _call_google
        elif name == "groq":
            key = os.environ.get(pcfg["api_key_env"], "")
            if not key:
                sys.exit(f"set {pcfg['api_key_env']} first (for --providers {name})")
            try:
                from openai import OpenAI
            except ImportError:
                sys.exit("pip install openai")
            clients[name] = OpenAI(api_key=key,
                                   base_url="https://api.groq.com/openai/v1")
            call_fns[name] = _call_groq
        else:  # ollama -- local, no real API key, just a base URL
            base_url = os.environ.get(pcfg["base_url_env"], "")
            if not base_url:
                sys.exit(f"set {pcfg['base_url_env']} first (for --providers {name})")
            try:
                from openai import OpenAI
            except ImportError:
                sys.exit("pip install openai")
            clients[name] = OpenAI(api_key="ollama", base_url=base_url)
            model = args.ollama_model or pcfg["model"]
            call_fns[name] = lambda c, p, m=model: _call_ollama(c, p, m)
            print(f"  ollama model: {model}")

    t0 = time.time()
    todo = todo.copy()
    todo["context"] = (todo.headline.map(lambda h: ctx_map.get(str(h), ""))
                       if args.with_context else "")
    if not args.no_anonymize:
        aliases = load_aliases(COMPANY_NAMES)
        todo["prompt_headline"] = [anonymize(h, t, aliases.get(t, []))
                                   for h, t in zip(todo.headline, todo.ticker)]
        todo["prompt_ticker"] = MASK
    _score_sequential(clients, call_fns, args.providers, todo, cache,
                      args.with_context, args.agents)
    save_cache(cache)
    print(f"\nscored in {time.time()-t0:.0f}s | cache now {len(cache):,} entries")

    # ---------------- pilot report
    if args.pilot:
        scored = [cache[k] for k in todo.key if k in cache]
        if scored:
            s = pd.DataFrame(scored)
            print("\n" + "=" * 62)
            print("PILOT QUALITY REPORT")
            print("=" * 62)
            print(f"  scored ok        : {len(s)}/{len(todo)}")
            print(f"  strength range   : {s.strength.min():+.2f} to "
                  f"{s.strength.max():+.2f}")
            print(f"  strength std dev : {s.strength.std():.3f}  "
                  f"(keyword scorer was 0.238, mostly stuck at 1.0)")
            print(f"  unique |strength|: {s.strength.abs().nunique()} distinct "
                  f"values")
            print(f"  direction split  : {(s.strength>0).mean():.0%} long / "
                  f"{(s.strength<0).mean():.0%} short / "
                  f"{(s.strength==0).mean():.0%} neutral")
            print(f"  duration spread  : {s.duration.value_counts().sort_index().to_dict()}")
            print(f"  importance mean  : {s.importance.mean():.1f}/10")
            print(f"\n  ACTUAL COST      : {money(cost_of(len(s), primary))}")
            print(f"  full run would be: "
                  f"{money(cost_of(len(kept)-len(cache)+len(s), primary))}")
            print("\n  sample scores:")
            samp = todo.head(8)
            for r in samp.itertuples(index=False):
                c = cache.get(r.key)
                if c:
                    print(f"    s={c['strength']:+.2f} d={c['duration']} "
                          f"i={c['importance']:>2}  {r.headline[:62]}")
            print("\n  >>> if strength varies widely, the LLM adds what the")
            print("      keyword scorer could not. If it clusters at +/-1,")
            print("      the prompt needs work before the full run.")
    _write_output(nw, cache, tmap, _out_name(args))


def _provider_tag(args) -> str:
    """Cache/output namespace: the primary provider, plus the model when a
    non-default Ollama model is chosen, so two models never share entries."""
    primary = args.providers[0]
    model = getattr(args, "ollama_model", None)
    if primary == "ollama" and model and model != PROVIDERS["ollama"]["model"]:
        return "ollama-" + re.sub(r"[^A-Za-z0-9.]+", "-", model)
    return primary


def _out_name(args) -> str:
    base = "news_scored_agents" if args.agents else "news_scored_llm"
    if args.with_context:
        base += "_context"
    base += f"_{_provider_tag(args)}"
    if not args.no_anonymize:
        base += "_anon"
    if getattr(args, "include_test_period", False):
        base += "_incl_test"         # never mix test rows into the training file
    return str(DATA / (base + ".csv"))


def _build_prompt(r, with_context: bool, agents: bool = False) -> str:
    # prompt_* columns hold the anonymized headline/ticker when masking is on
    headline = getattr(r, "prompt_headline", r.headline)
    ticker = getattr(r, "prompt_ticker", r.ticker)
    ctx = getattr(r, "context", "") if with_context else ""
    if agents:
        block = (f"\nHistorical context (computed ONLY from events before "
                 f"this headline's date):\n{ctx}\n" if ctx else "")
        tmpl = (PROMPT_MACRO if getattr(r, "route", "company") == "macro"
                else PROMPT_COMPANY)
        return tmpl.format(headline=headline, ticker=ticker, context=block)
    if with_context and ctx:
        return PROMPT_WITH_CONTEXT.format(headline=headline,
                                          ticker=ticker, context=ctx)
    return PROMPT.format(headline=headline, ticker=ticker)


def _call_google(client, prompt: str) -> str:
    resp = client.models.generate_content(
        model=PROVIDERS["google"]["model"], contents=prompt)
    return resp.text


def _call_groq(client, prompt: str) -> str:
    # max_tokens=500 + reasoning_effort="low": gpt-oss is a reasoning model,
    # it needs headroom for hidden chain-of-thought before the JSON answer.
    resp = client.chat.completions.create(
        model=PROVIDERS["groq"]["model"], max_tokens=500,
        reasoning_effort="low",
        messages=[{"role": "user", "content": prompt}])
    return resp.choices[0].message.content


def _call_ollama(client, prompt: str, model: str | None = None) -> str:
    # think=False: hybrid reasoning models (qwen3.x) would otherwise spend
    # max_tokens on hidden reasoning and return no JSON; ignored by llama
    resp = client.chat.completions.create(
        model=model or PROVIDERS["ollama"]["model"], max_tokens=300,
        temperature=0.2, extra_body={"think": False},
        messages=[{"role": "user", "content": prompt}])
    return resp.choices[0].message.content


def _score_sequential(clients: dict, call_fns: dict, providers: list,
                      todo, cache, with_context=False, agents=False):
    total = len(todo)
    idx = 0  # current provider in the cascade -- advances forward only
    last_call_ts: dict[str, float] = {}
    consecutive_errors = 0
    for i, r in enumerate(todo.itertuples(index=False), 1):
        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            # server down (e.g. host asleep): stop instead of timing out on
            # every remaining headline; unscored ones are retried next run
            print(f"  [{consecutive_errors} errors in a row @ {i} -- provider "
                  f"unreachable, stopping this run; rerun to resume]")
            break
        prompt = _build_prompt(r, with_context, agents)
        retries = 0
        while True:
            name = providers[idx]
            # proactive pacing -- stay under the provider's known per-minute
            # cap instead of finding out about it via 429s (see MIN_INTERVAL_SEC)
            wait = (MIN_INTERVAL_SEC.get(name, 0.0)
                   - (time.time() - last_call_ts.get(name, 0.0)))
            if wait > 0:
                time.sleep(wait)
            last_call_ts[name] = time.time()
            try:
                text = call_fns[name](clients[name], prompt)
                parsed = parse_reply(text)
                if parsed:
                    cache[r.key] = parsed
                consecutive_errors = 0
                break
            except Exception as e:
                if not _is_rate_limited(e):
                    print(f"  [error @{i} via {name}] {e}")
                    consecutive_errors += 1
                    time.sleep(2)
                    break
                if retries < MAX_RETRIES_PER_HEADLINE:
                    delay = _extract_retry_delay(e)
                    print(f"  [{name} rate-limited @ {i}, retrying in "
                          f"{delay:.0f}s ({retries + 1}/"
                          f"{MAX_RETRIES_PER_HEADLINE})]")
                    time.sleep(delay)
                    retries += 1
                    continue
                if idx < len(providers) - 1:
                    idx += 1
                    print(f"  [{name} still rate-limited @ {i}, "
                          f"falling back to {providers[idx]}]")
                    retries = 0
                    continue
                print(f"  [{name} rate-limited @ {i}, no more providers -- "
                      f"skipping this headline]")
                break
        if i % 25 == 0 or i == total:
            print(f"  {i}/{total} scored (current provider: {providers[idx]})")
            save_cache(cache)
    save_cache(cache)


def _write_output(nw: pd.DataFrame, cache: dict, template_map: dict = None,
                  out_file: str = OUT_FILE):
    """template_map: template -> representative headline key, so every
    variant of a scored template inherits that score for free."""
    out = nw.copy()
    out["key"] = out.headline.map(headline_key)
    if template_map:
        miss = ~out.key.isin(cache)
        out.loc[miss, "key"] = (out.loc[miss, "headline"]
                                .map(normalize_template).map(template_map)
                                .fillna(out.loc[miss, "key"]))
    sc = out.key.map(lambda k: cache.get(k))
    out["strength"] = [c["strength"] if c else np.nan for c in sc]
    out["duration"] = [c["duration"] if c else np.nan for c in sc]
    out["importance"] = [c["importance"] if c else np.nan for c in sc]
    out = out.dropna(subset=["strength"])
    cols = ["timestamp", "ticker", "headline", "strength", "duration",
            "importance"]
    out[cols].to_csv(out_file, index=False)
    print(f"\nwrote {len(out):,} scored rows -> {out_file}")


if __name__ == "__main__":
    main()
