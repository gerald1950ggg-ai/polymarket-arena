# S4 — Wikipedia Edit Velocity Strategy

## Overview

The Wikipedia Edit Velocity bot monitors the English Wikipedia API for **unusual
edit spikes** on pages closely related to active Polymarket prediction markets.
A sudden burst of edits on a Wikipedia article signals that something newsworthy
is being documented in real-time — which means the prediction market hasn't
repriced yet. Get in early.

---

## Core Hypothesis

Wikipedia is one of the fastest public records of breaking events. When a page
about a political figure, economic indicator, or financial asset starts receiving
a high volume of edits in a short window, it's because editors are rapidly
updating facts — i.e., **something just happened**.

Prediction markets are typically slower to reprice than Wikipedia is to update.
That lag = edge.

**Example:**
- Wikipedia page "Federal Reserve" receives 5 edits in 4 minutes
- News is breaking: Fed just announced surprise rate cut
- Polymarket's "Will Fed cut rates in March?" market still shows 30% YES
- Signal: **BUY YES** before the market catches up

---

## Data Sources

| Source | Endpoint | Auth |
|--------|----------|------|
| Wikipedia Recent Changes | `/w/api.php?action=query&list=recentchanges` | None |
| Wikipedia Page Revisions | `/w/api.php?action=query&prop=revisions&titles={title}` | None |

---

## Watched Pages

### Political
- Federal Reserve
- Donald Trump
- Joe Biden
- Congress
- Supreme Court

### Economic
- Recession
- Inflation
- Gross domestic product
- Unemployment

### Crypto
- Bitcoin
- Ethereum
- U.S. Securities and Exchange Commission
- Cryptocurrency

### Events
- United States presidential election
- Impeachment
- Federal funds rate

---

## Signal Logic

| Edits in 5 min | Signal Level | Conviction | Win Rate |
|----------------|-------------|-----------|---------|
| > 3 | HIGH | 7.0 – 10.0 | 68% |
| > 1 | MEDIUM | 5.5 – 7.0 | 55% |
| ≤ 1 | None | — | — |

**Detection flow:**
1. Fetch 100 most recent Wikipedia changes (namepsace 0 = articles)
2. Match changed page titles against watched keyword list (substring match)
3. For each match, fetch up to 10 recent revisions via page API
4. Count edits within last 5 minutes
5. Classify as HIGH / MEDIUM / none
6. Log opportunity + execute paper trade for any signal

---

## Trade Parameters

| Parameter | Value |
|-----------|-------|
| Position size | 4% of balance, max $400 |
| Scan interval | 60 seconds |
| Signal window | 5 minutes |
| HIGH win rate (modelled) | 68% |
| MEDIUM win rate (modelled) | 55% |
| Expected ROI per trade | 50% |

---

## Paper Trading Mode

All trades are simulated. Entry prices are randomised near 0.55 ± 0.15 to
simulate the pre-reprice window. Win outcomes drawn from Bernoulli(win_rate).

---

## Files

| File | Purpose |
|------|---------|
| `wiki_bot.py` | Main bot implementation |
| `test_s4.py` | Single-scan integration test |
| `SPEC.md` | This document |

---

## Edge Cases & Risks

- **Vandalism edits:** Not all edit spikes are news; bots and vandals also edit pages.
  Future fix: filter by trusted editor list or use Wikipedia's damage-detection API.
- **Topic mismatch:** Substring matching can occasionally over-match.
  Future fix: use embedding similarity against Polymarket market descriptions.
- **API rate limits:** Wikipedia has soft rate limits (~200 req/min). Single-bot usage
  at 60s intervals is well within limits.
- **Signal decay:** Wikipedia edits happen fast; a 5-minute window may miss the
  initial spike if the scan cycle lands late.

---

## Future Enhancements

- [ ] Wikidata integration for structured event data
- [ ] Editor reputation scoring (ignore bots and IP edits)
- [ ] NLP on edit comments to extract sentiment / direction
- [ ] Cross-signal with S3 (LP withdrawals) for double-confirmation
- [ ] Auto-link Wikipedia topic to Polymarket condition_id via Gamma API
