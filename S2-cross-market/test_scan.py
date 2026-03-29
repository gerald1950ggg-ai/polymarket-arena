"""
One-shot test script: runs a single scan and exits.
"""
import asyncio
import logging
import sys
sys.path.insert(0, '/Users/gerald/.openclaw/workspace/projects/polymarket-arena')

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from divergence_bot import CrossMarketDivergenceBot


async def main():
    bot = CrossMarketDivergenceBot()
    logging.info("Running single scan test...")
    result = await bot.scan_once()
    print("\n=== SCAN RESULT ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
    print("===================\n")
    return result


if __name__ == "__main__":
    asyncio.run(main())
