#!/usr/bin/env python3
"""
Polymarket Arena — Dashboard
Real signals, real bots, real data.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sqlite3
import os
from datetime import datetime, timedelta

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Polymarket Arena",
    page_icon="🏟️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Theme ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Force dark everywhere */
  html, body { background-color: #0d1117 !important; }
  .stApp { background-color: #0d1117 !important; }
  .main, .main > div, section[data-testid="stMain"] { background-color: #0d1117 !important; }
  [class*="css"], [data-testid] { color: #e6edf3; }
  .block-container { background-color: #0d1117 !important; padding: 1.5rem 2rem 2rem 2rem; max-width: 1400px; }

  /* Readable text — no more pale grey */
  p, span, div, label, li { color: #e6edf3 !important; }
  .stMarkdown, .stMarkdown p { color: #e6edf3 !important; }
  td, th { color: #e6edf3 !important; }

  /* Selectbox dark theme */
  [data-testid="stSelectbox"] > div > div {
    background-color: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 6px !important;
    color: #e6edf3 !important;
  }
  [data-testid="stSelectbox"] svg { fill: #8b949e !important; }
  div[data-baseweb="select"] > div { background-color: #161b22 !important; border-color: #30363d !important; }
  div[data-baseweb="popover"] { background-color: #161b22 !important; }
  li[role="option"] { background-color: #161b22 !important; color: #e6edf3 !important; }
  li[role="option"]:hover { background-color: #1c2128 !important; }

  /* Button */
  .stButton > button {
    background-color: #21262d !important;
    color: #e6edf3 !important;
    border: 1px solid #30363d !important;
    border-radius: 6px !important;
  }
  .stButton > button:hover { background-color: #30363d !important; }

  /* Font */
  html, body, [class*="css"] {
    font-family: 'Inter', 'Segoe UI', sans-serif;
  }

  /* Hide Streamlit chrome */
  #MainMenu, footer, header { visibility: hidden; }

  /* Bot pills */
  .bot-pill {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 8px 16px; border-radius: 8px;
    background: #161b22; border: 1px solid #30363d;
    margin-right: 10px; margin-bottom: 8px;
    font-size: 13px; font-weight: 500;
  }
  .dot-live  { width: 8px; height: 8px; border-radius: 50%; background: #3fb950; display:inline-block; }
  .dot-error { width: 8px; height: 8px; border-radius: 50%; background: #f85149; display:inline-block; }
  .dot-idle  { width: 8px; height: 8px; border-radius: 50%; background: #8b949e; display:inline-block; }

  /* Section headers */
  .section-title {
    font-size: 11px; font-weight: 600; letter-spacing: 0.08em;
    text-transform: uppercase; color: #8b949e;
    margin-bottom: 12px; margin-top: 4px;
  }

  /* Cards */
  .card {
    background: #161b22; border: 1px solid #30363d;
    border-radius: 10px; padding: 16px 20px; margin-bottom: 16px;
  }

  /* Signal table */
  .signal-row {
    display: grid;
    grid-template-columns: 80px 110px 1fr 60px 70px 70px 80px;
    gap: 8px; align-items: center;
    padding: 8px 12px; border-radius: 6px;
    font-size: 12.5px; border-bottom: 1px solid #21262d;
  }
  .signal-row:hover { background: #1c2128; }
  .signal-row.header { color: #8b949e; font-size: 11px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.06em; border-bottom: 1px solid #30363d; }

  .tag { display:inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 11px; font-weight: 600; }
  .tag-buy   { background: #1a3a2a; color: #3fb950; }
  .tag-sell  { background: #3a1a1a; color: #f85149; }
  .tag-s1    { background: #1a2a3a; color: #58a6ff; }
  .tag-s2    { background: #2a1a3a; color: #bc8cff; }
  .tag-s3    { background: #1a3a3a; color: #39d353; }
  .tag-s4    { background: #3a3a1a; color: #e3b341; }
  .tag-s5    { background: #3a2a1a; color: #f0883e; }
  .tag-pending { background: #1a2a1a; color: #8b949e; }
  .tag-won   { background: #1a3a2a; color: #3fb950; }
  .tag-lost  { background: #3a1a1a; color: #f85149; }

  /* Leaderboard */
  .lb-row {
    display: grid; grid-template-columns: 30px 1fr 60px 80px;
    gap: 8px; align-items: center;
    padding: 7px 12px; border-radius: 6px; font-size: 12.5px;
    border-bottom: 1px solid #21262d;
  }
  .lb-row:hover { background: #1c2128; }
  .rank { color: #8b949e; font-size: 12px; }

  /* Stat numbers */
  .stat-big { font-size: 28px; font-weight: 700; line-height: 1.1; }
  .stat-label { font-size: 11px; color: #8b949e; text-transform: uppercase;
    letter-spacing: 0.06em; margin-top: 2px; }

  /* Scrollable feed */
  .feed-wrap { max-height: 520px; overflow-y: auto; }
  .feed-wrap::-webkit-scrollbar { width: 4px; }
  .feed-wrap::-webkit-scrollbar-track { background: #161b22; }
  .feed-wrap::-webkit-scrollbar-thumb { background: #30363d; border-radius: 2px; }
</style>
""", unsafe_allow_html=True)

# ── Bot metadata ──────────────────────────────────────────────────────────────
BOT_META = {
    "S1_sharp_copy":  {
        "label": "S1 · Sharp Wallet Copy",
        "short": "S1",
        "emoji": "🎯",
        "tag": "tag-s1",
        "color": "#58a6ff",
        "desc": "Tracks the most profitable wallets on Polymarket and copies their trades. Scans 1,000 recent trades per hour to find who's winning."
    },
    "S2_divergence":  {
        "label": "S2 · Cross-Market Divergence",
        "short": "S2",
        "emoji": "⚡",
        "tag": "tag-s2",
        "color": "#bc8cff",
        "desc": "Compares the same market on Polymarket vs Kalshi. When prices differ by more than 5%, it signals a trade toward convergence."
    },
    "S3_lp_monitor":  {
        "label": "S3 · LP Withdrawal Monitor",
        "short": "S3",
        "emoji": "🌊",
        "tag": "tag-s3",
        "color": "#39d353",
        "desc": "Watches on-chain liquidity provider exits via the Goldsky subgraph. When LPs pull money out, they usually know something — this bot follows them."
    },
    "S4_wikipedia":   {
        "label": "S4 · Wikipedia Velocity",
        "short": "S4",
        "emoji": "📖",
        "tag": "tag-s4",
        "color": "#e3b341",
        "desc": "Monitors Wikipedia edit frequency on pages tied to active markets. A sudden spike in edits = breaking news forming = trade before the market reprices."
    },
    "S5_econ_data":   {
        "label": "S5 · Economic Data Positioning",
        "short": "S5",
        "emoji": "📊",
        "tag": "tag-s5",
        "color": "#f0883e",
        "desc": "Positions ahead of scheduled economic releases (Fed decisions, GDP, CPI). Uses CME FedWatch and Atlanta Fed GDPNow to find markets mispriced vs consensus."
    },
}

# ── Data loading ──────────────────────────────────────────────────────────────
DB_PATHS = [
    "/home/ubuntu/polymarket-arena/shadow.db",
    "/home/ubuntu/polymarket-arena/arena.db",
    os.path.join(os.path.dirname(__file__), "shadow.db"),
    os.path.join(os.path.dirname(__file__), "arena.db"),
]

def get_db(name="shadow.db"):
    base = os.path.dirname(__file__)
    return os.path.join(base, name)

@st.cache_data(ttl=10)
def load_signals(limit=200, bot_filter=None):
    try:
        conn = sqlite3.connect(get_db("shadow.db"))
        query = "SELECT * FROM shadow_signals ORDER BY rowid DESC LIMIT ?"
        params = [limit]
        if bot_filter and bot_filter != "All":
            query = "SELECT * FROM shadow_signals WHERE bot_id=? ORDER BY rowid DESC LIMIT ?"
            params = [bot_filter, limit]
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=10)
def load_bot_status():
    try:
        conn = sqlite3.connect(get_db("arena.db"))
        df = pd.read_sql_query("SELECT * FROM bot_status", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=10)
def load_stats():
    try:
        conn = sqlite3.connect(get_db("shadow.db"))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM shadow_signals")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM shadow_signals WHERE resolution_status='won'")
        won = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM shadow_signals WHERE resolution_status='lost'")
        lost = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM shadow_signals WHERE timestamp > datetime('now', '-1 hour')")
        last_hour = cur.fetchone()[0]
        cur.execute("SELECT bot_id, COUNT(*) as cnt, AVG(conviction_score) as avg_conv FROM shadow_signals GROUP BY bot_id ORDER BY cnt DESC")
        by_bot = cur.fetchall()
        conn.close()
        return {"total": total, "won": won, "lost": lost, "last_hour": last_hour, "by_bot": by_bot}
    except Exception:
        return {"total": 0, "won": 0, "lost": 0, "last_hour": 0, "by_bot": []}

# ── Helpers ───────────────────────────────────────────────────────────────────
def bot_tag(bot_id):
    m = BOT_META.get(bot_id, {"label": bot_id, "tag": "tag-s1", "emoji": "🤖"})
    return f'<span class="tag {m["tag"]}">{m["emoji"]} {m["label"]}</span>'

def direction_tag(direction):
    d = (direction or "").upper()
    cls = "tag-buy" if d == "BUY" else "tag-sell"
    return f'<span class="tag {cls}">{d}</span>'

def status_tag(status):
    s = (status or "pending").lower()
    cls = {"won": "tag-won", "lost": "tag-lost"}.get(s, "tag-pending")
    return f'<span class="tag {cls}">{s}</span>'

def fmt_time(ts):
    try:
        dt = datetime.fromisoformat(str(ts))
        delta = datetime.utcnow() - dt
        if delta.seconds < 60:
            return f"{delta.seconds}s ago"
        if delta.seconds < 3600:
            return f"{delta.seconds//60}m ago"
        return dt.strftime("%H:%M")
    except Exception:
        return str(ts)[:16] if ts else "—"

def is_alive(heartbeat_str):
    try:
        hb = datetime.fromisoformat(str(heartbeat_str))
        return (datetime.utcnow() - hb).seconds < 180
    except Exception:
        return False

# ── Main app ──────────────────────────────────────────────────────────────────
def main():
    stats      = load_stats()
    bot_status = load_bot_status()
    signals    = load_signals(limit=200)

    # ── Header ────────────────────────────────────────────────────────────
    col_title, col_refresh = st.columns([6, 1])
    with col_title:
        st.markdown("## 🏟️ Polymarket Arena")
    with col_refresh:
        st.markdown("<div style='padding-top:8px'></div>", unsafe_allow_html=True)
        if st.button("⟳ Refresh"):
            st.cache_data.clear()
            st.rerun()

    st.markdown(
        f"<div style='color:#8b949e; font-size:12px; margin-top:-12px; margin-bottom:16px'>"
        f"Last updated {datetime.utcnow().strftime('%H:%M:%S UTC')} · "
        f"{stats['total']:,} total signals · "
        f"{stats['last_hour']} in last hour</div>",
        unsafe_allow_html=True
    )

    # ── Bot legend ────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">The Bots</div>', unsafe_allow_html=True)
    bot_cols = st.columns(5)
    for i, (bot_id, meta) in enumerate(BOT_META.items()):
        row = bot_status[bot_status["bot_id"] == bot_id] if not bot_status.empty else pd.DataFrame()
        if not row.empty:
            alive = is_alive(row.iloc[0]["last_heartbeat"])
            task  = str(row.iloc[0].get("current_task", "—"))[:60]
            dot   = "dot-live" if alive else "dot-error"
            status_text = "Live" if alive else "Error"
            status_color = "#3fb950" if alive else "#f85149"
        else:
            task  = "No data yet"
            dot   = "dot-idle"
            status_text = "Waiting"
            status_color = "#8b949e"

        cnt = next((b[1] for b in stats["by_bot"] if b[0] == bot_id), 0)

        with bot_cols[i]:
            st.markdown(
                f'<div class="card" style="border-top: 3px solid {meta["color"]}; min-height: 160px">'
                f'<div style="font-size:20px; margin-bottom:4px">{meta["emoji"]}</div>'
                f'<div style="font-size:13px; font-weight:700; color:{meta["color"]}; margin-bottom:6px">{meta["label"]}</div>'
                f'<div style="font-size:11.5px; color:#c9d1d9; line-height:1.5; margin-bottom:8px">{meta["desc"]}</div>'
                f'<div style="display:flex; align-items:center; gap:6px; font-size:11px">'
                f'<span class="{dot}"></span>'
                f'<span style="color:{status_color}; font-weight:600">{status_text}</span>'
                f'<span style="color:#484f58">·</span>'
                f'<span style="color:#c9d1d9">{cnt:,} signals</span>'
                f'</div>'
                f'<div style="font-size:10.5px; color:#8b949e; margin-top:4px; font-style:italic">{task}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── Stat row ──────────────────────────────────────────────────────────
    sc1, sc2, sc3, sc4, sc5 = st.columns(5)
    def stat_card(col, value, label, color="#e6edf3"):
        col.markdown(
            f'<div class="card" style="text-align:center">'
            f'<div class="stat-big" style="color:{color}">{value}</div>'
            f'<div class="stat-label">{label}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    stat_card(sc1, f"{stats['total']:,}", "Total Signals")
    stat_card(sc2, f"{stats['last_hour']}", "Last Hour", "#58a6ff")
    stat_card(sc3, f"{stats['won']}", "Resolved Won", "#3fb950")
    stat_card(sc4, f"{stats['lost']}", "Resolved Lost", "#f85149")
    pending = stats["total"] - stats["won"] - stats["lost"]
    stat_card(sc5, f"{pending:,}", "Pending", "#8b949e")

    # ── Main layout: signal feed | right panel ────────────────────────────
    feed_col, right_col = st.columns([2, 1])

    # ── Signal Feed ───────────────────────────────────────────────────────
    with feed_col:
        st.markdown('<div class="section-title">Live Signal Feed</div>', unsafe_allow_html=True)

        # Filter
        filter_opts = ["All"] + [BOT_META[b]["label"] for b in BOT_META]
        bot_filter_label = st.selectbox("Filter by bot", filter_opts, label_visibility="collapsed")
        bot_filter_id = None
        for bid, meta in BOT_META.items():
            if meta["label"] == bot_filter_label:
                bot_filter_id = bid
                break

        df = load_signals(limit=200, bot_filter=bot_filter_id)

        if df.empty:
            st.markdown('<div class="card" style="color:#8b949e; text-align:center; padding:40px">No signals yet</div>', unsafe_allow_html=True)
        else:
            # Header row
            header = (
                '<div class="signal-row header">'
                '<span>Time</span><span>Bot</span><span>Market</span>'
                '<span>Dir</span><span>Size</span><span>Conv</span><span>Status</span>'
                '</div>'
            )
            rows_html = header
            for _, row in df.iterrows():
                market = str(row.get("market_title", ""))
                market_short = market[:55] + "…" if len(market) > 55 else market
                size = float(row.get("shadow_size", 0) or 0)
                conv = float(row.get("conviction_score", 0) or 0)
                rows_html += (
                    f'<div class="signal-row">'
                    f'<span style="color:#8b949e">{fmt_time(row.get("timestamp"))}</span>'
                    f'{bot_tag(row.get("bot_id",""))}'
                    f'<span title="{market}">{market_short}</span>'
                    f'{direction_tag(row.get("direction",""))}'
                    f'<span>${size:,.0f}</span>'
                    f'<span style="color:#e3b341">{conv:.1f}</span>'
                    f'{status_tag(row.get("resolution_status",""))}'
                    f'</div>'
                )
            st.markdown(
                f'<div class="card" style="padding:0"><div class="feed-wrap">{rows_html}</div></div>',
                unsafe_allow_html=True
            )

    # ── Right panel ───────────────────────────────────────────────────────
    with right_col:

        # Leaderboard
        st.markdown('<div class="section-title">Signal Leaderboard</div>', unsafe_allow_html=True)
        if stats["by_bot"]:
            lb_html = (
                '<div class="lb-row header" style="color:#8b949e; font-size:11px; '
                'text-transform:uppercase; letter-spacing:.06em">'
                '<span>#</span><span>Bot</span><span>Signals</span><span>Avg Conv</span>'
                '</div>'
            )
            for i, (bot_id, cnt, avg_conv) in enumerate(stats["by_bot"], 1):
                meta = BOT_META.get(bot_id, {"label": bot_id, "emoji": "🤖", "color": "#8b949e"})
                lb_html += (
                    f'<div class="lb-row">'
                    f'<span class="rank">{i}</span>'
                    f'<span>{meta["emoji"]} {meta["label"]}</span>'
                    f'<span style="color:{meta["color"]}">{cnt:,}</span>'
                    f'<span style="color:#e3b341">{avg_conv:.1f}</span>'
                    f'</div>'
                )
            st.markdown(
                f'<div class="card" style="padding:0 0 8px 0">{lb_html}</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown('<div class="card" style="color:#8b949e">No data</div>', unsafe_allow_html=True)

        # Signal distribution chart
        st.markdown('<div class="section-title">Signals by Bot</div>', unsafe_allow_html=True)
        if stats["by_bot"]:
            labels = [BOT_META.get(b[0], {"label": b[0]})["label"] for b in stats["by_bot"]]
            values = [b[1] for b in stats["by_bot"]]
            colors = [BOT_META.get(b[0], {"color": "#8b949e"})["color"] for b in stats["by_bot"]]

            fig = go.Figure(go.Bar(
                x=labels, y=values,
                marker_color=colors,
                text=values, textposition="outside",
                textfont=dict(color="#e6edf3", size=12),
            ))
            fig.update_layout(
                paper_bgcolor="#161b22",
                plot_bgcolor="#161b22",
                font=dict(color="#e6edf3", size=11),
                margin=dict(l=8, r=8, t=8, b=8),
                height=220,
                xaxis=dict(showgrid=False, tickangle=-20,
                           tickfont=dict(size=10), color="#8b949e"),
                yaxis=dict(showgrid=True, gridcolor="#21262d", color="#8b949e"),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # Recent signal explanations
        st.markdown('<div class="section-title">Latest Signal Detail</div>', unsafe_allow_html=True)
        recent = load_signals(limit=3)
        if not recent.empty:
            for _, row in recent.iterrows():
                meta = BOT_META.get(row.get("bot_id", ""), {"label": "Bot", "emoji": "🤖", "color": "#8b949e"})
                explanation = str(row.get("signal_explanation", ""))[:200]
                st.markdown(
                    f'<div class="card" style="border-left: 3px solid {meta["color"]}; padding: 12px 16px">'
                    f'<div style="font-size:12px; font-weight:600; margin-bottom:4px">'
                    f'{meta["emoji"]} {row.get("signal_headline","")[:60]}</div>'
                    f'<div style="font-size:11.5px; color:#8b949e; line-height:1.5">{explanation}…</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

    # ── Auto-refresh ──────────────────────────────────────────────────────
    st.markdown(
        "<div style='text-align:center; color:#484f58; font-size:11px; margin-top:24px'>"
        "Auto-refreshes every 15 seconds · All data from live Polymarket APIs</div>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()

# Auto-refresh every 15 seconds
import time
time.sleep(15)
st.rerun()
