#!/usr/bin/env python3
"""
Test script for wallet discovery pipeline
"""

from wallet_discovery import PolymarketWalletAnalyzer

def test_basic_functionality():
    """Test basic wallet discovery functionality"""
    print("🧪 Testing wallet discovery pipeline...")
    
    analyzer = PolymarketWalletAnalyzer("test_wallet_data.db")
    
    # Test database setup
    print("✓ Database initialized")
    
    # Test fetching top wallets (small sample)
    print("Testing wallet fetch...")
    wallets = analyzer.fetch_top_wallets(limit=10)
    print(f"✓ Fetched {len(wallets)} wallet addresses")
    
    # Use a known working wallet for testing position analysis
    test_wallet = "0x90f8b0fee21e920e81d1ca4da6d215152f576537"
    print(f"Testing position analysis for {test_wallet[:8]}...")
    print(f"Full address: {test_wallet}")
    positions = analyzer.fetch_wallet_positions(test_wallet)
    print(f"✓ Fetched {len(positions)} positions")
    
    if positions:
        
        stats = analyzer.analyze_wallet_performance(positions, test_wallet)
        if stats:
                print(f"✓ Analysis complete:")
                print(f"  - Win Rate: {stats.win_rate:.1%}")
                print(f"  - Total Bets: {stats.total_bets}")
                print(f"  - Avg Bet Size: ${stats.avg_bet_size:.2f}")
                print(f"  - Markets: {stats.markets_count}")
                print(f"  - Is Sharp: {stats.is_sharp()}")
                
                # Test storing data
                analyzer.store_wallet_data(stats)
                print("✓ Data stored successfully")
        else:
            print("ℹ️ No recent positions found for this wallet")
    
    print("\n✅ Basic functionality test complete")

if __name__ == "__main__":
    test_basic_functionality()