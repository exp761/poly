"""
📡 Data Fetcher — Multi-source data aggregator
Fetches from Polymarket, Metaculus, news, social media
"""

import aiohttp
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

POLYMARKET_API = "https://clob.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"
METACULUS_API = "https://www.metaculus.com/api2"
NEWS_API = "https://newsapi.org/v2"
GDELT_API = "https://api.gdeltproject.org/api/v2"


class DataFetcher:
    def __init__(self, openrouter_key: str, model: str):
        self.openrouter_key = openrouter_key
        self.model = model
        self.session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self.session

    # ─── Polymarket ────────────────────────────────────────────

    async def get_active_markets(self, limit: int = 50) -> list:
        """Get active markets from Polymarket"""
        try:
            session = await self._get_session()
            url = f"{GAMMA_API}/markets"
            params = {
                "active": "true",
                "closed": "false",
                "limit": limit,
                "order": "volume24hr",
                "ascending": "false"
            }
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data if isinstance(data, list) else data.get("markets", [])
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
        return []

    async def search_markets(self, keyword: str) -> list:
        """Search markets by keyword"""
        try:
            session = await self._get_session()
            url = f"{GAMMA_API}/markets"
            params = {
                "active": "true",
                "closed": "false",
                "limit": 10,
                "keyword": keyword
            }
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    markets = data if isinstance(data, list) else data.get("markets", [])
                    # Filter by keyword manually if needed
                    if markets:
                        keyword_lower = keyword.lower()
                        filtered = [
                            m for m in markets
                            if keyword_lower in m.get("question", "").lower()
                            or keyword_lower in m.get("description", "").lower()
                        ]
                        return filtered if filtered else markets
        except Exception as e:
            logger.error(f"Error searching markets: {e}")
        return []

    async def get_market_by_id(self, market_id: str) -> Optional[dict]:
        """Get specific market by ID"""
        try:
            session = await self._get_session()
            url = f"{GAMMA_API}/markets/{market_id}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            logger.error(f"Error fetching market {market_id}: {e}")
        return None

    async def get_market_orderbook(self, token_id: str) -> Optional[dict]:
        """Get orderbook for a market token"""
        try:
            session = await self._get_session()
            url = f"{POLYMARKET_API}/book"
            params = {"token_id": token_id}
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            logger.error(f"Error fetching orderbook: {e}")
        return None

    # ─── Metaculus ─────────────────────────────────────────────

    async def get_metaculus_question(self, keyword: str) -> Optional[dict]:
        """Search Metaculus for related questions"""
        try:
            session = await self._get_session()
            url = f"{METACULUS_API}/questions/"
            params = {
                "search": keyword,
                "status": "open",
                "type": "forecast",
                "order_by": "-activity",
                "limit": 5
            }
            headers = {"Accept": "application/json"}
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    if results:
                        # Return the most relevant
                        return results[0]
        except Exception as e:
            logger.error(f"Error fetching Metaculus: {e}")
        return None

    async def get_metaculus_community_prediction(self, question_id: int) -> Optional[float]:
        """Get community prediction from Metaculus"""
        try:
            session = await self._get_session()
            url = f"{METACULUS_API}/questions/{question_id}/"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    prediction = data.get("community_prediction", {})
                    return prediction.get("full", {}).get("q2")  # median
        except Exception as e:
            logger.error(f"Error fetching Metaculus prediction: {e}")
        return None

    # ─── News ──────────────────────────────────────────────────

    async def get_gdelt_news(self, keyword: str, days: int = 7) -> list:
        """Get news from GDELT (free, no API key needed)"""
        try:
            session = await self._get_session()
            # GDELT Article Search
            url = "https://api.gdeltproject.org/api/v2/doc/doc"
            params = {
                "query": keyword,
                "mode": "artlist",
                "maxrecords": 10,
                "format": "json",
                "timespan": f"{days}d",
                "sort": "datedesc"
            }
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("articles", [])
        except Exception as e:
            logger.error(f"Error fetching GDELT: {e}")
        return []

    async def get_gdelt_sentiment(self, keyword: str) -> Optional[dict]:
        """Get sentiment analysis from GDELT"""
        try:
            session = await self._get_session()
            url = "https://api.gdeltproject.org/api/v2/doc/doc"
            params = {
                "query": keyword,
                "mode": "timelinetone",
                "format": "json",
                "timespan": "7d"
            }
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            logger.error(f"Error fetching GDELT sentiment: {e}")
        return None

    # ─── Wikipedia ─────────────────────────────────────────────

    async def get_wikipedia_summary(self, keyword: str) -> Optional[str]:
        """Get Wikipedia summary for context"""
        try:
            session = await self._get_session()
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{keyword.replace(' ', '_')}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("extract", "")[:500]
        except Exception as e:
            logger.error(f"Error fetching Wikipedia: {e}")
        return None

    # ─── Historical Polymarket Data ────────────────────────────

    async def get_price_history(self, market_id: str) -> list:
        """Get price history for a market"""
        try:
            session = await self._get_session()
            url = f"{GAMMA_API}/markets/{market_id}/prices-history"
            params = {"interval": "1d", "fidelity": 100}
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            logger.error(f"Error fetching price history: {e}")
        return []

    async def get_related_resolved_markets(self, keyword: str) -> list:
        """Get resolved markets similar to this one - for base rate"""
        try:
            session = await self._get_session()
            url = f"{GAMMA_API}/markets"
            params = {
                "closed": "true",
                "keyword": keyword,
                "limit": 20
            }
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    markets = data if isinstance(data, list) else data.get("markets", [])
                    # Only return resolved ones
                    return [m for m in markets if m.get("resolved") == True]
        except Exception as e:
            logger.error(f"Error fetching resolved markets: {e}")
        return []

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
