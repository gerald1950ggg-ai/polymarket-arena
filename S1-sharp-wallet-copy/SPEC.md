# S1: Sharp Wallet Copy-Trading

## Strategy Overview

Identify high-performing wallets on Polymarket and mirror their trades with a configurable delay. The thesis: sharp traders have already done the research — we're paying for their alpha via copy-trading.

## Core Components

### 1. Wallet Discovery & Ranking
- **Scan Polygon blockchain** for Polymarket contract interactions
- **Build wallet performance database** 
  - Win rate by wallet over last 90 days
  - Average bet size (filter out micro-bets)  
  - Total PnL
  - Market diversity (avoid single-market specialists)
- **Minimum criteria for "sharp" classification:**
  - Win rate >65% 
  - 20+ bets in last 90 days
  - Average bet >$100 equivalent
  - Active in 5+ different markets

### 2. Real-Time Trade Monitoring
- **WebSocket connection** to Polygon node
- **Contract event filtering** for Polymarket trade events
- **Wallet whitelist matching** against sharp wallet database
- **Trade parsing** to extract:
  - Market ID
  - Position (YES/NO)
  - Size
  - Price
  - Timestamp

### 3. Copy Logic & Risk Management
- **Lag parameter**: 2-5 minute delay to avoid front-running detection
- **Position sizing**: 
  - Max 5% of portfolio per trade
  - Scale based on sharp trader's conviction (bet size relative to their typical)
- **Market filtering**:
  - Only copy trades on markets with >$10k liquidity
  - Avoid markets <24hrs from resolution
  - Skip if current market odds moved >15% since sharp trader's entry

### 4. Exit Strategy
- **Follow the leader**: If sharp trader exits, we exit
- **Time-based stops**: Close all positions 6 hours before market resolution
- **Loss limits**: -20% stop loss per position

## Technical Architecture

```
[Polygon Node] → [Event Parser] → [Wallet Filter] → [Copy Engine] → [Paper Trading API]
       ↓                ↓               ↓              ↓
[Wallet Analytics] [Trade Logger] [Risk Checks] [Performance Tracker]
```

## Data Sources

1. **Polygon RPC endpoint** for real-time blockchain events
2. **Polymarket subgraph** for historical wallet performance  
3. **Polymarket API** for market metadata and current odds

## Success Metrics

- **Primary**: Net ROI over 48 hours
- **Secondary**: Win rate, Sharpe ratio, max drawdown
- **Tertiary**: Number of copied trades, average lag time

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Sharp trader turns cold | Continuous reranking, remove underperformers |
| Front-running by others | Random lag (2-5 min), small position sizes |
| Market manipulation | Liquidity filters, market maturity checks |
| API rate limits | Caching, request batching |

## Implementation Priority

**Week 1**: Wallet discovery + ranking system  
**Week 2**: Real-time monitoring + copy engine  
**Week 3**: Risk management + paper trading integration  
**Week 4**: Performance tracking + optimization

---

Next: Begin wallet discovery pipeline