import asyncio
import requests
from dataclasses import dataclass
from typing import List, Optional, Dict
import logging
import sys
sys.path.insert(0, '/Users/gerald/.openclaw/workspace/projects/polymarket-arena')
from arena_database import ArenaDatabase
from shadow_log import log_signal as shadow_log_signal


@dataclass
class DivergenceSignal:
    market_title: str
    polymarket_price: float
    external_price: float
    divergence_pct: float  # abs difference
    direction: str  # 'BUY' or 'SELL'
    confidence: float  # 1-10
    source: str  # 'kalshi', 'betfair', etc
    condition_id: str


class CrossMarketDivergenceBot:
    BOT_ID = "S2_divergence"
    BOT_NAME = "Cross-Market Divergence"
    STRATEGY = "Detects price differences across prediction markets and trades toward consensus"

    def __init__(self):
        self.db = ArenaDatabase()
        self.db.register_bot(self.BOT_ID, self.BOT_NAME, self.STRATEGY)

        # Bot state
        self.balance = 10000.0
        self.total_trades = 0
        self.winning_trades = 0
        self.trade_history = []

        # Kalshi public API (no auth needed for market data)
        self.kalshi_api = "https://api.elections.kalshi.com/trade-api/v2"

        # Polymarket gamma API
        self.polymarket_api = "https://gamma-api.polymarket.com"

        # Min divergence to trigger signal (10%)
        self.MIN_DIVERGENCE = 0.10
        self.MIN_CONVICTION = 6.0

    def get_polymarket_markets(self) -> List[Dict]:
        """Fetch active Polymarket markets"""
        try:
            resp = requests.get(
                f"{self.polymarket_api}/markets",
                params={
                    "limit": 50,
                    "active": "true",
                    "closed": "false"
                },
                timeout=10
            )
            if resp.status_code == 200:
                markets = resp.json()
                if isinstance(markets, list):
                    return markets[:20]
                elif isinstance(markets, dict):
                    return markets.get("markets", [])[:20]
        except Exception as e:
            logging.error(f"Polymarket fetch error: {e}")
        return []

    def get_kalshi_markets(self) -> List[Dict]:
        """Fetch active Kalshi markets with prices via events API.
        
        Kalshi's /markets endpoint returns sports parlays without prices.
        Real political/economic markets require fetching via event_ticker.
        We iterate over open events and fetch their markets.
        """
        all_markets = []
        
        # Relevant categories for cross-market matching
        relevant_categories = {"Economics", "Financials", "Politics", "Elections", "Crypto"}
        
        try:
            # Step 1: Get open events
            resp = requests.get(
                f"{self.kalshi_api}/events",
                params={"status": "open", "limit": 200},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            if resp.status_code != 200:
                logging.warning(f"Kalshi events returned status {resp.status_code}: {resp.text[:200]}")
                return []
            
            events = resp.json().get("events", [])
            relevant_events = [e for e in events if e.get("category") in relevant_categories]
            logging.info(f"Kalshi: {len(events)} events, {len(relevant_events)} relevant")
            
            # Step 2: Fetch markets for top N events (avoid rate limits)
            for event in relevant_events[:15]:
                event_ticker = event.get("event_ticker", "")
                try:
                    mresp = requests.get(
                        f"{self.kalshi_api}/markets",
                        params={"event_ticker": event_ticker, "limit": 5},
                        timeout=5
                    )
                    if mresp.status_code == 200:
                        markets = mresp.json().get("markets", [])
                        # Only keep markets with real prices
                        priced = [m for m in markets if float(m.get("yes_bid_dollars") or 0) > 0]
                        # Enrich with event title for matching
                        for m in priced:
                            m["_event_title"] = event.get("title", "")
                            m["_category"] = event.get("category", "")
                        all_markets.extend(priced)
                except Exception as e:
                    logging.debug(f"Kalshi market fetch error for {event_ticker}: {e}")
                    continue
            
            logging.info(f"Kalshi: fetched {len(all_markets)} priced markets")
        except Exception as e:
            logging.error(f"Kalshi fetch error: {e}")
        
        return all_markets[:20]

    def find_matching_markets(self, pm_markets: List[Dict], kalshi_markets: List[Dict]) -> List[tuple]:
        """Match markets across exchanges by keyword similarity"""
        matches = []

        # Keywords to look for common topics
        topics = {
            "bitcoin": ["bitcoin", "btc", "crypto"],
            "fed": ["federal reserve", "fed rate", "interest rate", "fomc"],
            "trump": ["trump", "republican", "gop"],
            "recession": ["recession", "gdp", "economy"],
            "election": ["election", "president", "senate", "congress"],
            "oil": ["oil", "crude", "energy"]
        }

        for pm in pm_markets:
            pm_q = pm.get("question", "").lower()
            for topic, keywords in topics.items():
                if any(kw in pm_q for kw in keywords):
                    for kalshi in kalshi_markets:
                        # Match against Kalshi's event title (enriched field) or market title
                        kalshi_title = (kalshi.get("_event_title", "") + " " + kalshi.get("title", "")).lower()
                        if any(kw in kalshi_title for kw in keywords):
                            matches.append((pm, kalshi, topic))
                            break

        return matches[:10]  # Return top 10 matches

    def calculate_divergence(self, pm_market: Dict, kalshi_market: Dict) -> Optional[DivergenceSignal]:
        """Calculate price divergence between markets"""
        try:
            # Polymarket price (from outcomePrices for YES) - field is a JSON string or list
            pm_prices_raw = pm_market.get("outcomePrices", pm_market.get("outcome_prices", []))
            if isinstance(pm_prices_raw, str):
                import json as _json
                try:
                    pm_prices_raw = _json.loads(pm_prices_raw)
                except Exception:
                    pm_prices_raw = []
            pm_price = float(pm_prices_raw[0]) if pm_prices_raw else None

            # Kalshi price - yes_bid_dollars is already in dollar decimal (0.0 - 1.0)
            kalshi_yes_bid = kalshi_market.get("yes_bid_dollars", None)
            if kalshi_yes_bid is None:
                kalshi_yes_bid = kalshi_market.get("last_price_dollars", None)
            kalshi_price = float(kalshi_yes_bid) if kalshi_yes_bid is not None else None

            if pm_price is None or kalshi_price is None:
                return None
            if pm_price <= 0 or pm_price >= 1 or kalshi_price <= 0 or kalshi_price >= 1:
                return None

            divergence = abs(pm_price - kalshi_price)

            if divergence < self.MIN_DIVERGENCE:
                return None

            # Trade toward the higher-priced market (buy the cheaper one)
            direction = "BUY" if pm_price < kalshi_price else "SELL"

            # Conviction scales with divergence size
            conviction = min(10.0, 5.0 + (divergence / 0.05))

            return DivergenceSignal(
                market_title=pm_market.get("question", "Unknown"),
                polymarket_price=pm_price,
                external_price=kalshi_price,
                divergence_pct=divergence,
                direction=direction,
                confidence=conviction,
                source="kalshi",
                condition_id=pm_market.get("conditionId", pm_market.get("condition_id", ""))
            )
        except Exception as e:
            logging.error(f"Divergence calc error: {e}")
            return None

    def execute_paper_trade(self, signal: DivergenceSignal):
        """Log shadow signal — no fake paper trading"""
        size = min(self.balance * 0.05, 500)  # 5% max, $500 cap
        price = signal.polymarket_price

        signal_explanation = (
            f"Cross-market divergence detected: Polymarket shows {signal.polymarket_price:.2f} "
            f"while {signal.source} shows {signal.external_price:.2f} — a {signal.divergence_pct*100:.1f}% gap. "
            f"Theory: markets should converge, so we {signal.direction} Polymarket expecting it to reprice. "
            f"Shadow position: ${size:.0f} {signal.direction} at {price:.2f}. "
            f"Confidence: {signal.confidence:.1f}/10. Edge disappears if divergence persists >24h."
        )

        signal_id = shadow_log_signal(
            bot_id=self.BOT_ID,
            bot_name="Cross-Market Divergence",
            bot_emoji="⚡",
            signal_headline=f"Divergence {signal.divergence_pct*100:.1f}% vs {signal.source}: {signal.market_title[:50]}",
            signal_explanation=signal_explanation,
            market_title=signal.market_title,
            direction=signal.direction,
            entry_price=price,
            conviction_score=signal.confidence,
            condition_id=signal.condition_id,
            shadow_size=size,
            raw_signal={
                "polymarket_price": signal.polymarket_price,
                "external_price": signal.external_price,
                "divergence_pct": signal.divergence_pct,
                "source": signal.source,
            },
            notes=f"Divergence vs {signal.source}: PM={signal.polymarket_price:.2f} vs ext={signal.external_price:.2f}"
        )

        self.total_trades += 1
        self.trade_history.append({"pnl": 0, "size": size * price})

        roi = ((self.balance - 10000) / 10000) * 100
        win_rate = self.winning_trades / max(self.total_trades, 1)
        self.db.update_bot_performance(self.BOT_ID, {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.total_trades - self.winning_trades,
            "total_roi": roi,
            "current_balance": self.balance,
            "win_rate": win_rate,
            "sharpe_ratio": roi / 10.0,
            "max_drawdown": 0.0,
            "avg_trade_size": size
        })

        logging.info(f"🕵️ Shadow signal #{signal_id} | {signal.direction} {signal.market_title[:40]}")
        return 0

    async def scan_once(self):
        """Single scan for divergence opportunities"""
        self.db.heartbeat(self.BOT_ID, "scanning", "Fetching markets")

        pm_markets = self.get_polymarket_markets()
        kalshi_markets = self.get_kalshi_markets()

        logging.info(f"Fetched {len(pm_markets)} PM markets, {len(kalshi_markets)} Kalshi markets")

        if not pm_markets:
            self.db.heartbeat(self.BOT_ID, "waiting", "No PM markets")
            return {
                "pm_markets": 0,
                "kalshi_markets": len(kalshi_markets),
                "matches": 0,
                "signals": 0,
                "trades": 0
            }

        matches = self.find_matching_markets(pm_markets, kalshi_markets)
        logging.info(f"Found {len(matches)} matched markets")

        signals = []
        for pm, kalshi, topic in matches:
            signal = self.calculate_divergence(pm, kalshi)
            if signal and signal.confidence >= self.MIN_CONVICTION:
                signals.append(signal)
                logging.info(f"  Signal [{topic}]: PM={signal.polymarket_price:.2f} vs Kalshi={signal.external_price:.2f} → {signal.direction} (conf={signal.confidence:.1f})")
                self.db.log_opportunity(self.BOT_ID, {
                    "type": "price_divergence",
                    "market_title": signal.market_title,
                    "condition_id": signal.condition_id,
                    "confidence_score": signal.confidence,
                    "expected_edge": signal.divergence_pct,
                    "time_sensitivity_minutes": 60,
                    "data_source": f"Polymarket vs {signal.source.title()}"
                })

        logging.info(f"Generated {len(signals)} signals")

        trades_executed = 0
        for signal in signals[:3]:  # Max 3 trades per scan
            self.execute_paper_trade(signal)
            trades_executed += 1

        self.db.heartbeat(self.BOT_ID, "active", f"Scanned. {len(signals)} signals found.")

        return {
            "pm_markets": len(pm_markets),
            "kalshi_markets": len(kalshi_markets),
            "matches": len(matches),
            "signals": len(signals),
            "trades": trades_executed
        }

    async def run_forever(self):
        """Main bot loop"""
        logging.info(f"🚀 {self.BOT_NAME} starting...")
        while True:
            try:
                await self.scan_once()
            except Exception as e:
                logging.error(f"Error in scan: {e}")
                self.db.heartbeat(self.BOT_ID, "error", str(e))
            await asyncio.sleep(120)  # Scan every 2 minutes


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    bot = CrossMarketDivergenceBot()
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
