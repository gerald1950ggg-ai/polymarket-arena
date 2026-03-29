#!/usr/bin/env python3
"""
Polymarket Arena - Mobile Version
Optimized for phones and tablets with touch-friendly interface
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import random
import sys
import os

# Make live_arena_data importable from the project root
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
# Also add S1 dir so live_data.py is importable
_S1_DIR = os.path.join(_PROJECT_ROOT, 'S1-sharp-wallet-copy')
if _S1_DIR not in sys.path:
    sys.path.insert(0, _S1_DIR)
import live_arena_data

# Page config optimized for mobile
st.set_page_config(
    page_title="🏟️ Arena", 
    page_icon="🏟️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Mobile-first CSS
st.markdown("""
<style>
    /* Mobile-optimized styles */
    .main .block-container {
        padding: 1rem 0.5rem;
        max-width: 100%;
    }
    
    .metric-card {
        background: linear-gradient(135deg, #f8f9fa, #e9ecef);
        padding: 25px 15px;
        border-radius: 20px;
        margin: 15px 0;
        text-align: center;
        border: 2px solid #dee2e6;
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
        transition: transform 0.2s;
    }
    
    .metric-card:active {
        transform: scale(0.98);
    }
    
    .winner {
        background: linear-gradient(135deg, #d4edda, #c3e6cb);
        border: 4px solid #28a745;
        animation: winner-pulse 3s infinite;
    }
    
    .second {
        background: linear-gradient(135deg, #fff3cd, #ffeeba);
        border: 4px solid #ffc107;
    }
    
    .third {
        background: linear-gradient(135deg, #fde2e4, #f1aeb5);
        border: 4px solid #fd7e14;
    }
    
    @keyframes winner-pulse {
        0%, 100% { transform: scale(1); box-shadow: 0 6px 12px rgba(0,0,0,0.15); }
        50% { transform: scale(1.02); box-shadow: 0 8px 16px rgba(40, 167, 69, 0.3); }
    }
    
    .trade-item {
        background: rgba(248, 249, 250, 0.9);
        border-left: 6px solid;
        padding: 20px;
        margin: 15px 0;
        border-radius: 10px;
        font-size: 16px;
        line-height: 1.4;
    }
    
    .competition-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 30px 20px;
        border-radius: 25px;
        text-align: center;
        margin-bottom: 25px;
        box-shadow: 0 10px 20px rgba(0,0,0,0.2);
    }
    
    .refresh-btn {
        background: linear-gradient(135deg, #28a745, #20c997);
        color: white;
        border: none;
        padding: 20px 40px;
        border-radius: 30px;
        font-size: 18px;
        font-weight: bold;
        width: 100%;
        margin: 20px 0;
        cursor: pointer;
        transition: all 0.3s;
    }
    
    .refresh-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(40, 167, 69, 0.3);
    }
    
    .stats-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 15px;
        margin: 20px 0;
    }
    
    .stat-card {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
    }
    
    .opportunity-card {
        border: 3px solid;
        padding: 20px;
        margin: 15px 0;
        border-radius: 15px;
        background: rgba(255, 255, 255, 0.9);
        backdrop-filter: blur(10px);
    }
    
    /* Touch-friendly sizing */
    h1, h2, h3 { 
        line-height: 1.2; 
    }
    
    .stButton > button {
        height: 60px;
        font-size: 18px;
        border-radius: 20px;
        border: none;
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        font-weight: bold;
    }
    
    .stSelectbox, .stMultiSelect {
        font-size: 16px;
    }
    
    /* Chart sizing for mobile */
    .js-plotly-plot {
        width: 100% !important;
    }
</style>
""", unsafe_allow_html=True)

# Generate mobile-optimized demo data
@st.cache_data(ttl=10)  # 10-second refresh for mobile
def get_mobile_arena_data():
    """Fetch live Polymarket data for mobile (falls back to demo if API unavailable)."""
    bots, trades, _opportunities, _competition = live_arena_data.get_arena_data()
    return bots, trades


def main():
    # Load mobile data
    bots, trades = get_mobile_arena_data()
    
    # Mobile header
    st.markdown("""
    <div class="competition-header">
        <h1>🏟️ POLYMARKET ARENA</h1>
        <h3>Live Trading Competition</h3>
        <p>⏱️ 18h 32m remaining</p>
        <p>5 AI Bots • $50K Prize Pool</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Mobile refresh button
    if st.button("🔄 Refresh Live Data", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()
    
    # Mobile leaderboard - large cards
    st.markdown("## 🏆 Live Leaderboard")
    
    for i, bot in enumerate(bots[:3]):
        medal = ["🥇", "🥈", "🥉"][i]
        card_class = ["winner", "second", "third"][i]
        status_icon = "🟢" if bot['status'] == 'online' else "🔴"
        
        st.markdown(f"""
        <div class="metric-card {card_class}">
            <h2>{medal} {bot['emoji']} {bot['name']}</h2>
            <h1 style="color: {'#28a745' if bot['roi'] > 0 else '#dc3545'}; margin: 15px 0;">
                {bot['roi']:+.1f}%
            </h1>
            <div style="display: flex; justify-content: space-around; margin: 20px 0; font-size: 18px;">
                <div><strong>${bot['balance']:,}</strong><br>Balance</div>
                <div><strong>{bot['trades']}</strong><br>Trades</div>
                <div><strong>{bot['win_rate']:.0f}%</strong><br>Win Rate</div>
            </div>
            <p style="font-size: 16px; color: #666;">{bot['strategy']}</p>
            <p style="font-size: 18px;"><strong>Status:</strong> {status_icon} {bot['status'].title()}</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Show other bots in compact form
    if len(bots) > 3:
        st.markdown("### Other Competitors")
        for i, bot in enumerate(bots[3:], 4):
            status_icon = "🟢" if bot['status'] == 'online' else "🔴"
            st.markdown(f"""
            <div style="background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 10px; border-left: 5px solid #6c757d;">
                <strong>{i}. {bot['emoji']} {bot['name']}</strong> | {bot['roi']:+.1f}% | ${bot['balance']:,} | {status_icon}
            </div>
            """, unsafe_allow_html=True)
    
    # Mobile performance chart
    st.markdown("## 📈 Performance")
    df = pd.DataFrame(bots)
    fig = px.bar(
        df, x='short_name', y='roi',
        color='roi',
        color_continuous_scale='RdYlGn',
        height=350,
        title=''
    )
    fig.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, t=0, b=50),
        font=dict(size=14)
    )
    fig.update_xaxes(title='', tickangle=0)
    fig.update_yaxes(title='ROI %', title_font_size=16)
    st.plotly_chart(fig, use_container_width=True)
    
    # Mobile stats grid
    st.markdown("## 📊 Arena Stats")
    
    active_bots = sum(1 for bot in bots if bot['status'] == 'online')
    total_trades = sum(bot['trades'] for bot in bots)
    total_volume = sum(bot['balance'] for bot in bots)
    avg_roi = sum(bot['roi'] for bot in bots) / len(bots)
    
    st.markdown(f"""
    <div class="stats-grid">
        <div class="stat-card">
            <h2>{active_bots}</h2>
            <p>Active Bots</p>
        </div>
        <div class="stat-card">
            <h2>{total_trades}</h2>
            <p>Total Trades</p>
        </div>
        <div class="stat-card">
            <h2>${total_volume:,.0f}</h2>
            <p>Total Volume</p>
        </div>
        <div class="stat-card">
            <h2>{avg_roi:+.1f}%</h2>
            <p>Avg ROI</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Mobile trade feed
    st.markdown("## 🔄 Recent Trades")
    
    for trade in trades[:6]:
        if trade['status'] == 'won':
            color = "#28a745"
            icon = "✅"
        else:
            color = "#dc3545"
            icon = "❌"
        
        st.markdown(f"""
        <div class="trade-item" style="border-left-color: {color};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <strong style="font-size: 18px;">{trade['time']}</strong>
                <span style="color: {color}; font-size: 20px; font-weight: bold;">
                    {icon} ${int(trade['pnl']):+,}
                </span>
            </div>
            <div style="font-size: 16px;">
                <strong>{trade['bot_emoji']} {trade['bot_name']}</strong> | {trade['action']}
            </div>
            <div style="font-size: 15px; color: #666; margin-top: 5px;">
                📊 {trade['market']}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Mobile opportunities
    st.markdown("## 💡 Live Opportunities")
    
    opportunities = [
        {
            'type': 'Price Gap',
            'market': 'Bitcoin $100k',
            'confidence': round(random.uniform(7.5, 9.0), 1),
            'edge': round(random.uniform(8, 15), 1),
        },
        {
            'type': 'Smart Money',
            'market': 'Trump 2028',
            'confidence': round(random.uniform(6.5, 8.0), 1),
            'edge': round(random.uniform(5, 10), 1),
        }
    ]
    
    for opp in opportunities:
        confidence_color = "#28a745" if opp['confidence'] > 8 else "#ffc107" if opp['confidence'] > 7 else "#dc3545"
        
        st.markdown(f"""
        <div class="opportunity-card" style="border-color: {confidence_color};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <strong style="color: {confidence_color}; font-size: 18px;">{opp['type']}</strong>
                <span style="background: {confidence_color}; color: white; padding: 5px 12px; border-radius: 15px; font-weight: bold;">
                    {opp['edge']}% edge
                </span>
            </div>
            <div style="font-size: 16px; margin-bottom: 8px;">
                📊 <strong>{opp['market']}</strong>
            </div>
            <div style="font-size: 15px;">
                🎯 Confidence: <strong>{opp['confidence']}/10</strong>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Mobile info section
    with st.expander("📖 About This Competition", expanded=False):
        st.markdown("""
        ### 🏟️ Polymarket Trading Arena
        
        **5 AI bots compete for 48 hours:**
        
        🔄 **Divergence Bot** - Finds price differences across markets  
        🎯 **Wallet Copier** - Copies trades from smart traders  
        📰 **News Bot** - Detects breaking news via Wikipedia  
        💧 **Liquidity Bot** - Monitors smart money movements  
        📊 **Econ Bot** - Trades on economic data releases  
        
        **Rules:**
        - 48-hour competition
        - $10,000 starting balance each
        - Paper trading (no real money)
        - Winner: Highest ROI
        - $50,000 total prize pool
        
        **Updates every 10 seconds**
        """)
    
    # Mobile footer
    st.markdown("---")
    st.markdown(f"""
    <div style="text-align: center; padding: 25px; background: linear-gradient(135deg, #f8f9fa, #e9ecef); border-radius: 20px; margin-top: 25px;">
        <p style="font-size: 18px;"><strong>🔄 Live Mobile Dashboard</strong></p>
        <p style="font-size: 16px;">Updates every 10 seconds</p>
        <p style="font-size: 14px; color: #666;"><em>Last updated: {datetime.now().strftime('%H:%M:%S')}</em></p>
        <p style="font-size: 16px;">🚀 <strong>Polymarket Arena</strong> | Built with Streamlit</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()