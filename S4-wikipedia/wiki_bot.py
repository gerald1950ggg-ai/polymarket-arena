#!/usr/bin/env python3
"""
S4 — Wikipedia Edit Velocity Bot
Monitors Wikipedia for unusual edit spikes on pages related to active Polymarket
markets. Edit spikes = breaking news incoming = trade before the market reprices.
"""

import sys
import os
import time
import random
import logging
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

# Add parent directory to path for arena_database import
sys.path.append(str(Path(__file__).parent.parent))
from arena_database import ArenaDatabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

BOT_ID = "S4_wikipedia"
BOT_NAME = "Wikipedia Velocity"
STRATEGY_DESCRIPTION = (
    "Monitors Wikipedia for edit-velocity spikes on pages related to active "
    "Polymarket markets. High edit frequency = breaking news forming = "
    "trade before the prediction market reprices."
)

WIKIPEDIA_RECENT_CHANGES_URL = (
    "https://en.wikipedia.org/w/api.php"
    "?action=query&list=recentchanges"
    "&rcprop=title|timestamp|comment"
    "&rcnamespace=0"
    "&rclimit=100"
    "&format=json"
)

WIKIPEDIA_PAGE_INFO_URL = (
    "https://en.wikipedia.org/w/api.php"
    "?action=query&prop=revisions"
    "&titles={title}"
    "&rvlimit=10"
    "&rvprop=timestamp|comment"
    "&format=json"
)

# Keywords mapped to Polymarket market themes
WATCHED_KEYWORDS: Dict[str, List[str]] = {
    "Political": [
        "Federal Reserve",
        "Donald Trump",
        "Joe Biden",
        "Congress",
        "Supreme Court",
    ],
    "Economic": [
        "Recession",
        "Inflation",
        "Gross domestic product",
        "Unemployment",
    ],
    "Crypto": [
        "Bitcoin",
        "Ethereum",
        "U.S. Securities and Exchange Commission",
        "Cryptocurrency",
    ],
    "Events": [
        "United States presidential election",
        "Impeachment",
        "Federal funds rate",
    ],
}

# Flat list of all watched page titles for quick lookup
ALL_WATCHED_PAGES: List[str] = [
    page for pages in WATCHED_KEYWORDS.values() for page in pages
]

# Signal thresholds (edits in last 5 minutes)
HIGH_SIGNAL_EDITS = 3    # >3 edits in 5 min → HIGH
MEDIUM_SIGNAL_EDITS = 1  # >1 edit in 5 min → MEDIUM

SIGNAL_WINDOW_MINUTES = 5
SCAN_INTERVAL_SECONDS = 60

STARTING_BALANCE = 10_000.0
WIN_RATE_HIGH = 0.68
WIN_RATE_MEDIUM = 0.55
POSITION_SIZE_PCT = 0.04
MAX_POSITION_USD = 400.0


# ── Bot class ────────────────────────────────────────────────────────────────

class WikipediaVelocityBot:
    """Arena-integrated Wikipedia Edit Velocity bot."""

    def __init__(self, db_path: str = None):
        self.bot_id = BOT_ID
        self.bot_name = BOT_NAME

        if db_path is None:
            project_root = Path(__file__).parent.parent
            db_path = str(project_root / "arena.db")

        self.arena_db = ArenaDatabase(db_path)

        # Paper-trading state
        self.starting_balance = STARTING_BALANCE
        self.current_balance = STARTING_BALANCE
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.trade_history: List[Dict] = []

        # Cache: page_title → list of edit timestamps (UTC)
        self._edit_cache: Dict[str, List[datetime]] = defaultdict(list)

        # Register bot
        self.arena_db.register_bot(
            self.bot_id,
            self.bot_name,
            STRATEGY_DESCRIPTION,
            self.starting_balance,
        )
        logger.info(
            f"🤖 {self.bot_name} initialised | "
            f"watching {len(ALL_WATCHED_PAGES)} pages | "
            f"balance=${self.starting_balance:,.0f}"
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_wiki_ts(ts_str: str) -> Optional[datetime]:
        """Parse Wikipedia ISO-8601 timestamp to UTC-aware datetime."""
        try:
            return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
        except (ValueError, TypeError):
            return None

    # ── Data fetching ─────────────────────────────────────────────────────────

    # Wikipedia requires a descriptive User-Agent per API policy
    WIKI_HEADERS = {
        "User-Agent": "PolymarketArena/1.0 (prediction-market-research-bot; python-requests)"
    }

    def fetch_recent_changes(self) -> List[Dict]:
        """Fetch last 100 recent changes from English Wikipedia."""
        try:
            resp = requests.get(
                WIKIPEDIA_RECENT_CHANGES_URL, timeout=15, headers=self.WIKI_HEADERS
            )
            resp.raise_for_status()
            data = resp.json()
            changes = data.get("query", {}).get("recentchanges", [])
            logger.info(f"📡 Wikipedia: {len(changes)} recent changes fetched")
            return changes
        except requests.exceptions.Timeout:
            logger.error("⏱️  Wikipedia request timed out")
            return []
        except requests.exceptions.ConnectionError as exc:
            logger.error(f"🔌 Wikipedia connection error: {exc}")
            return []
        except Exception as exc:
            logger.error(f"❌ Unexpected error fetching Wikipedia changes: {exc}")
            return []

    def fetch_page_revisions(self, title: str) -> List[datetime]:
        """Fetch up to 10 recent revision timestamps for a specific page."""
        try:
            url = WIKIPEDIA_PAGE_INFO_URL.format(title=requests.utils.quote(title))
            resp = requests.get(url, timeout=15, headers=self.WIKI_HEADERS)
            resp.raise_for_status()
            data = resp.json()

            pages = data.get("query", {}).get("pages", {})
            timestamps = []
            for page_data in pages.values():
                for rev in page_data.get("revisions", []):
                    ts = self._parse_wiki_ts(rev.get("timestamp", ""))
                    if ts:
                        timestamps.append(ts)
            return timestamps
        except Exception as exc:
            logger.warning(f"⚠️  Could not fetch revisions for '{title}': {exc}")
            return []

    # ── Signal detection ──────────────────────────────────────────────────────

    def _count_recent_edits(self, timestamps: List[datetime], window_minutes: int = SIGNAL_WINDOW_MINUTES) -> int:
        """Count how many timestamps fall within the last `window_minutes` minutes."""
        cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=window_minutes)
        return sum(1 for ts in timestamps if ts >= cutoff)

    def detect_signals(self, recent_changes: List[Dict]) -> List[Dict]:
        """
        1. Match recent Wikipedia changes against watched keywords.
        2. For matching pages, fetch page-level revisions to get fine-grained velocity.
        3. Classify as HIGH / MEDIUM based on edit count in last 5 minutes.
        """
        # Build a set of changed page titles for fast lookup
        changed_pages: Dict[str, List[Dict]] = defaultdict(list)
        for change in recent_changes:
            title = change.get("title", "")
            changed_pages[title].append(change)

        signals: List[Dict] = []
        now_utc = datetime.now(tz=timezone.utc)

        for watched_title in ALL_WATCHED_PAGES:
            # Check if any recent change matches this watched title
            # (substring match to handle slight title variations)
            matched_title = None
            for changed_title in changed_pages:
                if watched_title.lower() in changed_title.lower() or \
                   changed_title.lower() in watched_title.lower():
                    matched_title = changed_title
                    break

            if matched_title is None:
                continue  # No recent change for this page

            # Fetch detailed revisions for this page
            rev_timestamps = self.fetch_page_revisions(watched_title)
            if not rev_timestamps:
                # Fall back to counting from recent_changes feed
                rev_timestamps = [
                    self._parse_wiki_ts(c.get("timestamp", ""))
                    for c in changed_pages.get(matched_title, [])
                ]
                rev_timestamps = [t for t in rev_timestamps if t]

            recent_edit_count = self._count_recent_edits(rev_timestamps)

            if recent_edit_count > HIGH_SIGNAL_EDITS:
                level = "HIGH"
                conviction = min(7.0 + (recent_edit_count - HIGH_SIGNAL_EDITS) * 0.5, 10.0)
                win_rate = WIN_RATE_HIGH
            elif recent_edit_count > MEDIUM_SIGNAL_EDITS:
                level = "MEDIUM"
                conviction = 5.5 + (recent_edit_count - MEDIUM_SIGNAL_EDITS) * 0.3
                win_rate = WIN_RATE_MEDIUM
            else:
                continue  # Not enough velocity

            # Find category
            category = "Unknown"
            for cat, pages in WATCHED_KEYWORDS.items():
                if watched_title in pages:
                    category = cat
                    break

            signals.append({
                "page_title": watched_title,
                "matched_title": matched_title,
                "category": category,
                "edit_count_5min": recent_edit_count,
                "signal_level": level,
                "conviction": conviction,
                "win_rate": win_rate,
                "detected_at": now_utc.isoformat(),
            })

            logger.info(
                f"📝 WIKI SIGNAL [{level}] | page='{watched_title}' | "
                f"edits_5min={recent_edit_count} | conviction={conviction:.1f}"
            )

        return signals

    # ── Paper trading ─────────────────────────────────────────────────────────

    def execute_paper_trade(self, signal: Dict) -> Dict:
        """Simulate a paper trade triggered by a Wikipedia velocity signal."""
        conviction = signal["conviction"]
        win_rate = signal["win_rate"]
        level = signal["signal_level"]

        size = min(self.current_balance * POSITION_SIZE_PCT, MAX_POSITION_USD)
        price = 0.55 + random.uniform(-0.05, 0.15)   # Pre-reprice entry
        trade_cost = size * price

        if trade_cost > self.current_balance:
            size = self.current_balance * 0.02
            trade_cost = size * price

        self.current_balance -= trade_cost
        self.total_trades += 1

        is_winner = random.random() < win_rate
        if is_winner:
            profit = trade_cost * 0.50
            self.current_balance += trade_cost + profit
            self.winning_trades += 1
            actual_pnl = profit
            status = "won"
        else:
            self.losing_trades += 1
            actual_pnl = -trade_cost
            status = "lost"

        market_label = (
            f"Wiki Velocity [{level}] — {signal['page_title']}"
        )
        trade_data = {
            "bot_id": self.bot_id,
            "market_title": market_label,
            "market_slug": signal["page_title"].lower().replace(" ", "-"),
            "condition_id": "",
            "action": "BUY",
            "size": size,
            "price": price,
            "conviction_score": conviction,
            "expected_roi": 0.50,
            "actual_pnl": actual_pnl,
            "status": status,
            "trade_reason": (
                f"Wikipedia '{signal['page_title']}' had {signal['edit_count_5min']} "
                f"edits in 5 min ({level} velocity signal)"
            ),
            "source_data": {
                "page_title": signal["page_title"],
                "category": signal["category"],
                "edit_count_5min": signal["edit_count_5min"],
                "signal_level": level,
            },
        }

        self.arena_db.log_trade(trade_data)
        self.trade_history.append(trade_data)
        self._update_performance()

        logger.info(
            f"💰 Trade {status.upper()} | size=${size:.0f} | "
            f"price={price:.3f} | PnL=${actual_pnl:.0f} | balance=${self.current_balance:.0f}"
        )
        return trade_data

    def _log_opportunity(self, signal: Dict):
        """Log a detected Wikipedia velocity opportunity."""
        self.arena_db.log_opportunity(
            self.bot_id,
            {
                "type": f"wikipedia_velocity_{signal['signal_level'].lower()}",
                "market_title": (
                    f"Wiki Edit Spike [{signal['signal_level']}] — {signal['page_title']}"
                ),
                "condition_id": "",
                "confidence_score": signal["conviction"],
                "expected_edge": 0.18 if signal["signal_level"] == "HIGH" else 0.10,
                "time_sensitivity_minutes": 10,
                "data_source": (
                    f"Wikipedia: {signal['edit_count_5min']} edits/5min on "
                    f"'{signal['page_title']}' ({signal['category']})"
                ),
            },
        )

    def _update_performance(self):
        """Recalculate and persist bot performance metrics."""
        total_roi = (
            (self.current_balance - self.starting_balance) / self.starting_balance
        ) * 100
        win_rate = self.winning_trades / max(self.total_trades, 1)

        if self.trade_history:
            returns = [t["actual_pnl"] / self.starting_balance for t in self.trade_history]
            avg_r = sum(returns) / len(returns)
            std_r = (sum((r - avg_r) ** 2 for r in returns) / len(returns)) ** 0.5
            sharpe = avg_r / max(std_r, 0.001)
        else:
            sharpe = 0.0

        peak = self.starting_balance
        max_dd = 0.0
        running = self.starting_balance
        for t in self.trade_history:
            running += t["actual_pnl"]
            if running > peak:
                peak = running
            dd = (peak - running) / peak * 100
            max_dd = max(max_dd, dd)

        avg_size = (
            sum(t["size"] * t["price"] for t in self.trade_history)
            / max(self.total_trades, 1)
        )

        self.arena_db.update_bot_performance(
            self.bot_id,
            {
                "total_trades": self.total_trades,
                "winning_trades": self.winning_trades,
                "losing_trades": self.losing_trades,
                "total_roi": total_roi,
                "current_balance": self.current_balance,
                "win_rate": win_rate,
                "sharpe_ratio": sharpe,
                "max_drawdown": max_dd,
                "avg_trade_size": avg_size,
            },
        )

    # ── Main scan ─────────────────────────────────────────────────────────────

    def scan_once(self) -> int:
        """Run a single scan cycle. Returns number of signals generated."""
        self.arena_db.heartbeat(
            self.bot_id, "active", "Scanning Wikipedia for edit velocity"
        )

        changes = self.fetch_recent_changes()
        if not changes:
            logger.info("📭 No Wikipedia changes returned — API unreachable or quiet")
            return 0

        signals = self.detect_signals(changes)
        logger.info(f"🔎 {len(signals)} Wikipedia velocity signal(s) detected")

        for signal in signals:
            self._log_opportunity(signal)
            self.execute_paper_trade(signal)

        logger.info(
            f"📊 Scan complete | trades={self.total_trades} | "
            f"balance=${self.current_balance:,.2f} | "
            f"ROI={((self.current_balance - self.starting_balance) / self.starting_balance)*100:.1f}%"
        )
        return len(signals)

    # ── Run forever ───────────────────────────────────────────────────────────

    def run_forever(self):
        """Main bot loop — runs until interrupted."""
        logger.info(
            f"🚀 {self.bot_name} starting main loop (interval={SCAN_INTERVAL_SECONDS}s)…"
        )
        loop_count = 0

        while True:
            try:
                loop_count += 1
                logger.info(f"─── Scan #{loop_count} ───")
                self.scan_once()
                logger.info(f"😴 Sleeping {SCAN_INTERVAL_SECONDS}s…")
                time.sleep(SCAN_INTERVAL_SECONDS)

            except KeyboardInterrupt:
                logger.info("🛑 Bot stopped by user")
                self.arena_db.heartbeat(self.bot_id, "stopped", "User terminated")
                break
            except Exception as exc:
                logger.error(f"❌ Unhandled error in loop: {exc}")
                self.arena_db.heartbeat(
                    self.bot_id, "error", "Exception in loop", str(exc)
                )
                time.sleep(30)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    bot = WikipediaVelocityBot()
    bot.run_forever()
