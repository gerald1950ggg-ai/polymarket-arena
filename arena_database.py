#!/usr/bin/env python3
"""
Shared database interface for Polymarket Arena
Handles communication between async bots and Streamlit dashboard
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class ArenaDatabase:
    """Shared database for bot performance tracking and dashboard display"""
    
    def __init__(self, db_path: str = "arena.db"):
        self.db_path = db_path
        self.setup_tables()
        logger.info(f"📊 Arena database initialized: {db_path}")
    
    def setup_tables(self):
        """Create all necessary tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Bot performance tracking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_performance (
            bot_id TEXT PRIMARY KEY,
            bot_name TEXT,
            total_trades INTEGER DEFAULT 0,
            winning_trades INTEGER DEFAULT 0,
            losing_trades INTEGER DEFAULT 0,
            total_roi REAL DEFAULT 0.0,
            current_balance REAL DEFAULT 10000.0,
            win_rate REAL DEFAULT 0.0,
            sharpe_ratio REAL DEFAULT 0.0,
            max_drawdown REAL DEFAULT 0.0,
            avg_trade_size REAL DEFAULT 0.0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'inactive',
            strategy_description TEXT
        )
        ''')
        
        # Individual trade log
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            market_title TEXT,
            market_slug TEXT,
            condition_id TEXT,
            action TEXT,
            size REAL,
            price REAL,
            conviction_score REAL,
            expected_roi REAL,
            actual_pnl REAL,
            status TEXT,
            trade_reason TEXT,
            source_data TEXT,
            FOREIGN KEY (bot_id) REFERENCES bot_performance (bot_id)
        )
        ''')
        
        # Bot status and heartbeat
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_status (
            bot_id TEXT PRIMARY KEY,
            status TEXT,
            last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            current_task TEXT,
            error_message TEXT,
            restart_count INTEGER DEFAULT 0,
            uptime_seconds INTEGER DEFAULT 0
        )
        ''')
        
        # Arena competitions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS competitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            duration_hours INTEGER,
            status TEXT,
            winner_bot_id TEXT,
            eliminated_bots TEXT,
            total_volume REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Market opportunities (for cross-bot intelligence)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detected_by_bot TEXT,
            opportunity_type TEXT,
            market_title TEXT,
            condition_id TEXT,
            confidence_score REAL,
            expected_edge REAL,
            time_sensitivity_minutes INTEGER,
            data_source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active'
        )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Database tables created/verified")
    
    # BOT INTERFACE METHODS (called by async bots)
    
    def register_bot(self, bot_id: str, bot_name: str, strategy_description: str, starting_balance: float = 10000.0):
        """Register a new bot in the arena"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT OR REPLACE INTO bot_performance
        (bot_id, bot_name, current_balance, strategy_description, status, last_updated)
        VALUES (?, ?, ?, ?, 'active', CURRENT_TIMESTAMP)
        ''', (bot_id, bot_name, starting_balance, strategy_description))
        
        cursor.execute('''
        INSERT OR REPLACE INTO bot_status
        (bot_id, status, current_task, last_heartbeat)
        VALUES (?, 'starting', 'initializing', CURRENT_TIMESTAMP)
        ''', (bot_id,))
        
        conn.commit()
        conn.close()
        logger.info(f"🤖 Bot registered: {bot_name} ({bot_id})")
    
    def log_trade(self, trade_data: Dict):
        """Log a trade executed by a bot"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO trades 
        (bot_id, market_title, market_slug, condition_id, action, size, price, 
         conviction_score, expected_roi, status, trade_reason, source_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_data['bot_id'],
            trade_data.get('market_title', 'Unknown'),
            trade_data.get('market_slug', ''),
            trade_data.get('condition_id', ''),
            trade_data['action'],
            trade_data['size'],
            trade_data['price'],
            trade_data.get('conviction_score', 0.0),
            trade_data.get('expected_roi', 0.0),
            trade_data.get('status', 'pending'),
            trade_data.get('trade_reason', ''),
            json.dumps(trade_data.get('source_data', {}))
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"📝 Trade logged: {trade_data['bot_id']} {trade_data['action']} {trade_data['size']:.0f}")
    
    def update_bot_performance(self, bot_id: str, performance: Dict):
        """Update bot's overall performance metrics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE bot_performance SET
            total_trades = ?,
            winning_trades = ?,
            losing_trades = ?,
            total_roi = ?,
            current_balance = ?,
            win_rate = ?,
            sharpe_ratio = ?,
            max_drawdown = ?,
            avg_trade_size = ?,
            last_updated = CURRENT_TIMESTAMP
        WHERE bot_id = ?
        ''', (
            performance.get('total_trades', 0),
            performance.get('winning_trades', 0),
            performance.get('losing_trades', 0),
            performance.get('total_roi', 0.0),
            performance.get('current_balance', 10000.0),
            performance.get('win_rate', 0.0),
            performance.get('sharpe_ratio', 0.0),
            performance.get('max_drawdown', 0.0),
            performance.get('avg_trade_size', 0.0),
            bot_id
        ))
        
        conn.commit()
        conn.close()
        logger.debug(f"📊 Performance updated: {bot_id}")
    
    def heartbeat(self, bot_id: str, status: str, current_task: str = None, error_message: str = None):
        """Bot heartbeat to show it's alive"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT OR REPLACE INTO bot_status
        (bot_id, status, last_heartbeat, current_task, error_message)
        VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?)
        ''', (bot_id, status, current_task, error_message))
        
        conn.commit()
        conn.close()
        logger.debug(f"💓 Heartbeat: {bot_id} - {status}")
    
    def log_opportunity(self, bot_id: str, opportunity_data: Dict):
        """Log a market opportunity detected by a bot"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO market_opportunities
        (detected_by_bot, opportunity_type, market_title, condition_id, confidence_score,
         expected_edge, time_sensitivity_minutes, data_source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            bot_id,
            opportunity_data['type'],
            opportunity_data.get('market_title', ''),
            opportunity_data.get('condition_id', ''),
            opportunity_data.get('confidence_score', 0.0),
            opportunity_data.get('expected_edge', 0.0),
            opportunity_data.get('time_sensitivity_minutes', 60),
            opportunity_data.get('data_source', '')
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"💡 Opportunity logged: {bot_id} - {opportunity_data['type']}")
    
    # DASHBOARD INTERFACE METHODS (called by Streamlit)
    
    def get_live_leaderboard(self) -> List[Dict]:
        """Get current bot rankings for dashboard"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT 
            bp.bot_id, bp.bot_name, bp.total_trades, bp.winning_trades,
            bp.total_roi, bp.current_balance, bp.win_rate, bp.sharpe_ratio,
            bp.max_drawdown, bp.last_updated, bp.status,
            bs.last_heartbeat, bs.current_task, bs.status as live_status
        FROM bot_performance bp
        LEFT JOIN bot_status bs ON bp.bot_id = bs.bot_id
        ORDER BY bp.total_roi DESC
        ''')
        
        results = []
        for row in cursor.fetchall():
            # Check if bot is alive (heartbeat within 2 minutes)
            last_heartbeat = datetime.fromisoformat(row[11]) if row[11] else None
            is_alive = False
            if last_heartbeat:
                is_alive = (datetime.now() - last_heartbeat).seconds < 120
            
            results.append({
                'bot_id': row[0],
                'bot_name': row[1],
                'total_trades': row[2],
                'winning_trades': row[3],
                'total_roi': row[4],
                'current_balance': row[5],
                'win_rate': row[6],
                'sharpe_ratio': row[7],
                'max_drawdown': row[8],
                'last_updated': row[9],
                'status': row[10],
                'is_alive': is_alive,
                'current_task': row[12],
                'live_status': row[13]
            })
        
        conn.close()
        return results
    
    def get_recent_trades(self, limit: int = 50, bot_id: str = None) -> List[Dict]:
        """Get recent trades for dashboard feed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if bot_id:
            cursor.execute('''
            SELECT bot_id, timestamp, market_title, action, size, price, 
                   conviction_score, expected_roi, actual_pnl, status, trade_reason
            FROM trades 
            WHERE bot_id = ?
            ORDER BY timestamp DESC 
            LIMIT ?
            ''', (bot_id, limit))
        else:
            cursor.execute('''
            SELECT bot_id, timestamp, market_title, action, size, price,
                   conviction_score, expected_roi, actual_pnl, status, trade_reason
            FROM trades 
            ORDER BY timestamp DESC 
            LIMIT ?
            ''', (limit,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'bot_id': row[0],
                'timestamp': row[1],
                'market_title': row[2],
                'action': row[3],
                'size': row[4],
                'price': row[5],
                'conviction_score': row[6],
                'expected_roi': row[7],
                'actual_pnl': row[8],
                'status': row[9],
                'trade_reason': row[10]
            })
        
        conn.close()
        return results
    
    def get_performance_history(self, bot_id: str = None, hours: int = 24) -> List[Dict]:
        """Get performance history for charts"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since_time = datetime.now() - timedelta(hours=hours)
        
        if bot_id:
            cursor.execute('''
            SELECT timestamp, size, actual_pnl, status
            FROM trades 
            WHERE bot_id = ? AND timestamp > ?
            ORDER BY timestamp
            ''', (bot_id, since_time.isoformat()))
        else:
            cursor.execute('''
            SELECT bot_id, timestamp, size, actual_pnl, status
            FROM trades 
            WHERE timestamp > ?
            ORDER BY timestamp
            ''', (since_time.isoformat(),))
        
        results = []
        for row in cursor.fetchall():
            if bot_id:
                results.append({
                    'timestamp': row[0],
                    'size': row[1],
                    'pnl': row[2],
                    'status': row[3]
                })
            else:
                results.append({
                    'bot_id': row[0],
                    'timestamp': row[1],
                    'size': row[2], 
                    'pnl': row[3],
                    'status': row[4]
                })
        
        conn.close()
        return results
    
    def get_market_opportunities(self, active_only: bool = True) -> List[Dict]:
        """Get current market opportunities for dashboard"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if active_only:
            cursor.execute('''
            SELECT detected_by_bot, opportunity_type, market_title, confidence_score,
                   expected_edge, time_sensitivity_minutes, created_at
            FROM market_opportunities
            WHERE status = 'active' AND 
                  datetime(created_at, '+' || time_sensitivity_minutes || ' minutes') > datetime('now')
            ORDER BY confidence_score DESC, created_at DESC
            LIMIT 20
            ''')
        else:
            cursor.execute('''
            SELECT detected_by_bot, opportunity_type, market_title, confidence_score,
                   expected_edge, time_sensitivity_minutes, created_at
            FROM market_opportunities
            ORDER BY created_at DESC
            LIMIT 50
            ''')
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'detected_by': row[0],
                'type': row[1],
                'market_title': row[2],
                'confidence': row[3],
                'expected_edge': row[4],
                'time_sensitivity': row[5],
                'created_at': row[6]
            })
        
        conn.close()
        return results
    
    # ARENA MANAGEMENT METHODS
    
    def start_competition(self, name: str, duration_hours: int = 48):
        """Start a new arena competition"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=duration_hours)
        
        cursor.execute('''
        INSERT INTO competitions (name, start_time, end_time, duration_hours, status)
        VALUES (?, ?, ?, ?, 'active')
        ''', (name, start_time, end_time, duration_hours))
        
        competition_id = cursor.lastrowid
        
        # Reset all bot balances to starting amount
        cursor.execute('''
        UPDATE bot_performance SET 
            current_balance = 10000.0,
            total_roi = 0.0,
            total_trades = 0,
            winning_trades = 0,
            losing_trades = 0
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"🏁 Competition started: {name} (ID: {competition_id})")
        return competition_id
    
    def get_active_competition(self) -> Optional[Dict]:
        """Get currently active competition"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT id, name, start_time, end_time, status
        FROM competitions
        WHERE status = 'active'
        ORDER BY start_time DESC
        LIMIT 1
        ''')
        
        result = cursor.fetchone()
        if result:
            return {
                'id': result[0],
                'name': result[1],
                'start_time': result[2],
                'end_time': result[3],
                'status': result[4]
            }
        
        conn.close()
        return None
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old trade data to keep database manageable"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        cursor.execute('DELETE FROM trades WHERE timestamp < ?', (cutoff_date,))
        cursor.execute('DELETE FROM market_opportunities WHERE created_at < ?', (cutoff_date,))
        
        deleted_trades = cursor.rowcount
        conn.commit()
        conn.close()
        logger.info(f"🧹 Cleaned up {deleted_trades} old records")


# Test the database
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    db = ArenaDatabase("test_arena.db")
    
    # Test bot registration
    db.register_bot("S1_sharp_copy", "Sharp Wallet Copy", "Monitors high-performing wallets and copies their trades")
    db.register_bot("S2_divergence", "Cross-Market Divergence", "Detects price differences across prediction markets")
    
    # Test trade logging
    db.log_trade({
        'bot_id': 'S1_sharp_copy',
        'market_title': 'Will Bitcoin hit $100k in 2026?',
        'action': 'BUY',
        'size': 500,
        'price': 0.67,
        'conviction_score': 8.5,
        'expected_roi': 0.15,
        'status': 'executed',
        'trade_reason': 'Sharp wallet 0x123 bought large position'
    })
    
    # Test performance update
    db.update_bot_performance('S1_sharp_copy', {
        'total_trades': 1,
        'winning_trades': 1,
        'total_roi': 15.2,
        'current_balance': 11520.0,
        'win_rate': 1.0
    })
    
    # Test dashboard queries
    leaderboard = db.get_live_leaderboard()
    trades = db.get_recent_trades(10)
    
    print("📊 Leaderboard:")
    for bot in leaderboard:
        print(f"  {bot['bot_name']}: {bot['total_roi']:.1f}% ROI")
    
    print(f"\n📝 Recent trades: {len(trades)}")
    for trade in trades[:3]:
        print(f"  {trade['bot_id']}: {trade['action']} {trade['market_title']}")