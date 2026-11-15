"""
raw_news_pusher.py -- Step 1: just get news pushed to Telegram INSTANTLY.
No scoring, no LLM, no filtering logic beyond basic dedupe and a freshness
guard against stale/unparseable timestamps. This proves the plumbing
(websocket -> Telegram) works and is fast, before we add any intelligence
on top.

COVERAGE: SYMBOLS = ["*"] subscribes to the ENTIRE Benzinga wire -- this is
already every stock, not just Nasdaq, plus commodities and macro coverage,
which Benzinga tags with proxy tickers (oil under USO/XLE/CVX/XOM, broad
macro under SPY/QQQ/DIA, or with NO ticker at all for pure Fed/CPI/economic
releases). Nothing is excluded. The only thing added below is a CATEGORY
LABEL per headline so your feed is readable, not a filter -- every item
still gets pushed regardless of category.

ARCHITECTURE:
  Alpaca real-time news WEBSOCKET (Benzinga newswire, free)
    -> headline PUSHED to this script the instant the wire publishes it
    -> dedupe (in case the same item streams twice)
    -> freshness guard (discard anything older than MAX_NEWS_AGE_SECONDS,
       from the future, or with an unparseable timestamp)
    -> tag with a category label (Nasdaq / Oil & Energy / Macro / Other)
    -> straight to Telegram, no scoring, no delay, nothing dropped
    -> logged to CSV for the record

LATENCY: wire publish -> Telegram message, typically 1-3 seconds total.

SETUP:
  pip install websocket-client requests
  export ALPACA_KEY=...      export ALPACA_SECRET=...
  export TELEGRAM_TOKEN=...  export TELEGRAM_CHAT_ID=...
    (TELEGRAM_CHAT_ID can be your personal chat id OR a group id -- group
    ids are negative numbers, e.g. -1001234567890. Both work identically.)

  python raw_news_pusher.py
"""
from __future__ import annotations
import csv
import json
import os
import re
import time
from datetime import datetime, timezone

import certifi
import requests
import websocket  # pip install websocket-client

from paths import ROOT, LOGS

# ============================== CONFIG ======================================
ENV_FILE = str(ROOT / ".env")


def load_env_file(path=ENV_FILE):
    """Populate os.environ from a KEY=VALUE .env file, if present.

    Needed because launching this script from an editor's Run button
    starts a fresh process that never sees vars exported in a terminal.
    """
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


load_env_file()
ALPACA_KEY = os.environ.get("ALPACA_KEY", "")
ALPACA_SECRET = os.environ.get("ALPACA_SECRET", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "PASTE_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "PASTE_CHAT_ID")

NEWS_WS_URL = "wss://stream.data.alpaca.markets/v1beta1/news"

# Fail-safe freshness guard: items whose timestamp can't be verified as
# recent are discarded rather than pushed (see handle_news_item).
MAX_NEWS_AGE_SECONDS = 120

# "*" = EVERYTHING on the wire: every stock (not just Nasdaq), commodities,
# macro, Fed releases -- all of it. This is intentionally the full firehose.
SYMBOLS = ["*"]

LOG_FILE = str(LOGS / "raw_news_log.csv")
seen_ids: set = set()

# ---- category labels, for readability only -- NOT a filter --------------
# Load the Nasdaq-100 (+ former members) universe if the file is present.
NASDAQ_SET: set = set()
if os.path.exists("nasdaq100.txt"):
    NASDAQ_SET = {t.strip().upper() for t in open("nasdaq100.txt") if t.strip()}

OIL_ENERGY = {"USO", "BNO", "XLE", "CVX", "XOM", "OXY", "SLB", "COP", "HAL",
             "UCO", "SCO", "XOP"}
BROAD_MACRO = {"SPY", "QQQ", "DIA", "IWM", "TLT", "IEF", "SHY", "UUP", "GLD",
               "SLV", "VIX", "UVXY"}
MACRO_KEYWORDS = re.compile(
    r"\bfomc\b|\bfed(eral reserve)?\b|\bcpi\b|\bpayrolls\b|\bnonfarm\b|"
    r"\bgdp\b|\binflation\b|\brate (cut|hike|decision)\b|\btariff|"
    r"\bpowell\b|\becb\b|\brecession\b", re.IGNORECASE)


def categorize(symbols: list[str], headline: str) -> str:
    syms = set(symbols)
    if syms & NASDAQ_SET:
        return "NASDAQ"
    if syms & OIL_ENERGY:
        return "OIL/ENERGY"
    if syms & BROAD_MACRO or MACRO_KEYWORDS.search(headline):
        return "MACRO"
    if not syms:
        return "MACRO"          # untagged wire items are usually macro/general
    return "OTHER"


# ============================ PLUMBING =======================================
def send_telegram(text: str):
    if "PASTE" in TELEGRAM_TOKEN:
        print("  [telegram] not configured -- printed only")
        print("  " + text.replace("\n", " | "))
        return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": text,
                            "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"  [telegram error] {e}")


def log_row(row: dict):
    exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["wire_time", "received_at_utc",
                                          "latency_s", "category", "headline",
                                          "symbols", "source", "url"])
        if not exists:
            w.writeheader()
        w.writerow(row)


def check_freshness(wire_time: str, now: datetime) -> tuple[bool, float | str]:
    """Return (is_fresh, age_seconds_or_reason).

    Fail-SAFE: any parsing failure is treated as not fresh, not let through.
    """
    if not wire_time:
        return False, "unparseable timestamp: '' (missing)"
    try:
        wire_dt = datetime.fromisoformat(wire_time.replace("Z", "+00:00"))
    except Exception:
        return False, f"unparseable timestamp: {wire_time!r}"

    age_seconds = (now - wire_dt).total_seconds()
    if age_seconds > MAX_NEWS_AGE_SECONDS:
        return False, age_seconds
    if age_seconds < -30:
        return False, age_seconds
    return True, age_seconds


def handle_news_item(item: dict):
    nid = item.get("id")
    if nid in seen_ids:
        return
    seen_ids.add(nid)

    headline = (item.get("headline") or "").strip()
    if not headline:
        return

    wire_time = item.get("created_at", "")
    now = datetime.now(timezone.utc)
    is_fresh, result = check_freshness(wire_time, now)
    if not is_fresh:
        if isinstance(result, str):
            print(f"[discard] {result}")
        else:
            print(f"[discard] stale/future item: age={result:.1f}s "
                  f"(limit {MAX_NEWS_AGE_SECONDS}s) -- {headline[:60]}")
        return
    lat = round(result, 1)

    symbols = item.get("symbols") or []
    category = categorize(symbols, headline)

    log_row({"wire_time": wire_time,
             "received_at_utc": now.isoformat(timespec="seconds"),
             "latency_s": lat, "category": category, "headline": headline,
             "symbols": "|".join(symbols), "source": item.get("source", ""),
             "url": item.get("url", "")})

    sym_tag = f" [{', '.join(symbols)}]" if symbols else ""
    print(f"[{lat}s] ({category}){sym_tag} {headline[:80]}")

    icon = {"NASDAQ": "💻", "OIL/ENERGY": "🛢️", "MACRO": "🌐",
            "OTHER": "📰"}.get(category, "📰")
    msg = f"{icon} *{category}*{sym_tag}\n{headline}"
    send_telegram(msg)


# ============================ WEBSOCKET ======================================
def on_open(ws):
    print("[ws] connected -- authenticating")
    ws.send(json.dumps({"action": "auth", "key": ALPACA_KEY,
                        "secret": ALPACA_SECRET}))


def on_message(ws, message):
    try:
        data = json.loads(message)
    except Exception:
        return
    for item in (data if isinstance(data, list) else [data]):
        t = item.get("T")
        if t == "success" and item.get("msg") == "authenticated":
            print(f"[ws] authenticated -- subscribing to {SYMBOLS}")
            ws.send(json.dumps({"action": "subscribe", "news": SYMBOLS}))
        elif t == "subscription":
            print(f"[ws] subscribed: {item.get('news')}")
        elif t == "n":
            handle_news_item(item)
        elif t == "error":
            print(f"[ws error] {item}")


def on_error(ws, err):
    print(f"[ws error] {err}")


def on_close(ws, code, msg):
    print(f"[ws] closed ({code} {msg}) -- reconnecting in 5s")


def main():
    if not ALPACA_KEY or not ALPACA_SECRET:
        raise SystemExit("Set ALPACA_KEY and ALPACA_SECRET env vars first.")
    print(f"raw_news_pusher running | symbols={SYMBOLS} | no scoring, "
          f"instant push")
    while True:                       # auto-reconnect loop
        ws = websocket.WebSocketApp(
            NEWS_WS_URL, on_open=on_open, on_message=on_message,
            on_error=on_error, on_close=on_close)
        ws.run_forever(ping_interval=30, ping_timeout=10,
                       sslopt={"ca_certs": certifi.where()})
        time.sleep(5)


if __name__ == "__main__":
    main()
