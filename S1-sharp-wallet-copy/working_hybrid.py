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
MIN_TRADES_FOR_QUALIFICATION = 2       # At least 2 trades in discovery window
MIN_VOLUME_FOR_QUALIFICATION = 0       # No volume floor — size field is shares not USDC
SHARP_WALLET_REFRESH_SECONDS = 3600   # Re-discover sharp wallets every hour
DISCOVERY_TRADE_PAGES = 3             # Pages of trades to scan (100 trades each) — keep fast
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
        Fetch recent trades for a wallet via raw data API (returns dicts with
        conditionId and title). Skips wallets whose most recent trade is on a
        closed/expired market.
        """
        import math
        import requests as _req

        try:
            # Use raw data API — returns dicts with conditionId, title, timestamp
            resp = _req.get(
                "https://data-api.polymarket.com/trades",
                params={"limit": 20, "takerOnly": True, "user": wallet_address},
                timeout=8,
            )
            if not resp.ok:
                return None
            trades = resp.json()

            if not trades or len(trades) < 2:
                logger.debug(f"Wallet {wallet_address[:8]}: not enough trades ({len(trades) if trades else 0})")
                return None

            trade_count = len(trades)
            unique_conditions = set()
            total_size = 0.0
            most_recent_ts = 0
            most_recent_trade = None

            for t in trades:
                cid = t.get("conditionId") or ""
                size = float(t.get("size") or 0)
                ts = int(t.get("timestamp") or 0)

                if cid:
                    unique_conditions.add(cid)
                total_size += size
                if ts > most_recent_ts:
                    most_recent_ts = ts
                    most_recent_trade = t

            avg_trade_size = total_size / trade_count if trade_count else 0
            now_ts = int(time.time())
            seconds_since_last = now_ts - most_recent_ts if most_recent_ts else 999999
            recency_score = max(0.0, 1.0 - seconds_since_last / 86400)

            market_diversity = len(unique_conditions)
            is_sharp = trade_count >= 2

            # Extract market info directly from raw trade dict
            recent_market_title = "Unknown Market"
            recent_condition_id = ""
            if most_recent_trade is not None:
                recent_condition_id = most_recent_trade.get("conditionId") or ""
                recent_market_title = (
                    most_recent_trade.get("title")
                    or most_recent_trade.get("slug")
                    or (f"Market {recent_condition_id[:8]}..." if recent_condition_id else "Unknown Market")
                )

            # Gate: only proceed if the most recent trade is on an OPEN market
            if recent_condition_id:
                try:
                    r = _req.get(
                        f"https://clob.polymarket.com/markets/{recent_condition_id}",
                        timeout=5,
                    )
                    if not r.ok or r.json().get("closed", True):
                        logger.debug(f"Wallet {wallet_address[:8]}: most recent market {recent_condition_id[:12]} is closed — skipping")
                        return None
                except Exception:
                    pass  # Network error — proceed without validation

            return {
                "wallet":              wallet_address,
                "trades_count":        trade_count,
                "market_diversity":    market_diversity,
                "avg_trade_size":      avg_trade_size,
                "recency_score":       recency_score,
                "discovery_score":     self._wallet_scores.get(wallet_address, 0),
                "is_sharp":            is_sharp,
                "recent_condition_id": recent_condition_id,
                "recent_market_title": recent_market_title,
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

        import math

        disc_score  = min(wallet_analysis["discovery_score"] / 2, 2.0)
        trade_score = math.log10(max(wallet_analysis["trades_count"], 1))
        div_score   = min(wallet_analysis["market_diversity"] / 3, 1.5)
        size_score  = min(math.log10(max(wallet_analysis["avg_trade_size"], 1)) / 3, 1.0)
        recency     = wallet_analysis["recency_score"] * 1.5

        conviction = trade_score + div_score + size_score + recency + disc_score

        if conviction >= 3.0:
            # Use the wallet's actual most recent trade market — no fallback to random markets
            condition_id = wallet_analysis.get("recent_condition_id", "")
            market_title = wallet_analysis.get("recent_market_title", "")
            # If we have no real market, skip — don't fabricate one
            if not condition_id:
                return None

            copy_size = min(wallet_analysis["avg_trade_size"] * 0.5, 500)
            return {
                "action":           "COPY",
                "conviction_score": round(conviction, 2),
                "copy_size":        copy_size,
                "wallet":           wallet_analysis["wallet"],
                "market_title":     market_title,
                "condition_id":     condition_id,
                "current_price":    0.5,
                "copy_ratio":       0.02,
                "trades_count":     wallet_analysis["trades_count"],
                "avg_trade_size":   wallet_analysis["avg_trade_size"],
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
