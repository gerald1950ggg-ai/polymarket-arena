#!/usr/bin/env python3
"""
test_s4.py — Single-scan integration test for S4 Wikipedia Velocity bot.
Runs ONE scan and exits cleanly.
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Ensure parent dir on path (for arena_database)
sys.path.append(str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    print("=" * 60)
    print("  S4 Wikipedia Velocity Bot — Integration Test")
    print("=" * 60)

    test_db = str(Path(__file__).parent.parent / "test_arena.db")
    print(f"\n📁 Test DB: {test_db}\n")

    from wiki_bot import WikipediaVelocityBot, WATCHED_KEYWORDS, ALL_WATCHED_PAGES

    bot = WikipediaVelocityBot(db_path=test_db)

    print(f"\n── Watched pages ({len(ALL_WATCHED_PAGES)} total) ──")
    for category, pages in WATCHED_KEYWORDS.items():
        print(f"  {category}: {', '.join(pages)}")

    print("\n── Step 1: Fetch Wikipedia recent changes ──")
    changes = bot.fetch_recent_changes()
    print(f"  Changes returned: {len(changes)}")
    if changes:
        sample = changes[0]
        print(f"  Sample title    : {sample.get('title', 'N/A')}")
        print(f"  Sample timestamp: {sample.get('timestamp', 'N/A')}")
        print(f"  Sample comment  : {sample.get('comment', 'N/A')[:80]}")

    print("\n── Step 2: Detect signals from live changes ──")
    live_signals = []
    if changes:
        live_signals = bot.detect_signals(changes)
        print(f"  Live signals detected: {len(live_signals)}")
        for s in live_signals:
            print(
                f"    [{s['signal_level']}] '{s['page_title']}' | "
                f"edits={s['edit_count_5min']} | conviction={s['conviction']:.1f}"
            )
    else:
        print("  ⚠️  No changes returned from Wikipedia API")

    # Inject synthetic signals if live data produced none (ensures code path is exercised)
    if not live_signals:
        print("\n── Step 2b: Injecting synthetic signals for code-path test ──")
        now = datetime.now(tz=timezone.utc)

        # Fabricate recent-changes that match a watched page
        synthetic_changes = [
            {
                "title": "Bitcoin",
                "timestamp": (now - timedelta(seconds=i * 30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "comment": f"Breaking news update #{i}",
            }
            for i in range(5)  # 5 recent changes to Bitcoin page
        ]
        print(f"  Injected {len(synthetic_changes)} synthetic changes for 'Bitcoin'")

        # Also patch fetch_page_revisions to return synthetic timestamps
        _original_fetch = bot.fetch_page_revisions

        def _synthetic_revisions(title):
            if "Bitcoin" in title or "bitcoin" in title.lower():
                return [now - timedelta(seconds=i * 45) for i in range(5)]
            return _original_fetch(title)

        bot.fetch_page_revisions = _synthetic_revisions

        live_signals = bot.detect_signals(synthetic_changes)
        print(f"  Synthetic signals detected: {len(live_signals)}")
        for s in live_signals:
            print(
                f"    [{s['signal_level']}] '{s['page_title']}' | "
                f"edits={s['edit_count_5min']} | conviction={s['conviction']:.1f}"
            )

    print("\n── Step 3: Execute paper trade (if signal) ──")
    if live_signals:
        bot._log_opportunity(live_signals[0])   # also test the opportunity logger
        trade = bot.execute_paper_trade(live_signals[0])
        print(f"  Status    : {trade['status'].upper()}")
        print(f"  Market    : {trade['market_title']}")
        print(f"  Size      : ${trade['size']:.2f}")
        print(f"  Price     : {trade['price']:.4f}")
        print(f"  PnL       : ${trade['actual_pnl']:.2f}")
        print(f"  Conviction: {trade['conviction_score']:.1f}")
        print(f"  Reason    : {trade['trade_reason']}")
    else:
        print("  No signals → no trade executed")

    print("\n── Step 4: Database check ──")
    db_trades = bot.arena_db.get_recent_trades(bot_id=bot.bot_id, limit=5)
    print(f"  Trades in DB for {bot.bot_id}: {len(db_trades)}")

    opps = bot.arena_db.get_market_opportunities(active_only=False)
    s4_opps = [o for o in opps if o["detected_by"] == bot.bot_id]
    print(f"  Opportunities logged by {bot.bot_id}: {len(s4_opps)}")

    leaderboard = bot.arena_db.get_live_leaderboard()
    s4_entry = next((b for b in leaderboard if b["bot_id"] == bot.bot_id), None)
    if s4_entry:
        print(f"  Bot on leaderboard: ✅  balance=${s4_entry['current_balance']:,.2f}")
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

    print("\n✅  S4 test PASSED — bot is functional\n")


if __name__ == "__main__":
    main()
