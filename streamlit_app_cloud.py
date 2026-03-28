#!/usr/bin/env python3
"""
Polymarket Arena - Streamlit Cloud Version
Mobile-optimized trading bot competition dashboard
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import time
import random

# Page config
st.set_page_config(
    page_title="🏟️ Polymarket Arena", 
    page_icon="🏟️",
    layout="wide"
)

# Custom CSS for mobile
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 15px;
        margin: 15px 0;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .winner {
        background: linear-gradient(135deg, #d4edda, #c3e6cb);
        border: 3px solid #28a745;
    }
    .second {
        background: linear-gradient(135deg, #fff3cd, #ffeaa7);
        border: 3px solid #ffc107;
    }
    .third {
        background: linear-gradient(135deg, #f8d7da, #f1b0b7);
        border: 3px solid #fd7e14;
    }
    .trade-item {
        padding: 15px;
        margin: 10px 0;
        border-radius: 10px;
        border-left: 5px solid;
        background-color: #f8f9fa;
    }
    .btn-refresh {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        border: none;
        padding: 15px 30px;
        border-radius: 25px;
        font-size: 18px;
        margin: 20px 0;
    }
    @media (max-width: 768px) {
        .metric-card h3 {
            font-size: 1.2em;
        }
        .stColumn {
            padding: 0 5px;
        }
    }
</style>
""", unsafe_allow_html=True)

# Generate dynamic demo data
@st.cache_data(ttl=10)  # Cache for 10 seconds to simulate real-time updates
def get_live_arena_data():
    """Generate realistic live arena data"""
    
    # Base data with some randomization for "live" feel
    base_time = datetime.now()
    
    bots_data = [
        {
            'name': 'Cross-Market Divergence',
            'short_name': 'S2_divergence',
            'base_roi': 18.7,
            'base_balance': 11870,
            'trades': 8 + random.randint(0, 2),
            'base_win_rate': 75,
            'status': 'online'
        },
        {
            'name': 'Sharp Wallet Copy',
            'short_name': 'S1_sharp_copy', 
            'base_roi': 12.5,
            'base_balance': 11250,
            'trades': 5 + random.randint(0, 2),
            'base_win_rate': 60,
            'status': 'online'
        },
        {
            'name': 'LP Withdrawal Monitor',
            'short_name': 'S3_lp_monitor',
            'base_roi': 7.2,
            'base_balance': 10720,
            'trades': 3 + random.randint(0, 1),
            'base_win_rate': 67,
            'status': 'online'
        },
        {
            'name': 'Wikipedia Velocity',
            'short_name': 'S4_wikipedia',
            'base_roi': -2.3,
            'base_balance': 9770,
            'trades': 2,
            'base_win_rate': 50,
            'status': random.choice(['online', 'offline'])
        },
        {
            'name': 'Economic Data Bot',
            'short_name': 'S5_econ_data',
            'base_roi': -5.8,
            'base_balance': 9420,
            'trades': 1,
            'base_win_rate': 0,
            'status': 'offline'
        }
    ]
    
    # Add some randomization for "live" feeling
    for bot in bots_data:
        # ROI fluctuates slightly
        roi_change = random.uniform(-0.5, 0.5)
        bot['roi'] = bot['base_roi'] + roi_change
        bot['balance'] = bot['base_balance'] + (bot['base_balance'] * roi_change / 100)
        bot['win_rate'] = min(100, max(0, bot['base_win_rate'] + random.randint(-2, 2)))
    
    # Generate recent trades
    markets = [
        'Bitcoin $100k 2026?',
        'Trump wins 2028?',
        'Fed cuts rates Q1?', 
        'AI achieves AGI 2026?',
        'Recession in 2026?',
        'Polymarket hits $1B volume?'
    ]
    
    trades = []
    for i in range(8):
        bot = random.choice(bots_data)
        market = random.choice(markets)
        action = random.choice(['BUY', 'SELL'])
        status = random.choice(['won', 'lost', 'pending'])
        
        # Generate realistic PnL
        if status == 'won':
            pnl = random.randint(50, 500)
        elif status == 'lost':
            pnl = -random.randint(30, 300)
        else:
            pnl = 0
            
        trade_time = base_time - timedelta(minutes=random.randint(1, 180))
        
        trades.append({
            'time': trade_time.strftime('%H:%M:%S'),
            'bot': bot['short_name'],
            'bot_name': bot['name'],
            'action': action,
            'market': market,
            'pnl': pnl,
            'status': status,
            'conviction': random.uniform(6.0, 9.5)
        })
    
    trades.sort(key=lambda x: x['time'], reverse=True)
    
    # Competition info
    competition = {
        'name': 'Polymarket Arena Demo',
        'start_time': base_time - timedelta(hours=6, minutes=32),
        'duration_hours': 48,
        'status': 'active'
    }
    
    return bots_data, trades, competition

# Header
st.markdown("""
<div style="text-align: center; padding: 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 15px; margin-bottom: 30px;">
    <h1>🏟️ POLYMARKET ARENA</h1>
    <h3>Real-Time AI Trading Competition</h3>
    <p>5 bots battle for trading supremacy</p>
</div>
""", unsafe_allow_html=True)

# Load live data
bots_data, trades, competition = get_live_arena_data()

# Competition status
elapsed_hours = 6.5 + (datetime.now().minute / 60)  # Simulate progress
remaining_hours = 48 - elapsed_hours
remaining_minutes = int((remaining_hours % 1) * 60)
remaining_hours = int(remaining_hours)

st.success(f"🟢 **{competition['name']}** - {remaining_hours}h {remaining_minutes}m remaining")

# Auto-refresh
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if st.button("🔄 Refresh Live Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# Leaderboard
st.markdown("## 🏆 Live Leaderboard")

# Top 3 bots in large cards
for i, bot in enumerate(bots_data[:3]):
    medal = ["🥇", "🥈", "🥉"][i]
    card_class = ["winner", "second", "third"][i]
    status_icon = "🟢" if bot['status'] == 'online' else "🔴"
    
    st.markdown(f"""
    <div class="metric-card {card_class}">
        <h2>{medal} {bot['name']}</h2>
        <div style="display: flex; justify-content: space-around; align-items: center; margin: 20px 0;">
            <div>
                <h3 style="color: {'#28a745' if bot['roi'] > 0 else '#dc3545'};">{bot['roi']:+.1f}%</h3>
                <p>ROI</p>
            </div>
            <div>
                <h3>${bot['balance']:,.0f}</h3>
                <p>Balance</p>
            </div>
            <div>
                <h3>{bot['trades']}</h3>
                <p>Trades</p>
            </div>
            <div>
                <h3>{bot['win_rate']:.0f}%</h3>
                <p>Win Rate</p>
            </div>
        </div>
        <p><strong>Status:</strong> {status_icon} {bot['status'].title()}</p>
    </div>
    """, unsafe_allow_html=True)

# Performance chart
st.markdown("## 📈 Performance Comparison")
df = pd.DataFrame(bots_data)
fig = px.bar(
    df, 
    x='name', 
    y='roi',
    color='roi',
    color_continuous_scale='RdYlGn',
    title='Bot Performance (ROI %)',
    height=500
)
fig.update_layout(
    xaxis_tickangle=45,
    showlegend=False,
    title_x=0.5
)
fig.update_xaxis(title='')
fig.update_yaxis(title='ROI %')
st.plotly_chart(fig, use_container_width=True)

# Layout for trades and stats
col1, col2 = st.columns([3, 2])

with col1:
    st.markdown("## 🔄 Live Trade Feed")
    
    for trade in trades[:8]:
        if trade['status'] == 'won':
            color = "#28a745"
            icon = "✅"
        elif trade['status'] == 'lost':
            color = "#dc3545"
            icon = "❌"
        else:
            color = "#6c757d"
            icon = "⏳"
        
        st.markdown(f"""
        <div class="trade-item" style="border-left-color: {color};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <strong>{trade['time']}</strong>
                <span style="color: {color}; font-weight: bold;">{icon} ${trade['pnl']:+d}</span>
            </div>
            <div><strong>{trade['bot']}</strong> | {trade['action']}</div>
            <div>📊 {trade['market']}</div>
            <div style="font-size: 0.9em; color: #666;">Conviction: {trade['conviction']:.1f}/10</div>
        </div>
        """, unsafe_allow_html=True)

with col2:
    st.markdown("## 📊 Arena Stats")
    
    # Quick stats
    active_bots = sum(1 for bot in bots_data if bot['status'] == 'online')
    total_trades = sum(bot['trades'] for bot in bots_data)
    total_volume = sum(bot['balance'] for bot in bots_data)
    avg_roi = sum(bot['roi'] for bot in bots_data) / len(bots_data)
    
    st.metric("🤖 Active Bots", f"{active_bots}/{len(bots_data)}")
    st.metric("📈 Total Trades", total_trades)
    st.metric("💰 Total Volume", f"${total_volume:,.0f}")
    st.metric("📊 Average ROI", f"{avg_roi:.1f}%")
    
    # Market opportunities
    st.markdown("### 💡 Live Opportunities")
    
    opportunities = [
        {"type": "Price Divergence", "market": "Bitcoin $100k", "confidence": 8.5, "edge": 12},
        {"type": "Sharp Wallet Alert", "market": "Trump 2028", "confidence": 7.2, "edge": 8},
        {"type": "LP Exit Signal", "market": "Fed Rates", "confidence": 6.8, "edge": 6}
    ]
    
    for opp in opportunities:
        confidence_color = "#28a745" if opp['confidence'] > 7 else "#ffc107" if opp['confidence'] > 6 else "#dc3545"
        
        st.markdown(f"""
        <div style="border: 2px solid {confidence_color}; padding: 12px; margin: 8px 0; border-radius: 8px;">
            <strong>{opp['type']}</strong><br>
            📊 {opp['market']}<br>
            <div style="display: flex; justify-content: space-between; margin-top: 5px;">
                <span>🎯 {opp['confidence']:.1f}/10</span>
                <span>📈 {opp['edge']}% edge</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

# Footer info
st.markdown("---")

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("### 🎮 Competition Rules")
    st.markdown("""
    - **Duration:** 48 hours
    - **Starting Balance:** $10,000 each
    - **Mode:** Paper trading
    - **Winner:** Highest ROI
    """)

with col2:
    st.markdown("### 🤖 Bot Strategies")
    st.markdown("""
    - **S1:** Copy sharp wallet trades
    - **S2:** Cross-market arbitrage  
    - **S3:** Liquidity exit signals
    - **S4:** Wikipedia news detection
    - **S5:** Economic data positioning
    """)

with col3:
    st.markdown("### ⚡ Live Features")
    st.markdown("""
    - **Real-time updates** every 10s
    - **Mobile optimized** interface
    - **Live trade execution**
    - **Cross-bot intelligence**
    """)

# Auto-refresh notice
st.markdown(f"""
<div style="text-align: center; padding: 20px; background-color: #f8f9fa; border-radius: 10px; margin-top: 20px;">
    <p><strong>🔄 Live Dashboard</strong> | Updates every 10 seconds</p>
    <p><em>Last updated: {datetime.now().strftime('%H:%M:%S')}</em></p>
    <p>🚀 Built with Streamlit | 🏟️ Polymarket Arena Demo</p>
</div>
""", unsafe_allow_html=True)