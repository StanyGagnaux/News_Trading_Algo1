"""
live_pipeline.py -- live news -> scores, through the SAME functions as the
historical pipeline (decisions note of 24 Oct 2026, item 6b). Shadow mode
only: this file contains no order code (paper trading comes after the parity
test and explicit approval).

Imported, not re-implemented:
  universe rows, cleaning ........ news_cleaning.universe_rows / clean_news
  keyword score .................. newsdrift.KeywordScorer
  pre-filter, template, cache key  score_news_llm.tier0_keep / normalize_template / headline_key
  anonymisation .................. anonymize.anonymize / load_aliases / MASK
  prompt, model call, parsing .... score_news_llm._build_prompt / _call_ollama / parse_reply
  LLM cache ...................... score_news_llm.load_cache / save_cache (same file, same keys)
  rung 1b score .................. rung_embeddings.strength_from_embedding + saved parameters
  daily netting and gates ........ newsdrift.build_signal_table / build_event_table
  freshness check ................ raw_news_pusher.check_freshness

LLM rule, as in the batch run (_write_output): a row takes the cached score of
its TEMPLATE's representative; a template's representative is its first
headline that passes tier0_keep; a representative not yet in the cache is
scored once and cached. Rows whose template has no representative get no LLM
score. Live-only code: websocket plumbing, the session schedule, revision
tracking and logging. Session hours are US RTH in UTC while New York is on
EDT (until 1 Nov 2026); from 2 Nov the session is 14:30-21:00 UTC.

USAGE (from the project root; keep this Mac and the Ollama machine awake):
  caffeinate -i python3 src/live_pipeline.py --dates 2026-10-26 2026-10-27
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import threading
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import certifi
import numpy as np
import pandas as pd
import websocket

import raw_news_pusher as feed                       # loads .env; freshness guard
from paths import TICKERS, COMPANY_NAMES, OUTPUTS
from news_cleaning import universe_rows, clean_news, ROW_COLUMNS
from newsdrift import Config, KeywordScorer, build_signal_table, build_event_table
from score_news_llm import (tier0_keep, normalize_template, headline_key, load_cache, save_cache,
                            parse_reply, _build_prompt, _call_ollama, PROVIDERS)
from anonymize import anonymize, load_aliases, MASK
from rung_embeddings import MODEL_ID, PARAMS, strength_from_embedding

LLM_PREFIX = "ollama_anon_"                          # = batch namespace (provider + anonymised)
LLM_TIMEOUT_S = 30.0
LLM_BACKOFF_S = 60.0                                 # skip LLM calls this long after a failure
SESSION_UTC = (pd.Timedelta(hours=13, minutes=30), pd.Timedelta(hours=20))   # US RTH while EDT
LIVE_DIR = OUTPUTS / "live"
SAVE_EVERY = 10
REV_COLS = ["received_at_utc", "news_id", "revision", "created_at", "updated_at", "headline",
            "symbols", "source", "fresh", "age_or_reason"]
SCORE_COLS = ["received_at_utc", "news_id", "revision", "created_at", "updated_at", "ticker", "headline",
              "kw_strength", "kw_duration", "kw_t0", "kw_t1",
              "llm_strength", "llm_duration", "llm_importance", "llm_source", "llm_t0", "llm_t1",
              "emb_strength", "emb_t0", "emb_t1"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(t: datetime) -> str:
    return t.isoformat(timespec="milliseconds")


class Scorers:
    """The three rungs, each through the historical functions."""

    def __init__(self, use_llm: bool = True, use_embed: bool = True, llm_call=None):
        self.cfg = Config()
        self.keyword = KeywordScorer(self.cfg.signal)
        self.aliases = load_aliases(COMPANY_NAMES)
        self.cache = load_cache()
        self.tmap: dict = {}                  # template -> representative key (this session)
        self.rep_text: dict = {}              # representative key -> (headline, ticker)
        self.new_scores = 0
        self.llm_down_until = None            # circuit breaker after a failed call
        self.llm_call = llm_call
        if use_llm and llm_call is None:
            from openai import OpenAI
            client = OpenAI(api_key="ollama", base_url=os.environ["OLLAMA_BASE_URL"],
                            timeout=LLM_TIMEOUT_S, max_retries=0)
            model = PROVIDERS["ollama"]["model"]
            self.llm_call = lambda prompt: _call_ollama(client, prompt, model)
        self.embed = None
        if use_embed:
            from sentence_transformers import SentenceTransformer
            p = np.load(PARAMS)
            self.emb_params = (float(p["alpha"]), p["beta"], float(p["q95"]))
            self.embed = SentenceTransformer(MODEL_ID, revision=str(p["revision"]), device="cpu")

    def score_keyword(self, headline, ticker):
        t0 = now_utc()
        s, d = self.keyword.score(headline, ticker)
        return {"kw_strength": s, "kw_duration": d, "kw_t0": iso(t0), "kw_t1": iso(now_utc())}

    def _rep_for(self, headline, ticker):
        tpl = normalize_template(headline)
        if tpl in self.tmap:
            return self.tmap[tpl]
        if tier0_keep(headline, ticker):
            key = LLM_PREFIX + headline_key(headline)
            self.tmap[tpl], self.rep_text[key] = key, (headline, ticker)
            return key
        return None

    def score_llm(self, headline, ticker):
        t0 = now_utc()
        out = {"llm_strength": np.nan, "llm_duration": np.nan, "llm_importance": np.nan, "llm_source": "none"}
        rep = self._rep_for(headline, ticker)
        if rep is not None and rep in self.cache:
            out.update(llm_source="cache")
        elif rep is not None and self.llm_down_until and now_utc() < self.llm_down_until:
            out["llm_source"] = "skipped: server down"
        elif rep is not None and self.llm_call is not None:
            h, t = self.rep_text[rep]
            row = SimpleNamespace(headline=h, ticker=t, prompt_ticker=MASK,
                                  prompt_headline=anonymize(h, t, self.aliases.get(t, [])))
            try:
                parsed = parse_reply(self.llm_call(_build_prompt(row, with_context=False)))
            except Exception as e:                   # server down: logged, row unscored
                parsed, out["llm_source"] = None, f"error: {type(e).__name__}"
                self.llm_down_until = now_utc() + pd.Timedelta(seconds=LLM_BACKOFF_S)
            if parsed:
                self.cache[rep] = parsed
                self.new_scores += 1
                if self.new_scores % SAVE_EVERY == 0:
                    save_cache(self.cache)
                out.update(llm_source="scored")
            elif out["llm_source"] == "none":
                out["llm_source"] = "unparseable"
        if rep is not None and rep in self.cache:
            c = self.cache[rep]
            out.update(llm_strength=c["strength"], llm_duration=c["duration"], llm_importance=c["importance"])
        return {**out, "llm_t0": iso(t0), "llm_t1": iso(now_utc())}

    def score_embed(self, headline, ticker):
        t0 = now_utc()
        if self.embed is None:
            return {"emb_strength": np.nan, "emb_t0": iso(t0), "emb_t1": iso(now_utc())}
        text = anonymize(headline, ticker, self.aliases.get(ticker, []))
        e = self.embed.encode([text], convert_to_numpy=True)
        s = float(strength_from_embedding(e, *self.emb_params)[0])
        return {"emb_strength": s, "emb_t0": iso(t0), "emb_t1": iso(now_utc())}


class Session:
    """One trading day: every revision logged; latest revision per news id kept."""

    def __init__(self, day: str, scorers: Scorers, universe: set, out_dir=LIVE_DIR):
        out_dir.mkdir(parents=True, exist_ok=True)
        self.day, self.scorers, self.universe = day, scorers, universe
        self.rev_file, self.score_file = out_dir / f"revisions_{day}.csv", out_dir / f"scores_{day}.csv"
        self.out_dir = out_dir
        self.latest: dict = {}                # news_id -> (revision, item)
        self.revisions: dict = {}             # news_id -> count

    def _append(self, path, cols, row):
        new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            if new:
                w.writeheader()
            w.writerow(row)

    def handle(self, item: dict, received: datetime | None = None) -> None:
        received = received or now_utc()
        nid = item.get("id")
        rev = self.revisions.get(nid, 0) + 1
        self.revisions[nid] = rev
        fresh, age = feed.check_freshness(item.get("created_at", ""), received)
        base = {"received_at_utc": iso(received), "news_id": nid, "revision": rev,
                "created_at": item.get("created_at", ""), "updated_at": item.get("updated_at", "")}
        self._append(self.rev_file, REV_COLS, {**base, "headline": (item.get("headline") or "").strip(),
                     "symbols": "|".join(item.get("symbols") or []), "source": item.get("source", ""),
                     "fresh": fresh, "age_or_reason": age})
        self.latest[nid] = (rev, item)
        for _ts, ticker, headline, _src in universe_rows(item, self.universe):
            row = {**base, "ticker": ticker, "headline": headline,
                   **self.scorers.score_keyword(headline, ticker),
                   **self.scorers.score_llm(headline, ticker),
                   **self.scorers.score_embed(headline, ticker)}
            self._append(self.score_file, SCORE_COLS, row)

    def close(self) -> None:
        """End of day: cleaned table of the LATEST revision per news id, and the
        daily signal / event tables per rung through the historical functions."""
        save_cache(self.scorers.cache)
        rows = [r for _, item in self.latest.values() for r in universe_rows(item, self.universe)]
        if not rows:
            return
        news = clean_news(pd.DataFrame(rows, columns=ROW_COLUMNS))
        news.to_csv(self.out_dir / f"news_latest_{self.day}.csv", index=False)
        scores = pd.read_csv(self.score_file).drop_duplicates(["news_id", "ticker"], keep="last")
        news["timestamp"] = pd.to_datetime(news.timestamp, utc=True).dt.tz_localize(None)
        days = pd.bdate_range(pd.Timestamp(self.day) - pd.Timedelta(days=7), periods=20)
        for rung, col, dcol in (("keyword", "kw_strength", "kw_duration"), ("llm", "llm_strength", "llm_duration"),
                                ("embed", "emb_strength", None)):
            table = {(r.headline, r.ticker): (float(getattr(r, col)) if pd.notna(getattr(r, col)) else 0.0,
                                              int(getattr(r, dcol)) if dcol and pd.notna(getattr(r, dcol)) else 2)
                     for r in scores.itertuples(index=False)}
            scorer = SimpleNamespace(score=lambda h, t, tb=table: tb.get((h, t), (0.0, 2)))
            sig = build_signal_table(news, scorer, days, self.scorers.cfg.signal)
            ev = build_event_table(news.assign(timestamp=pd.to_datetime(news.timestamp, utc=True)),
                                   scorer, self.scorers.cfg.signal)
            sig.to_csv(self.out_dir / f"signals_{rung}_{self.day}.csv", index=False)
            ev.to_csv(self.out_dir / f"events_{rung}_{self.day}.csv", index=False)


def run_window(session: Session, start: datetime, end: datetime, symbols: list) -> None:
    """Websocket during [start, end); reconnects within the window."""
    def on_open(ws):
        ws.send(json.dumps({"action": "auth", "key": feed.ALPACA_KEY, "secret": feed.ALPACA_SECRET}))

    def on_message(ws, message):
        received = now_utc()
        data = json.loads(message)
        for item in (data if isinstance(data, list) else [data]):
            if item.get("T") == "success" and item.get("msg") == "authenticated":
                ws.send(json.dumps({"action": "subscribe", "news": symbols}))
            elif item.get("T") == "n":
                session.handle(item, received)
            elif item.get("T") in ("error", "subscription"):
                print(f"[ws] {item}", flush=True)

    while now_utc() < end:
        ws = websocket.WebSocketApp(feed.NEWS_WS_URL, on_open=on_open, on_message=on_message,
                                    on_error=lambda ws, e: print(f"[ws error] {e}", flush=True))
        timer = threading.Timer(max(1.0, (end - now_utc()).total_seconds()), ws.close)
        timer.start()
        ws.run_forever(ping_interval=30, ping_timeout=10, sslopt={"ca_certs": certifi.where()})
        timer.cancel()
        if now_utc() < end:
            time.sleep(5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dates", nargs="+", required=True, help="trading days, YYYY-MM-DD")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--no-embed", action="store_true")
    a = ap.parse_args()
    universe = {t.strip().upper() for t in open(TICKERS) if t.strip() and not t.startswith("#")}
    scorers = Scorers(use_llm=not a.no_llm, use_embed=not a.no_embed)
    for day in a.dates:
        start = (pd.Timestamp(day, tz="UTC") + SESSION_UTC[0]).to_pydatetime()
        end = (pd.Timestamp(day, tz="UTC") + SESSION_UTC[1]).to_pydatetime()
        if now_utc() >= end:
            continue
        wait = (start - now_utc()).total_seconds()
        print(f"[{iso(now_utc())}] session {day}: {start:%H:%M}-{end:%H:%M} UTC, "
              f"waiting {max(wait, 0) / 3600:.1f} h", flush=True)
        if wait > 0:
            time.sleep(wait)
        session = Session(day, scorers, universe)
        run_window(session, start, end, sorted(universe))
        session.close()
        print(f"[{iso(now_utc())}] session {day} closed: {len(session.latest)} news ids, "
              f"{sum(session.revisions.values())} revisions", flush=True)


if __name__ == "__main__":
    main()
