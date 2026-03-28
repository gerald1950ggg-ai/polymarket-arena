#!/usr/bin/env python3
"""
Explore the actual polymarket-apis library methods
"""

from polymarket_apis import *
import inspect

def explore_api():
    """Explore what's actually available in polymarket-apis"""
    print("🔍 Exploring polymarket-apis library...")
    
    # List all available classes
    print("\n📦 Available classes:")
    classes = [
        PolymarketDataClient,
        PolymarketGammaClient, 
        PolymarketReadOnlyClobClient,
        PolymarketClobClient,
        PolymarketWebsocketsClient
    ]
    
    for cls in classes:
        print(f"   📋 {cls.__name__}")
        methods = [method for method in dir(cls) if not method.startswith('_')]
        for method in methods[:5]:  # Show first 5 methods
            print(f"      - {method}")
        if len(methods) > 5:
            print(f"      ... and {len(methods) - 5} more")
        print()

def test_data_client():
    """Test PolymarketDataClient with correct methods"""
    print("🧪 Testing PolymarketDataClient...")
    
    try:
        client = PolymarketDataClient()
        print("✅ Client created")
        
        # List actual methods
        methods = [m for m in dir(client) if not m.startswith('_') and callable(getattr(client, m))]
        print(f"📋 Available methods ({len(methods)}):")
        for method in methods:
            print(f"   - {method}")
            
        # Try some methods that might work for wallet analysis
        test_wallet = "0x90f8b0fee21e920e81d1ca4da6d215152f576537"
        
        print(f"\n🎯 Testing methods with wallet {test_wallet[:8]}...")
        
        # Try positions method (without user_address parameter)
        if hasattr(client, 'get_positions'):
            print("Testing get_positions...")
            try:
                # Check method signature
                sig = inspect.signature(client.get_positions)
                print(f"   Signature: get_positions{sig}")
                
                # Try calling with wallet parameter name variations
                positions = client.get_positions(address=test_wallet, limit=5)
                print(f"   ✅ Success! Got {len(positions) if positions else 0} positions")
                
            except Exception as e:
                print(f"   ❌ get_positions failed: {e}")
        
        # Try trades method  
        if hasattr(client, 'get_trades'):
            print("Testing get_trades...")
            try:
                sig = inspect.signature(client.get_trades)
                print(f"   Signature: get_trades{sig}")
                
                trades = client.get_trades(user_address=test_wallet, limit=5)
                print(f"   ✅ Success! Got {len(trades) if trades else 0} trades")
                
            except Exception as e:
                print(f"   ❌ get_trades failed: {e}")
                
    except Exception as e:
        print(f"❌ Error creating client: {e}")

def test_gamma_client():
    """Test PolymarketGammaClient"""
    print("\n🎲 Testing PolymarketGammaClient...")
    
    try:
        client = PolymarketGammaClient()
        print("✅ Client created")
        
        # List methods
        methods = [m for m in dir(client) if not m.startswith('_') and callable(getattr(client, m))]
        print(f"📋 Available methods ({len(methods)}):")
        for method in methods[:10]:  # Show first 10
            print(f"   - {method}")
        
        # Try markets method
        if hasattr(client, 'get_markets'):
            print("\nTesting get_markets...")
            try:
                sig = inspect.signature(client.get_markets)
                print(f"   Signature: get_markets{sig}")
                
                markets = client.get_markets(limit=3)
                print(f"   ✅ Success! Got {len(markets) if markets else 0} markets")
                
                if markets:
                    for i, market in enumerate(markets):
                        print(f"      {i+1}. {market}")
                        
            except Exception as e:
                print(f"   ❌ get_markets failed: {e}")
        
    except Exception as e:
        print(f"❌ Error creating gamma client: {e}")

if __name__ == "__main__":
    explore_api()
    test_data_client() 
    test_gamma_client()