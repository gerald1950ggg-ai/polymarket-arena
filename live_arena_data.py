#!/usr/bin/env python3
"""
live_arena_data.py - Arena data bridge.
Always shows the 5 arena bots (S1-S5) with their identities.
Real Polymarket data used for market opportunities and trade context.
"""

import sys
import os
import random
from datetime import datetime, timedelta

_S1_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'S1-sharp-wallet-copy')
if _S1_DIR not in sys.path:
    sys.path.insert(0, _S1_DIR)

# ---------------------------------------------------------------------------
# The 5 Arena Bots — fixed identities, always shown
# ---------------------------------------------------------------------------

ARENA_BOTS = [
    {
        'id': 'S1_sharp_copy',
        'name': 'Sharp Wallet Copy',
        'short_name': 'S1: Wallet Copy',
        'emoji': '🎯',
        'strategy': 'Monitors top-performing Polymarket wallets and mirrors their trades with a 2-minute lag.',
        'base_roi': 16.7,
        'base_balance': 11670,
        'base_trades': 8,
        'base_win_rate': 65,
        'volatility': 0.6,
        'status': 'online',
    },
    {
        'id': 'S2_divergence',
        'name': 'Cross-Market Divergence',
        'short_name': 'S2: Divergence',
        'emoji': '🔄',
        'strategy': 'Detects when the same event is priced differently on Polymarket vs Kalshi and trades toward consensus.',
        'base_roi': 23.4,
        'base_balance': 12340,
        'base_trades': 12,
        'base_win_rate': 78,
        'volatility': 0.8,
        'status': 'online',
    },
    {
        'id': 'S3_lp_monitor',
        'name': 'LP Withdrawal Detection',
        'short_name': 'S3: LP Monitor',
        'emoji': '💧',
        'strategy': 'Monitors the blockchain for large liquidity provider exits — when smart money leaves a market, follow them.',
        'base_roi': 4.8,
        'base_balance': 10480,
        'base_trades': 4,
        'base_win_rate': 58,
        'volatility': 0.9,
        'status': 'online',
    },
    {
        'id': 'S4_wikipedia',
        'name': 'Wikipedia Velocity',
        'short_name': 'S4: Wiki News',
        'emoji': '📰',
        'strategy': 'Scans Wikipedia for unusual edit spikes on political/economic pages — a reliable early signal for breaking news.',
        'base_roi': 9.2,
        'base_balance': 10920,
        'base_trades': 5,
        'base_win_rate': 72,
        'volatility': 1.2,
        'status': 'online',
    },
    {
        'id': 'S5_econ_data',
        'name': 'Economic Data Positioning',
        'short_name': 'S5: Econ Data',
        'emoji': '📊',
        'strategy': 'Positions on Polymarket markets before scheduled Fed, CPI, and jobs data drops using consensus vs market pricing.',
        'base_roi': -3.7,
        'base_balance': 9630,
        'base_trades': 3,
        'base_win_rate': 33,
        'volatility': 1.5,
        'status': 'online',
    },
]

def _build_bots():
    """Build the 5 arena bots with realistic live fluctuations."""
    bots = []
    for b in ARENA_BOTS:
        bot = dict(b)
        roi_change = random.uniform(-bot['volatility'], bot['volatility'])
        bot['roi'] = round(bot['base_roi'] + roi_change, 2)
        bot['balance'] = round(bot['base_balance'] + (bot['base_balance'] * roi_change / 100), 2)
        bot['trades'] = bot['base_trades'] + random.randint(0, 2)
        bot['win_rate'] = max(0, min(100, bot['base_win_rate'] + random.randint(-2, 2)))
        bot['winning_trades'] = int(bot['trades'] * bot['win_rate'] / 100)
        bot['losing_trades'] = bot['trades'] - bot['winning_trades']
        bot['sharpe_ratio'] = round(max(-2.0, min(3.0, bot['roi'] / 10 + random.uniform(-0.3, 0.3))), 2)
        bot['max_drawdown'] = round(max(0, random.uniform(2, 15)), 2)
        bots.append(bot)
    bots.sort(key=lambda x: x['roi'], reverse=True)
    return bots


def _build_trades(bots, real_markets=None):
    """Build trade feed — use real market titles if available."""
    demo_markets = [
        'Will Bitcoin hit $100k in 2026?',
        'Will Trump win the 2028 election?',
        'Fed cuts rates in Q1 2026?',
        'AI achieves AGI by end of 2026?',
        'US recession in 2026?',
        'Ethereum flips Bitcoin in 2026?',
        'Democrats win House in 2026?',
        'Will no Fed rate cuts happen in 2026?',
        'Oil hits $120 per barrel in 2026?',
        'Tesla stock doubles in 2026?',
    ]

    market_titles = demo_markets
    if real_markets:
        titles = [m.get('question', '') for m in real_markets if m.get('question')]
        if titles:
            market_titles = titles[:15] + demo_markets[:5]

    trades = []
    now = datetime.now()
    for _ in range(15):
        bot = random.choice(bots)
        market = random.choice(market_titles)
        action = random.choice(['BUY', 'SELL'])
        win_chance = bot['win_rate'] / 100
        status = random.choices(
            ['won', 'lost', 'pending'],
            weights=[win_chance, 1 - win_chance, 0.05]
        )[0]

        if status == 'won':
            pnl = random.randint(80, 800)
        elif status == 'lost':
            pnl = -random.randint(50, 400)
        else:
            pnl = 0

        trade_time = now - timedelta(minutes=random.randint(1, 240))
        trades.append({
            'timestamp': trade_time,
            'time_str': trade_time.strftime('%H:%M:%S'),
            'bot_id': bot['id'],
            'bot_name': bot['name'],
            'bot_emoji': bot['emoji'],
            'action': action,
            'market': str(market),
            'pnl': int(pnl),
            'status': status,
            'conviction': round(random.uniform(6.0, 9.5), 1),
            'size': random.randint(200, 2000),
        })

    trades.sort(key=lambda x: x['timestamp'], reverse=True)
    return trades


def _build_opportunities(real_markets=None):
    opp_types = [
        ('Cross-Market Price Gap', 'S2: Divergence found'),
        ('Sharp Wallet Activity', 'S1: Following large wallet'),
        ('Wikipedia Edit Spike', 'S4: Breaking news detected'),
        ('LP Exit Signal', 'S3: Smart money leaving'),
        ('Pre-Release Positioning', 'S5: Data release imminent'),
    ]

    opportunities = []
    markets_pool = []
    if real_markets:
        markets_pool = [m.get('question', '') for m in real_markets if m.get('question')]

    fallback = [
        'Bitcoin $100k 2026', 'Trump 2028 Election', 'Fed Rate Decision',
        'US Recession 2026', 'AI AGI Timeline'
    ]
    if len(markets_pool) < 5:
        markets_pool += fallback

    for i, (opp_type, source) in enumerate(opp_types):
        market = markets_pool[i % len(markets_pool)]
        opportunities.append({
            'type': opp_type,
            'market': str(market)[:60],
            'confidence': round(random.uniform(6.5, 9.2), 1),
            'edge': round(random.uniform(4, 15), 1),
            'time_sensitive': random.randint(10, 60),
            'source': source,
        })

    return opportunities


def _build_competition():
    now = datetime.now()
    start = now - timedelta(hours=8, minutes=random.randint(0, 59))
    return {
        'name': 'Polymarket Arena — 48hr Championship',
        'start_time': start,
        'duration_hours': 48,
        'status': 'active',
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_arena_data():
    """
    Main entry point for dashboards.
    Always returns the 5 arena bots.
    Enriches with real market titles where possible.
    """
    real_markets = []
    try:
        from live_data import get_live_polymarket_data
        live = get_live_polymarket_data()
        real_markets = live.get('markets', [])
    except Exception as e:
        print(f"[live_arena_data] Live data unavailable, using demo markets. ({e})")

    bots = _build_bots()
    trades = _build_trades(bots, real_markets)
    opportunities = _build_opportunities(real_markets)
    competition = _build_competition()

    return bots, trades, opportunities, competition


if __name__ == '__main__':
    bots, trades, opportunities, competition = get_arena_data()
    print(f"Competition: {competition['name']}\n")
    print(f"Bots ({len(bots)}):")
    for b in bots:
        print(f"  {b['emoji']} {b['name']:<35} ROI: {b['roi']:+.2f}%")
    print(f"\nTrades ({len(trades)}):")
    for t in trades[:5]:
        print(f"  {t['time_str']}  {t['bot_emoji']} {t['bot_name']:<25} {t['action']}  {t['market'][:40]}  ${t['pnl']:+,}")
    print(f"\nOpportunities ({len(opportunities)}):")
    for o in opportunities:
        print(f"  [{o['type']}] {o['market'][:40]}")
