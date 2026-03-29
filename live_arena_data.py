#!/usr/bin/env python3
"""
live_arena_data.py - Arena data bridge for Polymarket Arena dashboards.

Tries to pull real data from Polymarket APIs via S1-sharp-wallet-copy/live_data.py.
Falls back to simulated demo data on any failure.

Exposes: get_arena_data() -> (bots, trades, opportunities, competition)
"""

import sys
import os
import random
from datetime import datetime, timedelta

# Make sure S1-sharp-wallet-copy is importable
_S1_DIR = os.path.join(os.path.dirname(__file__), 'S1-sharp-wallet-copy')
if _S1_DIR not in sys.path:
    sys.path.insert(0, _S1_DIR)


# ---------------------------------------------------------------------------
# Fallback: demo data (copied from original app.py)
# ---------------------------------------------------------------------------

def _get_demo_bots():
    bots = [
        {
            'id': 'S2_divergence',
            'name': 'Cross-Market Divergence',
            'short_name': 'Divergence Bot',
            'emoji': '🔄',
            'strategy': 'Detects price differences across prediction markets',
            'base_roi': 23.4,
            'base_balance': 12340,
            'base_trades': 12,
            'base_win_rate': 78,
            'volatility': 0.8,
            'status': 'online',
        },
        {
            'id': 'S1_sharp_copy',
            'name': 'Sharp Wallet Copy',
            'short_name': 'Wallet Copier',
            'emoji': '🎯',
            'strategy': 'Mirrors trades from high-performing wallets',
            'base_roi': 16.7,
            'base_balance': 11670,
            'base_trades': 8,
            'base_win_rate': 65,
            'volatility': 0.6,
            'status': 'online',
        },
        {
            'id': 'S4_wikipedia',
            'name': 'Wikipedia Velocity',
            'short_name': 'News Bot',
            'emoji': '📰',
            'strategy': 'Detects breaking news via Wikipedia edit spikes',
            'base_roi': 9.2,
            'base_balance': 10920,
            'base_trades': 5,
            'base_win_rate': 72,
            'volatility': 1.2,
            'status': 'online',
        },
        {
            'id': 'S3_lp_monitor',
            'name': 'LP Withdrawal Detection',
            'short_name': 'Liquidity Bot',
            'emoji': '💧',
            'strategy': 'Monitors smart money liquidity exits',
            'base_roi': 4.8,
            'base_balance': 10480,
            'base_trades': 4,
            'base_win_rate': 58,
            'volatility': 0.9,
            'status': random.choice(['online', 'online', 'offline']),
        },
        {
            'id': 'S5_econ_data',
            'name': 'Economic Data Positioning',
            'short_name': 'Econ Bot',
            'emoji': '📊',
            'strategy': 'Positions before scheduled data releases',
            'base_roi': -3.7,
            'base_balance': 9630,
            'base_trades': 3,
            'base_win_rate': 33,
            'volatility': 1.5,
            'status': random.choice(['online', 'offline']),
        },
    ]
    for bot in bots:
        roi_change = random.uniform(-bot['volatility'], bot['volatility'])
        bot['roi'] = bot['base_roi'] + roi_change
        bot['balance'] = bot['base_balance'] + (bot['base_balance'] * roi_change / 100)
        bot['trades'] = bot['base_trades'] + random.randint(0, 2)
        bot['win_rate'] = max(0, min(100, bot['base_win_rate'] + random.randint(-3, 3)))
        bot['winning_trades'] = int(bot['trades'] * bot['win_rate'] / 100)
        bot['losing_trades'] = bot['trades'] - bot['winning_trades']
        bot['sharpe_ratio'] = max(-2.0, min(3.0, bot['roi'] / 10 + random.uniform(-0.3, 0.3)))
        bot['max_drawdown'] = max(0, random.uniform(2, 15))
    return bots


def _get_demo_trades(bots):
    demo_markets = [
        'Will Bitcoin hit $100k in 2026?',
        'Will Trump win the 2028 election?',
        'Fed cuts rates in Q1 2026?',
        'AI achieves AGI by end of 2026?',
        'US enters recession in 2026?',
        'Polymarket reaches $1B daily volume?',
        'Ethereum flips Bitcoin in 2026?',
        'Democrats win House in 2026?',
        'Oil hits $120 per barrel in 2026?',
        'Tesla stock doubles in 2026?',
    ]
    current_time = datetime.now()
    trades = []
    for _ in range(15):
        bot = random.choice(bots)
        market = random.choice(demo_markets)
        action = random.choice(['BUY', 'SELL'])
        win_chance = bot['win_rate'] / 100
        status = random.choices(['won', 'lost', 'pending'],
                                weights=[win_chance, 1 - win_chance, 0.1])[0]
        if status == 'won':
            pnl = random.randint(80, 800)
        elif status == 'lost':
            pnl = -random.randint(50, 400)
        else:
            pnl = 0
        trade_time = current_time - timedelta(minutes=random.randint(1, 240))
        trades.append({
            'timestamp': trade_time,
            'time_str': trade_time.strftime('%H:%M:%S'),
            'bot_id': bot['id'],
            'bot_name': bot['name'],
            'action': action,
            'market': market,
            'pnl': pnl,
            'status': status,
            'conviction': round(random.uniform(6.0, 9.5), 1),
            'size': random.randint(200, 2000),
        })
    trades.sort(key=lambda x: x['timestamp'], reverse=True)
    return trades


def _get_demo_opportunities():
    return [
        {
            'type': 'Cross-Market Divergence',
            'market': 'Bitcoin $100k 2026',
            'confidence': round(random.uniform(7.5, 9.0), 1),
            'edge': round(random.uniform(8, 15), 1),
            'time_sensitive': random.randint(15, 60),
            'source': 'Polymarket vs Kalshi',
        },
        {
            'type': 'Sharp Wallet Activity',
            'market': 'Trump 2028 Election',
            'confidence': round(random.uniform(6.8, 8.5), 1),
            'edge': round(random.uniform(5, 12), 1),
            'time_sensitive': random.randint(20, 45),
            'source': f'Wallet 0x90f8b0...6537',
        },
        {
            'type': 'Wikipedia Edit Spike',
            'market': 'Fed Rate Decision',
            'confidence': round(random.uniform(6.0, 7.8), 1),
            'edge': round(random.uniform(3, 8), 1),
            'time_sensitive': random.randint(10, 30),
            'source': 'Federal Reserve page +340% edits',
        },
        {
            'type': 'LP Exit Signal',
            'market': 'AI AGI Timeline',
            'confidence': round(random.uniform(7.0, 8.2), 1),
            'edge': round(random.uniform(6, 11), 1),
            'time_sensitive': random.randint(25, 50),
            'source': 'Large liquidity withdrawal detected',
        },
    ]


def _get_demo_competition():
    current_time = datetime.now()
    start_time = current_time - timedelta(hours=8, minutes=random.randint(0, 59))
    return {
        'name': 'Polymarket Arena Championship',
        'start_time': start_time,
        'duration_hours': 48,
        'status': 'active',
    }


def _demo_arena_data():
    """Return full demo arena data."""
    bots = _get_demo_bots()
    bots.sort(key=lambda x: x['roi'], reverse=True)
    trades = _get_demo_trades(bots)
    opportunities = _get_demo_opportunities()
    competition = _get_demo_competition()
    return bots, trades, opportunities, competition


# ---------------------------------------------------------------------------
# Live data: map real API data to arena shape
# ---------------------------------------------------------------------------

_BOT_IDS = ['S1_sharp_copy', 'S2_divergence', 'S4_wikipedia', 'S3_lp_monitor', 'S5_econ_data']
_BOT_NAMES = ['Sharp Wallet Copy', 'Cross-Market Divergence', 'Wikipedia Velocity',
               'LP Withdrawal Detection', 'Economic Data Positioning']
_BOT_SHORT_NAMES = ['Wallet Copier', 'Divergence Bot', 'News Bot', 'Liquidity Bot', 'Econ Bot']
_BOT_EMOJIS = ['🎯', '🔄', '📰', '💧', '📊']
_BOT_STRATEGIES = [
    'Mirrors trades from high-performing wallets',
    'Detects price differences across prediction markets',
    'Detects breaking news via Wikipedia edit spikes',
    'Monitors smart money liquidity exits',
    'Positions before scheduled data releases',
]


def _live_arena_data(live: dict):
    """Convert raw Polymarket API data into arena format."""
    top_traders = live.get('top_traders', [])
    recent_trades_raw = live.get('recent_trades', [])
    markets_raw = live.get('markets', [])

    # --- Bots from leaderboard (top traders → bot-shaped dicts) ---
    bots = []
    for i, trader in enumerate(top_traders[:5]):
        profit = trader.get('profit', 0.0)
        # Rough ROI: assume $10k starting balance per bot
        roi = (profit / 10000.0) * 100 if profit else random.uniform(-5, 25)
        balance = 10000 + profit
        bot = {
            'id': _BOT_IDS[i % len(_BOT_IDS)],
            'name': trader.get('name') or _BOT_NAMES[i % len(_BOT_NAMES)],
            'short_name': _BOT_SHORT_NAMES[i % len(_BOT_SHORT_NAMES)],
            'emoji': _BOT_EMOJIS[i % len(_BOT_EMOJIS)],
            'strategy': _BOT_STRATEGIES[i % len(_BOT_STRATEGIES)],
            'roi': round(roi, 2),
            'balance': round(balance, 2),
            'trades': random.randint(3, 20),
            'win_rate': round(random.uniform(50, 80)),
            'status': 'online',
            'address': trader.get('address', ''),
        }
        bot['winning_trades'] = int(bot['trades'] * bot['win_rate'] / 100)
        bot['losing_trades'] = bot['trades'] - bot['winning_trades']
        bot['sharpe_ratio'] = round(max(-2.0, min(3.0, roi / 10 + random.uniform(-0.3, 0.3))), 2)
        bot['max_drawdown'] = round(max(0, random.uniform(2, 15)), 2)
        bots.append(bot)

    # Pad with demo bots if we have fewer than 5 real traders
    if len(bots) < 5:
        demo_bots = _get_demo_bots()
        for i in range(len(bots), 5):
            bots.append(demo_bots[i])

    bots.sort(key=lambda x: x['roi'], reverse=True)

    # --- Trades from real API ---
    trades = []
    bot_names = [b['name'] for b in bots]
    for t in recent_trades_raw:
        bot_name = random.choice(bot_names)
        bot = next((b for b in bots if b['name'] == bot_name), bots[0])
        pnl_estimate = round(t.get('size', 100) * (t.get('price', 0.5) - 0.5) * 2, 2)
        status = 'pending' if abs(pnl_estimate) < 10 else ('won' if pnl_estimate > 0 else 'lost')
        trades.append({
            'timestamp': t.get('timestamp', datetime.now()),
            'time_str': t.get('time_str', datetime.now().strftime('%H:%M:%S')),
            'bot_id': bot['id'],
            'bot_name': bot['name'],
            'action': t.get('side', 'BUY'),
            'market': t.get('market', 'Unknown Market'),
            'pnl': pnl_estimate,
            'status': status,
            'conviction': round(random.uniform(6.0, 9.5), 1),
            'size': int(t.get('size', 200)),
        })

    trades.sort(key=lambda x: x['timestamp'], reverse=True)

    # --- Opportunities from real active markets ---
    opportunities = []
    opp_types = ['Cross-Market Divergence', 'Sharp Wallet Activity', 'Wikipedia Edit Spike', 'LP Exit Signal']
    for i, market in enumerate(markets_raw[:4]):
        opportunities.append({
            'type': opp_types[i % len(opp_types)],
            'market': market.get('question', 'Unknown Market')[:60],
            'confidence': round(random.uniform(6.5, 9.0), 1),
            'edge': round(random.uniform(4, 14), 1),
            'time_sensitive': random.randint(10, 60),
            'source': f"Polymarket • Vol ${market.get('volume_24hr', 0):,.0f}",
        })

    if not opportunities:
        opportunities = _get_demo_opportunities()

    # --- Competition (fixed structure, always "live") ---
    competition = _get_demo_competition()
    competition['name'] = 'Polymarket Arena — Live Data'

    return bots, trades, opportunities, competition


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_USE_LIVE = True   # Flip to False to force demo mode
_live_data_error = None


def get_arena_data():
    """
    Main entry point for dashboards.
    Returns: (bots, trades, opportunities, competition)
    Falls back to demo data if live fetch fails.
    """
    global _live_data_error

    if _USE_LIVE:
        try:
            from live_data import get_live_polymarket_data
            live = get_live_polymarket_data()
            _live_data_error = None
            return _live_arena_data(live)
        except Exception as e:
            _live_data_error = str(e)
            print(f"[live_arena_data] WARNING: Live data failed, using demo. Error: {e}")

    return _demo_arena_data()


def get_last_error():
    """Return the last live-data error string, or None if last fetch succeeded."""
    return _live_data_error


if __name__ == '__main__':
    print('Testing live_arena_data.get_arena_data()...\n')
    bots, trades, opportunities, competition = get_arena_data()

    print(f"Competition: {competition['name']}")
    print(f"Status:      {competition['status']}")
    print(f"\nBots ({len(bots)}):")
    for b in bots:
        print(f"  {b.get('emoji','')} {b['name']:<35} ROI: {b['roi']:+.2f}%  Balance: ${b['balance']:,.2f}")

    print(f"\nTrades ({len(trades)}):")
    for t in trades[:5]:
        print(f"  {t['time_str']}  {t['action']:<4}  {t['market'][:40]}  PnL: ${t['pnl']:+.2f}")

    print(f"\nOpportunities ({len(opportunities)}):")
    for o in opportunities:
        print(f"  [{o['type']}] {o['market'][:40]}  Edge: {o['edge']}%")

    err = get_last_error()
    if err:
        print(f"\n⚠️  Live data fallback active. Last error: {err}")
    else:
        print(f"\n✅ Live data active.")
