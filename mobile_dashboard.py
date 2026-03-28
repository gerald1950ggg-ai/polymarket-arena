#!/usr/bin/env python3
"""
Polymarket Arena - Mobile-Optimized Dashboard
Simplified version that works well on phones
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import sqlite3
import os

# Page config for mobile
st.set_page_config(
    page_title="🏟️ Arena", 
    page_icon="🏟️",
    layout="wide",
    initial_sidebar_state="collapsed"  # Better for mobile
)

# Mobile-optimized CSS
st.markdown("""
<style>
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        text-align: center;
    }
    .winner {
        background-color: #d4edda;
        border: 2px solid #28a745;
    }
    .loser {
        background-color: #f8d7da;
        border: 2px solid #dc3545;
    }
</style>
""", unsafe_allow_html=True)

# Simplified database for demo (embedded data)
def get_demo_data():
    """Get demo data for mobile display"""
    bots = [
        {
            'name': 'Cross-Market Divergence',
            'roi': 18.7,
            'balance': 11870,
            'trades': 8,
            'win_rate': 75,
            'status': 'online'
        },
        {
            'name': 'Sharp Wallet Copy', 
            'roi': 12.5,
            'balance': 11250,
            'trades': 5,
            'win_rate': 60,
            'status': 'online'
        },
        {
            'name': 'LP Withdrawal Monitor',
            'roi': 7.2,
            'balance': 10720,
            'trades': 3,
            'win_rate': 67,
            'status': 'online'
        },
        {
            'name': 'Wikipedia Velocity',
            'roi': -2.3,
            'balance': 9770,
            'trades': 2,
            'win_rate': 50,
            'status': 'offline'
        },
        {
            'name': 'Economic Data Bot',
            'roi': -5.8,
            'balance': 9420,
            'trades': 1,
            'win_rate': 0,
            'status': 'offline'
        }
    ]
    
    trades = [
        {
            'time': '12:45:32',
            'bot': 'S2_divergence',
            'action': 'BUY',
            'market': 'Bitcoin $100k 2026',
            'pnl': 420,
            'status': 'won'
        },
        {
            'time': '12:42:18',
            'bot': 'S1_sharp_copy',
            'action': 'BUY', 
            'market': 'Trump wins 2026',
            'pnl': 290,
            'status': 'won'
        },
        {
            'time': '12:38:55',
            'bot': 'S3_lp_monitor',
            'action': 'SELL',
            'market': 'Fed rate cuts Q1',
            'pnl': -150,
            'status': 'lost'
        }
    ]
    
    return bots, trades

# Header - mobile optimized
st.markdown("# 🏟️ POLYMARKET ARENA")

# Competition status
st.success("🟢 **Demo Competition** - 18h 32m remaining")

# Refresh button
if st.button("🔄 Refresh", use_container_width=True):
    st.rerun()

# Get data
bots, trades = get_demo_data()

# Mobile layout - single column with cards
st.markdown("## 🏆 Live Leaderboard")

# Top 3 in cards format
for i, bot in enumerate(bots[:3]):
    medal = ["🥇", "🥈", "🥉"][i]
    card_class = "winner" if i == 0 else "loser" if i == 2 else ""
    status_icon = "🟢" if bot['status'] == 'online' else "🔴"
    
    st.markdown(f"""
    <div class="metric-card {card_class}">
        <h3>{medal} {bot['name']}</h3>
        <p><strong>ROI:</strong> {bot['roi']:.1f}% | <strong>Balance:</strong> ${bot['balance']:,}</p>
        <p><strong>Trades:</strong> {bot['trades']} | <strong>Win Rate:</strong> {bot['win_rate']}%</p>
        <p>{status_icon} {bot['status'].title()}</p>
    </div>
    """, unsafe_allow_html=True)

# Performance chart - mobile optimized
st.markdown("## 📈 Performance")
df = pd.DataFrame(bots)
fig = px.bar(
    df, 
    x='name', 
    y='roi',
    color='roi',
    color_continuous_scale='RdYlGn',
    height=300
)
fig.update_layout(
    xaxis_tickangle=45,
    margin=dict(l=0, r=0, t=0, b=0)
)
fig.update_xaxis(title='')
fig.update_yaxis(title='ROI %')
st.plotly_chart(fig, use_container_width=True)

# Recent trades - compact for mobile
st.markdown("## 🔄 Recent Trades")
for trade in trades:
    icon = "✅" if trade['status'] == 'won' else "❌"
    color = "green" if trade['status'] == 'won' else "red"
    
    st.markdown(f"""
    <div style="border-left: 4px solid {color}; padding: 10px; margin: 8px 0; background-color: #f8f9fa;">
        <strong>{trade['time']}</strong> | <strong>{trade['bot']}</strong><br>
        {icon} {trade['action']} | ${trade['pnl']:+d}<br>
        📊 {trade['market']}
    </div>
    """, unsafe_allow_html=True)

# Quick stats
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Active Bots", "3")
with col2:
    st.metric("Total Trades", "19")  
with col3:
    st.metric("Total Volume", "$52,030")

# Instructions for mobile
with st.expander("📖 About This Arena"):
    st.markdown("""
    **🏟️ Polymarket Trading Arena**
    
    5 AI bots compete in real-time:
    - **S1:** Copies smart wallet trades
    - **S2:** Finds price differences across markets  
    - **S3:** Monitors liquidity exits
    - **S4:** Detects news via Wikipedia edits
    - **S5:** Positions before economic data
    
    **Competition:** 48-hour battle royale
    **Mode:** Paper trading (no real money)
    **Winner:** Highest ROI after 48 hours
    """)

# Footer
st.markdown("---")
st.markdown("🏟️ **Real-time AI trading competition** | Built with Streamlit")
st.markdown(f"*Last updated: {datetime.now().strftime('%H:%M:%S')}*")