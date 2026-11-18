# Thesis

MSc Banking & Finance thesis at ZHAW: **"News-Driven Automated Trading versus
Traditional Systematic Strategies."** Supervisor: Prof. Martin Schnauss.
Started 13 July 2026.

## Core question

Can news be converted into a systematic trading strategy that survives
transaction costs, position sizing, stops and a drawdown limit — and does an
LLM read news better than a keyword dictionary?

## Three pillars

1. **Signal generation** — every scorer emits TWO outputs per headline:
   `strength` ∈ [-1,1] (feeds position size) and `duration` ∈ {1,2,3} days
   (feeds the time exit). Keyword baseline vs LLM.
2. **Risk-controlled execution** — fractional Kelly vs fixed-fractional
   (Kelly is a TESTED HYPOTHESIS, not an assumption), ATR-scaled stops,
   drawdown control.
3. **Empirical test** — net of costs, benchmarked against time-series
   momentum, 80/20 chronological split.

**The tradable object:** NOT the initial spike (HFT owns the first seconds —
conceded by design). The target is the post-news DRIFT.

## Writing status

- **Introduction + Literature Review: FINAL** — 27 pages, ~60 verified
  citations, Times New Roman 12pt, 1.5 spacing. Lit review is 20 pages across
  12 sections.
- **Methodology: drafted**, 14 pages, same formatting. Documents the bugs in
  `bugs.md` as methodological findings. Needs: chapter numbering check against
  the lit review, decision on whether Data becomes its own chapter, tense
  updates. Should add bugs 6–9 as methodological findings (same treatment as
  1–5), and describe the drawdown control as sizing + throttle (`methodology.md`).
- **Methodology vs code mismatch:** the methodology describes Glasserman-Lin
  headline anonymization, but the scores in use were NOT anonymized (see
  `bugs.md`, open item). Fix before the final scoring run, or change the text.
- Results / Discussion / Conclusion: not started (blocked on the open items
  in `bugs.md`).

## Thesis extensions (agreed, pending supervisor scope approval)

1. **Cost of alpha** — same strategy across an infrastructure ladder: free
   (local Ollama + RSS) → cheap (Haiku API + Benzinga) → expensive (frontier +
   RavenPack). Does costlier infrastructure pay for itself? Operationalises
   Grossman-Stiglitz (lit review §2.1). Novel. The local 3B Ollama run is
   already the "free" rung (`results.md`).
2. **R² and Sharpe year by year** — tests Lo's adaptive markets hypothesis
   (§2.2): do edges decay as capital learns, especially post-2023 as LLM
   adoption spread? Parallels Fischer & Krauss (2018) on LSTM decay.
3. **Strategy correlation** — correlate daily returns of A/B/C/momentum; does
   combining weakly-correlated strategies raise portfolio Sharpe? Results
   subsection, not a research question.
4. **Medallion Fund — framing device, NOT replication.** Strategy is secret,
   fund closed, and it is HFT market-making = the Tier 1 domain this thesis
   concedes. Use: (a) lit review §2.1, cite Cornell (2019) — $100 in 1988 →
   $398.7m by 2018, 63.3% compound, no negative year in 31 years, negative
   factor loadings so not a risk premium; strongest empirical challenge to
   EMH. (b) RIEF-vs-Medallion capacity contrast as evidence alpha is
   capacity-constrained. (c) Discussion: Medallion's edge is infrastructure
   and speed; this thesis's edge is interpretation — different edge, scales
   differently.

**Scope warning:** the thesis is already structurally complete. Ideas 1 and 2
add two results sections. Confirm scope with Prof. Schnauss first.
