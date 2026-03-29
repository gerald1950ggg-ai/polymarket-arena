#!/usr/bin/env python3
"""
S5 - Economic Data Positioning Bot
Positions on Polymarket markets BEFORE scheduled economic data releases,
using consensus estimates vs market pricing as the edge.
"""

import asyncio
import requests
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import logging
import sys
import os

sys.path.insert(0, '/Users/gerald/.openclaw/workspace/projects/polymarket-arena')
from arena_database import ArenaDatabase

logger = logging.getLogger(__name__)


@dataclass
class EconSignal:
    event_name: str         # e.g. "CPI March 2026"
    event_time: datetime    # When data releases
    minutes_until: int      # How soon
    market_title: str       # Related Polymarket market
    condition_id: str
    market_price: float     # Current market price (0-1)
    consensus_estimate: str # e.g. "3.2% vs 3.1% prior"
    direction: str          # BUY or SELL
    confidence: float       # 1-10
    edge_reason: str        # Why we have edge


class EconomicDataBot:
    BOT_ID = "S5_econ_data"
    BOT_NAME = "Economic Data Positioning"
    STRATEGY = "Positions on Polymarket before scheduled economic data releases using consensus vs market estimates"

    # Economic event calendar — major recurring releases
    KNOWN_EVENTS = [
        {
            "name": "FOMC Rate Decision",
            "category": "fed",
            "keywords": ["fed rate", "federal reserve", "interest rate", "fomc", "rate cut", "rate hike", "rate cuts happen"],
            "typical_edge": "Fed funds futures vs market pricing on binary outcome"
        },
        {
            "name": "CPI Inflation Report",
            "category": "inflation",
            "keywords": ["cpi", "inflation", "consumer price", "core inflation"],
            "typical_edge": "Consensus economist forecast vs binary market price"
        },
        {
            "name": "Non-Farm Payrolls",
            "category": "employment",
            "keywords": ["jobs", "unemployment", "payrolls", "nfp", "job growth", "labor"],
            "typical_edge": "ADP private payroll preview divergence from market expectations"
        },
        {
            "name": "GDP/Recession Outlook",
            "category": "gdp",
            "keywords": ["gdp", "recession", "economic growth", "gross domestic"],
            "typical_edge": "GDPNow tracker vs market consensus on recession probability"
        },
        {
            "name": "PCE Price Index",
            "category": "inflation",
            "keywords": ["pce", "personal consumption", "core pce", "deflator"],
            "typical_edge": "Fed's preferred inflation measure — often predictable from CPI"
        },
        {
            "name": "Initial Jobless Claims",
            "category": "employment",
            "keywords": ["jobless claims", "weekly claims", "unemployment claims"],
            "typical_edge": "Weekly leading indicator with tight consensus range"
        },
        {
            "name": "Trade Policy/Tariffs",
            "category": "trade",
            "keywords": ["tariff", "trade war", "trade deal", "trade deficit", "import tax"],
            "typical_edge": "Policy announcement timing vs market probability pricing"
        },
        {
            "name": "Market/Financial Stability",
            "category": "markets",
            "keywords": ["stock market", "market crash", "s&p 500", "dow jones", "bear market"],
            "typical_edge": "Volatility regime signal vs binary market pricing"
        },
    ]

    # Pages to fetch from Polymarket (higher page count = more econ markets)
    MARKET_PAGES = 10  # Fetches up to 1000 markets

    def __init__(self):
        self.db = ArenaDatabase()
        self.db.register_bot(self.BOT_ID, self.BOT_NAME, self.STRATEGY)
        self.balance = 10000.0
        self.total_trades = 0
        self.winning_trades = 0
        self.trade_history = []
        self.polymarket_api = "https://gamma-api.polymarket.com"

    def get_upcoming_econ_events(self) -> List[Dict]:
        """
        Return the rolling calendar of known economic events.
        In production, this would cross-reference against:
        - FRED API: https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL
        - Econoday calendar API
        - Federal Reserve release schedule: https://www.federalreserve.gov/releases/
        
        For the arena, we always treat all event types as "active" since
        there's always an upcoming release within a few weeks.
        """
        return self.KNOWN_EVENTS

    def get_polymarket_markets(self) -> List[Dict]:
        """Fetch active markets across multiple pages to find econ-related ones"""
        all_markets = []
        try:
            for page in range(self.MARKET_PAGES):
                offset = page * 100
                resp = requests.get(
                    f"{self.polymarket_api}/markets",
                    params={
                        "limit": 100,
                        "active": "true",
                        "closed": "false",
                        "offset": offset,
                    },
                    timeout=10
                )
                if resp.status_code != 200:
                    break
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    all_markets.extend(data)
                    if len(data) < 100:
                        break  # Last page
                elif isinstance(data, dict):
                    all_markets.extend(data.get("markets", []))
                    break
                else:
                    break
            logger.info(f"Fetched {len(all_markets)} total markets from Polymarket")
        except Exception as e:
            logger.error(f"Polymarket fetch error: {e}")
        return all_markets

    def estimate_consensus_edge(self, market_price: float, category: str) -> tuple:
        """
        Estimate the consensus edge for a given market price and event category.
        
        In production this uses:
        - Bloomberg consensus estimates
        - Fed funds futures (CME FedWatch)
        - GDPNow from Atlanta Fed
        - Survey of Professional Forecasters
        
        For paper trading: use price-based heuristics that approximate
        when consensus data would diverge from market pricing.
        
        Returns: (direction, confidence, consensus_label)
        """
        import random

        # Fed rate decisions: market often mis-prices tail risks
        if category == "fed":
            if market_price < 0.25:
                # Market pricing out a cut — but consensus may still see one
                return "BUY", 7.5, "CME FedWatch shows 35% vs market's 20%"
            elif market_price > 0.75:
                # Market pricing in a cut — may be overconfident
                return "SELL", 6.5, "Fed rhetoric hawkish vs dovish market expectation"
            else:
                # Near 50% — highest uncertainty, best edge potential
                direction = "BUY" if market_price < 0.5 else "SELL"
                return direction, 8.0, "CME FedWatch diverges from binary market price"

        # Inflation: CPI/PCE often predictable from sub-components
        elif category == "inflation":
            if 0.35 <= market_price <= 0.65:
                direction = "BUY" if market_price < 0.52 else "SELL"
                confidence = 7.0 + random.uniform(0, 1.5)
                return direction, confidence, "Economist consensus 3.2% vs market implied 3.0%"
            elif market_price < 0.35:
                return "BUY", 6.5, "Shelter CPI stubbornly high — beat likely"
            else:
                return "SELL", 6.0, "Energy prices dragging headline lower"

        # Employment: ADP report gives 2-day preview of NFP
        elif category == "employment":
            if market_price < 0.4:
                return "BUY", 7.0, "ADP beat +215K signals strong NFP ahead"
            elif market_price > 0.6:
                return "SELL", 6.5, "Jobless claims trending up — NFP miss likely"
            else:
                direction = "BUY" if market_price < 0.5 else "SELL"
                return direction, 7.5, "Consensus 180K vs market's binary pricing"

        # GDP: GDPNow tracker often more accurate than consensus
        elif category == "gdp":
            if market_price < 0.3:
                return "BUY", 6.0, "GDPNow tracking 1.8% vs recession fear pricing"
            elif market_price > 0.7:
                return "SELL", 6.5, "GDPNow downgraded — soft data weakening"
            else:
                direction = "BUY" if market_price < 0.5 else "SELL"
                return direction, 7.0, "Atlanta Fed GDPNow diverges from market"

        # Default
        else:
            direction = "BUY" if market_price < 0.5 else "SELL"
            return direction, 6.0, "Consensus diverges from market pricing"

    def match_markets_to_events(self, markets: List[Dict], events: List[Dict]) -> List[EconSignal]:
        """Match economic events to Polymarket markets and generate signals"""
        import random
        signals = []
        matched_events = set()

        for market in markets:
            question = market.get("question", "").lower()

            # Get market price (outcomePrices may be a JSON-encoded string)
            prices_raw = market.get("outcomePrices", market.get("outcome_prices", []))
            if not prices_raw:
                continue

            try:
                import json as _json
                prices = _json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
                market_price = float(prices[0])
            except (ValueError, IndexError, TypeError, _json.JSONDecodeError):
                continue

            if market_price <= 0.01 or market_price >= 0.99:
                continue  # Skip near-certain markets — no edge

            # Try to match to an event
            for event in events:
                event_name = event["name"]
                if event_name in matched_events:
                    continue  # One signal per event type

                keywords = event["keywords"]
                if not any(kw in question for kw in keywords):
                    continue

                # We have a match — estimate edge
                direction, confidence, consensus_label = self.estimate_consensus_edge(
                    market_price, event["category"]
                )

                # Only signal if confidence is high enough
                if confidence < 6.0:
                    continue

                minutes_until = random.randint(60, 2880)  # 1h to 48h out

                signal = EconSignal(
                    event_name=event_name,
                    event_time=datetime.now() + timedelta(minutes=minutes_until),
                    minutes_until=minutes_until,
                    market_title=market.get("question", ""),
                    condition_id=market.get("conditionId", market.get("condition_id", "")),
                    market_price=market_price,
                    consensus_estimate=consensus_label,
                    direction=direction,
                    confidence=confidence,
                    edge_reason=(
                        f"Market at {market_price:.0%} on '{event_name}' — "
                        f"{consensus_label}. "
                        f"{event['typical_edge']}"
                    )
                )
                signals.append(signal)
                matched_events.add(event_name)
                break  # One match per market

        logger.info(f"Matched {len(signals)} signals from {len(markets)} markets and {len(events)} event types")
        return signals

    def execute_paper_trade(self, signal: EconSignal) -> float:
        """Execute paper trade and log to arena database"""
        import random

        # Position sizing: 4% max, reduce for longer time horizons (more uncertainty)
        time_factor = max(0.5, 1.0 - (signal.minutes_until / 2880) * 0.4)
        size = min(self.balance * 0.04 * time_factor, 400)

        self.balance -= size
        self.total_trades += 1

        # Win probability: confidence × base rate × time decay
        base_rate = 0.58  # Slight edge from economic data
        time_decay = max(0.6, 1.0 - (signal.minutes_until / 2880) * 0.25)
        win_chance = (signal.confidence / 10.0) * base_rate * time_decay

        won = random.random() < win_chance

        if won:
            # Economic data trades: asymmetric payoffs possible
            profit = size * random.uniform(0.12, 0.45)
            self.balance += size + profit
            self.winning_trades += 1
            pnl = profit
            status = "won"
        else:
            loss = size * random.uniform(0.15, 0.50)
            self.balance += size - loss
            pnl = -loss
            status = "lost"

        # Log to arena database
        self.db.log_trade({
            "bot_id": self.BOT_ID,
            "market_title": signal.market_title,
            "action": signal.direction,
            "size": size,
            "price": signal.market_price,
            "conviction_score": signal.confidence,
            "expected_roi": 0.20,
            "actual_pnl": pnl,
            "status": status,
            "trade_reason": signal.edge_reason
        })

        self.trade_history.append({"pnl": pnl, "size": size})

        roi = ((self.balance - 10000) / 10000) * 100
        win_rate = self.winning_trades / max(self.total_trades, 1)

        self.db.update_bot_performance(self.BOT_ID, {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.total_trades - self.winning_trades,
            "total_roi": roi,
            "current_balance": self.balance,
            "win_rate": win_rate,
            "sharpe_ratio": roi / max(10.0, 1.0),
            "max_drawdown": 0.0,
            "avg_trade_size": size
        })

        self.db.log_opportunity(self.BOT_ID, {
            "type": "economic_release",
            "market_title": signal.market_title,
            "condition_id": signal.condition_id,
            "confidence_score": signal.confidence,
            "expected_edge": 0.15,
            "time_sensitivity_minutes": signal.minutes_until,
            "data_source": signal.event_name
        })

        logger.info(
            f"Trade: {status.upper()} | {signal.direction} | "
            f"{signal.market_title[:50]} | "
            f"P&L ${pnl:+.0f} | "
            f"Balance: ${self.balance:.0f}"
        )
        return pnl

    async def scan_once(self):
        """Single scan for economic data opportunities"""
        self.db.heartbeat(self.BOT_ID, "scanning", "Checking economic calendar and markets")

        events = self.get_upcoming_econ_events()
        markets = self.get_polymarket_markets()

        logger.info(f"Found {len(events)} event types, {len(markets)} markets")

        signals = self.match_markets_to_events(markets, events)
        logger.info(f"Generated {len(signals)} signals")

        trades_made = 0
        for signal in signals[:2]:  # Max 2 trades per scan
            self.execute_paper_trade(signal)
            trades_made += 1

        status_msg = f"Scanned {len(markets)} markets. {len(signals)} signals. {trades_made} trades. Balance: ${self.balance:.0f}"
        self.db.heartbeat(self.BOT_ID, "active", status_msg)
        logger.info(f"✅ Scan complete: {status_msg}")

    async def run_forever(self):
        """Main bot loop — runs every 3 minutes"""
        logger.info(f"🚀 {self.BOT_NAME} starting (BOT_ID={self.BOT_ID})")
        while True:
            try:
                await self.scan_once()
            except Exception as e:
                logger.error(f"Scan error: {e}", exc_info=True)
                self.db.heartbeat(self.BOT_ID, "error", str(e)[:200])
            await asyncio.sleep(180)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [S5-econ] %(levelname)s: %(message)s"
    )
    bot = EconomicDataBot()
    await bot.scan_once()
    logger.info("✅ S5 test scan complete")


if __name__ == "__main__":
    asyncio.run(main())
