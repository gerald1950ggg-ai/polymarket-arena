# S2 — Cross-Market Divergence Strategy

## Overview

The Cross-Market Divergence bot monitors the **same real-world events** as they are priced across multiple independent prediction markets. When prices diverge significantly, one market is likely mispriced — and that represents an arbitrage/edge opportunity.

---

## Core Hypothesis

Different prediction markets (Polymarket, Kalshi, Betfair) attract different user bases, liquidity levels, and information flows. This leads to **temporary price discrepancies** for identical or near-identical outcomes.

**Example:**
- Polymarket: "Will the Fed cut rates in March?" → 65¢ YES
- Kalshi: Same question → 58¢ YES
- **Divergence: 7¢ (10.8%)** → Signal to BUY on Kalshi (cheaper)

The "consensus" of multiple markets is more accurate than any single market. The outlier is mispriced.

---

## Markets Monitored

| Exchange | Access Method | Auth Required |
|----------|--------------|---------------|
| Polymarket | Gamma API (public) | No |
| Kalshi | REST API v2 (public for market data) | No (read-only) |
| Betfair | Exchange API | Yes (future) |

---

## Signal Logic

1. **Fetch** active markets from Polymarket and Kalshi
2. **Match** markets by topic keywords (BTC, Fed, Trump, election, etc.)
3. **Compare** YES prices between matched markets
4. **Flag** divergences ≥ 10% (MIN_DIVERGENCE = 0.10)
5. **Direction:**
   - Polymarket price < Kalshi price → **BUY on Polymarket** (it's cheaper, likely to rise)
   - Polymarket price > Kalshi price → **SELL on Polymarket** (it's overpriced, likely to fall)
6. **Conviction** scales with divergence size (5.0 base + divergence/0.05, max 10.0)

---

## Trade Parameters

| Parameter | Value |
|-----------|-------|
| Min Divergence | 10% |
| Min Conviction Score | 6.0 / 10 |
| Max Trades per Scan | 3 |
| Position Size | 5% of balance, max $500 |
| Scan Interval | 120 seconds |
| Time Horizon | 48 hours (short-term convergence) |

---

## Edge Cases & Risks

- **False matches:** Keyword matching can pair unrelated markets (e.g., "oil" matching "olive oil")
- **Stale prices:** Kalshi prices may lag if liquidity is thin
- **Market structure differences:** Kalshi uses cent-denominated prices, Polymarket uses decimal
- **Resolution timing:** Markets may resolve at different times even for same event
- **Liquidity risk:** The divergence may be real but uncloseable due to thin book

---

## Paper Trading Mode

All trades are simulated with $10,000 starting balance. Win probability is modeled as:
```
win_chance = (conviction / 10.0) * 0.70  # max 70% win rate
```

Profit from convergence: `size × divergence_pct × 2`
Loss on wrong side: `size × 0.30`

---

## Files

| File | Purpose |
|------|---------|
| `divergence_bot.py` | Main bot implementation |
| `SPEC.md` | This document |

---

## Future Enhancements

- [ ] Add Betfair exchange integration
- [ ] NLP-based market matching (embeddings vs keywords)
- [ ] Real-time websocket price feeds
- [ ] Automated cross-exchange execution via CLOB APIs
- [ ] Correlation tracking for known market pairs
- [ ] Alert when divergence exceeds 20% (high-conviction)
