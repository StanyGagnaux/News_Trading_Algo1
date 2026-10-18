"""
test_freshness_guard.py -- standalone check for the freshness guard in
raw_news_pusher.py. Does NOT touch the live websocket or send real
Telegram messages: send_telegram/log_row are monkey-patched to no-ops so
this is safe to run repeatedly.

Feeds 3 fake news items through handle_news_item() and reports which ones
were pushed vs discarded, so the fix can be confirmed before running the
real script against the live wire.

Run (from the project root): python3 tests/test_freshness_guard.py
"""
from __future__ import annotations
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import raw_news_pusher as m

pushed: list[str] = []


def fake_send_telegram(text: str):
    pushed.append(text)


def fake_log_row(row: dict):
    pass


m.send_telegram = fake_send_telegram
m.log_row = fake_log_row


def make_item(item_id: str, headline: str, created_at: str) -> dict:
    return {"id": item_id, "headline": headline, "symbols": [],
            "created_at": created_at, "source": "test"}


def iso_ago(seconds: float) -> str:
    dt = datetime.now(timezone.utc) - timedelta(seconds=seconds)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


CASES = [
    ("fresh (5s old)", make_item("t1", "Fresh headline 5s old", iso_ago(5)),
     True),
    ("stale (5h old)", make_item("t2", "Stale headline 5h old", iso_ago(5 * 3600)),
     False),
    ("missing timestamp", make_item("t3", "Headline with no timestamp", ""),
     False),
]

print(f"MAX_NEWS_AGE_SECONDS = {m.MAX_NEWS_AGE_SECONDS}\n")

results = []
for label, item, expect_pushed in CASES:
    before = len(pushed)
    m.handle_news_item(item)
    was_pushed = len(pushed) > before
    ok = was_pushed == expect_pushed
    status = "PASS" if ok else "FAIL"
    outcome = "pushed" if was_pushed else "discarded"
    print(f"[{status}] {label}: {outcome} (expected "
          f"{'pushed' if expect_pushed else 'discarded'})")
    results.append(ok)

print()
if all(results):
    print("All cases behaved as expected.")
else:
    print("Some cases did NOT behave as expected -- see FAIL lines above.")
