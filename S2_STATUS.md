# S2 Cross-Market Divergence — Build Status

**Built:** 2026-03-28  
**Status:** ✅ WORKING — test scan successful

---

## What Was Built

### Files Created
- `S2-cross-market/SPEC.md` — Full strategy spec with rationale, trade params, edge cases
- `S2-cross-market/divergence_bot.py` — Async `CrossMarketDivergenceBot` class
- `S2-cross-market/test_scan.py` — One-shot test runner (scan once, exit)

### Bot Architecture
- Registers with `ArenaDatabase` as `S2_divergence`
- Fetches Polymarket markets via Gamma API
- Fetches Kalshi markets via Elections API (two-stage: events → markets)
- Keyword-based topic matching across exchanges (bitcoin, fed, trump, election, oil, recession)
- Calculates price divergence and fires signals when delta ≥ 10%
- Paper trades with $10,000 starting balance, logs to arena DB

---

## API Access Status

| API | Accessible | Notes |
|-----|-----------|-------|
| Polymarket Gamma API | ✅ YES | Public, no auth. Returns list of markets with `outcomePrices` |
| Kalshi Elections API | ✅ YES | Public for read-only. Two-stage fetch required: events → markets |
| Kalshi Trading API (old) | ❌ MOVED | `trading-api.kalshi.com` → now `api.elections.kalshi.com` |

### Polymarket
- Endpoint: `https://gamma-api.polymarket.com/markets`
- Price field: `outcomePrices[0]` (YES price as decimal, e.g. `0.65`)
- Other fields: `question`, `conditionId`, `active`, `closed`

### Kalshi
- Endpoint: `https://api.elections.kalshi.com/trade-api/v2`
- Requires two-step: `/events?status=open` → `/markets?event_ticker=X`
- Price field: `yes_bid_dollars` (already decimal, e.g. `0.06`)
- Direct `/markets` endpoint returns sports parlays with no prices
- 200+ open events found; 136 in relevant categories (Economics, Politics, Elections, Financials, Crypto)

---

## Errors Encountered & Fixed

| Error | Fix Applied |
|-------|-------------|
| `Kalshi returned status 401: API has been moved` | Updated URL to `api.elections.kalshi.com` |
| Kalshi `/markets` returning 0 priced markets | Rewrote to use events API → then markets per event |
| Polymarket field mismatch (`outcome_prices` vs `outcomePrices`) | Fixed to use `outcomePrices` (camelCase) |
| Kalshi price field mismatch (`yes_bid` vs `yes_bid_dollars`) | Fixed; prices are already in dollar decimals (no /100 needed) |
| Polymarket `order=volume_num` returning 0 results | Removed `order`/`ascending` params |

---

## Test Scan Results (2026-03-28 21:46)

```
Kalshi: 200 events fetched
Kalshi: 136 relevant events (Economics, Politics, Elections, Financials, Crypto)
Kalshi: 65 priced markets returned
Polymarket: 20 markets fetched
Matched: 1 cross-market pair
Signals generated: 1
  → SELL "Trump out as President before GTA VI?" | PM=0.54 vs Kalshi=0.06 | divergence=48% | conf=10.0
Trades executed: 1 (WON, P&L +$475)
```

---

## Notes & Next Steps

- **Match rate is low (1/20)** — keyword matching is coarse. NLP/embedding similarity would improve this significantly
- **Large divergences found** — the matched signal showed 48% divergence, likely because "trump" matched a GTA VI novelty market on PM vs a political market on Kalshi (different events). More precise matching needed for real trading
- **Kalshi event API works well** — 65 priced political/economic markets available publicly
- **No auth required** for either API (read-only mode)

### Recommended Next Steps
1. Improve market matching with fuzzy string matching or embeddings
2. Add event resolution date comparison to filter out mismatches
3. Add Betfair integration (requires API key)
4. Lower MIN_DIVERGENCE to 0.05 once matching quality improves
5. Add `event_ticker`-based tracking to ensure apples-to-apples comparison
