#!/usr/bin/env python3
"""
live_data.py - Real Polymarket data fetcher for S1 Sharp Wallet Copy bot
Uses polymarket-apis library to pull live markets, leaderboard, and trades.
"""

import sys
from datetime import datetime

WATCHED_WALLET = '0x90f8b0fee21e920e81d1ca4da6d215152f576537'


def get_live_polymarket_data() -> dict:
    """
    Fetch real live data from Polymarket APIs.
    Returns dict with keys: markets, top_traders, recent_trades
    Raises on failure — callers should wrap in try/except.
    """
    from polymarket_apis import PolymarketDataClient, PolymarketGammaClient

    data_client = PolymarketDataClient()
    gamma_client = PolymarketGammaClient()

    # --- Active Markets ---
    markets_raw = gamma_client.get_markets(limit=20, active=True, closed=False)
    markets = []
    for m in markets_raw:
        prices = []
        if m.outcome_prices:
            try:
                prices = [float(p) for p in m.outcome_prices]
            except (ValueError, TypeError):
                prices = []

        markets.append({
            'id': m.condition_id or m.id,
            'question': m.question or 'Unknown Market',
            'category': m.category or 'General',
            'volume': float(m.volume_num or m.volume or 0),
            'volume_24hr': float(m.volume_24hr or 0),
            'liquidity': float(m.liquidity_num or m.liquidity or 0),
            'outcomes': m.outcomes or ['Yes', 'No'],
            'outcome_prices': prices,
            'end_date': str(m.end_date_iso or m.end_date or ''),
            'active': m.active,
            'slug': m.slug or '',
        })

    # --- Leaderboard Top Traders ---
    top_users_raw = data_client.get_leaderboard_top_users(window='7d', limit=10)
    top_traders = []
    for u in top_users_raw:
        top_traders.append({
            'address': u.proxy_wallet or '',
            'name': u.name or u.pseudonym or (u.proxy_wallet[:8] + '...' if u.proxy_wallet else 'Unknown'),
            'profit': float(u.amount or 0),
            'volume': 0.0,  # UserMetric.amount is profit by default
            'roi': 0.0,     # Not directly available from this endpoint
        })

    # --- Recent Trades: try watched wallet first, fall back to general feed ---
    trades_raw = data_client.get_trades(user=WATCHED_WALLET, limit=20, taker_only=False)
    if not trades_raw:
        # Wallet has no trades — pull general market activity instead
        trades_raw = data_client.get_trades(limit=20)
    recent_trades = []
    for t in trades_raw:
        try:
            ts = t.timestamp
            if isinstance(ts, (int, float)):
                trade_dt = datetime.fromtimestamp(ts / 1000 if ts > 1e10 else ts)
            elif isinstance(ts, str):
                trade_dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            else:
                trade_dt = ts or datetime.now()
        except Exception:
            trade_dt = datetime.now()

        recent_trades.append({
            'wallet': WATCHED_WALLET,
            'side': t.side or 'BUY',
            'size': float(t.size or 0),
            'price': float(t.price or 0),
            'timestamp': trade_dt,
            'time_str': trade_dt.strftime('%H:%M:%S'),
            'market': t.title or t.slug or 'Unknown Market',
            'outcome': t.outcome or '',
            'tx_hash': t.transaction_hash or '',
        })

    return {
        'markets': markets,
        'top_traders': top_traders,
        'recent_trades': recent_trades,
        'fetched_at': datetime.now(),
    }


if __name__ == '__main__':
    print('Fetching live Polymarket data...')
    try:
        data = get_live_polymarket_data()
        print(f"\n✅ SUCCESS")
        print(f"  Markets fetched: {len(data['markets'])}")
        print(f"  Top traders:     {len(data['top_traders'])}")
        print(f"  Recent trades:   {len(data['recent_trades'])}")

        if data['markets']:
            print(f"\n  Sample market: {data['markets'][0]['question']}")
            print(f"    Volume 24h: ${data['markets'][0]['volume_24hr']:,.0f}")

        if data['top_traders']:
            t = data['top_traders'][0]
            print(f"\n  Top trader: {t['name']}")
            print(f"    7d profit: ${t['profit']:,.2f}")

        if data['recent_trades']:
            tr = data['recent_trades'][0]
            print(f"\n  Latest trade: {tr['side']} {tr['outcome']} @ {tr['price']:.3f}")
            print(f"    Market: {tr['market']}")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
