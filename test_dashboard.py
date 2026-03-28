#!/usr/bin/env python3
"""
Test the arena database and dashboard setup
"""

import asyncio
import time
from arena_database import ArenaDatabase

def setup_demo_data():
    """Create some demo data for dashboard testing"""
    db = ArenaDatabase()
    
    # Register 5 bots
    bots = [
        ("S1_sharp_copy", "Sharp Wallet Copy", "Monitors high-performing wallets and copies trades"),
        ("S2_divergence", "Cross-Market Divergence", "Detects price differences across prediction markets"),
        ("S3_lp_monitor", "LP Withdrawal Detection", "Monitors liquidity provider exits"),
        ("S4_wikipedia", "Wikipedia Edit Velocity", "Detects breaking news via Wikipedia edit spikes"),
        ("S5_econ_data", "Economic Data Positioning", "Positions before scheduled data releases")
    ]
    
    for bot_id, name, description in bots:
        db.register_bot(bot_id, name, description, 10000.0)
        db.heartbeat(bot_id, 'active', 'demo_mode')
    
    # Create some sample trades
    trades = [
        {
            'bot_id': 'S1_sharp_copy',
            'market_title': 'Will Bitcoin hit $100k in 2026?',
            'action': 'BUY',
            'size': 1500,
            'price': 0.67,
            'conviction_score': 8.5,
            'expected_roi': 0.15,
            'status': 'executed'
        },
        {
            'bot_id': 'S2_divergence', 
            'market_title': 'Will Trump win 2026?',
            'action': 'BUY',
            'size': 2000,
            'price': 0.45,
            'conviction_score': 7.2,
            'expected_roi': 0.22,
            'status': 'executed'
        },
        {
            'bot_id': 'S3_lp_monitor',
            'market_title': 'Will Fed cut rates in Q1?',
            'action': 'SELL',
            'size': 800,
            'price': 0.35,
            'conviction_score': 6.8,
            'expected_roi': 0.18,
            'status': 'pending'
        }
    ]
    
    for trade in trades:
        db.log_trade(trade)
    
    # Update bot performances with realistic data
    performances = [
        {
            'bot_id': 'S1_sharp_copy',
            'total_trades': 5,
            'winning_trades': 3,
            'losing_trades': 2,
            'total_roi': 12.5,
            'current_balance': 11250.0,
            'win_rate': 0.6,
            'sharpe_ratio': 1.8,
            'max_drawdown': 5.2
        },
        {
            'bot_id': 'S2_divergence',
            'total_trades': 8,
            'winning_trades': 6,
            'losing_trades': 2,
            'total_roi': 18.7,
            'current_balance': 11870.0,
            'win_rate': 0.75,
            'sharpe_ratio': 2.3,
            'max_drawdown': 3.1
        },
        {
            'bot_id': 'S3_lp_monitor',
            'total_trades': 3,
            'winning_trades': 2,
            'losing_trades': 1,
            'total_roi': 7.2,
            'current_balance': 10720.0,
            'win_rate': 0.67,
            'sharpe_ratio': 1.2,
            'max_drawdown': 2.8
        },
        {
            'bot_id': 'S4_wikipedia',
            'total_trades': 2,
            'winning_trades': 1,
            'losing_trades': 1,
            'total_roi': -2.3,
            'current_balance': 9770.0,
            'win_rate': 0.5,
            'sharpe_ratio': 0.3,
            'max_drawdown': 8.4
        },
        {
            'bot_id': 'S5_econ_data',
            'total_trades': 1,
            'winning_trades': 0,
            'losing_trades': 1,
            'total_roi': -5.8,
            'current_balance': 9420.0,
            'win_rate': 0.0,
            'sharpe_ratio': -0.8,
            'max_drawdown': 12.1
        }
    ]
    
    for perf in performances:
        db.update_bot_performance(perf['bot_id'], perf)
    
    # Add some market opportunities
    opportunities = [
        {
            'type': 'price_divergence',
            'market_title': 'Bitcoin $100k 2026',
            'confidence_score': 8.5,
            'expected_edge': 0.12,
            'time_sensitivity_minutes': 45,
            'data_source': 'Polymarket vs Kalshi'
        },
        {
            'type': 'sharp_wallet_activity',
            'market_title': 'Fed rate cuts',
            'confidence_score': 7.2,
            'expected_edge': 0.08,
            'time_sensitivity_minutes': 30,
            'data_source': 'Wallet 0x123...789'
        }
    ]
    
    for opp in opportunities:
        db.log_opportunity('S2_divergence', opp)
    
    # Start a competition
    competition_id = db.start_competition("Demo Arena Competition", 48)
    
    print(f"🎯 Demo data created!")
    print(f"📊 5 bots registered")
    print(f"💹 {len(trades)} sample trades logged") 
    print(f"🏁 Competition #{competition_id} started")
    print(f"🎮 Dashboard ready!")

if __name__ == "__main__":
    setup_demo_data()