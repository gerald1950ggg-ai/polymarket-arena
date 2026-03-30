# 🕵️ Shadow Mode Status

**Built:** 2026-03-29  
**Commit:** 761fe68  
**Status:** ✅ Complete

## What Was Built

### Core Files
- **`shadow_log.py`** — SQLite-backed signal logger. Stores real bot signals with full context. Functions: `log_signal()`, `get_signals()`, `resolve_signal()`, `get_shadow_stats()`. DB: `shadow.db`.
- **`shadow_page.py`** — Standalone Streamlit app showing the full signal journal with filters, P&L summary, and styled signal cards.

### Bot Updates (S1–S5)
All 5 bots now call `shadow_log.log_signal()` instead of fake paper trades with `random.random()`:

| Bot | File | Signal Style |
|-----|------|-------------|
| S1 Sharp Wallet Copy | `S1-sharp-wallet-copy/arena_bot.py` | "Wallet 0xABC... just took a position..." |
| S2 Cross-Market Divergence | `S2-cross-market/divergence_bot.py` | "X% gap vs Kalshi — markets should converge..." |
| S3 LP Monitor | `S3-lp-monitor/lp_bot.py` | "N LP merges removing $X collateral — smart money exiting..." |
| S4 Wikipedia Velocity | `S4-wikipedia/wiki_bot.py` | "Page 'X' got N edits in 5min [LEVEL] signal..." |
| S5 Economic Data | `S5-econ-data/econ_bot.py` | "Event 'X' in Nh — edge reason — position before reprice..." |

### Dashboard Update
- `app.py` — Added **"🕵️ Shadow Signals"** as 4th tab in the performance charts section
- Shows: stats row (total/pending/won/lost/win rate), P&L summary, full signal cards

## How It Works

1. **Signal logging** — Bots detect real signals from live Polymarket data and call `shadow_log_signal()` with human-readable explanations
2. **No fake P&L** — No more `random.random()` to determine outcomes; resolution is tracked separately
3. **Real scoring** — When a market resolves, call `resolve_signal(signal_id, resolved_price)` where `1.0` = YES won, `0.0` = NO won
4. **P&L calculation** — Retroactive P&L uses real entry price and shadow size against actual resolution price

## P&L Formula
```
BUY signal: shares = shadow_size / entry_price; pnl = shares * resolved_price - shadow_size
SELL signal: no_price = 1 - entry_price; shares = shadow_size / no_price; pnl = shares * (1 - resolved_price) - shadow_size
```

## Test Results
```
✅ shadow_log.py — logged signal #1, stats returned correctly
✅ All 5 bot files compiled without errors
✅ app.py compiled without errors
✅ Pushed to GitHub main (commit 761fe68)
```

## To View Shadow Signals
- Open the main arena dashboard → "🕵️ Shadow Signals" tab
- Or run standalone: `streamlit run shadow_page.py`

## To Resolve a Signal
```python
from shadow_log import resolve_signal
resolve_signal(signal_id=1, resolved_price=1.0)  # YES won
resolve_signal(signal_id=2, resolved_price=0.0)  # NO won (YES lost)
```
