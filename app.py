#!/usr/bin/env python3
"""
Polymarket Arena - Main Streamlit App
Regular desktop version with full features
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import random
import time
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

# Page config
st.set_page_config(
    page_title="🏟️ Polymarket Arena", 
    page_icon="🏟️",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #f0f2f6, #e9ecef);
        padding: 20px;
        border-radius: 15px;
        margin: 10px 0;
        text-align: center;
        border: 1px solid #dee2e6;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .winner-card {
        background: linear-gradient(135deg, #d4edda, #c3e6cb);
        border: 3px solid #28a745;
        animation: pulse 2s infinite;
    }
    .second-card {
        background: linear-gradient(135deg, #fff3cd, #ffeeba);
        border: 3px solid #ffc107;
    }
    .third-card {
        background: linear-gradient(135deg, #f8d7da, #f1b0b7);
        border: 3px solid #fd7e14;
    }
    .trade-feed {
        height: 400px;
        overflow-y: scroll;
        background: linear-gradient(135deg, #f8f9fa, #e9ecef);
        padding: 15px;
        border-radius: 10px;
        font-family: 'Courier New', monospace;
    }
    .competition-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 30px;
        border-radius: 20px;
        text-align: center;
        margin-bottom: 30px;
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
    }
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.02); }
        100% { transform: scale(1); }
    }
    .stMetric > div {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        padding: 15px;
        border-radius: 10px;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)

# Live arena data — delegates to live_arena_data.py (real Polymarket APIs + fallback)
@st.cache_data(ttl=8)  # Cache for 8 seconds
def get_live_arena_data():
    """Fetch live Polymarket data (falls back to demo data if API unavailable)."""
    return live_arena_data.get_arena_data()


# Main app
def main():
    # Load live data
    bots, trades, opportunities, competition = get_live_arena_data()
    
    # Competition header
    elapsed = datetime.now() - competition['start_time']
    elapsed_hours = elapsed.total_seconds() / 3600
    remaining_hours = competition['duration_hours'] - elapsed_hours
    remaining_h = int(remaining_hours)
    remaining_m = int((remaining_hours % 1) * 60)
    
    st.markdown(f"""
    <div class="competition-header">
        <h1>🏟️ POLYMARKET ARENA</h1>
        <h2>{competition['name']}</h2>
        <h3>⏱️ {remaining_h}h {remaining_m}m remaining</h3>
        <p>5 AI trading bots compete for supremacy • $50,000 total prize pool</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Auto-refresh controls
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔄 Refresh Live Data", use_container_width=True, type="primary"):
            st.cache_data.clear()
            st.rerun()
    
    # Main layout
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("## 🏆 Live Leaderboard")
        
        # Top 3 showcase
        podium_cols = st.columns(3)
        for i, bot in enumerate(bots[:3]):
            medal = ["🥇", "🥈", "🥉"][i]
            card_class = ["winner-card", "second-card", "third-card"][i]
            
            with podium_cols[i]:
                status_icon = "🟢" if bot['status'] == 'online' else "🔴"
                
                st.markdown(f"""
                <div class="metric-card {card_class}">
                    <h3>{medal} {bot['name']}</h3>
                    <h2 style="color: {'#28a745' if bot['roi'] > 0 else '#dc3545'};">
                        {bot['roi']:+.1f}%
                    </h2>
                    <p><strong>${bot['balance']:,.0f}</strong></p>
                    <p>{bot['trades']} trades • {bot['win_rate']:.0f}% WR</p>
                    <p>{status_icon} {bot['status'].title()}</p>
                </div>
                """, unsafe_allow_html=True)
        
        # Detailed leaderboard table
        st.markdown("### 📊 Detailed Performance")
        
        df = pd.DataFrame(bots)
        display_df = df[[
            'name', 'roi', 'balance', 'trades', 'winning_trades', 
            'win_rate', 'sharpe_ratio', 'max_drawdown', 'status'
        ]].copy()
        
        display_df.columns = [
            'Bot Name', 'ROI (%)', 'Balance ($)', 'Total Trades', 'Wins',
            'Win Rate (%)', 'Sharpe Ratio', 'Max Drawdown (%)', 'Status'
        ]
        
        # Format columns
        for col in ['ROI (%)', 'Balance ($)', 'Win Rate (%)', 'Sharpe Ratio', 'Max Drawdown (%)']:
            if col == 'Balance ($)':
                display_df[col] = display_df[col].apply(lambda x: f"${x:,.0f}")
            else:
                display_df[col] = display_df[col].round(1)
        
        display_df['Status'] = display_df['Status'].apply(
            lambda x: "🟢 Online" if x == 'online' else "🔴 Offline"
        )
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Performance charts
        st.markdown("### 📈 Performance Analysis")
        
        chart_tabs = st.tabs(["ROI Comparison", "Risk vs Return", "Trade Activity"])
        
        with chart_tabs[0]:
            fig = px.bar(
                df, x='name', y='roi',
                color='roi',
                color_continuous_scale='RdYlGn',
                title='Bot Performance (ROI %)'
            )
            fig.update_layout(height=400, showlegend=False)
            fig.update_xaxes(title='', tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
        
        with chart_tabs[1]:
            fig = px.scatter(
                df, x='max_drawdown', y='roi',
                size='trades',
                color='sharpe_ratio',
                hover_data=['name', 'win_rate'],
                title='Risk vs Return Analysis'
            )
            fig.update_layout(height=400)
            fig.update_xaxes(title='Max Drawdown (%)')
            fig.update_yaxes(title='ROI (%)')
            st.plotly_chart(fig, use_container_width=True)
        
        with chart_tabs[2]:
            fig = px.bar(
                df, x='name', y='trades',
                color='win_rate',
                title='Trading Activity by Bot'
            )
            fig.update_layout(height=400, showlegend=False)
            fig.update_xaxes(title='', tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Live statistics
        st.markdown("## 📊 Arena Statistics")
        
        stat_cols = st.columns(2)
        with stat_cols[0]:
            active_bots = sum(1 for bot in bots if bot['status'] == 'online')
            st.metric("🤖 Active Bots", f"{active_bots}/{len(bots)}")
            
            total_trades = sum(bot['trades'] for bot in bots)
            st.metric("📈 Total Trades", total_trades)
        
        with stat_cols[1]:
            total_volume = sum(bot['balance'] for bot in bots)
            st.metric("💰 Total Volume", f"${total_volume:,.0f}")
            
            avg_roi = sum(bot['roi'] for bot in bots) / len(bots)
            st.metric("📊 Average ROI", f"{avg_roi:.1f}%")
        
        # Live trade feed
        st.markdown("## 🔄 Live Trade Feed")
        
        trade_html = '<div class="trade-feed">'
        for trade in trades[:12]:
            if trade['status'] == 'won':
                color = "#28a745"
                icon = "✅"
            elif trade['status'] == 'lost':
                color = "#dc3545"
                icon = "❌"
            else:
                color = "#6c757d"
                icon = "⏳"
            
            trade_html += f"""
            <div style="border-left: 4px solid {color}; padding: 12px; margin: 8px 0; background: rgba(255,255,255,0.8); border-radius: 5px;">
                <div style="display: flex; justify-content: space-between; font-weight: bold;">
                    <span>{trade['time_str']}</span>
                    <span style="color: {color};">{icon} ${trade['pnl']:+d}</span>
                </div>
                <div><strong>{trade['bot_id']}</strong> | {trade['action']} ${trade['size']:,}</div>
                <div style="font-size: 0.9em;">📊 {trade['market'][:45]}{'...' if len(trade['market']) > 45 else ''}</div>
                <div style="font-size: 0.8em; color: #666;">Conviction: {trade['conviction']}/10</div>
            </div>
            """
        trade_html += '</div>'
        st.markdown(trade_html, unsafe_allow_html=True)
        
        # Market opportunities
        st.markdown("## 💡 Live Market Opportunities")
        
        for opp in opportunities:
            confidence_color = "#28a745" if opp['confidence'] > 8 else "#ffc107" if opp['confidence'] > 7 else "#dc3545"
            
            st.markdown(f"""
            <div style="border: 2px solid {confidence_color}; padding: 15px; margin: 10px 0; border-radius: 10px; background: rgba(248, 249, 250, 0.8);">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <strong style="color: {confidence_color};">{opp['type']}</strong>
                    <span style="background: {confidence_color}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.8em;">
                        {opp['time_sensitive']}min
                    </span>
                </div>
                <div style="margin: 8px 0;">📊 <strong>{opp['market']}</strong></div>
                <div style="display: flex; justify-content: space-between; font-size: 0.9em;">
                    <span>🎯 Confidence: {opp['confidence']}/10</span>
                    <span>📈 Edge: {opp['edge']}%</span>
                </div>
                <div style="font-size: 0.8em; color: #666; margin-top: 5px;">
                    📡 {opp['source']}
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Footer
    st.markdown("---")
    
    footer_cols = st.columns(4)
    
    with footer_cols[0]:
        st.markdown("### 🎮 Competition Info")
        st.markdown(f"""
        - **Duration:** {competition['duration_hours']} hours
        - **Starting Capital:** $10,000 each
        - **Mode:** Paper trading simulation
        - **Prize Pool:** $50,000 total
        """)
    
    with footer_cols[1]:
        st.markdown("### 🤖 Bot Strategies")
        st.markdown("""
        - **S1:** Smart wallet copying
        - **S2:** Cross-market arbitrage
        - **S3:** Liquidity monitoring
        - **S4:** News detection
        - **S5:** Economic data
        """)
    
    with footer_cols[2]:
        st.markdown("### ⚡ Live Features")
        st.markdown("""
        - Real-time updates (8s refresh)
        - Live trade execution
        - Performance analytics
        - Risk management
        """)
    
    with footer_cols[3]:
        st.markdown("### 🔗 Links")
        st.markdown("""
        - [Mobile Version](./mobile)
        - [API Documentation](./docs)
        - [GitHub Repository](https://github.com)
        - [Polymarket](https://polymarket.com)
        """)
    
    # Auto-refresh status
    st.markdown(f"""
    <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #f8f9fa, #e9ecef); border-radius: 15px; margin-top: 20px;">
        <p><strong>🔄 Live Dashboard</strong> | Auto-refreshing every 8 seconds</p>
        <p><em>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
        <p>🚀 Built with Streamlit | 🏟️ Polymarket Trading Arena</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()