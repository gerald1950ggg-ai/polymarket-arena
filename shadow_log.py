#!/usr/bin/env python3
"""
Shadow Mode Signal Logger
Logs real bot signals with full context for retroactive scoring
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict

DB_PATH = "shadow.db"

def init_shadow_db(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS shadow_signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_id TEXT NOT NULL,
        bot_name TEXT NOT NULL,
        bot_emoji TEXT DEFAULT "🤖",
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        -- What the bot saw (raw data)
        raw_signal_json TEXT,

        -- Human-readable explanation
        signal_headline TEXT,
        signal_explanation TEXT,

        -- The trade we would have made
        market_title TEXT,
        condition_id TEXT,
        direction TEXT,
        shadow_size REAL DEFAULT 500.0,
        entry_price REAL,
        conviction_score REAL,

        -- Resolution tracking
        market_end_date TEXT,
        resolution_status TEXT DEFAULT "pending",
        resolved_at TIMESTAMP,
        resolved_price REAL,
        actual_pnl REAL,

        -- Meta
        notes TEXT
    )
    ''')
    conn.commit()
    conn.close()

def log_signal(
    bot_id: str,
    bot_name: str,
    bot_emoji: str,
    signal_headline: str,
    signal_explanation: str,
    market_title: str,
    direction: str,
    entry_price: float,
    conviction_score: float,
    condition_id: str = "",
    market_end_date: str = "",
    shadow_size: float = 500.0,
    raw_signal: Optional[Dict] = None,
    notes: str = "",
    db_path: str = DB_PATH
) -> int:
    """Log a shadow signal. Returns the signal ID."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO shadow_signals
    (bot_id, bot_name, bot_emoji, signal_headline, signal_explanation,
     market_title, condition_id, direction, shadow_size, entry_price,
     conviction_score, market_end_date, raw_signal_json, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        bot_id, bot_name, bot_emoji,
        signal_headline, signal_explanation,
        market_title, condition_id,
        direction, shadow_size, entry_price,
        conviction_score, market_end_date,
        json.dumps(raw_signal or {}), notes
    ))
    signal_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return signal_id

def get_signals(limit=50, bot_id=None, status=None, db_path=DB_PATH):
    """Fetch signals for dashboard display."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT * FROM shadow_signals"
    params = []
    conditions = []

    if bot_id:
        conditions.append("bot_id = ?")
        params.append(bot_id)
    if status:
        conditions.append("resolution_status = ?")
        params.append(status)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def resolve_signal(signal_id: int, resolved_price: float, db_path: str = DB_PATH):
    """
    Mark a signal as resolved.
    resolved_price: 1.0 = YES won, 0.0 = NO won (YES lost)
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT direction, entry_price, shadow_size FROM shadow_signals WHERE id = ?", (signal_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return

    direction, entry_price, shadow_size = row

    # Calculate real P&L
    if direction == "BUY":
        # Bought YES at entry_price. If YES wins (resolved_price=1.0), we get $1 per share
        shares = shadow_size / entry_price
        payout = shares * resolved_price
        actual_pnl = payout - shadow_size
    else:  # SELL
        # Bet NO (bought NO). NO wins if resolved_price = 0.0
        no_price = 1.0 - entry_price
        shares = shadow_size / no_price
        payout = shares * (1.0 - resolved_price)
        actual_pnl = payout - shadow_size

    status = "won" if actual_pnl > 0 else "lost"

    cursor.execute('''
    UPDATE shadow_signals SET
        resolution_status = ?,
        resolved_at = CURRENT_TIMESTAMP,
        resolved_price = ?,
        actual_pnl = ?
    WHERE id = ?
    ''', (status, resolved_price, round(actual_pnl, 2), signal_id))

    conn.commit()
    conn.close()
    return actual_pnl

def get_shadow_stats(db_path: str = DB_PATH) -> Dict:
    """Get overall shadow mode performance stats."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM shadow_signals")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM shadow_signals WHERE resolution_status = 'pending'")
    pending = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM shadow_signals WHERE resolution_status = 'won'")
    won = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM shadow_signals WHERE resolution_status = 'lost'")
    lost = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(actual_pnl), 0) FROM shadow_signals WHERE resolution_status IN ('won','lost')")
    total_pnl = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(shadow_size), 0) FROM shadow_signals WHERE resolution_status IN ('won','lost')")
    total_risked = cursor.fetchone()[0]

    conn.close()

    resolved = won + lost
    win_rate = (won / resolved * 100) if resolved > 0 else 0
    roi = (total_pnl / total_risked * 100) if total_risked > 0 else 0

    return {
        "total_signals": total,
        "pending": pending,
        "won": won,
        "lost": lost,
        "win_rate": round(win_rate, 1),
        "total_pnl": round(total_pnl, 2),
        "roi": round(roi, 2)
    }

# Initialize DB on import
init_shadow_db()

if __name__ == "__main__":
    # Demo: log a test signal
    sid = log_signal(
        bot_id="S1_sharp_copy",
        bot_name="Sharp Wallet Copy",
        bot_emoji="🎯",
        signal_headline='Following wallet 0x90f8b0 into "Fed cuts rates in Q1?"',
        signal_explanation=(
            "Wallet 0x90f8b0 (ranked #3 by 7-day profit, $847k earned) just bought "
            "2,400 YES shares at $0.38. Their last 5 calls resulted in 4 winners. "
            "This is a high-conviction follow. Market currently at 38¢ implying 62% "
            "chance of NO — we disagree based on wallet signal strength."
        ),
        market_title='Will the Fed cut rates in Q1 2026?',
        direction="BUY",
        entry_price=0.38,
        conviction_score=8.5,
        condition_id="0xabc123",
        market_end_date="2026-03-31",
        shadow_size=500.0,
        raw_signal={"wallet": "0x90f8b0", "shares_bought": 2400, "price": 0.38, "rank": 3},
        notes="High priority — large wallet, strong track record"
    )
    print(f"✅ Logged signal #{sid}")

    signals = get_signals(limit=5)
    print(f"\n📋 {len(signals)} signals in log:")
    for s in signals:
        print(f"  [{s['id']}] {s['bot_emoji']} {s['signal_headline'][:60]}")

    stats = get_shadow_stats()
    print(f"\n📊 Stats: {stats}")
