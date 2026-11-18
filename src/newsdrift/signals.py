"""
Pillar 1 -- Signal generation from news.

Core architectural decision (thesis requirement): every scorer emits TWO
separate outputs per news item:

    strength  in [-1, +1]  -> feeds POSITION SIZE (Pillar 2, Kelly module)
    duration  in {1..3}    -> feeds TIME-BASED EXIT (Pillar 2, stop module)

Two scorer implementations share the same interface:

  KeywordScorer  -- Loughran-McDonald-style dictionary baseline. Duration is
                    proxied by keyword *density* (more loaded words -> bigger
                    event -> longer drift), which is deliberately crude: it is
                    the baseline the LLM must beat.

  LLMScorer      -- calls an LLM (Anthropic API adapter included) with a
                    prompt that requests strength and duration as separate
                    JSON fields. Supports Glasserman-Lin headline
                    anonymization to control look-ahead bias in evaluation.
                    Falls back to a deterministic offline stub when no API
                    is available, so the pipeline never blocks on access.

LOOK-AHEAD BIAS -- structural enforcement, not convention:
`build_signal_table` assigns every news item an `effective_date`, the first
trading day STRICTLY AFTER the news date plus the configured lag. The backtest
engine keys exclusively on `effective_date`; it is impossible for it to see a
signal on the bar in which the news occurred.
"""
from __future__ import annotations
import json
import re
import numpy as np
import pandas as pd

from .config import SignalConfig


# ----------------------------------------------------------------------------
# Glasserman-Lin anonymization
# ----------------------------------------------------------------------------
def anonymize_headline(headline: str, ticker: str,
                       company_name: str | None = None) -> str:
    """Replace ticker / company identifiers with a neutral token so an LLM
    cannot recall firm-specific outcomes from its training data."""
    out = headline
    for ident in filter(None, [company_name, ticker]):
        out = re.sub(re.escape(ident), "the company", out, flags=re.IGNORECASE)
    return out


# ----------------------------------------------------------------------------
# Scorers (shared interface: .score(headline, ticker) -> (strength, duration))
# ----------------------------------------------------------------------------
class KeywordScorer:
    """Dictionary baseline. Strength = normalized net tone; duration = density."""

    def __init__(self, cfg: SignalConfig):
        self.cfg = cfg
        self.pos = set(cfg.lm_positive)
        self.neg = set(cfg.lm_negative)

    def score(self, headline: str, ticker: str = "") -> tuple[float, int]:
        words = re.findall(r"[a-z']+", headline.lower())
        p = sum(w in self.pos for w in words)
        n = sum(w in self.neg for w in words)
        total = p + n
        if total == 0:
            return 0.0, self.cfg.duration_min_days
        strength = float(np.clip((p - n) / total, *self.cfg.strength_range))
        # duration proxy: 1 loaded word -> 1 day, 2 -> 2 days, 3+ -> ceiling
        duration = int(np.clip(total, self.cfg.duration_min_days,
                               self.cfg.duration_max_days))
        return strength, duration


LLM_PROMPT = """You are a quantitative news analyst. Read the headline below and
respond ONLY with a JSON object, no other text, with exactly two fields:
  "strength": a float in [-1, 1]. Sign = expected direction of the stock's
      short-term drift AFTER the initial price reaction (negative = down).
      Magnitude = your confidence times the economic materiality of the news.
      Use 0 if the headline is not materially informative.
  "duration": an integer 1, 2, or 3 = number of trading days you expect the
      drift to persist (empirically, drift rarely survives past 2 days).
Headline: "{headline}"
"""


class PrecomputedScorer:
    """Scorer backed by an already-scored CSV (e.g. score_news_llm.py's
    output: [timestamp, ticker, headline, strength, duration, importance]).
    Same .score() interface as KeywordScorer/LLMScorer so it drops straight
    into build_signal_table with no other pipeline changes. Headlines not
    present in the CSV (not yet scored) return strength=0.0, which the
    noise gate in build_signal_table then drops -- unscored headlines are
    never silently traded as if they were neutral."""

    def __init__(self, scored_csv: str, default_duration: int = 1):
        df = pd.read_csv(scored_csv)
        self._lookup = {(r.headline, r.ticker): (float(r.strength), int(r.duration))
                        for r in df.itertuples(index=False)}
        self._default_duration = default_duration

    def score(self, headline: str, ticker: str = "") -> tuple[float, int]:
        return self._lookup.get((headline, ticker), (0.0, self._default_duration))


class LLMScorer:
    """
    LLM-based dual-output scorer.

    mode="api"  -> calls the Anthropic API (set api_key / model).
    mode="stub" -> deterministic offline model: keyword tone + calibrated
                   magnitude + hash-jitter. Keeps the pipeline runnable
                   end-to-end without network access; swap to "api" for the
                   thesis production runs.
    """

    def __init__(self, cfg: SignalConfig, mode: str = "stub",
                 api_key: str | None = None,
                 model: str = "claude-sonnet-4-6"):
        self.cfg = cfg
        self.mode = mode
        self.api_key = api_key
        self.model = model
        self._kw = KeywordScorer(cfg)

    # --- production path -----------------------------------------------
    def _score_api(self, headline: str) -> tuple[float, int]:
        import anthropic  # pip install anthropic
        client = anthropic.Anthropic(api_key=self.api_key)
        msg = client.messages.create(
            model=self.model, max_tokens=100,
            messages=[{"role": "user",
                       "content": LLM_PROMPT.format(headline=headline)}],
        )
        raw = msg.content[0].text.strip().strip("`")
        raw = raw[raw.find("{"): raw.rfind("}") + 1]
        obj = json.loads(raw)
        s = float(np.clip(obj["strength"], *self.cfg.strength_range))
        d = int(np.clip(obj["duration"], self.cfg.duration_min_days,
                        self.cfg.duration_max_days))
        return s, d

    # --- offline stub ----------------------------------------------------
    def _score_stub(self, headline: str) -> tuple[float, int]:
        base_s, base_d = self._kw.score(headline)
        if base_s == 0.0:
            return 0.0, base_d
        # deterministic per-headline jitter (simulates LLM nuance, no RNG state)
        h = (hash(headline) % 1000) / 1000.0
        strength = float(np.clip(base_s * (0.6 + 0.4 * h),
                                 *self.cfg.strength_range))
        duration = int(np.clip(base_d + (1 if h > 0.7 else 0),
                               self.cfg.duration_min_days,
                               self.cfg.duration_max_days))
        return strength, duration

    def score(self, headline: str, ticker: str = "") -> tuple[float, int]:
        text = (anonymize_headline(headline, ticker)
                if self.cfg.anonymize_headlines else headline)
        if self.mode == "api":
            return self._score_api(text)
        return self._score_stub(text)


# ----------------------------------------------------------------------------
# Signal table construction with STRUCTURAL lag enforcement
# ----------------------------------------------------------------------------
def build_signal_table(news: pd.DataFrame, scorer, trading_days: pd.DatetimeIndex,
                       cfg: SignalConfig) -> pd.DataFrame:
    """
    Returns one row per actionable news item:
      [news_date, effective_date, ticker, strength, duration]

    effective_date = first trading day strictly after news_date + (lag-1).
    With lag=1 and overnight news on day t, the signal becomes tradable at the
    open of day t+1 -- i.e. the day-t reaction bar is never touched.
    """
    td = pd.DatetimeIndex(sorted(trading_days.unique()))
    rows = []
    for r in news.itertuples(index=False):
        strength, duration = scorer.score(r.headline, r.ticker)
        if abs(strength) < cfg.min_abs_strength:
            continue
        news_date = pd.Timestamp(r.timestamp).normalize()
        pos = td.searchsorted(news_date + pd.Timedelta(days=1))
        pos += cfg.signal_lag_days - 1
        if pos >= len(td):
            continue
        rows.append({
            "news_date": news_date,
            "effective_date": td[pos],
            "ticker": r.ticker,
            "strength": strength,
            "duration": duration,
        })
    sig = pd.DataFrame(rows)
    if sig.empty:
        return sig
    # multiple same-day items on one ticker: net the strengths, max the duration
    sig = (sig.groupby(["effective_date", "ticker"], as_index=False)
              .agg(news_date=("news_date", "min"),
                   strength=("strength", "mean"),
                   duration=("duration", "max")))
    # Bug 11 (fixed 18 Oct 2026): the gate above is per headline; opposite
    # headlines can net to 0 (traded as a SHORT by the engine) or to a weak
    # average. Re-apply the gate to the netted value, as build_event_table does.
    sig = sig[sig["strength"].abs() >= cfg.min_abs_strength]
    # assert the invariant rather than trusting it
    assert (sig["effective_date"] > sig["news_date"]).all(), \
        "LOOK-AHEAD VIOLATION: effective_date must be strictly after news_date"
    return sig.sort_values(["effective_date", "ticker"], kind="mergesort").reset_index(drop=True)


def build_event_table(news: pd.DataFrame, scorer, cfg: SignalConfig) -> pd.DataFrame:
    """
    POINT-IN-TIME events for the intraday-entry strategies (B and C).
    Returns one row per headline timestamp: [ticker, news_ts, strength, duration].

    Why this exists (Sept 2026 fix): B and C used to merge build_signal_table's
    DAILY aggregate back onto every headline timestamp of that day. That gave
    a 14:40 entry a strength averaged over headlines published later the same
    day (and over weekend headlines rolled into Monday) -- look-ahead -- and
    turned every headline of the day, including ones that failed the noise
    gate themselves, into a separate trade (up to 366 per ticker-day).

    Here each event uses ONLY its own headline's score, and only headlines
    that pass the noise gate on their own become events. Headlines sharing
    the exact same timestamp and ticker are all known at that instant, so
    they are netted (mean strength, max duration) -- no information from any
    later time is used.
    """
    rows = []
    for r in news.itertuples(index=False):
        strength, duration = scorer.score(r.headline, r.ticker)
        if abs(strength) < cfg.min_abs_strength:
            continue
        rows.append({"ticker": r.ticker, "news_ts": r.timestamp,
                     "strength": float(strength), "duration": int(duration)})
    ev = pd.DataFrame(rows, columns=["ticker", "news_ts", "strength", "duration"])
    if ev.empty:
        return ev
    ev = (ev.groupby(["ticker", "news_ts"], as_index=False)
            .agg(strength=("strength", "mean"), duration=("duration", "max")))
    ev = ev[ev["strength"].abs() >= cfg.min_abs_strength]   # netting can cancel
    # invariant: one row per (ticker, timestamp) -- nothing aggregated across time
    assert not ev.duplicated(["ticker", "news_ts"]).any(), \
        "LOOK-AHEAD RISK: event table aggregates across timestamps"
    return ev.sort_values(["news_ts", "ticker"], kind="mergesort").reset_index(drop=True)
