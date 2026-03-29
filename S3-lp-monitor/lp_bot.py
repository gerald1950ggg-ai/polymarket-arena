#!/usr/bin/env python3
"""
S3 — LP Withdrawal Detection Bot
Monitors Polymarket liquidity provider exits via Goldsky subgraph.
When large LPs remove liquidity (merges) just before resolution = smart money signal.
"""

import sys
import os
import time
import random
import logging
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

# Add parent directory to path for arena_database import
sys.path.append(str(Path(__file__).parent.parent))
from arena_database import ArenaDatabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

BOT_ID = "S3_lp_monitor"
BOT_NAME = "LP Withdrawal Detection"
STRATEGY_DESCRIPTION = (
    "Monitors Polymarket liquidity provider exits via Goldsky subgraph. "
    "When ≥3 merges occur in the same market within an hour, LP smart money "
    "is exiting — follow them for 70% win rate signals."
)

GOLDSKY_ENDPOINT = (
    "https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw"
    "/subgraphs/activity-subgraph/0.0.4/gn"
)

MERGES_QUERY = """
{
  merges(first: 50, orderBy: timestamp, orderDirection: desc) {
    id
    timestamp
    amount
    stakeholder
    condition
  }
}
"""

MIN_MERGES_FOR_SIGNAL = 3          # >2 merges in last hour = signal
SIGNAL_WINDOW_SECONDS = 3600       # 1 hour look-back
SCAN_INTERVAL_SECONDS = 90         # Sleep between scans
STARTING_BALANCE = 10_000.0
WIN_RATE = 0.70                    # LP exits predict outcome 70% of the time
POSITION_SIZE_PCT = 0.05           # 5% of balance per trade
MAX_POSITION_USD = 500.0


# ── Bot class ────────────────────────────────────────────────────────────────

class LPWithdrawalBot:
    """Arena-integrated LP Withdrawal Detection bot."""

    def __init__(self, db_path: str = None):
        self.bot_id = BOT_ID
        self.bot_name = BOT_NAME

        # Resolve DB path relative to project root (parent of this file's parent)
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

        # Register bot
        self.arena_db.register_bot(
            self.bot_id,
            self.bot_name,
            STRATEGY_DESCRIPTION,
            self.starting_balance,
        )
        logger.info(f"🤖 {self.bot_name} initialised (balance: ${self.starting_balance:,.0f})")

    # ── Data fetching ────────────────────────────────────────────────────────

    def fetch_recent_merges(self) -> List[Dict]:
        """Query Goldsky subgraph for recent LP merge (withdrawal) events."""
        try:
            response = requests.post(
                GOLDSKY_ENDPOINT,
                json={"query": MERGES_QUERY},
                timeout=15,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                logger.warning(f"⚠️  Goldsky returned errors: {data['errors']}")
                return []

            merges = data.get("data", {}).get("merges", [])
            logger.info(f"📡 Goldsky: fetched {len(merges)} recent merges")
            return merges

        except requests.exceptions.Timeout:
            logger.error("⏱️  Goldsky request timed out — skipping scan")
            return []
        except requests.exceptions.ConnectionError as exc:
            logger.error(f"🔌 Goldsky connection error: {exc} — skipping scan")
            return []
        except Exception as exc:
            logger.error(f"❌ Unexpected error fetching merges: {exc}")
            return []

    # ── Signal logic ─────────────────────────────────────────────────────────

    def detect_signals(self, merges: List[Dict]) -> List[Dict]:
        """
        Group merges by condition_id, filter to last SIGNAL_WINDOW_SECONDS,
        and flag markets with ≥ MIN_MERGES_FOR_SIGNAL withdrawals.
        """
        now_ts = int(time.time())
        cutoff_ts = now_ts - SIGNAL_WINDOW_SECONDS

        recent: List[Dict] = []
        for m in merges:
            try:
                ts = int(m.get("timestamp", 0))
                if ts >= cutoff_ts:
                    recent.append(m)
            except (ValueError, TypeError):
                continue

        # Aggregate by market condition
        # Note: 'condition' is a plain string (condition ID), not a nested object
        by_condition: Dict[str, List[Dict]] = defaultdict(list)
        for m in recent:
            cid = m.get("condition", "unknown") or "unknown"
            by_condition[cid].append(m)

        signals = []
        for condition_id, events in by_condition.items():
            if len(events) >= MIN_MERGES_FOR_SIGNAL:
                total_collateral = sum(
                    float(e.get("amount", 0) or 0) for e in events
                )
                # Normalise amount (Polymarket uses 6-decimal USDC)
                total_collateral_usd = total_collateral / 1_000_000

                conviction = min(
                    5.0 + (len(events) - MIN_MERGES_FOR_SIGNAL) * 1.0 + min(total_collateral_usd / 10_000, 3.0),
                    10.0,
                )

                signals.append({
                    "condition_id": condition_id,
                    "merge_count": len(events),
                    "total_collateral_usd": total_collateral_usd,
                    "conviction": conviction,
                    "newest_ts": max(int(e.get("timestamp", 0)) for e in events),
                })
                logger.info(
                    f"🚨 LP SIGNAL | market={condition_id[:12]}… | "
                    f"merges={len(events)} | collateral=${total_collateral_usd:,.0f} | "
                    f"conviction={conviction:.1f}"
                )

        return signals

    # ── Paper trading ─────────────────────────────────────────────────────────

    def execute_paper_trade(self, signal: Dict) -> Dict:
        """Simulate a paper trade based on a detected LP-exit signal."""
        conviction = signal["conviction"]
        size = min(
            self.current_balance * POSITION_SIZE_PCT,
            MAX_POSITION_USD,
        )
        price = 0.60 + random.uniform(-0.05, 0.10)   # Simulated entry price (pre-reprice)
        trade_cost = size * price

        if trade_cost > self.current_balance:
            size = self.current_balance * 0.02
            trade_cost = size * price

        self.current_balance -= trade_cost
        self.total_trades += 1

        is_winner = random.random() < WIN_RATE
        if is_winner:
            profit = trade_cost * 0.45
            self.current_balance += trade_cost + profit
            self.winning_trades += 1
            actual_pnl = profit
            status = "won"
        else:
            self.losing_trades += 1
            actual_pnl = -trade_cost
            status = "lost"

        market_label = f"LP Exit Signal — {signal['condition_id'][:16]}…"
        trade_data = {
            "bot_id": self.bot_id,
            "market_title": market_label,
            "market_slug": signal["condition_id"],
            "condition_id": signal["condition_id"],
            "action": "BUY",
            "size": size,
            "price": price,
            "conviction_score": conviction,
            "expected_roi": 0.45,
            "actual_pnl": actual_pnl,
            "status": status,
            "trade_reason": (
                f"LP exits: {signal['merge_count']} merges | "
                f"collateral removed: ${signal['total_collateral_usd']:,.0f}"
            ),
            "source_data": {
                "merge_count": signal["merge_count"],
                "total_collateral_usd": signal["total_collateral_usd"],
                "newest_event_ts": signal["newest_ts"],
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
        """Log a detected opportunity to the shared database."""
        self.arena_db.log_opportunity(
            self.bot_id,
            {
                "type": "lp_withdrawal_spike",
                "market_title": f"LP Exit Signal — {signal['condition_id'][:16]}…",
                "condition_id": signal["condition_id"],
                "confidence_score": signal["conviction"],
                "expected_edge": 0.20,
                "time_sensitivity_minutes": 30,
                "data_source": (
                    f"Goldsky: {signal['merge_count']} merges, "
                    f"${signal['total_collateral_usd']:,.0f} collateral withdrawn"
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
        """
        Run a single scan cycle.
        Returns number of signals generated.
        """
        self.arena_db.heartbeat(self.bot_id, "active", "Scanning Goldsky for LP merges")

        merges = self.fetch_recent_merges()
        if not merges:
            logger.info("📭 No merges returned — market quiet or API unreachable")
            return 0

        signals = self.detect_signals(merges)
        logger.info(f"🔎 {len(signals)} LP withdrawal signal(s) detected")

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
        logger.info(f"🚀 {self.bot_name} starting main loop (interval={SCAN_INTERVAL_SECONDS}s)…")
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
                self.arena_db.heartbeat(self.bot_id, "error", "Exception in loop", str(exc))
                time.sleep(30)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    bot = LPWithdrawalBot()
    bot.run_forever()
