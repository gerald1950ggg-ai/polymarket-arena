#!/usr/bin/env python3
"""
Shared database interface for Polymarket Arena
Uses Supabase when SUPABASE_URL + SUPABASE_SERVICE_KEY env vars are set,
falls back to SQLite for local dev.
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Backend detection
# ──────────────────────────────────────────────────────────────────────────────

def _use_supabase() -> bool:
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_KEY"))


def _get_supabase_client():
    from supabase import create_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    return create_client(url, key)


# ──────────────────────────────────────────────────────────────────────────────
# SQLite helpers (unchanged from original)
# ──────────────────────────────────────────────────────────────────────────────

def _sqlite_conn(db_path: str):
    import sqlite3
    return sqlite3.connect(db_path)


# ──────────────────────────────────────────────────────────────────────────────
# Main class
# ──────────────────────────────────────────────────────────────────────────────

class ArenaDatabase:
    """Shared database for bot performance tracking and dashboard display.

    Identical public method signatures regardless of backend.
    """

    def __init__(self, db_path: str = "arena.db"):
        self.db_path = db_path
        self._backend = "supabase" if _use_supabase() else "sqlite"
        if self._backend == "supabase":
            self._sb = _get_supabase_client()
            logger.info("📊 Arena database initialized: Supabase backend")
        else:
            logger.info(f"📊 Arena database initialized: SQLite ({db_path})")
        self.setup_tables()

    # ──────────────────────────────────────────────────────────────────────────
    # Schema setup
    # ──────────────────────────────────────────────────────────────────────────

    def setup_tables(self):
        """Create all necessary tables (SQLite only; Supabase uses pre-created schema)."""
        if self._backend == "supabase":
            logger.info("✅ Supabase backend: skipping local table creation")
            return

        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

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
            status TEXT DEFAULT "inactive",
            strategy_description TEXT
        )
        ''')

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
            status TEXT DEFAULT "active"
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shadow_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id TEXT,
            bot_name TEXT,
            bot_emoji TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            raw_signal_json TEXT,
            signal_headline TEXT,
            signal_explanation TEXT,
            market_title TEXT,
            condition_id TEXT,
            direction TEXT,
            shadow_size REAL,
            entry_price REAL,
            conviction_score REAL,
            market_end_date TEXT,
            resolution_status TEXT DEFAULT "pending",
            resolved_at TIMESTAMP,
            resolved_price REAL,
            actual_pnl REAL,
            notes TEXT
        )
        ''')

        conn.commit()
        conn.close()
        logger.info("✅ SQLite tables created/verified")

    # ──────────────────────────────────────────────────────────────────────────
    # BOT INTERFACE METHODS
    # ──────────────────────────────────────────────────────────────────────────

    def register_bot(self, bot_id: str, bot_name: str, strategy_description: str,
                     starting_balance: float = 10000.0):
        """Register a new bot in the arena."""
        if self._backend == "supabase":
            self._sb.table("bot_performance").upsert({
                "bot_id": bot_id,
                "bot_name": bot_name,
                "current_balance": starting_balance,
                "strategy_description": strategy_description,
                "status": "active",
                "last_updated": datetime.utcnow().isoformat(),
            }).execute()
            self._sb.table("bot_status").upsert({
                "bot_id": bot_id,
                "status": "starting",
                "current_task": "initializing",
                "last_heartbeat": datetime.utcnow().isoformat(),
            }).execute()
        else:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
            INSERT OR REPLACE INTO bot_performance
            (bot_id, bot_name, current_balance, strategy_description, status, last_updated)
            VALUES (?, ?, ?, ?, "active", CURRENT_TIMESTAMP)
            ''', (bot_id, bot_name, starting_balance, strategy_description))
            cursor.execute('''
            INSERT OR REPLACE INTO bot_status
            (bot_id, status, current_task, last_heartbeat)
            VALUES (?, "starting", "initializing", CURRENT_TIMESTAMP)
            ''', (bot_id,))
            conn.commit()
            conn.close()
        logger.info(f"🤖 Bot registered: {bot_name} ({bot_id})")

    def log_trade(self, trade_data: Dict):
        """Log a trade executed by a bot."""
        if self._backend == "supabase":
            source = trade_data.get("source_data", {})
            self._sb.table("trades").insert({
                "bot_id": trade_data["bot_id"],
                "timestamp": datetime.utcnow().isoformat(),
                "market_title": trade_data.get("market_title", "Unknown"),
                "market_slug": trade_data.get("market_slug", ""),
                "condition_id": trade_data.get("condition_id", ""),
                "action": trade_data["action"],
                "size": trade_data["size"],
                "price": trade_data["price"],
                "conviction_score": trade_data.get("conviction_score", 0.0),
                "expected_roi": trade_data.get("expected_roi", 0.0),
                "actual_pnl": trade_data.get("actual_pnl"),
                "status": trade_data.get("status", "pending"),
                "trade_reason": trade_data.get("trade_reason", ""),
                "source_data": source if isinstance(source, dict) else {},
            }).execute()
        else:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO trades
            (bot_id, market_title, market_slug, condition_id, action, size, price,
             conviction_score, expected_roi, status, trade_reason, source_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade_data["bot_id"],
                trade_data.get("market_title", "Unknown"),
                trade_data.get("market_slug", ""),
                trade_data.get("condition_id", ""),
                trade_data["action"],
                trade_data["size"],
                trade_data["price"],
                trade_data.get("conviction_score", 0.0),
                trade_data.get("expected_roi", 0.0),
                trade_data.get("status", "pending"),
                trade_data.get("trade_reason", ""),
                json.dumps(trade_data.get("source_data", {})),
            ))
            conn.commit()
            conn.close()
        logger.info(f"📝 Trade logged: {trade_data['bot_id']} {trade_data['action']} {trade_data['size']:.0f}")

    def update_bot_performance(self, bot_id: str, performance: Dict):
        """Update bot's overall performance metrics."""
        if self._backend == "supabase":
            self._sb.table("bot_performance").upsert({
                "bot_id": bot_id,
                "total_trades": performance.get("total_trades", 0),
                "winning_trades": performance.get("winning_trades", 0),
                "losing_trades": performance.get("losing_trades", 0),
                "total_roi": performance.get("total_roi", 0.0),
                "current_balance": performance.get("current_balance", 10000.0),
                "win_rate": performance.get("win_rate", 0.0),
                "sharpe_ratio": performance.get("sharpe_ratio", 0.0),
                "max_drawdown": performance.get("max_drawdown", 0.0),
                "avg_trade_size": performance.get("avg_trade_size", 0.0),
                "last_updated": datetime.utcnow().isoformat(),
            }).execute()
        else:
            import sqlite3
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
                performance.get("total_trades", 0),
                performance.get("winning_trades", 0),
                performance.get("losing_trades", 0),
                performance.get("total_roi", 0.0),
                performance.get("current_balance", 10000.0),
                performance.get("win_rate", 0.0),
                performance.get("sharpe_ratio", 0.0),
                performance.get("max_drawdown", 0.0),
                performance.get("avg_trade_size", 0.0),
                bot_id,
            ))
            conn.commit()
            conn.close()
        logger.debug(f"📊 Performance updated: {bot_id}")

    def heartbeat(self, bot_id: str, status: str, current_task: str = None,
                  error_message: str = None):
        """Bot heartbeat to show it's alive."""
        if self._backend == "supabase":
            self._sb.table("bot_status").upsert({
                "bot_id": bot_id,
                "status": status,
                "last_heartbeat": datetime.utcnow().isoformat(),
                "current_task": current_task,
                "error_message": error_message,
            }).execute()
        else:
            import sqlite3
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
        """Log a market opportunity detected by a bot."""
        if self._backend == "supabase":
            self._sb.table("market_opportunities").insert({
                "detected_by_bot": bot_id,
                "opportunity_type": opportunity_data["type"],
                "market_title": opportunity_data.get("market_title", ""),
                "condition_id": opportunity_data.get("condition_id", ""),
                "confidence_score": opportunity_data.get("confidence_score", 0.0),
                "expected_edge": opportunity_data.get("expected_edge", 0.0),
                "time_sensitivity_minutes": opportunity_data.get("time_sensitivity_minutes", 60),
                "data_source": opportunity_data.get("data_source", ""),
                "created_at": datetime.utcnow().isoformat(),
            }).execute()
        else:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO market_opportunities
            (detected_by_bot, opportunity_type, market_title, condition_id, confidence_score,
             expected_edge, time_sensitivity_minutes, data_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                bot_id,
                opportunity_data["type"],
                opportunity_data.get("market_title", ""),
                opportunity_data.get("condition_id", ""),
                opportunity_data.get("confidence_score", 0.0),
                opportunity_data.get("expected_edge", 0.0),
                opportunity_data.get("time_sensitivity_minutes", 60),
                opportunity_data.get("data_source", ""),
            ))
            conn.commit()
            conn.close()
        logger.info(f"💡 Opportunity logged: {bot_id} - {opportunity_data['type']}")

    # ──────────────────────────────────────────────────────────────────────────
    # DASHBOARD INTERFACE METHODS
    # ──────────────────────────────────────────────────────────────────────────

    def get_live_leaderboard(self) -> List[Dict]:
        """Get current bot rankings for dashboard."""
        if self._backend == "supabase":
            bp_resp = self._sb.table("bot_performance").select("*").order("total_roi", desc=True).execute()
            bs_resp = self._sb.table("bot_status").select("*").execute()
            bs_map = {r["bot_id"]: r for r in (bs_resp.data or [])}

            results = []
            for bp in (bp_resp.data or []):
                bs = bs_map.get(bp["bot_id"], {})
                last_hb_str = bs.get("last_heartbeat")
                is_alive = False
                if last_hb_str:
                    try:
                        last_hb = datetime.fromisoformat(last_hb_str.replace("Z", "+00:00"))
                        delta = (datetime.utcnow().replace(tzinfo=last_hb.tzinfo) - last_hb).total_seconds()
                        is_alive = delta < 120
                    except Exception:
                        pass
                results.append({
                    "bot_id": bp.get("bot_id"),
                    "bot_name": bp.get("bot_name"),
                    "total_trades": bp.get("total_trades", 0),
                    "winning_trades": bp.get("winning_trades", 0),
                    "total_roi": bp.get("total_roi", 0.0),
                    "current_balance": bp.get("current_balance", 10000.0),
                    "win_rate": bp.get("win_rate", 0.0),
                    "sharpe_ratio": bp.get("sharpe_ratio", 0.0),
                    "max_drawdown": bp.get("max_drawdown", 0.0),
                    "last_updated": bp.get("last_updated"),
                    "status": bp.get("status"),
                    "is_alive": is_alive,
                    "current_task": bs.get("current_task"),
                    "live_status": bs.get("status"),
                })
            return results
        else:
            import sqlite3
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
                last_heartbeat = datetime.fromisoformat(row[11]) if row[11] else None
                is_alive = False
                if last_heartbeat:
                    is_alive = (datetime.now() - last_heartbeat).seconds < 120
                results.append({
                    "bot_id": row[0], "bot_name": row[1], "total_trades": row[2],
                    "winning_trades": row[3], "total_roi": row[4], "current_balance": row[5],
                    "win_rate": row[6], "sharpe_ratio": row[7], "max_drawdown": row[8],
                    "last_updated": row[9], "status": row[10], "is_alive": is_alive,
                    "current_task": row[12], "live_status": row[13],
                })
            conn.close()
            return results

    def get_recent_trades(self, limit: int = 50, bot_id: str = None) -> List[Dict]:
        """Get recent trades for dashboard feed."""
        if self._backend == "supabase":
            q = self._sb.table("trades").select(
                "bot_id,timestamp,market_title,action,size,price,conviction_score,expected_roi,actual_pnl,status,trade_reason"
            ).order("timestamp", desc=True).limit(limit)
            if bot_id:
                q = q.eq("bot_id", bot_id)
            resp = q.execute()
            return resp.data or []
        else:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            if bot_id:
                cursor.execute('''
                SELECT bot_id, timestamp, market_title, action, size, price,
                       conviction_score, expected_roi, actual_pnl, status, trade_reason
                FROM trades WHERE bot_id = ? ORDER BY timestamp DESC LIMIT ?
                ''', (bot_id, limit))
            else:
                cursor.execute('''
                SELECT bot_id, timestamp, market_title, action, size, price,
                       conviction_score, expected_roi, actual_pnl, status, trade_reason
                FROM trades ORDER BY timestamp DESC LIMIT ?
                ''', (limit,))
            results = []
            for row in cursor.fetchall():
                results.append({
                    "bot_id": row[0], "timestamp": row[1], "market_title": row[2],
                    "action": row[3], "size": row[4], "price": row[5],
                    "conviction_score": row[6], "expected_roi": row[7],
                    "actual_pnl": row[8], "status": row[9], "trade_reason": row[10],
                })
            conn.close()
            return results

    def get_performance_history(self, bot_id: str = None, hours: int = 24) -> List[Dict]:
        """Get performance history for charts."""
        if self._backend == "supabase":
            since_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            q = self._sb.table("trades").select(
                "bot_id,timestamp,size,actual_pnl,status"
            ).gte("timestamp", since_time).order("timestamp")
            if bot_id:
                q = q.eq("bot_id", bot_id)
            resp = q.execute()
            results = []
            for r in (resp.data or []):
                entry = {"timestamp": r["timestamp"], "size": r["size"],
                         "pnl": r["actual_pnl"], "status": r["status"]}
                if not bot_id:
                    entry["bot_id"] = r["bot_id"]
                results.append(entry)
            return results
        else:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            since_time = datetime.now() - timedelta(hours=hours)
            if bot_id:
                cursor.execute('''
                SELECT timestamp, size, actual_pnl, status FROM trades
                WHERE bot_id = ? AND timestamp > ? ORDER BY timestamp
                ''', (bot_id, since_time.isoformat()))
                results = [{"timestamp": r[0], "size": r[1], "pnl": r[2], "status": r[3]}
                           for r in cursor.fetchall()]
            else:
                cursor.execute('''
                SELECT bot_id, timestamp, size, actual_pnl, status FROM trades
                WHERE timestamp > ? ORDER BY timestamp
                ''', (since_time.isoformat(),))
                results = [{"bot_id": r[0], "timestamp": r[1], "size": r[2],
                            "pnl": r[3], "status": r[4]}
                           for r in cursor.fetchall()]
            conn.close()
            return results

    def get_market_opportunities(self, active_only: bool = True) -> List[Dict]:
        """Get current market opportunities for dashboard."""
        if self._backend == "supabase":
            q = self._sb.table("market_opportunities").select(
                "detected_by_bot,opportunity_type,market_title,confidence_score,"
                "expected_edge,time_sensitivity_minutes,created_at"
            ).order("confidence_score", desc=True).limit(20 if active_only else 50)
            if active_only:
                q = q.eq("status", "active")
            resp = q.execute()
            return [
                {
                    "detected_by": r["detected_by_bot"],
                    "type": r["opportunity_type"],
                    "market_title": r["market_title"],
                    "confidence": r["confidence_score"],
                    "expected_edge": r["expected_edge"],
                    "time_sensitivity": r["time_sensitivity_minutes"],
                    "created_at": r["created_at"],
                }
                for r in (resp.data or [])
            ]
        else:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            if active_only:
                cursor.execute('''
                SELECT detected_by_bot, opportunity_type, market_title, confidence_score,
                       expected_edge, time_sensitivity_minutes, created_at
                FROM market_opportunities
                WHERE status = "active" AND
                      datetime(created_at, "+" || time_sensitivity_minutes || " minutes") > datetime("now")
                ORDER BY confidence_score DESC, created_at DESC LIMIT 20
                ''')
            else:
                cursor.execute('''
                SELECT detected_by_bot, opportunity_type, market_title, confidence_score,
                       expected_edge, time_sensitivity_minutes, created_at
                FROM market_opportunities ORDER BY created_at DESC LIMIT 50
                ''')
            results = [
                {
                    "detected_by": r[0], "type": r[1], "market_title": r[2],
                    "confidence": r[3], "expected_edge": r[4],
                    "time_sensitivity": r[5], "created_at": r[6],
                }
                for r in cursor.fetchall()
            ]
            conn.close()
            return results

    # ──────────────────────────────────────────────────────────────────────────
    # ARENA MANAGEMENT METHODS
    # ──────────────────────────────────────────────────────────────────────────

    def start_competition(self, name: str, duration_hours: int = 48):
        """Start a new arena competition."""
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(hours=duration_hours)

        if self._backend == "supabase":
            resp = self._sb.table("competitions").insert({
                "name": name,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_hours": duration_hours,
                "status": "active",
                "created_at": start_time.isoformat(),
            }).execute()
            competition_id = (resp.data or [{}])[0].get("id")
            # Reset all bot balances
            self._sb.table("bot_performance").update({
                "current_balance": 10000.0,
                "total_roi": 0.0,
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
            }).neq("bot_id", "").execute()
        else:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO competitions (name, start_time, end_time, duration_hours, status)
            VALUES (?, ?, ?, ?, "active")
            ''', (name, start_time, end_time, duration_hours))
            competition_id = cursor.lastrowid
            cursor.execute('''
            UPDATE bot_performance SET
                current_balance = 10000.0, total_roi = 0.0,
                total_trades = 0, winning_trades = 0, losing_trades = 0
            ''')
            conn.commit()
            conn.close()

        logger.info(f"🏁 Competition started: {name} (ID: {competition_id})")
        return competition_id

    def get_active_competition(self) -> Optional[Dict]:
        """Get currently active competition."""
        if self._backend == "supabase":
            resp = self._sb.table("competitions").select(
                "id,name,start_time,end_time,status"
            ).eq("status", "active").order("start_time", desc=True).limit(1).execute()
            data = resp.data or []
            if data:
                r = data[0]
                return {
                    "id": r["id"], "name": r["name"],
                    "start_time": r["start_time"], "end_time": r["end_time"],
                    "status": r["status"],
                }
            return None
        else:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
            SELECT id, name, start_time, end_time, status FROM competitions
            WHERE status = "active" ORDER BY start_time DESC LIMIT 1
            ''')
            result = cursor.fetchone()
            conn.close()
            if result:
                return {
                    "id": result[0], "name": result[1],
                    "start_time": result[2], "end_time": result[3],
                    "status": result[4],
                }
            return None

    def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old trade data to keep database manageable."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

        if self._backend == "supabase":
            self._sb.table("trades").delete().lt(
                "timestamp", cutoff_date.isoformat()
            ).execute()
            self._sb.table("market_opportunities").delete().lt(
                "created_at", cutoff_date.isoformat()
            ).execute()
            logger.info(f"🧹 Supabase cleanup: records older than {days_to_keep} days deleted")
        else:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trades WHERE timestamp < ?", (cutoff_date,))
            cursor.execute("DELETE FROM market_opportunities WHERE created_at < ?", (cutoff_date,))
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            logger.info(f"🧹 Cleaned up {deleted} old records")


# ──────────────────────────────────────────────────────────────────────────────
# Smoke test
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    db = ArenaDatabase("test_arena.db")

    db.register_bot("S1_sharp_copy", "Sharp Wallet Copy",
                    "Monitors high-performing wallets and copies their trades")
    db.register_bot("S2_divergence", "Cross-Market Divergence",
                    "Detects price differences across prediction markets")

    db.log_trade({
        "bot_id": "S1_sharp_copy",
        "market_title": "Will Bitcoin hit $100k in 2026?",
        "action": "BUY",
        "size": 500,
        "price": 0.67,
        "conviction_score": 8.5,
        "expected_roi": 0.15,
        "status": "executed",
        "trade_reason": "Sharp wallet copy signal",
    })

    db.update_bot_performance("S1_sharp_copy", {
        "total_trades": 1, "winning_trades": 1,
        "total_roi": 15.2, "current_balance": 11520.0, "win_rate": 1.0,
    })

    leaderboard = db.get_live_leaderboard()
    trades = db.get_recent_trades(10)

    print(f"Backend: {db._backend}")
    print("📊 Leaderboard:")
    for bot in leaderboard:
        print(f"  {bot['bot_name']}: {bot['total_roi']:.1f}% ROI")
    print(f"\n📝 Recent trades: {len(trades)}")
