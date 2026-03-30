-- Polymarket Arena Supabase Schema
-- Run this in the Supabase SQL Editor at https://app.supabase.com/project/zfubbwntqigcemfdztab/sql

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
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    status TEXT DEFAULT 'inactive',
    strategy_description TEXT
);

CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    bot_id TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
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
    source_data JSONB
);

CREATE TABLE IF NOT EXISTS bot_status (
    bot_id TEXT PRIMARY KEY,
    status TEXT,
    last_heartbeat TIMESTAMPTZ DEFAULT NOW(),
    current_task TEXT,
    error_message TEXT,
    restart_count INTEGER DEFAULT 0,
    uptime_seconds INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS competitions (
    id SERIAL PRIMARY KEY,
    name TEXT,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    duration_hours INTEGER,
    status TEXT,
    winner_bot_id TEXT,
    eliminated_bots TEXT,
    total_volume REAL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS market_opportunities (
    id SERIAL PRIMARY KEY,
    detected_by_bot TEXT,
    opportunity_type TEXT,
    market_title TEXT,
    condition_id TEXT,
    confidence_score REAL,
    expected_edge REAL,
    time_sensitivity_minutes INTEGER,
    data_source TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS shadow_signals (
    id SERIAL PRIMARY KEY,
    bot_id TEXT,
    bot_name TEXT,
    bot_emoji TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    raw_signal_json JSONB,
    signal_headline TEXT,
    signal_explanation TEXT,
    market_title TEXT,
    condition_id TEXT,
    direction TEXT,
    shadow_size REAL,
    entry_price REAL,
    conviction_score REAL,
    market_end_date TEXT,
    resolution_status TEXT DEFAULT 'pending',
    resolved_at TIMESTAMPTZ,
    resolved_price REAL,
    actual_pnl REAL,
    notes TEXT
);
