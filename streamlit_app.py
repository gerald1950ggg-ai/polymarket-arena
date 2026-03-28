#!/usr/bin/env python3
"""
Polymarket Arena - Streamlit Dashboard
Real-time monitoring of 5 competing trading bots
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import asyncio
from arena_database import ArenaDatabase

# Page config
st.set_page_config(
    page_title="🏟️ Polymarket Arena", 
    page_icon="🏟️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 10px;
        margin: 5px 0;
    }
    .winner-card {
        background-color: #d4edda;
        border: 2px solid #28a745;
    }
    .loser-card {
        background-color: #f8d7da;
        border: 2px solid #dc3545;
    }
    .trade-feed {
        height: 300px;
        overflow-y: scroll;
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 5px;
        font-family: monospace;
        font-size: 12px;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=5)  # Cache for 5 seconds
def load_arena_data():
    """Load fresh data from arena database"""
    db = ArenaDatabase()
    
    leaderboard = db.get_live_leaderboard()
    recent_trades = db.get_recent_trades(limit=50)
    opportunities = db.get_market_opportunities()
    competition = db.get_active_competition()
    
    return leaderboard, recent_trades, opportunities, competition

def display_competition_header(competition):
    """Display competition status header"""
    if competition:
        start_time = datetime.fromisoformat(competition['start_time'])
        end_time = datetime.fromisoformat(competition['end_time'])
        now = datetime.now()
        
        if now < end_time:
            time_remaining = end_time - now
            hours = int(time_remaining.total_seconds() // 3600)
            minutes = int((time_remaining.total_seconds() % 3600) // 60)
            status_color = "🟢"
            status_text = f"ACTIVE - {hours}h {minutes}m remaining"
        else:
            status_color = "🔴"
            status_text = "COMPLETED"
        
        st.markdown(f"""
        <div style="text-align: center; padding: 20px; background-color: #f0f2f6; border-radius: 10px; margin-bottom: 20px;">
            <h1>🏟️ POLYMARKET ARENA</h1>
            <h3>{status_color} {competition['name']}</h3>
            <p><strong>Status:</strong> {status_text}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align: center; padding: 20px; background-color: #f0f2f6; border-radius: 10px; margin-bottom: 20px;">
            <h1>🏟️ POLYMARKET ARENA</h1>
            <p>No active competition</p>
        </div>
        """, unsafe_allow_html=True)

def display_live_leaderboard(leaderboard):
    """Display the main leaderboard"""
    st.subheader("🏆 Live Leaderboard")
    
    if not leaderboard:
        st.warning("No bots registered yet")
        return
    
    # Create columns for top 3
    cols = st.columns(3)
    
    for i, bot in enumerate(leaderboard[:3]):
        with cols[i]:
            # Determine medal and colors
            if i == 0:
                medal = "🥇"
                card_class = "winner-card"
            elif i == 1:
                medal = "🥈" 
                card_class = "metric-card"
            else:
                medal = "🥉"
                card_class = "metric-card"
            
            # Status indicator
            status_emoji = "🟢" if bot['is_alive'] else "🔴"
            
            st.markdown(f"""
            <div class="metric-card {card_class}">
                <h4>{medal} {bot['bot_name']}</h4>
                <p><strong>ROI:</strong> {bot['total_roi']:.1f}%</p>
                <p><strong>Balance:</strong> ${bot['current_balance']:.0f}</p>
                <p><strong>Trades:</strong> {bot['total_trades']}</p>
                <p><strong>Win Rate:</strong> {bot['win_rate']:.1%}</p>
                <p><strong>Status:</strong> {status_emoji} {bot['live_status'] or 'Unknown'}</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Full leaderboard table
    st.subheader("📊 Full Rankings")
    
    leaderboard_df = pd.DataFrame(leaderboard)
    if not leaderboard_df.empty:
        # Format the dataframe for display
        display_df = leaderboard_df[[
            'bot_name', 'total_roi', 'current_balance', 'total_trades', 
            'win_rate', 'sharpe_ratio', 'max_drawdown', 'is_alive'
        ]].copy()
        
        display_df.columns = [
            'Bot Name', 'ROI (%)', 'Balance ($)', 'Trades', 
            'Win Rate', 'Sharpe', 'Max DD (%)', 'Status'
        ]
        
        # Format columns
        display_df['ROI (%)'] = display_df['ROI (%)'].round(1)
        display_df['Balance ($)'] = display_df['Balance ($)'].round(0)
        display_df['Win Rate'] = (display_df['Win Rate'] * 100).round(1)
        display_df['Sharpe'] = display_df['Sharpe'].round(2)
        display_df['Max DD (%)'] = display_df['Max DD (%)'].round(1)
        display_df['Status'] = display_df['Status'].apply(lambda x: "🟢 Online" if x else "🔴 Offline")
        
        st.dataframe(display_df, use_container_width=True)

def display_performance_chart(leaderboard):
    """Display performance chart"""
    st.subheader("📈 Performance Chart")
    
    if not leaderboard:
        st.info("No performance data available")
        return
    
    # Create sample performance data (in production, this would be time series)
    chart_data = pd.DataFrame({
        'Bot': [bot['bot_name'] for bot in leaderboard],
        'ROI': [bot['total_roi'] for bot in leaderboard],
        'Trades': [bot['total_trades'] for bot in leaderboard],
        'Win Rate': [bot['win_rate'] * 100 for bot in leaderboard]
    })
    
    # Performance bar chart
    fig = px.bar(
        chart_data, 
        x='Bot', 
        y='ROI',
        title='Bot Performance (ROI %)',
        color='ROI',
        color_continuous_scale='RdYlGn'
    )
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

def display_trade_feed(recent_trades):
    """Display live trade feed"""
    st.subheader("🔄 Live Trade Feed")
    
    if not recent_trades:
        st.info("No trades yet")
        return
    
    # Create scrollable trade feed
    trade_html = "<div class='trade-feed'>"
    
    for trade in recent_trades[:20]:  # Show last 20 trades
        timestamp = datetime.fromisoformat(trade['timestamp']).strftime("%H:%M:%S")
        
        # Status color
        if trade['status'] == 'won':
            status_color = "#28a745"
            pnl_sign = "+"
        elif trade['status'] == 'lost':
            status_color = "#dc3545" 
            pnl_sign = ""
        else:
            status_color = "#6c757d"
            pnl_sign = ""
        
        trade_html += f"""
        <div style="margin: 5px 0; padding: 5px; border-left: 3px solid {status_color};">
            <strong>{timestamp}</strong> | <strong>{trade['bot_id']}</strong> | {trade['action']} | 
            <span style="color: {status_color};">{pnl_sign}${trade['actual_pnl']:.0f}</span><br>
            📊 {trade['market_title'][:50]}{'...' if len(trade['market_title']) > 50 else ''}<br>
            💡 {trade['trade_reason'][:60]}{'...' if len(trade['trade_reason']) > 60 else ''}
        </div>
        """
    
    trade_html += "</div>"
    st.markdown(trade_html, unsafe_allow_html=True)

def display_market_opportunities(opportunities):
    """Display current market opportunities"""
    st.subheader("💡 Market Opportunities")
    
    if not opportunities:
        st.info("No opportunities detected")
        return
    
    opp_df = pd.DataFrame(opportunities)
    if not opp_df.empty:
        display_opp = opp_df[['type', 'market_title', 'confidence', 'expected_edge', 'detected_by']].copy()
        display_opp.columns = ['Type', 'Market', 'Confidence', 'Edge (%)', 'Detected By']
        display_opp['Edge (%)'] = (display_opp['Edge (%)'] * 100).round(1)
        display_opp['Confidence'] = display_opp['Confidence'].round(1)
        
        st.dataframe(display_opp, use_container_width=True)

def main():
    """Main dashboard"""
    
    # Load data
    leaderboard, recent_trades, opportunities, competition = load_arena_data()
    
    # Competition header
    display_competition_header(competition)
    
    # Main layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Leaderboard
        display_live_leaderboard(leaderboard)
        
        # Performance chart
        display_performance_chart(leaderboard)
    
    with col2:
        # Trade feed
        display_trade_feed(recent_trades)
        
        # Market opportunities
        display_market_opportunities(opportunities)
    
    # Auto-refresh info
    st.sidebar.markdown("### ⚡ Auto-Refresh")
    st.sidebar.info("Dashboard refreshes every 5 seconds")
    
    # Bot controls
    st.sidebar.markdown("### 🤖 Bot Controls")
    if st.sidebar.button("🚀 Start New Competition"):
        db = ArenaDatabase()
        comp_id = db.start_competition("Arena Competition", 48)
        st.sidebar.success(f"Started competition #{comp_id}")
        st.rerun()
    
    # Arena stats
    st.sidebar.markdown("### 📊 Arena Stats")
    if leaderboard:
        active_bots = sum(1 for bot in leaderboard if bot['is_alive'])
        total_trades = sum(bot['total_trades'] for bot in leaderboard)
        
        st.sidebar.metric("Active Bots", active_bots)
        st.sidebar.metric("Total Trades", total_trades)
    
    # Footer
    st.markdown("---")
    st.markdown("🏟️ **Polymarket Arena** - Real-time bot competition dashboard")

# Auto-refresh logic
if __name__ == "__main__":
    # Initialize database
    db = ArenaDatabase()
    
    # Auto-refresh every 5 seconds
    placeholder = st.empty()
    
    while True:
        with placeholder.container():
            main()
        
        time.sleep(5)
        st.rerun()