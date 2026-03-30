#!/usr/bin/env python3
"""
S4 — Wikipedia Edit Velocity Bot (Dual-Mode)

Approach A — Proactive: Maintains a watched list of Wikipedia pages seeded
dynamically from the top active Polymarket markets. If any watched page
appears in Wikipedia recent changes with edit velocity >= threshold → signal.
Watched list refreshes every 30 minutes to stay current.

Approach B — Reactive: For every other changed page NOT on the watched list,
attempt keyword-overlap match to any active Polymarket market. Catches
surprises we didn't anticipate.

Both run in the same scan_once() loop with deduplication (one signal per
page/market pair per scan) and source tagging ("proactive" vs "reactive").
"""

import sys
import re
import math
import time
import logging
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict, Counter

sys.path.append(str(Path(__file__).parent.parent))
from arena_database import ArenaDatabase
from shadow_log import log_signal as shadow_log_signal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

BOT_ID   = "S4_wikipedia"
BOT_NAME = "Wikipedia Velocity"
STRATEGY_DESCRIPTION = (
    "Dual-mode Wikipedia edit-velocity bot. "
    "Proactive: watches Wikipedia pages seeded from top Polymarket markets. "
    "Reactive: scans all recent Wikipedia changes for surprise market matches. "
    "Edit velocity spikes = breaking news forming = trade before repricing."
)

WIKIPEDIA_RECENT_CHANGES_URL = (
    "https://en.wikipedia.org/w/api.php"
    "?action=query&list=recentchanges"
    "&rcprop=title|timestamp|comment"
    "&rcnamespace=0"
    "&rclimit=100"
    "&format=json"
)

WIKIPEDIA_PAGE_INFO_URL = (
    "https://en.wikipedia.org/w/api.php"
    "?action=query&prop=revisions"
    "&titles={title}"
    "&rvlimit=10"
    "&rvprop=timestamp|comment"
    "&format=json"
)

POLYMARKET_GAMMA_URL = "https://gamma-api.polymarket.com/markets"

# Thresholds
HIGH_SIGNAL_EDITS   = 3   # >= 3 edits in window → HIGH
MEDIUM_SIGNAL_EDITS = 2   # >= 2 edits in window → MEDIUM (minimum to fire)
SIGNAL_WINDOW_MINUTES = 5

SCAN_INTERVAL_SECONDS   = 60
MARKET_REFRESH_SECONDS  = 600   # Full market cache: 10 min
WATCHED_REFRESH_SECONDS = 1800  # Watched list rebuild: 30 min
MARKET_MIN_VOLUME       = 1_000.0
PROACTIVE_TOP_N_MARKETS = 30    # Seed watched list from top N by volume

STARTING_BALANCE  = 10_000.0
POSITION_SIZE_PCT = 0.04
MAX_POSITION_USD  = 400.0

# Stopwords for keyword matching
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "will", "would", "could", "should", "may", "might", "can", "do", "does",
    "did", "has", "have", "had", "not", "no", "nor", "so", "yet", "both",
    "this", "that", "these", "those", "it", "its", "than", "then", "when",
    "how", "who", "what", "which", "where", "why", "all", "any", "each",
    "if", "as", "up", "out", "about", "into", "over", "after", "before",
    "during", "through", "between", "among", "new", "old", "his", "her",
    "their", "our", "your", "my", "more", "most", "also", "just", "first",
    "2024", "2025", "2026", "2027", "hit", "win", "lose", "reach", "pass",
    "get", "take", "make", "say", "go", "come", "know", "see", "give",
    "think", "become", "show", "hear", "play", "run", "move", "live",
    "believe", "hold", "bring", "happen", "write", "provide", "sit", "stand",
    "lose", "pay", "meet", "include", "continue", "set", "learn", "change",
    "lead", "understand", "watch", "follow", "stop", "create", "speak", "read",
    "spend", "grow", "open", "walk", "offer", "remember", "love", "consider",
    "appear", "buy", "wait", "serve", "die", "send", "expect", "build",
    "stay", "fall", "cut", "reach", "kill", "remain", "suggest", "raise",
    "pass", "sell", "require", "report", "decide", "pull", "break",
}

# Known abbreviation → Wikipedia page title mappings used when seeding watched list
ABBREV_EXPANSIONS: Dict[str, str] = {
    "fed": "Federal Reserve",
    "feds": "Federal Reserve",
    "fomc": "Federal Open Market Committee",
    "btc": "Bitcoin",
    "eth": "Ethereum",
    "sec": "U.S. Securities and Exchange Commission",
    "cia": "Central Intelligence Agency",
    "fbi": "Federal Bureau of Investigation",
    "gop": "Republican Party (United States)",
    "nato": "NATO",
    "imf": "International Monetary Fund",
    "gdp": "Gross domestic product",
    "cpi": "Consumer price index",
    "ai": "Artificial intelligence",
    "ukraine": "Ukraine",
    "russia": "Russia",
    "china": "China",
    "iran": "Iran",
    "israel": "Israel",
    "taiwan": "Taiwan",
    "trump": "Donald Trump",
    "biden": "Joe Biden",
    "harris": "Kamala Harris",
    "musk": "Elon Musk",
    "powell": "Jerome Powell",
}


# ── Bot class ────────────────────────────────────────────────────────────────

class WikipediaVelocityBot:
    """Arena-integrated Wikipedia Edit Velocity bot — dual proactive+reactive mode."""

    def __init__(self, db_path: str = None):
        self.bot_id   = BOT_ID
        self.bot_name = BOT_NAME

        if db_path is None:
            project_root = Path(__file__).parent.parent
            db_path = str(project_root / "arena.db")

        self.arena_db = ArenaDatabase(db_path)

        # Paper-trading state
        self.starting_balance = STARTING_BALANCE
        self.current_balance  = STARTING_BALANCE
        self.total_trades     = 0
        self.winning_trades   = 0
        self.losing_trades    = 0
        self.trade_history: List[Dict] = []

        # ── Polymarket market cache (used by Approach B) ──────────────────
        self._markets: List[Dict] = []
        self._markets_last_fetched: Optional[datetime] = None

        # ── Approach A: proactive watched list ────────────────────────────
        # Maps Wikipedia page title → best-matching market dict
        self._watched_pages: Dict[str, Dict] = {}
        self._watched_last_built: Optional[datetime] = None

        self.arena_db.register_bot(
            self.bot_id, self.bot_name, STRATEGY_DESCRIPTION, self.starting_balance
        )
        logger.info(
            f"🤖 {self.bot_name} initialised (dual-mode: proactive + reactive) | "
            f"balance=${self.starting_balance:,.0f}"
        )

    # ── Keyword / entity helpers ──────────────────────────────────────────────

    @staticmethod
    def _parse_wiki_ts(ts_str: str) -> Optional[datetime]:
        try:
            return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _extract_keywords(text: str) -> Set[str]:
        """Generic keyword extraction — 3+ char alpha tokens, not stopwords."""
        words: Set[str] = set()
        for word in text.replace("'s", "").replace("-", " ").split():
            clean = "".join(c for c in word if c.isalpha()).lower()
            if len(clean) >= 3 and clean not in STOPWORDS:
                words.add(clean)
        return words

    @classmethod
    def _extract_entities_from_question(cls, question: str) -> List[str]:
        """
        Extract candidate Wikipedia page titles from a Polymarket question.

        Strategy:
        1. Pull consecutive Title-Cased / ALL-CAPS word sequences (proper nouns).
        2. Expand known abbreviations.
        3. Return de-duped candidate strings suitable as Wikipedia page titles.
        """
        candidates: List[str] = []

        # 1. Consecutive capitalised words (2–4 word phrases + single caps words)
        # Match sequences of Title Case words (e.g. "Federal Reserve", "Donald Trump")
        cap_phrases = re.findall(
            r'\b(?:[A-Z][a-z]{1,}(?:\s+[A-Z][a-z]{1,}){0,3})\b', question
        )
        for phrase in cap_phrases:
            phrase = phrase.strip()
            if len(phrase) >= 4 and phrase.lower() not in STOPWORDS:
                candidates.append(phrase)

        # 2. ALL-CAPS tokens (acronyms like BTC, ETH, Fed, NATO)
        acronyms = re.findall(r'\b[A-Z]{2,5}\b', question)
        for acr in acronyms:
            expansion = ABBREV_EXPANSIONS.get(acr.lower())
            if expansion:
                candidates.append(expansion)

        # 3. Lowercase known abbreviations in question
        q_lower = question.lower()
        for abbrev, expansion in ABBREV_EXPANSIONS.items():
            # word-boundary check
            if re.search(r'\b' + re.escape(abbrev) + r'\b', q_lower):
                candidates.append(expansion)

        # De-dup while preserving insertion order
        seen: Set[str] = set()
        result: List[str] = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                result.append(c)
        return result

    WIKI_HEADERS = {
        "User-Agent": (
            "PolymarketArena/1.0 (prediction-market-research-bot; python-requests)"
        )
    }

    # ── Polymarket fetching ────────────────────────────────────────────────────

    def _fetch_raw_markets(self) -> List[Dict]:
        """Fetch active markets from Polymarket gamma API. Returns raw list."""
        try:
            resp = requests.get(
                POLYMARKET_GAMMA_URL,
                params={"active": "true", "limit": 100},
                timeout=20,
                headers=self.WIKI_HEADERS,
            )
            resp.raise_for_status()
            raw = resp.json()
            if isinstance(raw, list):
                return raw
            elif isinstance(raw, dict):
                return raw.get("markets", raw.get("data", []))
        except Exception as exc:
            logger.error(f"❌ Failed to fetch Polymarket markets: {exc}")
        return []

    def _refresh_markets_if_needed(self):
        """Refresh the full market cache (Approach B keyword index) every 10 min."""
        now = datetime.now(tz=timezone.utc)
        if (
            self._markets_last_fetched is not None
            and (now - self._markets_last_fetched).total_seconds() < MARKET_REFRESH_SECONDS
            and self._markets
        ):
            return

        logger.info("🔄 Refreshing Polymarket markets cache (Approach B)…")
        all_markets = self._fetch_raw_markets()

        filtered = []
        for m in all_markets:
            vol = float(
                m.get("volume") or m.get("volumeNum") or m.get("volume_num") or 0
            )
            if vol >= MARKET_MIN_VOLUME:
                filtered.append({
                    "question":     m.get("question", ""),
                    "condition_id": m.get("conditionId") or m.get("condition_id", ""),
                    "volume":       vol,
                    "keywords":     self._extract_keywords(m.get("question", "")),
                })

        self._markets = filtered
        self._markets_last_fetched = now
        logger.info(
            f"✅ Market cache: {len(self._markets)} active markets (vol>$1k) "
            f"from {len(all_markets)} total"
        )

    def _rebuild_watched_list_if_needed(self):
        """
        Approach A: Rebuild the proactive watched list from top-N markets by volume.
        Refreshes every 30 minutes.
        """
        now = datetime.now(tz=timezone.utc)
        if (
            self._watched_last_built is not None
            and (now - self._watched_last_built).total_seconds() < WATCHED_REFRESH_SECONDS
            and self._watched_pages
        ):
            return

        logger.info("🔄 Rebuilding proactive watched-page list from Polymarket top markets…")
        all_markets = self._fetch_raw_markets()
        if not all_markets:
            logger.warning("⚠️  No markets returned — watched list not updated")
            return

        # Sort by volume descending, take top N
        def _vol(m: Dict) -> float:
            return float(
                m.get("volume") or m.get("volumeNum") or m.get("volume_num") or 0
            )

        top_markets = sorted(all_markets, key=_vol, reverse=True)[:PROACTIVE_TOP_N_MARKETS]

        new_watched: Dict[str, Dict] = {}
        for m in top_markets:
            vol = _vol(m)
            market_entry = {
                "question":     m.get("question", ""),
                "condition_id": m.get("conditionId") or m.get("condition_id", ""),
                "volume":       vol,
                "keywords":     self._extract_keywords(m.get("question", "")),
            }
            question = m.get("question", "")
            entities = self._extract_entities_from_question(question)
            for entity in entities:
                # Only add if not already mapped to a higher-volume market
                if entity not in new_watched:
                    new_watched[entity] = market_entry

        self._watched_pages = new_watched
        self._watched_last_built = now

        logger.info(
            f"✅ Proactive watched list: {len(self._watched_pages)} Wikipedia pages "
            f"seeded from {len(top_markets)} top markets"
        )
        # Log a sample
        sample = list(self._watched_pages.keys())[:10]
        logger.info(f"   Sample watched pages: {sample}")

    # ── Wikipedia fetching ─────────────────────────────────────────────────────

    def fetch_recent_changes(self) -> List[Dict]:
        try:
            resp = requests.get(
                WIKIPEDIA_RECENT_CHANGES_URL, timeout=15, headers=self.WIKI_HEADERS
            )
            resp.raise_for_status()
            changes = resp.json().get("query", {}).get("recentchanges", [])
            logger.info(f"📡 Wikipedia: {len(changes)} recent changes fetched")
            return changes
        except requests.exceptions.Timeout:
            logger.error("⏱️  Wikipedia request timed out")
        except requests.exceptions.ConnectionError as exc:
            logger.error(f"🔌 Wikipedia connection error: {exc}")
        except Exception as exc:
            logger.error(f"❌ Unexpected error fetching Wikipedia changes: {exc}")
        return []

    def fetch_page_revisions(self, title: str) -> List[datetime]:
        try:
            url = WIKIPEDIA_PAGE_INFO_URL.format(title=requests.utils.quote(title))
            resp = requests.get(url, timeout=15, headers=self.WIKI_HEADERS)
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", {})
            timestamps = []
            for page_data in pages.values():
                for rev in page_data.get("revisions", []):
                    ts = self._parse_wiki_ts(rev.get("timestamp", ""))
                    if ts:
                        timestamps.append(ts)
            return timestamps
        except Exception as exc:
            logger.warning(f"⚠️  Could not fetch revisions for '{title}': {exc}")
            return []

    # ── Edit velocity ──────────────────────────────────────────────────────────

    def _count_recent_edits(
        self,
        timestamps: List[datetime],
        window_minutes: int = SIGNAL_WINDOW_MINUTES,
    ) -> int:
        cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=window_minutes)
        return sum(1 for ts in timestamps if ts >= cutoff)

    def _get_edit_count_for_page(
        self,
        page_title: str,
        changes: List[Dict],
    ) -> int:
        """
        Return recent edit count for a page. Uses batch data first;
        falls back to fetching page revisions if count is below threshold.
        """
        batch_timestamps = [
            self._parse_wiki_ts(c.get("timestamp", ""))
            for c in changes
            if c.get("title", "") == page_title
        ]
        batch_timestamps = [t for t in batch_timestamps if t]
        count = self._count_recent_edits(batch_timestamps)

        if count < MEDIUM_SIGNAL_EDITS:
            rev_timestamps = self.fetch_page_revisions(page_title)
            if rev_timestamps:
                count = self._count_recent_edits(rev_timestamps)
        return count

    # ── Reactive match (Approach B) ───────────────────────────────────────────

    def _match_page_to_market(self, page_title: str) -> Optional[Tuple[Dict, int]]:
        """
        Keyword-overlap match of a Wikipedia page title against all cached markets.
        Returns (market_dict, score) if score >= 2, else None.
        """
        if not self._markets:
            return None
        page_kw = self._extract_keywords(page_title)
        if not page_kw:
            return None

        best_market, best_score = None, 0
        for market in self._markets:
            score = len(page_kw & market["keywords"])
            if score > best_score:
                best_score = score
                best_market = market

        return (best_market, best_score) if best_score >= 2 else None

    # ── Signal building ────────────────────────────────────────────────────────

    def _build_signal(
        self,
        page_title: str,
        market: Dict,
        edit_count: int,
        match_score: int,
        source: str,           # "proactive" | "reactive"
    ) -> Dict:
        """Classify conviction and assemble the signal dict."""
        vol = market["volume"]

        base = 5.0
        if edit_count >= HIGH_SIGNAL_EDITS:
            base += 2.0 + min((edit_count - HIGH_SIGNAL_EDITS) * 0.5, 1.5)
            level = "HIGH"
        else:
            base += 0.5 + (edit_count - MEDIUM_SIGNAL_EDITS) * 0.3
            level = "MEDIUM"

        if vol > 0:
            base += min(math.log10(vol / 1_000) * 0.5, 1.5)

        # Proactive gets a small bonus — these are known-important pages
        if source == "proactive":
            base += 0.3

        conviction = round(min(base, 10.0), 1)
        question   = market["question"]

        explanation = (
            f"Wikipedia page '{page_title}' received {edit_count} edit(s) in the last "
            f"{SIGNAL_WINDOW_MINUTES} minutes. "
            f"Detection mode: {source}. "
            f"This page matches active Polymarket market: '{question}'. "
            f"Edit spikes on related Wikipedia pages precede market repricing — "
            f"editors update articles when breaking news breaks, before prediction "
            f"markets catch up."
        )

        return {
            "page_title":     page_title,
            "market_question": question,
            "condition_id":   market["condition_id"],
            "market_volume":  vol,
            "edit_count_5min": edit_count,
            "signal_level":   level,
            "conviction":     conviction,
            "match_score":    match_score,
            "source":         source,
            "signal_explanation": explanation,
            "detected_at":    datetime.now(tz=timezone.utc).isoformat(),
        }

    # ── Main scan ──────────────────────────────────────────────────────────────

    def scan_once(self) -> int:
        """Run one dual-mode scan. Returns number of signals generated."""
        self.arena_db.heartbeat(
            self.bot_id, "active", "Scanning Wikipedia (dual-mode)"
        )

        # Refresh both caches
        self._refresh_markets_if_needed()
        self._rebuild_watched_list_if_needed()

        # Fetch Wikipedia recent changes
        changes = self.fetch_recent_changes()
        if not changes:
            logger.info("📭 No Wikipedia changes returned")
            return 0

        # ── DIAGNOSTIC ────────────────────────────────────────────────────────
        title_counts: Counter = Counter(
            c.get("title", "") for c in changes if c.get("title")
        )
        logger.info(f"🔬 DIAGNOSTIC: {len(changes)} changes, {len(title_counts)} unique pages")
        logger.info(f"🔬 DIAGNOSTIC: {len(self._watched_pages)} proactive watched pages")
        logger.info(f"🔬 DIAGNOSTIC: {len(self._markets)} reactive market index")
        top5 = title_counts.most_common(5)
        logger.info("🔬 DIAGNOSTIC: Top 5 most-edited pages this scan:")
        for i, (page, cnt) in enumerate(top5, 1):
            logger.info(f"   {i}. '{page}' ({cnt} edit(s))")
        # ── END DIAGNOSTIC ────────────────────────────────────────────────────

        signals_generated = 0
        fired_keys: Set[str] = set()   # dedup key = f"{page_title}::{condition_id}"

        changed_titles = set(title_counts.keys())

        # ═══════════════════════════════════════════════════════════════════════
        # APPROACH A — Proactive: check watched pages against this batch
        # ═══════════════════════════════════════════════════════════════════════
        proactive_hits = 0
        for watched_title, market in self._watched_pages.items():
            # Flexible match: watched title substring anywhere in changed title or vice-versa
            matched_changed_title = None
            for changed_title in changed_titles:
                wl = watched_title.lower()
                cl = changed_title.lower()
                if wl in cl or cl in wl:
                    matched_changed_title = changed_title
                    break

            if matched_changed_title is None:
                continue

            proactive_hits += 1
            edit_count = self._get_edit_count_for_page(matched_changed_title, changes)

            dedup_key = f"{watched_title}::{market['condition_id']}"
            if dedup_key in fired_keys:
                continue

            logger.info(
                f"👁️  PROACTIVE: '{watched_title}' found in changes "
                f"(matched '{matched_changed_title}', edits={edit_count})"
            )

            if edit_count < MEDIUM_SIGNAL_EDITS:
                logger.info(
                    f"   ↳ skipped (only {edit_count} edit(s) in 5min, need {MEDIUM_SIGNAL_EDITS})"
                )
                continue

            signal = self._build_signal(
                page_title=watched_title,
                market=market,
                edit_count=edit_count,
                match_score=99,   # Proactive match is exact/seeded, not scored
                source="proactive",
            )
            logger.info(
                f"📝 WIKI SIGNAL [PROACTIVE/{signal['signal_level']}] | "
                f"page='{watched_title}' | "
                f"market='{market['question'][:60]}' | "
                f"edits={edit_count} | conviction={signal['conviction']}"
            )
            fired_keys.add(dedup_key)
            self._log_opportunity(signal)
            self.execute_paper_trade(signal)
            signals_generated += 1

        logger.info(
            f"🔬 Approach A: {proactive_hits} watched page(s) found in changes, "
            f"{signals_generated} signal(s) fired"
        )

        # ═══════════════════════════════════════════════════════════════════════
        # APPROACH B — Reactive: scan remaining pages for surprise matches
        # ═══════════════════════════════════════════════════════════════════════
        # Pages already covered by proactive (avoid double-work on API calls)
        proactive_titles_lower = {t.lower() for t in self._watched_pages}

        reactive_checked = 0
        reactive_signals_before = signals_generated

        for changed_title in changed_titles:
            # Skip if already handled proactively
            if any(
                changed_title.lower() in p or p in changed_title.lower()
                for p in proactive_titles_lower
            ):
                continue

            reactive_checked += 1
            match_result = self._match_page_to_market(changed_title)
            if match_result is None:
                continue

            matched_market, score = match_result
            dedup_key = f"{changed_title}::{matched_market['condition_id']}"
            if dedup_key in fired_keys:
                continue

            edit_count = self._get_edit_count_for_page(changed_title, changes)

            logger.info(
                f"🎯 REACTIVE MATCH: '{changed_title}' → "
                f"'{matched_market['question'][:70]}' "
                f"(score={score}, edits={edit_count})"
            )

            if edit_count < MEDIUM_SIGNAL_EDITS:
                logger.info(
                    f"   ↳ skipped (only {edit_count} edit(s) in 5min, need {MEDIUM_SIGNAL_EDITS})"
                )
                continue

            signal = self._build_signal(
                page_title=changed_title,
                market=matched_market,
                edit_count=edit_count,
                match_score=score,
                source="reactive",
            )
            logger.info(
                f"📝 WIKI SIGNAL [REACTIVE/{signal['signal_level']}] | "
                f"page='{changed_title}' | "
                f"market='{matched_market['question'][:60]}' | "
                f"edits={edit_count} | conviction={signal['conviction']}"
            )
            fired_keys.add(dedup_key)
            self._log_opportunity(signal)
            self.execute_paper_trade(signal)
            signals_generated += 1

        reactive_new = signals_generated - reactive_signals_before
        logger.info(
            f"🔬 Approach B: {reactive_checked} non-watched pages checked, "
            f"{reactive_new} reactive signal(s) fired"
        )

        # ── Summary ───────────────────────────────────────────────────────────
        logger.info(
            f"🔎 Scan complete | total signals={signals_generated} | "
            f"trades={self.total_trades} | balance=${self.current_balance:,.2f} | "
            f"ROI={((self.current_balance - self.starting_balance) / self.starting_balance)*100:.1f}%"
        )
        return signals_generated

    # ── Paper trading ─────────────────────────────────────────────────────────

    def execute_paper_trade(self, signal: Dict) -> Dict:
        conviction       = signal["conviction"]
        level            = signal["signal_level"]
        edits            = signal["edit_count_5min"]
        page             = signal["page_title"]
        market_question  = signal["market_question"]
        condition_id     = signal["condition_id"]
        source           = signal["source"]

        size  = min(self.current_balance * POSITION_SIZE_PCT, MAX_POSITION_USD)
        price = 0.55

        signal_id = shadow_log_signal(
            bot_id=self.bot_id,
            bot_name="Wikipedia Velocity",
            bot_emoji="📚",
            signal_headline=(
                f"Wiki [{level}/{source}] spike: '{page}' — {edits} edits/5min"
            ),
            signal_explanation=signal["signal_explanation"],
            market_title=market_question,
            direction="BUY",
            entry_price=price,
            conviction_score=conviction,
            condition_id=condition_id,
            shadow_size=size,
            raw_signal={
                "page_title":       page,
                "market_question":  market_question,
                "edit_count_5min":  edits,
                "signal_level":     level,
                "source":           source,
                "match_score":      signal.get("match_score", 0),
                "market_volume":    signal.get("market_volume", 0),
            },
            notes=(
                f"source: {source} | Wiki velocity [{level}]: "
                f"{edits} edits/5min on '{page}'"
            ),
        )

        self.total_trades += 1
        self.trade_history.append({
            "pnl": 0, "size": size, "price": price,
            "actual_pnl": 0, "status": "pending",
            "conviction_score": conviction,
        })
        self._update_performance()

        logger.info(
            f"🕵️ Shadow signal #{signal_id} | "
            f"[{source}] Wiki [{level}] '{page}' → '{market_question[:50]}…'"
        )
        return {
            "signal_id":    signal_id,
            "market_title": market_question,
            "direction":    "BUY",
            "entry_price":  price,
            "shadow_size":  size,
        }

    def _log_opportunity(self, signal: Dict):
        self.arena_db.log_opportunity(
            self.bot_id,
            {
                "type":  f"wikipedia_velocity_{signal['signal_level'].lower()}_{signal['source']}",
                "market_title":       signal["market_question"],
                "condition_id":       signal["condition_id"],
                "confidence_score":   signal["conviction"],
                "expected_edge":      0.18 if signal["signal_level"] == "HIGH" else 0.10,
                "time_sensitivity_minutes": 10,
                "data_source": (
                    f"Wikipedia ({signal['source']}): "
                    f"{signal['edit_count_5min']} edits/5min on '{signal['page_title']}' "
                    f"(match_score={signal.get('match_score', 0)})"
                ),
            },
        )

    def _update_performance(self):
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

        peak, max_dd, running = self.starting_balance, 0.0, self.starting_balance
        for t in self.trade_history:
            running += t["actual_pnl"]
            peak = max(peak, running)
            max_dd = max(max_dd, (peak - running) / peak * 100)

        avg_size = (
            sum(t["size"] * t["price"] for t in self.trade_history)
            / max(self.total_trades, 1)
        )

        self.arena_db.update_bot_performance(
            self.bot_id,
            {
                "total_trades":   self.total_trades,
                "winning_trades": self.winning_trades,
                "losing_trades":  self.losing_trades,
                "total_roi":      total_roi,
                "current_balance": self.current_balance,
                "win_rate":       win_rate,
                "sharpe_ratio":   sharpe,
                "max_drawdown":   max_dd,
                "avg_trade_size": avg_size,
            },
        )

    # ── Run forever ───────────────────────────────────────────────────────────

    def run_forever(self):
        logger.info(
            f"🚀 {self.bot_name} starting dual-mode loop "
            f"(interval={SCAN_INTERVAL_SECONDS}s)…"
        )
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
                self.arena_db.heartbeat(
                    self.bot_id, "error", "Exception in loop", str(exc)
                )
                time.sleep(30)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    bot = WikipediaVelocityBot()
    bot.run_forever()
