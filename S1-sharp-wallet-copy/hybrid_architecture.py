#!/usr/bin/env python3
"""
Hybrid Polymarket Wallet Monitor
Combines direct blockchain monitoring with API enrichment for optimal speed + context
"""

import json
import asyncio
import websockets
import requests
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import sqlite3
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class BlockchainEvent:
    """Raw blockchain event from WebSocket"""
    transaction_hash: str
    block_number: int
    wallet_address: str
    token_id: str
    amount: float
    side: str  # 'BUY' or 'SELL'
    price: float
    timestamp: datetime
    
@dataclass
class EnrichedTrade:
    """Blockchain event + API enrichment"""
    # Blockchain data
    blockchain_event: BlockchainEvent
    
    # API enrichment
    market_title: str
    market_slug: str
    condition_id: str
    outcome: str  # 'YES' or 'NO'
    market_liquidity: float
    current_price: float
    volume_24h: float
    end_date: str
    
    # Analysis
    conviction_score: float  # 1-10 based on size relative to wallet history
    copy_signal: bool
    copy_size: float

class AlchemyWebSocketMonitor:
    """Direct blockchain monitoring via Alchemy WebSocket"""
    
    def __init__(self, alchemy_api_key: str, sharp_wallets: List[str]):
        self.api_key = alchemy_api_key
        self.sharp_wallets = [w.lower() for w in sharp_wallets]
        self.ws_url = f"wss://polygon-mainnet.g.alchemy.com/v2/{alchemy_api_key}"
        
        # Polymarket contract addresses (these are the main ones)
        self.conditional_tokens = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"  # Conditional tokens
        self.ctf_exchange = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"      # CTF Exchange
        
    async def connect_and_monitor(self):
        """Main WebSocket connection loop"""
        logger.info(f"🔌 Connecting to Alchemy WebSocket...")
        logger.info(f"📊 Monitoring {len(self.sharp_wallets)} sharp wallets")
        
        while True:
            try:
                async with websockets.connect(self.ws_url) as websocket:
                    # Subscribe to transfers involving our sharp wallets
                    await self._subscribe_to_transfers(websocket)
                    
                    logger.info("✅ Connected! Listening for trades...")
                    
                    async for message in websocket:
                        await self._process_message(message)
                        
            except Exception as e:
                logger.error(f"❌ WebSocket error: {e}")
                logger.info("🔄 Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
    
    async def _subscribe_to_transfers(self, websocket):
        """Subscribe to ERC1155 Transfer events for sharp wallets"""
        for wallet in self.sharp_wallets:
            subscription = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_subscribe",
                "params": [
                    "logs",
                    {
                        "address": self.conditional_tokens,
                        "topics": [
                            "0xc3d58168c5ae7397731d063d5bbf3d657854427343f4c083240f7aacaa2d0f62",  # TransferSingle
                            None,  # operator (anyone can trigger)
                            wallet,  # from (our sharp wallet)
                            None   # to (anyone)
                        ]
                    }
                ]
            }
            await websocket.send(json.dumps(subscription))
            
            # Also subscribe to incoming transfers (wallet buying)
            subscription_buy = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "eth_subscribe",
                "params": [
                    "logs",
                    {
                        "address": self.conditional_tokens,
                        "topics": [
                            "0xc3d58168c5ae7397731d063d5bbf3d657854427343f4c083240f7aacaa2d0f62",  # TransferSingle
                            None,  # operator
                            None,  # from (anyone)
                            wallet   # to (our sharp wallet receiving)
                        ]
                    }
                ]
            }
            await websocket.send(json.dumps(subscription_buy))
    
    async def _process_message(self, message: str):
        """Process incoming WebSocket message"""
        try:
            data = json.loads(message)
            
            if 'params' in data and 'result' in data['params']:
                log = data['params']['result']
                event = self._parse_transfer_log(log)
                
                if event:
                    logger.info(f"🎯 Sharp wallet trade detected: {event.wallet_address[:8]} {event.side} {event.amount:.0f} shares")
                    
                    # Send to enrichment pipeline
                    await self._send_for_enrichment(event)
                    
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def _parse_transfer_log(self, log: Dict) -> Optional[BlockchainEvent]:
        """Parse ERC1155 Transfer log into BlockchainEvent"""
        try:
            # Decode the transfer data
            topics = log['topics']
            data = log['data']
            
            # Extract addresses and amounts from log data
            # This is simplified - in production you'd use proper ABI decoding
            from_addr = "0x" + topics[2][-40:] if len(topics) > 2 else None
            to_addr = "0x" + topics[3][-40:] if len(topics) > 3 else None
            
            # Determine which wallet is ours and direction
            wallet_addr = None
            side = None
            
            if from_addr and from_addr.lower() in self.sharp_wallets:
                wallet_addr = from_addr.lower()
                side = "SELL"
            elif to_addr and to_addr.lower() in self.sharp_wallets:
                wallet_addr = to_addr.lower()
                side = "BUY"
            else:
                return None
            
            # Extract token ID and amount (simplified parsing)
            # In production, use web3.py or similar for proper decoding
            token_id = str(int(data[2:66], 16)) if len(data) > 66 else "unknown"
            amount = int(data[66:130], 16) / 1e6 if len(data) > 130 else 0  # Assuming 6 decimals
            
            return BlockchainEvent(
                transaction_hash=log['transactionHash'],
                block_number=int(log['blockNumber'], 16),
                wallet_address=wallet_addr,
                token_id=token_id,
                amount=amount,
                side=side,
                price=0.0,  # Will be enriched from API
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error parsing transfer log: {e}")
            return None
    
    async def _send_for_enrichment(self, event: BlockchainEvent):
        """Send blockchain event to API enrichment pipeline"""
        # This would typically use a queue (Redis, RabbitMQ) in production
        # For now, we'll call the enricher directly
        enricher = PolymarketAPIEnricher()
        enriched = await enricher.enrich_event(event)
        
        if enriched and enriched.copy_signal:
            logger.info(f"🚀 COPY SIGNAL: {enriched.market_title} - Conviction: {enriched.conviction_score:.1f}")
            await self._execute_copy_trade(enriched)
    
    async def _execute_copy_trade(self, trade: EnrichedTrade):
        """Execute copy trade (paper trading for now)"""
        logger.info(f"📝 PAPER TRADE: {trade.copy_size:.0f} shares of {trade.market_title}")
        
        # Store in database for tracking
        self._store_copy_trade(trade)
    
    def _store_copy_trade(self, trade: EnrichedTrade):
        """Store copy trade in database"""
        conn = sqlite3.connect("copy_trades.db")
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS copy_trades (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            wallet_address TEXT,
            market_title TEXT,
            side TEXT,
            amount REAL,
            price REAL,
            conviction_score REAL,
            tx_hash TEXT
        )
        ''')
        
        cursor.execute('''
        INSERT INTO copy_trades 
        (timestamp, wallet_address, market_title, side, amount, price, conviction_score, tx_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade.blockchain_event.timestamp.isoformat(),
            trade.blockchain_event.wallet_address,
            trade.market_title,
            trade.blockchain_event.side,
            trade.copy_size,
            trade.blockchain_event.price,
            trade.conviction_score,
            trade.blockchain_event.transaction_hash
        ))
        
        conn.commit()
        conn.close()

class PolymarketAPIEnricher:
    """Enrich blockchain events with Polymarket API data"""
    
    def __init__(self):
        # We'll install polymarket-apis later, for now use direct API calls
        self.gamma_url = "https://gamma-api.polymarket.com"
        self.clob_url = "https://clob.polymarket.com"
        
    async def enrich_event(self, event: BlockchainEvent) -> Optional[EnrichedTrade]:
        """Enrich blockchain event with market data"""
        try:
            # Get market metadata from token ID
            market_data = await self._get_market_by_token_id(event.token_id)
            if not market_data:
                logger.warning(f"❓ Unknown market for token {event.token_id}")
                return None
            
            # Get current market prices and liquidity
            order_book = await self._get_order_book(event.token_id)
            
            # Calculate conviction score
            conviction = self._calculate_conviction(event, market_data)
            
            # Determine if this should trigger a copy trade
            should_copy = self._should_copy_trade(event, market_data, conviction)
            
            copy_size = 0
            if should_copy:
                copy_size = self._calculate_copy_size(event, conviction)
            
            return EnrichedTrade(
                blockchain_event=event,
                market_title=market_data.get('question', 'Unknown Market'),
                market_slug=market_data.get('slug', ''),
                condition_id=market_data.get('condition_id', ''),
                outcome=market_data.get('outcome', 'YES'),
                market_liquidity=order_book.get('liquidity', 0),
                current_price=order_book.get('mid_price', 0),
                volume_24h=market_data.get('volume_24h', 0),
                end_date=market_data.get('end_date', ''),
                conviction_score=conviction,
                copy_signal=should_copy,
                copy_size=copy_size
            )
            
        except Exception as e:
            logger.error(f"Error enriching event: {e}")
            return None
    
    async def _get_market_by_token_id(self, token_id: str) -> Optional[Dict]:
        """Get market metadata by token ID"""
        # This is a placeholder - would need proper API integration
        # For now, return mock data to test pipeline
        return {
            'question': 'Will Bitcoin hit $100k in 2026?',
            'slug': 'bitcoin-100k-2026',
            'condition_id': 'mock_condition_123',
            'outcome': 'YES',
            'volume_24h': 50000,
            'end_date': '2026-12-31'
        }
    
    async def _get_order_book(self, token_id: str) -> Dict:
        """Get current order book data"""
        # Placeholder for order book API call
        return {
            'mid_price': 0.65,
            'liquidity': 25000,
            'spread': 0.02
        }
    
    def _calculate_conviction(self, event: BlockchainEvent, market_data: Dict) -> float:
        """Calculate conviction score 1-10 based on trade size and context"""
        # Placeholder scoring logic
        if event.amount > 1000:
            return 8.5
        elif event.amount > 500:
            return 6.0
        else:
            return 3.0
    
    def _should_copy_trade(self, event: BlockchainEvent, market_data: Dict, conviction: float) -> bool:
        """Determine if we should copy this trade"""
        # Copy high-conviction trades only
        return conviction >= 6.0 and event.amount >= 100
    
    def _calculate_copy_size(self, event: BlockchainEvent, conviction: float) -> float:
        """Calculate position size for copy trade"""
        # Start with 2% of original trade size
        base_size = event.amount * 0.02
        
        # Scale by conviction (higher conviction = larger position)
        conviction_multiplier = conviction / 10.0
        
        return base_size * conviction_multiplier

def load_sharp_wallets() -> List[str]:
    """Load sharp wallet addresses from database"""
    # For testing, return some known active addresses
    return [
        "0x90f8b0fee21e920e81d1ca4da6d215152f576537",  # We know this one has activity
        "0x8f3ff3c5750c20479f68db28407912bd8df67afa",  # Another active one
    ]

async def main():
    """Main entry point"""
    # Load configuration
    ALCHEMY_API_KEY = "your_alchemy_key_here"  # Would come from .env
    
    if ALCHEMY_API_KEY == "your_alchemy_key_here":
        logger.error("❌ Please set your Alchemy API key")
        return
    
    # Load sharp wallets
    sharp_wallets = load_sharp_wallets()
    logger.info(f"📊 Loaded {len(sharp_wallets)} sharp wallets to monitor")
    
    # Start hybrid monitoring
    monitor = AlchemyWebSocketMonitor(ALCHEMY_API_KEY, sharp_wallets)
    
    logger.info("🚀 Starting hybrid Polymarket monitor...")
    logger.info("💡 Blockchain events + API enrichment = Smart copy trades")
    
    await monitor.connect_and_monitor()

if __name__ == "__main__":
    asyncio.run(main())