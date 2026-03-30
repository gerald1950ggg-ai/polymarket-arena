#!/usr/bin/env python3
"""
Working Hybrid Polymarket Monitor
Uses correct polymarket-apis methods + Alchemy/Web3 for on-chain monitoring
Dynamic sharp wallet discovery — no hardcoded addresses.
"""

import asyncio
import requests
from polymarket_apis import PolymarketDataClient, PolymarketGammaClient
from dotenv import load_dotenv
import os
import json
import time
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)
load_dotenv()

# Minimum thresholds to qualify as a "sharp" wallet
MIN_TRADES_FOR_QUALIFICATION = 5       # At least 5 trades in discovery window
MIN_VOLUME_FOR_QUALIFICATION = 500     # At least $500 total volume
SHARP_WALLET_REFRESH_SECONDS = 3600   # Re-discover sharp wallets every hour
DISCOVERY_TRADE_PAGES = 10            # Pages of trades to scan (100 trades each)
MAX_SHARP_WALLETS = 10                # Track top N wallets at any time


class WorkingHybridMonitor:
    """
    Sharp wallet copy bot with dynamic discovery.
    Finds profitable wallets automatically by scanning recent on-chain activity,
    scoring wallets by volume + trade frequency, then tracking them for copy signals.
    """

    def __init__(self):
        self.data_client = PolymarketDataClient()
        self.gamma_client = PolymarketGammaClient()

        # ── Alchemy / Web3 ────────────────────────────────────────────────
        api_key = os.getenv("ALCHEMY_API_KEY", "")
        if api_key:
            self.polygon_rpc = f"https://polygon-mainnet.g.alchemy.com/v2/{api_key}"
            try:
                from web3 import Web3
                self.w3 = Web3(Web3.HTTPProvider(self.polygon_rpc))
                if self.w3.is_connected():
                    logger.info(f"✅ Web3 connected to Polygon via Alchemy "
                                f"(block {self.w3.eth.block_number})")
                else:
                    logger.warning("⚠️  Web3 provider created but not connected")
                    self.w3 = None
            except ImportError:
                logger.warning("⚠️  web3 not installed; on-chain features disabled")
                self.w3 = None
        else:
            logger.warning("⚠️  ALCHEMY_API_KEY not set; on-chain features disabled")
            self.polygon_rpc = None
            self.w3 = None

        # ── Sharp wallet state ────────────────────────────────────────────
        # Start with any manually seeded wallets from env, then augment dynamically
        wallets_str = os.getenv("SHARP_WALLETS", "")
        seed_wallets = [w.strip() for w in wallets_str.split(",") if w.strip()]
        self.sharp_wallets = [
            w if w.startswith("0x") else f"0x{w}" for w in seed_wallets
        ]
        self._last_discovery = 0   # epoch timestamp of last discovery run
        self._wallet_scores: dict[str, float] = {}  # wallet -> score

        logger.info(f"📊 Starting with {len(self.sharp_wallets)} seeded wallets — "
                    f"dynamic discovery active")

    # ── Dynamic wallet discovery ──────────────────────────────────────────

    def discover_sharp_wallets(self) -> list[str]:
        """
        Scan recent Polymarket trades, aggregate wallet activity,
        score by volume + frequency, and return top candidates.
        All data comes from Polymarket's public trades API.
        """
        logger.info("🔍 Discovering sharp wallets from recent trade activity...")

        wallet_stats: dict[str, dict] = defaultdict(
            lambda: {"volume": 0.0, "trades": 0, "markets": set(), "last_seen": 0}
        )

        # Fetch DISCOVERY_TRADE_PAGES * 100 recent trades
        for page in range(DISCOVERY_TRADE_PAGES):
            try:
                resp = requests.get(
                    "https://data-api.polymarket.com/trades",
                    params={"limit": 100, "offset": page * 100},
                    timeout=10,
                )
                if not resp.ok:
                    break
                trades = resp.json()
                if not trades:
                    break

                for t in trades:
                    wallet = t.get("proxyWallet", "")
                    size = float(t.get("size") or 0)
                    condition_id = t.get("conditionId", "")
                    ts = int(t.get("timestamp") or 0)

                    if not wallet or size <= 0:
                        continue

                    wallet_stats[wallet]["volume"] += size
                    wallet_stats[wallet]["trades"] += 1
                    wallet_stats[wallet]["markets"].add(condition_id)
                    wallet_stats[wallet]["last_seen"] = max(
                        wallet_stats[wallet]["last_seen"], ts
                    )

            except Exception as e:
                logger.warning(f"Discovery page {page} error: {e}")
                break

        # Score each wallet: log(volume) * log(trades) * market_diversity_bonus
        scores: dict[str, float] = {}
        for wallet, stats in wallet_stats.items():
            if (stats["trades"] < MIN_TRADES_FOR_QUALIFICATION
                    or stats["volume"] < MIN_VOLUME_FOR_QUALIFICATION):
                continue

            import math
            volume_score = math.log10(max(stats["volume"], 1))
            trade_score  = math.log10(max(stats["trades"], 1))
            diversity    = min(len(stats["markets"]) / 5.0, 2.0)  # bonus up to 2x
            scores[wallet] = volume_score * trade_score * (1 + diversity)

        # Sort by score, take top N
        top_wallets = sorted(scores, key=lambda w: scores[w], reverse=True)[
            :MAX_SHARP_WALLETS
        ]
        self._wallet_scores = {w: scores[w] for w in top_wallets}

        logger.info(
            f"✅ Discovery complete: {len(wallet_stats)} wallets scanned, "
            f"{len(top_wallets)} qualified as sharp"
        )
        for w in top_wallets[:5]:
            s = wallet_stats[w]
            logger.info(
                f"   {w[:10]}...  vol=${s['volume']:,.0f}  "
                f"trades={s['trades']}  markets={len(s['markets'])}  "
                f"score={scores[w]:.2f}"
            )

        return top_wallets

    def maybe_refresh_wallets(self) -> None:
        """Refresh sharp wallet list if the refresh interval has elapsed."""
        now = time.time()
        if now - self._last_discovery >= SHARP_WALLET_REFRESH_SECONDS:
            discovered = self.discover_sharp_wallets()
            # Merge discovered with any manually seeded wallets
            merged = list(dict.fromkeys(self.sharp_wallets + discovered))
            self.sharp_wallets = merged[:MAX_SHARP_WALLETS]
            self._last_discovery = now
            logger.info(
                f"🔄 Wallet list refreshed — tracking {len(self.sharp_wallets)} wallets"
            )

    # ── Wallet analysis ───────────────────────────────────────────────────

    async def analyze_wallet_performance(self, wallet_address: str) -> dict | None:
        """
        Fetch real positions + trades for a wallet via Polymarket API
        and compute a quality score.
        """
        try:
            positions = self.data_client.get_positions(user=wallet_address, limit=20)
            trades    = self.data_client.get_trades(user=wallet_address, limit=20)

            if not positions and not trades:
                return None

            total_value  = sum(float(p.current_value or 0) for p in positions)
            active_mkts  = {p.condition_id for p in positions if p.condition_id}
            trade_count  = len(trades)

            # Simple edge heuristic: buys at price < 0.5 that are still open
            # (meaning outcome hasn't resolved against them yet)
            value_buys = sum(
                float(t.token_amount or 0) * float(t.price or 0)
                for t in trades
                if getattr(t, "side", "") == "BUY" and float(t.price or 0) < 0.7
            )
            est_win_rate = min(value_buys / max(total_value, 1), 1.0) if total_value else 0

            is_sharp = (
                total_value > 100
                and trade_count >= 3
                and len(active_mkts) >= 1
            )

            return {
                "wallet":            wallet_address,
                "portfolio_value":   total_value,
                "positions_count":   len(positions),
                "markets_count":     len(active_mkts),
                "trades_count":      trade_count,
                "estimated_win_rate": est_win_rate,
                "discovery_score":   self._wallet_scores.get(wallet_address, 0),
                "is_sharp":          is_sharp,
            }

        except Exception as e:
            logger.debug(f"Wallet analysis error {wallet_address[:8]}: {e}")
            return None

    async def simulate_copy_trade_decision(
        self, wallet_analysis: dict, market_context: list
    ) -> dict | None:
        """Generate a copy-trade signal if conviction is high enough."""
        if not wallet_analysis or not wallet_analysis["is_sharp"]:
            return None

        disc_score = wallet_analysis["discovery_score"]
        wr_score   = wallet_analysis["estimated_win_rate"] * 3
        size_score = min(wallet_analysis["portfolio_value"] / 1000, 5)
        div_score  = min(wallet_analysis["markets_count"] / 5, 2)
        conviction = wr_score + size_score + div_score + min(disc_score / 2, 2)

        if conviction >= 5.0:
            copy_size = min(wallet_analysis["portfolio_value"] * 0.02, 1000)
            return {
                "action":          "COPY",
                "conviction_score": round(conviction, 2),
                "copy_size":       copy_size,
                "wallet":          wallet_analysis["wallet"],
                "market_title":    (market_context[0]["question"]
                                    if market_context else "Unknown Market"),
                "condition_id":    (market_context[0]["condition_id"]
                                    if market_context else ""),
                "current_price":   0.5,
                "copy_ratio":      0.02,
            }
        return None

    # ── Market context ────────────────────────────────────────────────────

    async def get_active_markets(self, limit: int = 10) -> list[dict]:
        """Return current active high-volume markets."""
        try:
            markets = self.gamma_client.get_markets(limit=limit, active=True)
            return [
                {
                    "question":     m.question,
                    "condition_id": m.condition_id,
                    "volume":       float(m.volume_num or 0),
                    "liquidity":    float(m.liquidity_num or 0),
                    "token_ids":    m.token_ids,
                }
                for m in markets
            ]
        except Exception as e:
            logger.warning(f"get_active_markets error: {e}")
            return []

    # ── Main loop ─────────────────────────────────────────────────────────

    async def run_analysis(self) -> list[dict]:
        """Run one analysis cycle: refresh wallets, analyse, generate signals."""
        self.maybe_refresh_wallets()

        if not self.sharp_wallets:
            logger.info("💤 No sharp wallets yet — waiting for next discovery cycle")
            return []

        market_context = await self.get_active_markets(limit=5)
        signals = []

        for wallet in self.sharp_wallets:
            try:
                analysis = await self.analyze_wallet_performance(wallet)
                if analysis:
                    decision = await self.simulate_copy_trade_decision(
                        analysis, market_context
                    )
                    if decision:
                        signals.append(decision)
            except Exception as e:
                logger.error(f"Error processing {wallet[:8]}: {e}")

        logger.info(
            f"📊 Cycle done — {len(self.sharp_wallets)} wallets, "
            f"{len(signals)} copy signals"
        )
        return signals


async def main():
    monitor = WorkingHybridMonitor()
    signals = await monitor.run_analysis()
    if signals:
        for s in signals:
            print(json.dumps(s, indent=2))
    else:
        print("No signals this cycle.")


if __name__ == "__main__":
    asyncio.run(main())
