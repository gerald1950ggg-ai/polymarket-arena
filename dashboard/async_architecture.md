# Streamlit + Async Bots Architecture

## 🔄 **Async Challenge & Solution**

### **The Problem**
- **Bots run async** — our `working_hybrid.py` uses `asyncio`, WebSocket connections, continuous monitoring
- **Streamlit is sync** — runs in request/response cycles, not persistent async loops
- **Need real-time communication** between async bots and sync dashboard

### **The Solution: Shared Database + Background Processes**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  ASYNC BOTS     │    │  SHARED DB      │    │  STREAMLIT      │
│                 │    │                 │    │  DASHBOARD      │
│ S1: monitoring  │◄──►│ SQLite/Redis    │◄──►│                 │
│ S2: analyzing   │    │                 │    │ Reads every 5s  │
│ S3: trading     │    │ - bot_status    │    │ Shows live data │
│ S4: scanning    │    │ - trades        │    │                 │
│ S5: positioning │    │ - performance   │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🛠️ **Implementation Strategy**

### **1. Bots Write to Database**
```python
# In our working_hybrid.py bot
class WorkingHybridMonitor:
    def __init__(self):
        self.db = ArenaDatabase()
    
    async def _execute_copy_trade(self, trade):
        # Execute the trade
        result = await self.paper_trade(trade)
        
        # Write to shared database
        self.db.log_trade({
            'bot_id': 'S1_sharp_copy',
            'timestamp': datetime.now(),
            'action': 'BUY',
            'market': trade.market_title,
            'size': trade.copy_size,
            'price': trade.current_price,
            'conviction': trade.conviction_score,
            'status': 'executed'
        })
        
        # Update bot performance
        self.db.update_bot_performance('S1_sharp_copy', {
            'total_trades': self.trade_count,
            'current_roi': self.calculate_roi(),
            'win_rate': self.calculate_win_rate()
        })

    async def run_forever(self):
        """Continuous bot operation"""
        while True:
            await self.analyze_markets()
            await self.check_copy_signals()
            await asyncio.sleep(30)  # Check every 30 seconds
```

### **2. Dashboard Reads from Database**
```python
# streamlit_app.py
import streamlit as st
import time
from arena_database import ArenaDatabase

def main():
    st.set_page_config(page_title="🏟️ Polymarket Arena", layout="wide")
    
    db = ArenaDatabase()
    
    # Auto-refresh container
    placeholder = st.empty()
    
    while True:
        with placeholder.container():
            # Get fresh data from database
            bot_performance = db.get_live_bot_performance()
            recent_trades = db.get_recent_trades(limit=20)
            
            display_arena_dashboard(bot_performance, recent_trades)
        
        time.sleep(5)  # Refresh every 5 seconds
        st.rerun()
```

### **3. Shared Database Interface**
```python
# arena_database.py
import sqlite3
import json
from datetime import datetime
from typing import Dict, List

class ArenaDatabase:
    def __init__(self, db_path="arena.db"):
        self.db_path = db_path
        self.setup_tables()
    
    def setup_tables(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Bot performance table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_performance (
            bot_id TEXT PRIMARY KEY,
            total_trades INTEGER,
            winning_trades INTEGER,
            total_roi REAL,
            current_balance REAL,
            win_rate REAL,
            sharpe_ratio REAL,
            max_drawdown REAL,
            last_updated TIMESTAMP,
            status TEXT
        )
        ''')
        
        # Individual trades table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id TEXT,
            timestamp TIMESTAMP,
            market_title TEXT,
            action TEXT,
            size REAL,
            price REAL,
            conviction_score REAL,
            pnl REAL,
            status TEXT
        )
        ''')
        
        # Bot status/heartbeat
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_status (
            bot_id TEXT PRIMARY KEY,
            status TEXT,
            last_heartbeat TIMESTAMP,
            current_task TEXT,
            error_message TEXT
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def log_trade(self, trade_data: Dict):
        """Bots call this to log trades"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO trades 
        (bot_id, timestamp, market_title, action, size, price, conviction_score, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_data['bot_id'],
            trade_data['timestamp'],
            trade_data['market'],
            trade_data['action'],
            trade_data['size'],
            trade_data['price'],
            trade_data['conviction'],
            trade_data['status']
        ))
        
        conn.commit()
        conn.close()
    
    def update_bot_performance(self, bot_id: str, performance: Dict):
        """Bots call this to update their performance metrics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT OR REPLACE INTO bot_performance
        (bot_id, total_trades, winning_trades, total_roi, win_rate, last_updated, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            bot_id,
            performance.get('total_trades', 0),
            performance.get('winning_trades', 0), 
            performance.get('total_roi', 0.0),
            performance.get('win_rate', 0.0),
            datetime.now(),
            'active'
        ))
        
        conn.commit()
        conn.close()
    
    def heartbeat(self, bot_id: str, status: str, current_task: str = None):
        """Bots call this to show they're alive"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT OR REPLACE INTO bot_status
        (bot_id, status, last_heartbeat, current_task)
        VALUES (?, ?, ?, ?)
        ''', (bot_id, status, datetime.now(), current_task))
        
        conn.commit()
        conn.close()
    
    def get_live_bot_performance(self) -> List[Dict]:
        """Dashboard calls this to get current bot performance"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT bot_id, total_trades, winning_trades, total_roi, win_rate, 
               last_updated, status
        FROM bot_performance
        ORDER BY total_roi DESC
        ''')
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'bot_id': row[0],
                'total_trades': row[1],
                'winning_trades': row[2],
                'total_roi': row[3],
                'win_rate': row[4],
                'last_updated': row[5],
                'status': row[6]
            })
        
        conn.close()
        return results
    
    def get_recent_trades(self, limit: int = 50) -> List[Dict]:
        """Dashboard calls this for trade feed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT bot_id, timestamp, market_title, action, size, price, conviction_score
        FROM trades
        ORDER BY timestamp DESC
        LIMIT ?
        ''', (limit,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'bot_id': row[0],
                'timestamp': row[1],
                'market': row[2],
                'action': row[3], 
                'size': row[4],
                'price': row[5],
                'conviction': row[6]
            })
        
        conn.close()
        return results
```

## 🚀 **Process Management**

### **Option A: Separate Processes**
```bash
# Terminal 1: Start bots
python S1_sharp_wallet/working_hybrid.py &
python S2_cross_market/monitor.py &
python S3_lp_monitor/scanner.py &

# Terminal 2: Start dashboard  
streamlit run dashboard/streamlit_app.py
```

### **Option B: Process Manager**
```python
# arena_manager.py
import asyncio
import subprocess
import streamlit as st

class ArenaManager:
    def __init__(self):
        self.bot_processes = {}
    
    def start_all_bots(self):
        bots = [
            'S1_sharp_wallet/working_hybrid.py',
            'S2_cross_market/monitor.py', 
            # etc
        ]
        
        for bot in bots:
            process = subprocess.Popen(['python', bot])
            self.bot_processes[bot] = process
    
    def stop_all_bots(self):
        for process in self.bot_processes.values():
            process.terminate()
```

### **Option C: Async Background Tasks (Streamlit Advanced)**
```python
# For true integration - run bots in background threads
import threading
import asyncio

def run_bot_in_background(bot_coroutine):
    """Run async bot in background thread"""
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot_coroutine)
    
    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()

# In streamlit app
if 'bots_started' not in st.session_state:
    st.session_state.bots_started = True
    run_bot_in_background(S1_bot.run_forever())
    run_bot_in_background(S2_bot.run_forever())
```

## ✅ **Yes, Full Async Support!**

**The architecture handles:**
- ✅ **Continuous async bot monitoring** (WebSocket connections, API polling)
- ✅ **Real-time dashboard updates** (5-second refresh cycle)  
- ✅ **Independent bot lifecycles** (start/stop individual bots)
- ✅ **Shared performance tracking** (SQLite database coordination)
- ✅ **Live trade feeds** (async bots → database → dashboard display)

**Best of both worlds:**
- **Bots run truly async** — continuous monitoring, WebSocket subscriptions
- **Dashboard shows everything live** — performance, trades, status
- **Clean separation** — bots can crash/restart without affecting dashboard

Want me to start building this architecture? I'll begin with the shared database and a simple async bot integration.