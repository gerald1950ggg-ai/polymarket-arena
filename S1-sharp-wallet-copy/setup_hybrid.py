#!/usr/bin/env python3
"""
Setup script for hybrid Polymarket monitoring
Installs dependencies and configures environment
"""

import subprocess
import sys
import os
from pathlib import Path

def install_dependencies():
    """Install required Python packages"""
    requirements = [
        "websockets>=11.0.0",
        "requests>=2.28.0", 
        "web3>=6.0.0",
        "python-dotenv>=0.19.0",
        "polymarket-apis>=0.5.4",  # The community library we found
        "asyncio-throttle>=1.0.2"  # For rate limiting API calls
    ]
    
    print("📦 Installing dependencies...")
    for req in requirements:
        print(f"   Installing {req}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", req])
    
    print("✅ Dependencies installed!")

def create_env_template():
    """Create .env template file"""
    env_content = """# Hybrid Polymarket Monitor Configuration

# Blockchain WebSocket Provider (choose one)
ALCHEMY_API_KEY=your_alchemy_key_here
# CHAINSTACK_API_KEY=your_chainstack_key_here

# Sharp Wallets to Monitor (comma-separated, no 0x prefix)
SHARP_WALLETS=90f8b0fee21e920e81d1ca4da6d215152f576537,8f3ff3c5750c20479f68db28407912bd8df67afa

# Trading Configuration  
MOCK_TRADING=true
MIN_COPY_AMOUNT=100.0
MAX_COPY_AMOUNT=5000.0
POSITION_SCALING=0.02  # Copy 2% of sharp wallet size
MIN_CONVICTION_SCORE=6.0

# API Rate Limiting
API_CALLS_PER_SECOND=10
WEBSOCKET_RECONNECT_DELAY=5

# Database
DB_PATH=hybrid_monitor.db

# Logging
LOG_LEVEL=INFO
LOG_FILE=monitor.log"""
    
    env_path = Path(".env.example")
    env_path.write_text(env_content)
    
    print(f"📝 Created {env_path}")
    
    if not Path(".env").exists():
        Path(".env").write_text(env_content)
        print("📝 Created .env file (copy of .env.example)")
        print("⚠️  EDIT .env and add your API keys before running!")

def test_imports():
    """Test that all required packages can be imported"""
    print("🧪 Testing imports...")
    
    try:
        import websockets
        import requests
        import web3
        import polymarket_apis
        print("✅ All packages imported successfully!")
        
        # Show polymarket-apis version
        print(f"📊 polymarket-apis version: {polymarket_apis.__version__}")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def create_test_script():
    """Create a simple test script"""
    test_content = """#!/usr/bin/env python3
\"\"\"
Test script for hybrid monitoring setup
\"\"\"

import asyncio
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

async def test_setup():
    \"\"\"Test basic setup\"\"\"
    print("🧪 Testing hybrid monitor setup...")
    
    # Test environment variables
    alchemy_key = os.getenv("ALCHEMY_API_KEY")
    if not alchemy_key or alchemy_key == "your_alchemy_key_here":
        print("⚠️  ALCHEMY_API_KEY not set in .env")
        return False
    
    # Test wallet list
    wallets_str = os.getenv("SHARP_WALLETS", "")
    wallets = [w.strip() for w in wallets_str.split(",") if w.strip()]
    print(f"📊 Found {len(wallets)} wallets to monitor:")
    for wallet in wallets:
        print(f"   {wallet}")
    
    if not wallets:
        print("⚠️  No sharp wallets configured in SHARP_WALLETS")
        return False
    
    # Test polymarket-apis import
    try:
        from polymarket_apis import PolymarketDataClient
        client = PolymarketDataClient()
        print("✅ Polymarket APIs client created successfully")
    except Exception as e:
        print(f"❌ Error creating Polymarket client: {e}")
        return False
    
    print("🎯 Setup test passed! Ready to run hybrid monitor.")
    return True

if __name__ == "__main__":
    asyncio.run(test_setup())"""
    
    test_path = Path("test_setup.py")
    test_path.write_text(test_content)
    test_path.chmod(0o755)  # Make executable
    
    print(f"🧪 Created {test_path}")

def main():
    """Main setup process"""
    print("🚀 Setting up Hybrid Polymarket Monitor...")
    print("=" * 50)
    
    # Install dependencies
    install_dependencies()
    print()
    
    # Test imports
    if not test_imports():
        print("❌ Setup failed - package import errors")
        return
    print()
    
    # Create config files
    create_env_template()
    print()
    
    # Create test script
    create_test_script()
    print()
    
    print("🎉 Setup complete!")
    print()
    print("📋 Next steps:")
    print("1. Edit .env file and add your Alchemy API key")
    print("2. Run: python3 test_setup.py")
    print("3. Run: python3 hybrid_architecture.py")
    print()
    print("🔗 Get Alchemy API key at: https://www.alchemy.com/")
    print("   (Free tier is fine for testing)")

if __name__ == "__main__":
    main()