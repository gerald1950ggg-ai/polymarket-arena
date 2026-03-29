# S5 — Economic Data Positioning Bot

## Strategy Overview

S5 monitors scheduled macroeconomic data releases and positions on related Polymarket markets **before** the data drops. The core edge comes from **consensus estimate divergence** — when what Wall Street economists expect differs meaningfully from what Polymarket's binary market has priced in.

## Why This Works

Polymarket binary markets often lag institutional consensus data. When a CPI report is widely expected to come in at 3.2% but the binary "CPI above 3%?" market is trading at 45%, there's an exploitable gap. S5 identifies and trades these gaps systematically.

## Data Sources (Production)

| Source | Data | Access |
|--------|------|--------|
| CME FedWatch | Fed funds futures probabilities | Free web scrape |
| Atlanta Fed GDPNow | Real-time GDP tracker | Free API |
| FRED API | Historical economic data | Free, no key required |
| Econoday | Economic event calendar | Free tier |
| Federal Reserve | Official FOMC calendar | Public website |
| Consensus Economics | Economist survey forecasts | Subscription |

## Economic Events Monitored

1. **FOMC Rate Decisions** (8x/year, ~every 6 weeks)
   - Edge: CME FedWatch futures vs binary market price
   - Historical accuracy: Fed futures within 10bps of outcome in 70%+ of cases

2. **CPI Inflation Report** (monthly, 2nd-3rd week)
   - Edge: Sub-component analysis (shelter, energy) predicts headline
   - Economist consensus survey has ~15bp standard deviation

3. **Non-Farm Payrolls** (first Friday of month)
   - Edge: ADP private payrolls report drops 2 days before — leading indicator
   - ISM employment sub-index also predictive

4. **GDP Growth** (quarterly, 3 releases: advance/second/final)
   - Edge: GDPNow real-time tracker often more accurate than consensus
   - Soft data (PMI, confidence surveys) feeds prediction

5. **PCE Price Index** (monthly, ~4 weeks after reference month)
   - Edge: CPI drops first and ~65% of PCE categories map directly
   - Fed's preferred inflation measure → huge market impact

6. **Initial Jobless Claims** (weekly, Thursdays)
   - Edge: Tight consensus range, predictable from state-level data
   - Leading indicator for NFP

## Signal Generation Logic

```
For each economic event type:
  1. Scan Polymarket for markets with matching keywords
  2. Get current binary market price
  3. Fetch consensus estimate for upcoming release
  4. Calculate divergence: |consensus_implied_prob - market_price|
  5. If divergence > threshold AND confidence > 6.0:
     → Generate EconSignal with direction and conviction
```

## Position Sizing

- **Base size**: 4% of balance per trade
- **Time decay**: Reduce size for distant events (uncertainty scales with time)
- **Max per scan**: 2 trades to prevent over-concentration
- **Formula**: `size = balance × 0.04 × time_factor × confidence_scalar`

## Win Rate Model

Theoretical basis for outperformance:
- Economic consensus beats the market ~58% on binary outcomes
- Time decay reduces this to ~52% for events >48 hours out
- Net Sharpe ratio target: >1.0 over full cycle

## Risk Management

- **No position > $400** regardless of balance
- **Max 2 trades per scan** (every 3 minutes)
- **Skip near-certainty markets** (>99% or <1%) — no edge there
- **Event type diversification** — one signal per event category per scan

## Architecture

```
EconomicDataBot
├── get_upcoming_econ_events()    # Rolling calendar of 6 event types
├── get_polymarket_markets()      # Live market data from gamma API
├── match_markets_to_events()     # Keyword match + price filter
├── estimate_consensus_edge()     # Category-specific edge calculation
├── execute_paper_trade()         # Log to arena_database.py
└── run_forever()                 # 3-minute loop
```

## Bot ID

`S5_econ_data` — registered in arena_database, visible on Streamlit dashboard

## Status

- ✅ Paper trading mode (no real money)
- ✅ Writes to shared arena.db
- ✅ Integrated with arena dashboard
- 🔜 Production: add real consensus data APIs, FRED integration

## Future Enhancements

1. **FRED API integration** — fetch actual historical data to calibrate priors
2. **Event calendar sync** — pull real release dates from Econoday
3. **Sentiment scraping** — Wall Street Journal, Bloomberg headlines
4. **Polymarket CLOB** — switch to order book API for better price data
5. **Options market cross-reference** — VIX futures implied vol around events
