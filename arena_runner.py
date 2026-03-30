#!/usr/bin/env python3
"""
Arena Runner — starts all 5 bots simultaneously.

Usage:
    python arena_runner.py

All bots run concurrently:
  S1 - Sharp Wallet Copy (async)
  S2 - Cross-Market Divergence (async)
  S3 - LP Withdrawal Monitor (sync — runs in thread)
  S4 - Wikipedia Velocity (sync — runs in thread)
  S5 - Economic Data Positioning (async)
"""

import asyncio
import importlib.util
import logging
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

logger = logging.getLogger("arena_runner")


def load_module_from_path(module_name: str, file_path: str, extra_paths: list = None):
    """Load a Python module from an absolute file path (handles hyphenated dirs)."""
    # Temporarily add the module's directory and any extra paths to sys.path
    module_dir = os.path.dirname(os.path.abspath(file_path))
    paths_to_add = [module_dir] + (extra_paths or [])
    original_path = sys.path[:]
    for p in reversed(paths_to_add):
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        # Restore original path (keep project root)
        sys.path[:] = original_path
        if PROJECT_ROOT not in sys.path:
            sys.path.insert(0, PROJECT_ROOT)


def run_resolution_tracker_loop(interval_seconds: int = 1800):
    """Run the resolution tracker in a background thread every `interval_seconds`."""
    try:
        from resolution_tracker import resolve_pending_signals
    except ImportError as e:
        logger.error(f"Could not import resolution_tracker: {e}")
        return

    logger.info(f"🔄 Resolution tracker thread started (interval={interval_seconds}s)")
    while True:
        try:
            resolve_pending_signals()
        except Exception as e:
            logger.error(f"Resolution tracker error: {e}", exc_info=True)
        time.sleep(interval_seconds)


def run_sync_bot(bot):
    """Run a synchronous bot's run_forever() in a thread."""
    try:
        bot.run_forever()
    except KeyboardInterrupt:
        logger.info(f"Bot {bot.__class__.__name__} stopped by KeyboardInterrupt")
    except Exception as e:
        logger.error(f"Bot {bot.__class__.__name__} crashed: {e}", exc_info=True)


async def run_sync_bot_async(bot, executor):
    """Wrap a sync bot's blocking run_forever() in an asyncio thread executor."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, run_sync_bot, bot)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    )

    logger.info("🏟️  Loading all arena bots...")

    # ── S1: Sharp Wallet Copy (async, hyphenated directory) ──────────────────
    s1_mod = load_module_from_path(
        "arena_bot_s1",
        os.path.join(PROJECT_ROOT, "S1-sharp-wallet-copy", "arena_bot.py")
    )
    s1_bot = s1_mod.ArenaSharpWalletBot()
    logger.info("✅ S1 Sharp Wallet Copy loaded")

    # ── S2: Cross-Market Divergence (async, hyphenated directory) ────────────
    s2_mod = load_module_from_path(
        "divergence_bot_s2",
        os.path.join(PROJECT_ROOT, "S2-cross-market", "divergence_bot.py")
    )
    s2_bot = s2_mod.CrossMarketDivergenceBot()
    logger.info("✅ S2 Cross-Market Divergence loaded")

    # ── S3: LP Withdrawal Monitor (sync, hyphenated directory) ───────────────
    s3_mod = load_module_from_path(
        "lp_bot_s3",
        os.path.join(PROJECT_ROOT, "S3-lp-monitor", "lp_bot.py")
    )
    s3_bot = s3_mod.LPWithdrawalBot()
    logger.info("✅ S3 LP Withdrawal Monitor loaded")

    # ── S4: Wikipedia Velocity (sync, hyphenated directory) ──────────────────
    s4_mod = load_module_from_path(
        "wiki_bot_s4",
        os.path.join(PROJECT_ROOT, "S4-wikipedia", "wiki_bot.py")
    )
    s4_bot = s4_mod.WikipediaVelocityBot()
    logger.info("✅ S4 Wikipedia Velocity loaded")

    # ── S5: Economic Data Positioning (async, hyphenated directory) ──────────
    s5_mod = load_module_from_path(
        "econ_bot_s5",
        os.path.join(PROJECT_ROOT, "S5-econ-data", "econ_bot.py")
    )
    s5_bot = s5_mod.EconomicDataBot()
    logger.info("✅ S5 Economic Data Positioning loaded")

    logger.info("🚀 Starting all 5 bots simultaneously...")
    logger.info("   Press Ctrl+C to stop all bots")

    # ── Resolution tracker — background thread every 30 minutes ──────────────
    tracker_thread = threading.Thread(
        target=run_resolution_tracker_loop,
        args=(1800,),
        name="resolution-tracker",
        daemon=True,
    )
    tracker_thread.start()
    logger.info("✅ Resolution tracker thread started (every 30 min)")

    # Thread pool for sync bots (S3, S4 use time.sleep internally)
    executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="sync-bot")

    try:
        await asyncio.gather(
            # Async bots run natively
            s1_bot.run_forever(),
            s2_bot.run_forever(),
            # Sync bots wrapped in thread executor
            run_sync_bot_async(s3_bot, executor),
            run_sync_bot_async(s4_bot, executor),
            # Async bot
            s5_bot.run_forever(),
        )
    except KeyboardInterrupt:
        logger.info("🛑 Arena Runner stopped by user (Ctrl+C)")
    finally:
        executor.shutdown(wait=False)
        logger.info("✅ Arena Runner shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
