#!/usr/bin/env python3
"""
Shadow Mode Signal Journal - Streamlit page
Shows real bot signals with full context and outcomes
"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shadow_log import get_signals, get_shadow_stats

st.set_page_config(page_title="🕵️ Shadow Mode", page_icon="🕵️", layout="wide")

def render_shadow_journal():
    st.markdown("# 🕵️ Shadow Mode Signal Journal")
    st.markdown("*Real bot signals logged against actual Polymarket conditions. P&L calculated at resolution.*")

    # Overall stats
    stats = get_shadow_stats()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Signals", stats["total_signals"])
    col2.metric("⏳ Pending", stats["pending"])
    col3.metric("✅ Won", stats["won"])
    col4.metric("❌ Lost", stats["lost"])
    col5.metric("Win Rate", f"{stats['win_rate']}%")

    # ROI summary
    pnl_color = "green" if stats["total_pnl"] >= 0 else "red"
    st.markdown(f"""
    <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0; text-align: center;">
        <h3>📊 Shadow Portfolio Performance</h3>
        <h2 style="color: {pnl_color};">${stats['total_pnl']:+,.2f} ({stats['roi']:+.1f}% ROI)</h2>
        <p>Based on resolved signals only. Pending signals not included.</p>
    </div>
    """, unsafe_allow_html=True)

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox("Filter by status", ["All", "Pending", "Won", "Lost"])
    with col2:
        bot_filter = st.selectbox("Filter by bot", ["All", "S1_sharp_copy", "S2_divergence", "S3_lp_monitor", "S4_wikipedia", "S5_econ_data"])

    # Fetch signals
    status_map = {"All": None, "Pending": "pending", "Won": "won", "Lost": "lost"}

    signals = get_signals(
        limit=50,
        bot_id=None if bot_filter == "All" else bot_filter,
        status=status_map[status_filter]
    )

    if not signals:
        st.info("No signals logged yet. Run the bots to generate real signals.")
        return

    st.markdown(f"### 📋 Signal Journal ({len(signals)} signals)")

    for signal in signals:
        # Status styling
        if signal['resolution_status'] == 'won':
            border_color = "#28a745"
            status_badge = "✅ WON"
            pnl_display = f"+${signal['actual_pnl']:,.0f}"
        elif signal['resolution_status'] == 'lost':
            border_color = "#dc3545"
            status_badge = "❌ LOST"
            pnl_display = f"-${abs(signal['actual_pnl']):,.0f}"
        else:
            border_color = "#6c757d"
            status_badge = "⏳ PENDING"
            pnl_display = "TBD"

        direction_color = "#28a745" if signal['direction'] == 'BUY' else "#dc3545"

        st.markdown(f"""
        <div style="border-left: 5px solid {border_color}; padding: 20px; margin: 15px 0;
                    background: white; border-radius: 0 10px 10px 0;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                <div>
                    <span style="font-size: 20px;">{signal['bot_emoji']}</span>
                    <strong style="font-size: 16px; margin-left: 8px;">{signal['bot_name']}</strong>
                    <span style="color: #888; margin-left: 10px; font-size: 13px;">{signal['timestamp'][:16]}</span>
                </div>
                <div style="text-align: right;">
                    <span style="background: {border_color}; color: white; padding: 4px 12px;
                                border-radius: 20px; font-size: 13px; font-weight: bold;">{status_badge}</span>
                    <div style="font-size: 20px; font-weight: bold; color: {border_color}; margin-top: 5px;">{pnl_display}</div>
                </div>
            </div>
            <h4 style="margin: 10px 0; color: #333;">📊 {signal['market_title']}</h4>
            <div style="background: #f8f9fa; padding: 12px; border-radius: 8px; margin: 10px 0;
                        font-size: 14px; line-height: 1.6; color: #444;">
                {signal['signal_explanation']}
            </div>
            <div style="display: flex; gap: 20px; font-size: 13px; color: #555; margin-top: 10px;">
                <span><strong style="color: {direction_color};">{signal['direction']}</strong> signal</span>
                <span>Entry: <strong>${signal['entry_price']:.2f}</strong></span>
                <span>Shadow size: <strong>${signal['shadow_size']:,.0f}</strong></span>
                <span>Conviction: <strong>{signal['conviction_score']:.1f}/10</strong></span>
                {f'<span>Resolves: <strong>{signal["market_end_date"]}</strong></span>' if signal.get("market_end_date") else ''}
            </div>
        </div>
        """, unsafe_allow_html=True)

    if st.button("🔄 Refresh"):
        st.rerun()

render_shadow_journal()
