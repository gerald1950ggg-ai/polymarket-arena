#!/usr/bin/env python3
"""
Resolution Tracker — automatically marks pending shadow signals as won/lost.

Queries shadow.db for pending signals with a valid condition_id, checks
Polymarket's gamma API to see if the market has resolved, and updates the DB.

Run standalone:
    python resolution_tracker.py

Or imported and called periodically from arena_runner.py.
"""

import json
import sqlite3
import logging
import requests
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent
SHADOW_DB_PATH = str(PROJECT_ROOT / "shadow.db")
GAMMA_API_URL = "https://gamma-api.polymarket.com/markets"
REQUEST_TIMEOUT = 10


def resolve_pending_signals(db_path: str = SHADOW_DB_PATH) -> int:
    """
    Check all pending signals with a valid condition_id against the Polymarket
    gamma API. Update won/lost/P&L in shadow.db.

    Returns the number of signals resolved this run.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Fetch all pending signals that have a real condition_id (hex string)
    cursor.execute("""
        SELECT id, condition_id, direction, entry_price, shadow_size
        FROM shadow_signals
        WHERE resolution_status = 'pending'
          AND condition_id IS NOT NULL
          AND condition_id != ''
          AND condition_id LIKE '0x%'
    """)
    pending = cursor.fetchall()

    if not pending:
        logger.info("📭 Resolution tracker: no pending signals with condition_id to check")
        conn.close()
        return 0

    logger.info(f"🔍 Resolution tracker: checking {len(pending)} pending signal(s)...")

    resolved_count = 0

    for row in pending:
        signal_id    = row["id"]
        condition_id = row["condition_id"]
        direction    = row["direction"]
        entry_price  = float(row["entry_price"] or 0.5)
        shadow_size  = float(row["shadow_size"] or 500.0)

        try:
            resp = requests.get(
                GAMMA_API_URL,
                params={"conditionIds": condition_id},
                timeout=REQUEST_TIMEOUT,
            )
            if not resp.ok:
                logger.warning(f"  Signal #{signal_id} — gamma API {resp.status_code} for {condition_id[:12]}...")
                continue

            markets = resp.json()
            if not markets:
                logger.debug(f"  Signal #{signal_id} — no market found for {condition_id[:12]}...")
                continue

            market = markets[0]
            closed = market.get("closed", False)

            if not closed:
                # Market still open
                logger.debug(f"  Signal #{signal_id} — market still open")
                continue

            # ── Determine resolution via outcomePrices ────────────────────
            # outcomePrices: ["1", "0"] = YES won, ["0", "1"] = NO won
            # outcome_prices[0] = YES price, outcome_prices[1] = NO price
            raw_prices = market.get("outcomePrices", [])
            # outcomePrices may be a JSON-encoded string or a list
            if isinstance(raw_prices, str):
                try:
                    raw_prices = json.loads(raw_prices)
                except (json.JSONDecodeError, ValueError):
                    raw_prices = []
            if not raw_prices or len(raw_prices) < 2:
                logger.debug(f"  Signal #{signal_id} — no outcomePrices data")
                continue

            yes_price = float(raw_prices[0])
            no_price  = float(raw_prices[1])

            # Resolved only if one outcome is 1 (or near 1) and other is 0
            if yes_price >= 0.99:
                yes_won = True
            elif no_price >= 0.99:
                yes_won = False
            else:
                # Not definitively resolved yet (prices still between 0 and 1)
                logger.debug(f"  Signal #{signal_id} — prices not resolved: YES={yes_price:.2f} NO={no_price:.2f}")
                continue

            if direction == "BUY":
                # We bet YES
                did_win = yes_won
            else:
                # We bet NO
                did_win = not yes_won

            # ── Calculate P&L ─────────────────────────────────────────────
            final_yes_price = 1.0 if yes_won else 0.0
            if did_win:
                # BUY YES at entry_price → receive $1 per share at resolution
                if entry_price > 0:
                    actual_pnl = shadow_size * (1.0 / entry_price - 1.0)
                else:
                    actual_pnl = 0.0
                status = "won"
            else:
                actual_pnl = -shadow_size
                status = "lost"
            resolved_price = final_yes_price

            resolved_at = datetime.now(timezone.utc).isoformat()

            cursor.execute("""
                UPDATE shadow_signals
                SET resolution_status = ?,
                    resolved_price    = ?,
                    actual_pnl        = ?,
                    resolved_at       = ?
                WHERE id = ?
            """, (status, resolved_price, round(actual_pnl, 2), resolved_at, signal_id))

            resolved_count += 1
            logger.info(
                f"  ✅ Signal #{signal_id} → {status.upper()} | "
                f"condition={condition_id[:12]}... | "
                f"winner='{winner}' | P&L=${actual_pnl:+.2f}"
            )

        except requests.exceptions.RequestException as e:
            logger.warning(f"  Signal #{signal_id} — network error: {e}")
        except Exception as e:
            logger.error(f"  Signal #{signal_id} — unexpected error: {e}")

    conn.commit()
    conn.close()

    logger.info(f"📊 Resolution tracker: {resolved_count}/{len(pending)} signal(s) resolved this run")
    return resolved_count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    import os
    # Allow override via env var for EC2 path
    db_path = os.getenv("SHADOW_DB_PATH", SHADOW_DB_PATH)
    count = resolve_pending_signals(db_path)
    print(f"\n✅ Resolved {count} signal(s)")
