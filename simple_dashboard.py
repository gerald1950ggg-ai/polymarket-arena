#!/usr/bin/env python3
"""
Polymarket Arena - Simple Streamlit Dashboard
Real-time monitoring of competing trading bots
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from arena_database import ArenaDatabase

# Page config
st.set_page_config(
    page_title="🏟️ Polymarket Arena", 
    page_icon="🏟️",
    layout="wide"
)

# Initialize database
@st.cache_resource
def init_database():
    return ArenaDatabase()

db = init_database()

# Auto-refresh button
if st.button("🔄 Refresh Dashboard"):
    st.rerun()

# Header
st.markdown("# 🏟️ POLYMARKET ARENA")
st.markdown("### Real-time bot competition dashboard")

# Check for active competition
competition = db.get_active_competition()
if competition:
    start_time = datetime.fromisoformat(competition['start_time'])
    end_time = datetime.fromisoformat(competition['end_time'])
    now = datetime.now()
    
    if now < end_time:
        time_remaining = end_time - now
        hours = int(time_remaining.total_seconds() // 3600)
        minutes = int((time_remaining.total_seconds() % 3600) // 60)
        st.success(f"🟢 **{competition['name']}** - {hours}h {minutes}m remaining")
    else:
        st.error(f"🔴 **{competition['name']}** - COMPLETED")
else:
    st.info("No active competition")

# Load data
leaderboard = db.get_live_leaderboard()
recent_trades = db.get_recent_trades(limit=20)
opportunities = db.get_market_opportunities()

# Main content in columns
col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("🏆 Live Leaderboard")
    
    if leaderboard:
        # Create leaderboard dataframe
        df = pd.DataFrame(leaderboard)
        
        # Format for display
        display_df = df[['bot_name', 'total_roi', 'current_balance', 'total_trades', 'win_rate', 'is_alive']].copy()
        display_df.columns = ['Bot Name', 'ROI (%)', 'Balance ($)', 'Trades', 'Win Rate (%)', 'Status']
        
        # Format columns
        display_df['ROI (%)'] = display_df['ROI (%)'].round(1)
        display_df['Balance ($)'] = display_df['Balance ($)'].round(0)
        display_df['Win Rate (%)'] = (display_df['Win Rate (%)'] * 100).round(1)
        display_df['Status'] = display_df['Status'].apply(lambda x: "🟢 Online" if x else "🔴 Offline")
        
        # Display with color coding
        def highlight_winner(row):
            if row.name == 0:  # First place
                return ['background-color: #d4edda'] * len(row)
            elif row.name == len(display_df) - 1:  # Last place
                return ['background-color: #f8d7da'] * len(row)
            else:
                return [''] * len(row)
        
        styled_df = display_df.style.apply(highlight_winner, axis=1)
        st.dataframe(styled_df, use_container_width=True)
        
        # Performance chart
        st.subheader("📈 Performance Chart")
        fig = px.bar(
            df, 
            x='bot_name', 
            y='total_roi',
            title='Bot Performance (ROI %)',
            color='total_roi',
            color_continuous_scale='RdYlGn'
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.warning("No bots registered yet")

with col2:
    st.subheader("🔄 Recent Trades")
    
    if recent_trades:
        for trade in recent_trades[:10]:
            timestamp = datetime.fromisoformat(trade['timestamp']).strftime("%H:%M:%S")
            
            if trade['status'] == 'won':
                color = "green"
                icon = "✅"
            elif trade['status'] == 'lost':
                color = "red"
                icon = "❌"
            else:
                color = "gray"
                icon = "⏳"
            
            st.markdown(f"""
            <div style="border-left: 3px solid {color}; padding: 10px; margin: 5px 0; background-color: #f8f9fa;">
                <strong>{timestamp}</strong> | <strong>{trade['bot_id']}</strong><br>
                {icon} {trade['action']} | ${trade['actual_pnl']:.0f}<br>
                📊 {trade['market_title'][:40]}{'...' if len(trade['market_title']) > 40 else ''}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No trades yet")
    
    st.subheader("💡 Market Opportunities")
    
    if opportunities:
        for opp in opportunities[:5]:
            confidence_color = "green" if opp['confidence'] > 7 else "orange" if opp['confidence'] > 5 else "red"
            
            st.markdown(f"""
            <div style="border: 1px solid {confidence_color}; padding: 8px; margin: 3px 0; border-radius: 5px;">
                <strong>{opp['type'].replace('_', ' ').title()}</strong><br>
                📊 {opp['market_title'][:35]}{'...' if len(opp['market_title']) > 35 else ''}<br>
                🎯 Confidence: {opp['confidence']:.1f}/10 | 📈 Edge: {opp['expected_edge']*100:.1f}%
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No opportunities detected")

# Sidebar controls
st.sidebar.markdown("### 🎮 Arena Controls")

if st.sidebar.button("🚀 Start New Competition"):
    comp_id = db.start_competition("Arena Competition", 48)
    st.sidebar.success(f"Started competition #{comp_id}")
    st.rerun()

if st.sidebar.button("🧹 Reset Demo Data"):
    # Re-run demo data setup
    import subprocess
    subprocess.run(["python", "test_dashboard.py"], cwd="/Users/gerald/.openclaw/workspace/projects/polymarket-arena")
    st.sidebar.success("Demo data reset!")
    st.rerun()

# Statistics
st.sidebar.markdown("### 📊 Arena Stats")
if leaderboard:
    active_bots = sum(1 for bot in leaderboard if bot['is_alive'])
    total_trades = sum(bot['total_trades'] for bot in leaderboard)
    total_volume = sum(bot['current_balance'] for bot in leaderboard)
    
    st.sidebar.metric("Active Bots", active_bots)
    st.sidebar.metric("Total Trades", total_trades)
    st.sidebar.metric("Total Volume", f"${total_volume:,.0f}")

# Auto-refresh info
st.sidebar.markdown("### ⚡ Auto-Refresh")
st.sidebar.info("Click 🔄 Refresh Dashboard to update data")

# Instructions
st.sidebar.markdown("### 📖 Instructions")
st.sidebar.markdown("""
**To run live bot:**
```bash
cd S1-sharp-wallet-copy
source venv/bin/activate
python arena_bot.py
```
""")

# Footer
st.markdown("---")
st.markdown("🏟️ **Polymarket Arena** - Built with Streamlit")
st.markdown(f"*Last updated: {datetime.now().strftime('%H:%M:%S')}*")