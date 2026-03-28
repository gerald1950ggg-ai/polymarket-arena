#!/usr/bin/env python3
"""
Polymarket Wallet Discovery Pipeline
Identifies high-performing wallets by analyzing historical trade data
"""

import json
import sqlite3
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class WalletStats:
    address: str
    total_bets: int
    wins: int
    losses: int
    total_volume: float
    net_pnl: float
    avg_bet_size: float
    markets_count: int
    win_rate: float
    last_active: str
    
    def is_sharp(self) -> bool:
        """Determine if wallet meets sharp trader criteria"""
        return (
            self.win_rate >= 0.65 and
            self.total_bets >= 20 and
            self.avg_bet_size >= 100 and
            self.markets_count >= 5
        )

class PolymarketWalletAnalyzer:
    def __init__(self, db_path: str = "wallet_data.db"):
        self.db_path = db_path
        self.setup_database()
        
        # Polymarket subgraph endpoints (Goldsky hosted)
        self.positions_url = "https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs/positions-subgraph/0.0.7/gn"
        self.orders_url = "https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs/orderbook-subgraph/0.0.1/gn"
        self.pnl_url = "https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs/pnl-subgraph/0.0.14/gn"
        
        # Rate limiting
        self.request_delay = 1  # seconds between requests
        
    def setup_database(self):
        """Initialize SQLite database for wallet data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Wallet performance table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS wallet_performance (
            address TEXT PRIMARY KEY,
            total_bets INTEGER,
            wins INTEGER,
            losses INTEGER,
            total_volume REAL,
            net_pnl REAL,
            avg_bet_size REAL,
            markets_count INTEGER,
            win_rate REAL,
            last_active TEXT,
            is_sharp BOOLEAN,
            updated_at TEXT
        )
        ''')
        
        # Individual trades table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id TEXT PRIMARY KEY,
            wallet_address TEXT,
            market_id TEXT,
            outcome_index INTEGER,
            shares REAL,
            price REAL,
            cost REAL,
            timestamp TEXT,
            block_number INTEGER,
            transaction_hash TEXT
        )
        ''')
        
        # Market metadata table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS markets (
            id TEXT PRIMARY KEY,
            title TEXT,
            description TEXT,
            end_date TEXT,
            resolution_source TEXT,
            total_volume REAL,
            outcome_count INTEGER
        )
        ''')
        
        conn.commit()
        conn.close()
        
    def fetch_wallet_positions(self, wallet_address: str) -> List[Dict]:
        """Fetch user positions and calculate trading performance"""
        query = """
        query GetUserPositions($wallet: String!) {
          userPositions(
            where: { user: $wallet },
            first: 100,
            orderBy: totalBought,
            orderDirection: desc
          ) {
            id
            user
            tokenId
            amount
            avgPrice
            realizedPnl
            totalBought
          }
        }
        """
        
        variables = {"wallet": wallet_address.lower()}
        
        response = requests.post(
            self.pnl_url,
            json={"query": query, "variables": variables}
        )
        
        if response.status_code == 200:
            data = response.json()
            positions = data.get("data", {}).get("userPositions", [])
            print(f"DEBUG: Query returned {len(positions)} positions for {wallet_address[:8]}")
            if "errors" in data:
                print(f"DEBUG: GraphQL errors: {data['errors']}")
            return positions
        else:
            print(f"Error fetching positions for {wallet_address}: {response.status_code}")
            return []
    
    def fetch_top_wallets(self, limit: int = 500) -> List[str]:
        """Fetch addresses of most active wallets from PnL data"""
        query = """
        query GetTopWallets($limit: Int!) {
          userPositions(
            orderBy: realizedPnl,
            orderDirection: desc,
            first: $limit
          ) {
            user
            realizedPnl
            totalBought
          }
        }
        """
        
        variables = {"limit": limit}
        
        response = requests.post(
            self.pnl_url,
            json={"query": query, "variables": variables}
        )
        
        if response.status_code == 200:
            data = response.json()
            positions = data.get("data", {}).get("userPositions", [])
            # Get unique wallets, filter for reasonable activity
            wallets = []
            seen = set()
            for pos in positions:
                wallet = pos["user"]
                pnl = float(pos.get("realizedPnl", 0))
                volume = float(pos.get("totalBought", 0))
                
                if (wallet not in seen and 
                    volume > 0 and 
                    pnl != 0 and 
                    wallet != "0x57ea53b3cf624d1030b2d5f62ca93f249adc95ba"):  # Skip the mega-whale that times out
                    wallets.append(wallet)
                    seen.add(wallet)
                    
                if len(wallets) >= limit//10:  # Take top subset
                    break
                    
            return wallets
        else:
            print(f"Error fetching top wallets: {response.status_code}")
            return []
    
    def analyze_wallet_performance(self, positions: List[Dict], wallet_address: str) -> WalletStats:
        """Calculate performance metrics from PnL positions"""
        if not positions:
            return None
            
        # Aggregate data from positions  
        unique_tokens = set()
        total_realized_pnl = 0
        total_volume = 0
        wins = 0
        losses = 0
        
        for pos in positions:
            unique_tokens.add(pos["tokenId"])
            realized = float(pos.get("realizedPnl", 0))
            volume = float(pos.get("totalBought", 0))
            
            total_realized_pnl += realized
            total_volume += volume
            
            # Count wins/losses based on realized PnL per position
            if realized > 0:
                wins += 1
            elif realized < 0:
                losses += 1
        
        total_positions = len(positions)
        
        return WalletStats(
            address=wallet_address,
            total_bets=total_positions,
            wins=wins,
            losses=losses,
            total_volume=total_volume,
            net_pnl=total_realized_pnl,
            avg_bet_size=total_volume / total_positions if total_positions > 0 else 0,
            markets_count=len(unique_tokens),  # Using unique token IDs as proxy for markets
            win_rate=wins / (wins + losses) if (wins + losses) > 0 else 0,
            last_active=""  # Not available in this schema
        )
    
    def store_wallet_data(self, wallet_stats: WalletStats):
        """Store wallet performance data in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT OR REPLACE INTO wallet_performance 
        (address, total_bets, wins, losses, total_volume, net_pnl, 
         avg_bet_size, markets_count, win_rate, last_active, is_sharp, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            wallet_stats.address,
            wallet_stats.total_bets,
            wallet_stats.wins,
            wallet_stats.losses,
            wallet_stats.total_volume,
            wallet_stats.net_pnl,
            wallet_stats.avg_bet_size,
            wallet_stats.markets_count,
            wallet_stats.win_rate,
            wallet_stats.last_active,
            wallet_stats.is_sharp(),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def get_sharp_wallets(self) -> List[WalletStats]:
        """Retrieve all wallets that meet sharp trader criteria"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT * FROM wallet_performance 
        WHERE is_sharp = 1 
        ORDER BY win_rate DESC, total_volume DESC
        ''')
        
        results = []
        for row in cursor.fetchall():
            results.append(WalletStats(
                address=row[0],
                total_bets=row[1],
                wins=row[2],
                losses=row[3],
                total_volume=row[4],
                net_pnl=row[5],
                avg_bet_size=row[6],
                markets_count=row[7],
                win_rate=row[8],
                last_active=row[9]
            ))
        
        conn.close()
        return results
    
    def run_discovery_scan(self, wallet_limit: int = 100):
        """Main discovery pipeline"""
        print(f"🔍 Starting wallet discovery scan...")
        
        # Fetch top wallets by volume
        print("Fetching top wallets by volume...")
        wallet_addresses = self.fetch_top_wallets(wallet_limit)
        print(f"Found {len(wallet_addresses)} wallets to analyze")
        
        sharp_count = 0
        
        for i, wallet in enumerate(wallet_addresses):
            print(f"Analyzing wallet {i+1}/{len(wallet_addresses)}: {wallet[:8]}...")
            
            # Fetch positions for this wallet
            positions = self.fetch_wallet_positions(wallet)
            time.sleep(self.request_delay)  # Rate limiting
            
            if not positions:
                continue
                
            # Analyze performance
            stats = self.analyze_wallet_performance(positions, wallet)
            if stats:
                self.store_wallet_data(stats)
                
                if stats.is_sharp():
                    sharp_count += 1
                    print(f"  ⭐ SHARP: {stats.win_rate:.1%} WR, {stats.total_bets} bets, ${stats.avg_bet_size:.0f} avg")
                else:
                    print(f"  📊 Stats: {stats.win_rate:.1%} WR, {stats.total_bets} bets")
        
        print(f"\n✅ Discovery complete: {sharp_count} sharp wallets identified")
        return self.get_sharp_wallets()

def main():
    """Run wallet discovery pipeline"""
    analyzer = PolymarketWalletAnalyzer()
    
    # Run discovery scan
    sharp_wallets = analyzer.run_discovery_scan(wallet_limit=50)  # Start small
    
    print(f"\n🎯 Sharp Wallets Found: {len(sharp_wallets)}")
    print("-" * 80)
    
    for wallet in sharp_wallets[:10]:  # Show top 10
        print(f"{wallet.address[:8]}... | {wallet.win_rate:.1%} WR | {wallet.total_bets:3d} bets | ${wallet.avg_bet_size:6.0f} avg | {wallet.markets_count} markets")

if __name__ == "__main__":
    main()