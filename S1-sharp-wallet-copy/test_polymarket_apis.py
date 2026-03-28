#!/usr/bin/env python3
"""
Test the polymarket-apis library to see what data we can access
"""

import asyncio
from polymarket_apis import PolymarketDataClient, PolymarketGammaClient

async def test_polymarket_apis():
    """Test basic polymarket-apis functionality"""
    print("🧪 Testing polymarket-apis library...")
    
    # Test Data client (user positions, trades)
    print("\n📊 Testing Data Client (portfolio/trades)...")
    try:
        data_client = PolymarketDataClient()
        
        # Try to get some sample data
        print("✅ Data client created successfully")
        
        # Test positions for one of our known wallets
        test_wallet = "0x90f8b0fee21e920e81d1ca4da6d215152f576537"
        print(f"📍 Getting positions for {test_wallet[:8]}...")
        
        positions = await data_client.get_positions(user_address=test_wallet, limit=5)
        print(f"✅ Found {len(positions)} positions")
        
        if positions:
            for i, pos in enumerate(positions[:3]):  # Show first 3
                print(f"   {i+1}. Market: {pos.get('market', 'Unknown')}")
                print(f"      Size: {pos.get('size', 0)} | Value: ${pos.get('value', 0)}")
        
    except Exception as e:
        print(f"❌ Data client error: {e}")
    
    # Test Gamma client (markets, events)
    print("\n🎲 Testing Gamma Client (markets/events)...")
    try:
        gamma_client = PolymarketGammaClient()
        print("✅ Gamma client created successfully")
        
        # Get recent active markets
        print("📈 Getting active markets...")
        markets = await gamma_client.get_markets(limit=5, active=True)
        print(f"✅ Found {len(markets)} active markets")
        
        if markets:
            for i, market in enumerate(markets[:3]):
                print(f"   {i+1}. {market.get('question', 'Unknown Question')}")
                print(f"      Volume: ${market.get('volume', 0):,.0f}")
                print(f"      Liquidity: ${market.get('liquidity', 0):,.0f}")
                
    except Exception as e:
        print(f"❌ Gamma client error: {e}")
    
    print("\n🎯 Testing wallet analysis...")
    
    # Test getting top traders
    try:
        # Get leaderboard data
        print("🏆 Getting profit leaderboard...")
        leaderboard = await data_client.get_leaderboard(window="7d", limit=10)
        print(f"✅ Found {len(leaderboard)} top traders")
        
        if leaderboard:
            for i, trader in enumerate(leaderboard[:5]):
                address = trader.get('user_address', 'Unknown')
                profit = trader.get('profit', 0)
                volume = trader.get('volume', 0)
                print(f"   {i+1}. {address[:8]}... Profit: ${profit:,.0f} | Volume: ${volume:,.0f}")
                
    except Exception as e:
        print(f"❌ Leaderboard error: {e}")
    
    print("\n✨ polymarket-apis test complete!")

if __name__ == "__main__":
    asyncio.run(test_polymarket_apis())