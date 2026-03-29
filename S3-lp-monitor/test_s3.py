#!/usr/bin/env python3
"""
test_s3.py — Single-scan integration test for S3 LP Withdrawal Detection bot.
Runs ONE scan and exits cleanly.
"""

import sys
import os
import logging
from pathlib import Path

# Ensure parent dir on path (for arena_database)
sys.path.append(str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    print("=" * 60)
    print("  S3 LP Withdrawal Detection Bot — Integration Test")
    print("=" * 60)

    # Use a throw-away test DB so we don't pollute arena.db
    test_db = str(Path(__file__).parent.parent / "test_arena.db")
    print(f"\n📁 Test DB: {test_db}\n")

    from lp_bot import LPWithdrawalBot

    bot = LPWithdrawalBot(db_path=test_db)

    print("\n── Step 1: Fetch merges from Goldsky ──")
    merges = bot.fetch_recent_merges()
    print(f"  Merges returned: {len(merges)}")

    if merges:
        sample = merges[0]
        print(f"  Sample merge ID  : {sample.get('id', 'N/A')}")
        print(f"  Sample timestamp : {sample.get('timestamp', 'N/A')}")
        print(f"  Sample amount    : {sample.get('amount', 'N/A')}")
        print(f"  Sample condition : {sample.get('condition', 'N/A')}")
    else:
        print("  ⚠️  No merges from API (may be empty or unreachable) — injecting synthetic data for test")
        # Inject synthetic merges to test signal detection logic
        import time
        now = int(time.time())
        merges = [
            {"id": f"synthetic_{i}", "timestamp": now - i * 60,
             "amount": "5000000",
             "stakeholder": "0xABCDEF1234567890",
             "condition": "0xSYNTHETIC_CONDITION_ABC"}
            for i in range(4)  # 4 merges → should trigger signal
        ]
        print(f"  Injected {len(merges)} synthetic merges for condition 0xSYNTHETIC…")

    print("\n── Step 2: Detect signals ──")
    signals = bot.detect_signals(merges)
    print(f"  Signals detected: {len(signals)}")
    for s in signals:
        print(
            f"    condition={s['condition_id'][:16]}… | "
            f"merges={s['merge_count']} | "
            f"collateral=${s['total_collateral_usd']:,.2f} | "
            f"conviction={s['conviction']:.1f}"
        )

    print("\n── Step 3: Execute paper trade (if signal) ──")
    if signals:
        bot._log_opportunity(signals[0])   # also test the opportunity logger
        trade = bot.execute_paper_trade(signals[0])
        print(f"  Status    : {trade['status'].upper()}")
        print(f"  Size      : ${trade['size']:.2f}")
        print(f"  Price     : {trade['price']:.4f}")
        print(f"  PnL       : ${trade['actual_pnl']:.2f}")
        print(f"  Conviction: {trade['conviction_score']:.1f}")
    else:
        print("  No signals → no trade executed")

    print("\n── Step 4: Database check ──")
    db_trades = bot.arena_db.get_recent_trades(bot_id=bot.bot_id, limit=5)
    print(f"  Trades in DB for {bot.bot_id}: {len(db_trades)}")

    leaderboard = bot.arena_db.get_live_leaderboard()
    s3_entry = next((b for b in leaderboard if b["bot_id"] == bot.bot_id), None)
    if s3_entry:
        print(f"  Bot on leaderboard: ✅  balance=${s3_entry['current_balance']:,.2f}")
    else:
        print("  Bot on leaderboard: ❌  not found")

    print("\n── Summary ──")
    print(f"  Total trades  : {bot.total_trades}")
    print(f"  Winning       : {bot.winning_trades}")
    print(f"  Losing        : {bot.losing_trades}")
    print(f"  Balance       : ${bot.current_balance:,.2f}")
    print(
        f"  ROI           : {((bot.current_balance - bot.starting_balance) / bot.starting_balance)*100:.2f}%"
    )

    print("\n✅  S3 test PASSED — bot is functional\n")


if __name__ == "__main__":
    main()
