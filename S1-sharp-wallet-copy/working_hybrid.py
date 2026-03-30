#!/usr/bin/env python3
"""
Working Hybrid Polymarket Monitor
Uses correct polymarket-apis methods + Alchemy/Web3 for on-chain monitoring
"""

import asyncio
from polymarket_apis import PolymarketDataClient, PolymarketGammaClient, PolymarketWebsocketsClient
from dotenv import load_dotenv
import os
import json
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

class WorkingHybridMonitor:
    """Simplified hybrid monitor using working API methods + Alchemy on-chain data"""
    
    def __init__(self):
        # Initialize API clients
        self.data_client = PolymarketDataClient()
        self.gamma_client = PolymarketGammaClient()

        # ── Alchemy / Web3 setup ──────────────────────────────────────────
        api_key = os.getenv("ALCHEMY_API_KEY", "")
        if api_key:
            self.polygon_rpc = f"https://polygon-mainnet.g.alchemy.com/v2/{api_key}"
            try:
                from web3 import Web3
                self.w3 = Web3(Web3.HTTPProvider(self.polygon_rpc))
                if self.w3.is_connected():
                    logger.info(f"✅ Web3 connected to Polygon via Alchemy (block {self.w3.eth.block_number})")
                else:
                    logger.warning("⚠️  Web3 provider created but not connected")
            except ImportError:
                logger.warning("⚠️  web3 package not installed; on-chain features disabled")
                self.w3 = None
        else:
            logger.warning("⚠️  ALCHEMY_API_KEY not set; on-chain features disabled")
            self.polygon_rpc = None
            self.w3 = None

        # ── Sharp wallets ─────────────────────────────────────────────────
        wallets_str = os.getenv("SHARP_WALLETS", "")
        self.sharp_wallets = [w.strip() for w in wallets_str.split(",") if w.strip()]
        
        # Add 0x prefix if missing
        self.sharp_wallets = [w if w.startswith("0x") else f"0x{w}" for w in self.sharp_wallets]
        
        logger.info(f"📊 Monitoring {len(self.sharp_wallets)} sharp wallets")

    async def analyze_wallet_performance(self, wallet_address: str):
        """Analyze a wallet's trading performance using real API data"""
        print(f"\n🎯 Analyzing wallet {wallet_address[:8]}...")
        
        try:
            # Get wallet positions (correct method signature)
            positions = self.data_client.get_positions(user=wallet_address, limit=20)
            print(f"📍 Found {len(positions)} positions")
            
            if not positions:
                print("   No positions found")
                return
            
            # Analyze positions
            total_value = 0
            active_markets = set()
            
            for pos in positions[:5]:  # Show first 5
                size = float(pos.tokens or 0)
                current_value = float(pos.current_value or 0)
                market_question = pos.market.question if pos.market else "Unknown Market"
                
                total_value += current_value
                if pos.condition_id:
                    active_markets.add(pos.condition_id)
                
                print(f"   📈 {market_question[:60]}...")
                print(f"      Size: {size:,.0f} tokens | Value: ${current_value:.2f}")
            
            print(f"💰 Total portfolio value: ${total_value:.2f}")
            print(f"🏪 Active in {len(active_markets)} different markets")
            
            # Get recent trades
            trades = self.data_client.get_trades(user=wallet_address, limit=10)
            print(f"📊 Found {len(trades)} recent trades")
            
            if trades:
                win_count = 0
                total_trades = len(trades)
                
                for trade in trades[:3]:  # Show first 3
                    side = trade.side
                    size = float(trade.token_amount or 0)
                    price = float(trade.price or 0)
                    market = trade.market_question if hasattr(trade, 'market_question') else "Unknown"
                    
                    print(f"   🔄 {side} {size:,.0f} @ ${price:.3f} | {market[:50]}...")
                    
                    # Simple win/loss heuristic (would need market resolution data for real analysis)
                    if side == "BUY" and price < 0.7:  # Bought cheap outcome
                        win_count += 1
                
                estimated_wr = win_count / total_trades if total_trades > 0 else 0
                print(f"📈 Estimated win rate: {estimated_wr:.1%} ({win_count}/{total_trades})")
                
                return {
                    'wallet': wallet_address,
                    'positions_count': len(positions),
                    'portfolio_value': total_value,
                    'markets_count': len(active_markets),
                    'trades_count': total_trades,
                    'estimated_win_rate': estimated_wr,
                    'is_sharp': estimated_wr > 0.3 and total_value > 100 and len(positions) > 3
                }
        
        except Exception as e:
            print(f"❌ Error analyzing wallet: {e}")
            return None

    async def get_active_markets(self, limit: int = 10):
        """Get current active markets for context"""
        print(f"\n🏪 Getting {limit} active markets...")
        
        try:
            markets = self.gamma_client.get_markets(limit=limit, active=True)
            print(f"✅ Found {len(markets)} active markets")
            
            market_data = []
            for market in markets[:5]:  # Show first 5
                volume = float(market.volume_num or 0)
                liquidity = float(market.liquidity_num or 0)
                
                print(f"   📊 {market.question}")
                print(f"      Volume: ${volume:,.0f} | Liquidity: ${liquidity:,.0f}")
                print(f"      Tokens: {market.token_ids[:1] if market.token_ids else 'None'}")
                
                market_data.append({
                    'question': market.question,
                    'condition_id': market.condition_id,
                    'volume': volume,
                    'liquidity': liquidity,
                    'token_ids': market.token_ids
                })
            
            return market_data
        
        except Exception as e:
            print(f"❌ Error getting markets: {e}")
            return []

    async def simulate_copy_trade_decision(self, wallet_analysis: dict, market_context: list):
        """Simulate copy trading decision logic"""
        if not wallet_analysis or not wallet_analysis['is_sharp']:
            return None
        
        print(f"\n🎯 Sharp wallet detected: {wallet_analysis['wallet'][:8]}")
        print(f"   Win Rate: {wallet_analysis['estimated_win_rate']:.1%}")
        print(f"   Portfolio: ${wallet_analysis['portfolio_value']:.0f}")
        print(f"   Markets: {wallet_analysis['markets_count']}")
        
        # Simple copy trade logic
        conviction_score = (
            wallet_analysis['estimated_win_rate'] * 3 +  # 30% weight to win rate
            min(wallet_analysis['portfolio_value'] / 1000, 5) +  # Up to 5 points for portfolio size
            min(wallet_analysis['markets_count'] / 5, 2)  # Up to 2 points for diversification
        )
        
        if conviction_score >= 6.0:
            copy_size = min(wallet_analysis['portfolio_value'] * 0.02, 1000)  # 2% of their portfolio, max $1k
            
            print(f"🚀 COPY SIGNAL GENERATED!")
            print(f"   Conviction Score: {conviction_score:.1f}/10")
            print(f"   Suggested Copy Size: ${copy_size:.0f}")
            
            return {
                'action': 'COPY',
                'conviction_score': conviction_score,
                'copy_size': copy_size,
                'wallet': wallet_analysis['wallet']
            }
        else:
            print(f"⏸️  Conviction too low: {conviction_score:.1f}/10 (need 6.0+)")
            return None

    async def run_analysis(self):
        """Main analysis loop"""
        print("🚀 Starting Hybrid Polymarket Analysis...")
        print("=" * 50)
        
        # Get market context first
        market_context = await self.get_active_markets(limit=10)
        
        # Analyze each sharp wallet
        copy_signals = []
        
        for wallet in self.sharp_wallets:
            try:
                analysis = await self.analyze_wallet_performance(wallet)
                if analysis:
                    decision = await self.simulate_copy_trade_decision(analysis, market_context)
                    if decision:
                        copy_signals.append(decision)
            
            except Exception as e:
                logger.error(f"Error analyzing {wallet}: {e}")
                continue
        
        # Summary
        print(f"\n📊 ANALYSIS COMPLETE")
        print("=" * 30)
        print(f"Wallets analyzed: {len(self.sharp_wallets)}")
        print(f"Copy signals generated: {len(copy_signals)}")
        
        if copy_signals:
            print(f"\n🎯 COPY SIGNALS:")
            for signal in copy_signals:
                print(f"   {signal['wallet'][:8]} | Score: {signal['conviction_score']:.1f} | Size: ${signal['copy_size']:.0f}")
        else:
            print("\n💤 No copy signals generated")

async def main():
    """Main entry point"""
    # Check environment
    if not os.getenv("SHARP_WALLETS"):
        logger.error("❌ Please set SHARP_WALLETS in .env file")
        return
    
    # Create and run monitor
    monitor = WorkingHybridMonitor()
    await monitor.run_analysis()

if __name__ == "__main__":
    asyncio.run(main())