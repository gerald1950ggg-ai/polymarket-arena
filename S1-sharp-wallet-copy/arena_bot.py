#!/usr/bin/env python3
"""
Arena-integrated version of the Sharp Wallet Copy bot
Writes performance data to shared database for Streamlit dashboard
"""

import asyncio
import sys
import os
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from arena_database import ArenaDatabase
from working_hybrid import WorkingHybridMonitor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ArenaSharpWalletBot(WorkingHybridMonitor):
    """Arena-integrated Sharp Wallet Copy bot"""
    
    def __init__(self):
        super().__init__()
        self.bot_id = "S1_sharp_copy"
        self.bot_name = "Sharp Wallet Copy"
        self.strategy_description = "Monitors high-performing wallets and copies their trades with 2% position sizing"
        
        # Arena database connection
        self.arena_db = ArenaDatabase()
        
        # Performance tracking
        self.starting_balance = 10000.0
        self.current_balance = 10000.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.trade_history = []
        
        # Register with arena
        self.arena_db.register_bot(
            self.bot_id, 
            self.bot_name, 
            self.strategy_description,
            self.starting_balance
        )
        
        logger.info(f"🤖 {self.bot_name} initialized for arena competition")
    
    async def execute_copy_trade(self, trade_decision: dict):
        """Execute copy trade and log to arena database"""
        # Simulate trade execution (paper trading)
        trade_size = trade_decision['copy_size']
        expected_price = trade_decision.get('current_price', 0.65)
        
        # Paper trade logic
        trade_cost = trade_size * expected_price
        if trade_cost > self.current_balance * 0.1:  # Max 10% per trade
            trade_size = (self.current_balance * 0.1) / expected_price
            trade_cost = trade_size * expected_price
        
        # Execute the trade
        self.current_balance -= trade_cost
        self.total_trades += 1
        
        # Simulate trade outcome (for demo purposes)
        import random
        success_chance = min(trade_decision['conviction_score'] / 10.0, 0.8)  # Max 80% based on conviction
        is_winner = random.random() < success_chance
        
        if is_winner:
            # Winning trade - assume 50% gain
            profit = trade_cost * 0.5
            self.current_balance += trade_cost + profit
            self.winning_trades += 1
            actual_pnl = profit
            status = "won"
        else:
            # Losing trade - lose the investment
            self.losing_trades += 1
            actual_pnl = -trade_cost
            status = "lost"
        
        # Log trade to arena database
        trade_data = {
            'bot_id': self.bot_id,
            'market_title': trade_decision.get('market_title', 'Unknown Market'),
            'market_slug': trade_decision.get('market_slug', ''),
            'condition_id': trade_decision.get('condition_id', ''),
            'action': 'BUY',
            'size': trade_size,
            'price': expected_price,
            'conviction_score': trade_decision['conviction_score'],
            'expected_roi': 0.5,  # 50% expected return
            'actual_pnl': actual_pnl,
            'status': status,
            'trade_reason': f"Copied from sharp wallet {trade_decision['wallet'][:8]}",
            'source_data': {
                'source_wallet': trade_decision['wallet'],
                'original_trade_size': trade_decision.get('original_size', 0),
                'copy_ratio': trade_decision.get('copy_ratio', 0.02)
            }
        }
        
        self.arena_db.log_trade(trade_data)
        self.trade_history.append(trade_data)
        
        # Update performance metrics
        await self.update_performance()
        
        logger.info(f"🎯 Trade executed: {status.upper()} | Size: ${trade_size:.0f} | P&L: ${actual_pnl:.0f}")
        return trade_data
    
    async def update_performance(self):
        """Update bot performance in arena database"""
        total_roi = ((self.current_balance - self.starting_balance) / self.starting_balance) * 100
        win_rate = self.winning_trades / max(self.total_trades, 1)
        
        # Calculate Sharpe ratio (simplified)
        if self.trade_history:
            returns = [trade['actual_pnl'] / self.starting_balance for trade in self.trade_history]
            avg_return = sum(returns) / len(returns)
            return_std = (sum([(r - avg_return)**2 for r in returns]) / len(returns))**0.5
            sharpe_ratio = avg_return / max(return_std, 0.01)  # Avoid division by zero
        else:
            sharpe_ratio = 0.0
        
        # Calculate max drawdown
        balance_history = [self.starting_balance]
        running_balance = self.starting_balance
        for trade in self.trade_history:
            running_balance += trade['actual_pnl']
            balance_history.append(running_balance)
        
        peak = self.starting_balance
        max_drawdown = 0.0
        for balance in balance_history:
            if balance > peak:
                peak = balance
            drawdown = (peak - balance) / peak * 100
            max_drawdown = max(max_drawdown, drawdown)
        
        avg_trade_size = sum([trade['size'] * trade['price'] for trade in self.trade_history]) / max(self.total_trades, 1)
        
        performance = {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'total_roi': total_roi,
            'current_balance': self.current_balance,
            'win_rate': win_rate,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'avg_trade_size': avg_trade_size
        }
        
        self.arena_db.update_bot_performance(self.bot_id, performance)
        logger.debug(f"📊 Performance updated: {total_roi:.1f}% ROI, {win_rate:.1%} WR")
    
    async def simulate_copy_trade_decision(self, wallet_analysis: dict, market_context: list):
        """Enhanced copy trade decision with arena integration"""
        decision = await super().simulate_copy_trade_decision(wallet_analysis, market_context)
        
        if decision and decision.get('action') == 'COPY':
            # Add market context for arena logging
            if market_context:
                market = market_context[0]  # Use first market as example
                decision.update({
                    'market_title': market.get('question', 'Unknown Market'),
                    'market_slug': market.get('slug', ''),
                    'condition_id': market.get('condition_id', ''),
                    'current_price': 0.65,  # Placeholder
                    'original_size': wallet_analysis.get('portfolio_value', 1000) * 0.1,  # Estimate
                    'copy_ratio': 0.02
                })
            
            # Execute the trade
            await self.execute_copy_trade(decision)
            
            # Log opportunity for other bots
            self.arena_db.log_opportunity(self.bot_id, {
                'type': 'sharp_wallet_activity',
                'market_title': decision.get('market_title', 'Unknown'),
                'condition_id': decision.get('condition_id', ''),
                'confidence_score': decision['conviction_score'],
                'expected_edge': 0.15,  # 15% expected edge
                'time_sensitivity_minutes': 30,
                'data_source': f"Sharp wallet {decision['wallet'][:8]}"
            })
        
        return decision
    
    async def run_forever(self):
        """Main bot loop with arena integration"""
        logger.info(f"🚀 {self.bot_name} starting main loop...")
        
        loop_count = 0
        while True:
            try:
                # Send heartbeat
                self.arena_db.heartbeat(
                    self.bot_id, 
                    'active', 
                    f'Analysis loop {loop_count}',
                    None
                )
                
                # Run analysis (from parent class)
                await self.run_analysis()
                
                loop_count += 1
                
                # Sleep before next analysis
                await asyncio.sleep(60)  # Check every minute
                
            except KeyboardInterrupt:
                logger.info("🛑 Bot stopped by user")
                self.arena_db.heartbeat(self.bot_id, 'stopped', 'User terminated', None)
                break
            except Exception as e:
                logger.error(f"❌ Bot error: {e}")
                self.arena_db.heartbeat(self.bot_id, 'error', 'Exception occurred', str(e))
                await asyncio.sleep(30)  # Wait before retry
    
    async def run_analysis(self):
        """Override to add arena-specific features"""
        logger.info("🔍 Running sharp wallet analysis...")
        
        # Get market context
        market_context = await self.get_active_markets(limit=10)
        
        # Analyze sharp wallets
        for wallet in self.sharp_wallets:
            try:
                analysis = await self.analyze_wallet_performance(wallet)
                if analysis:
                    await self.simulate_copy_trade_decision(analysis, market_context)
            except Exception as e:
                logger.error(f"Error analyzing {wallet}: {e}")
                continue
        
        logger.info(f"✅ Analysis complete. Balance: ${self.current_balance:.2f}")

async def main():
    """Run the arena bot"""
    bot = ArenaSharpWalletBot()
    await bot.run_forever()

if __name__ == "__main__":
    asyncio.run(main())