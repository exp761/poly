"""
🧠 Market Analyzer — AI-powered market analysis engine
The brain of PolyGenius - uses Claude via OpenRouter
"""

import aiohttp
import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from data_fetcher import DataFetcher
from probability_engine import ProbabilityEngine

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class MarketAnalyzer:
    def __init__(self, openrouter_key: str, model: str):
        self.api_key = openrouter_key
        self.model = model
        self.fetcher = DataFetcher(openrouter_key, model)
        self.engine = ProbabilityEngine()
        self.session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=60)
            )
        return self.session

    async def _call_ai(self, prompt: str, system: str = None) -> Optional[str]:
        """Call Claude via OpenRouter"""
        try:
            session = await self._get_session()
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 1500,
                "temperature": 0.3
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://polygenius.bot",
                "X-Title": "PolyGenius Research Bot"
            }

            async with session.post(OPENROUTER_URL, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    logger.error(f"OpenRouter error: {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"AI call error: {e}")
            return None

    # ─── Quick Analysis ────────────────────────────────────────

    async def quick_analyze(self, market: dict) -> Optional[dict]:
        """
        Fast analysis for scanning many markets.
        Uses minimal data for speed.
        """
        try:
            title = market.get("question", market.get("title", ""))
            if not title:
                return None

            # Get current market probability
            market_prob = self._get_market_prob(market)
            if market_prob is None:
                return None

            # Quick AI assessment
            prompt = f"""Analyze this prediction market question:
"{title}"

Current market probability: {market_prob*100:.1f}%
End date: {market.get('endDate', market.get('end_date_iso', 'Unknown'))}

Give a QUICK assessment in JSON format only:
{{
  "our_probability": <number 0-100>,
  "direction": "yes" or "no",
  "confidence": "High" or "Medium" or "Low",
  "one_line_reason": "<brief reason>",
  "worth_deep_analysis": true or false
}}

Base on your knowledge. Be calibrated and honest about uncertainty."""

            response = await self._call_ai(prompt)
            if not response:
                return None

            result = self._parse_json(response)
            if not result:
                return None

            our_prob = result.get("our_probability", 50) / 100
            edge = (our_prob - market_prob) * 100

            if abs(edge) < 3:  # Skip if tiny edge
                return None

            return {
                "market_id": market.get("id", market.get("conditionId", "")),
                "title": title[:80],
                "market_prob": round(market_prob * 100, 1),
                "our_prob": round(our_prob * 100, 1),
                "edge": round(edge, 1),
                "bet_direction": result.get("direction", "yes"),
                "confidence": result.get("confidence", "Medium"),
                "reason": result.get("one_line_reason", ""),
                "worth_deep": result.get("worth_deep_analysis", False),
                "volume": float(market.get("volume", 0)),
                "end_date": market.get("endDate", "Unknown")
            }

        except Exception as e:
            logger.error(f"Quick analyze error: {e}")
            return None

    # ─── Deep Analysis ─────────────────────────────────────────

    async def deep_analyze(self, market: dict) -> Optional[dict]:
        """
        Deep multi-source analysis.
        Fetches news, Metaculus, historical data.
        """
        try:
            title = market.get("question", market.get("title", ""))
            if not title:
                return None

            market_prob = self._get_market_prob(market)
            if market_prob is None:
                return None

            # Parallel data fetching
            keyword = self._extract_keyword(title)

            news_task = self.fetcher.get_gdelt_news(keyword, days=7)
            metaculus_task = self.fetcher.get_metaculus_question(keyword)
            history_task = self.fetcher.get_price_history(
                market.get("id", market.get("conditionId", ""))
            )
            resolved_task = self.fetcher.get_related_resolved_markets(keyword)

            news, metaculus, history, resolved = await asyncio.gather(
                news_task, metaculus_task, history_task, resolved_task,
                return_exceptions=True
            )

            # Handle exceptions from gather
            news = news if not isinstance(news, Exception) else []
            metaculus = metaculus if not isinstance(metaculus, Exception) else None
            history = history if not isinstance(history, Exception) else []
            resolved = resolved if not isinstance(resolved, Exception) else []

            # Get Metaculus prediction
            metaculus_prob = None
            metaculus_info = ""
            if metaculus and isinstance(metaculus, dict):
                q_id = metaculus.get("id")
                if q_id:
                    meta_pred = await self.fetcher.get_metaculus_community_prediction(q_id)
                    if meta_pred:
                        metaculus_prob = meta_pred
                        metaculus_info = f"Metaculus: {meta_pred*100:.0f}% ({metaculus.get('title', '')[:50]})"

            # Summarize news
            news_summary = ""
            if news and isinstance(news, list):
                headlines = [a.get("title", "") for a in news[:5] if a.get("title")]
                news_summary = "\n".join(headlines)

            # Calculate base rate
            base_rate = None
            if resolved and isinstance(resolved, list) and len(resolved) > 3:
                base_rate = self.engine.calculate_base_rate(resolved)

            # Calculate momentum
            momentum = None
            if history and isinstance(history, list):
                momentum = self.engine.calculate_momentum(history)

            # Deep AI analysis
            ai_result = await self._deep_ai_analysis(
                title=title,
                market_prob=market_prob,
                news_summary=news_summary,
                metaculus_info=metaculus_info,
                base_rate=base_rate,
                momentum=momentum,
                end_date=market.get("endDate", "Unknown")
            )

            if not ai_result:
                return None

            # Calculate final probability
            prob_result = self.engine.calculate(
                ai_prob=ai_result.get("our_prob_raw"),
                base_rate=base_rate,
                metaculus_prob=metaculus_prob,
                news_sentiment_score=ai_result.get("sentiment_score"),
                market_momentum=momentum,
                market_current_prob=market_prob
            )

            # Calculate end days
            end_days = self._calculate_end_days(market.get("endDate", ""))

            # Overall score
            score = self.engine.score_opportunity(
                edge=prob_result["edge"],
                confidence=prob_result["confidence"],
                volume=float(market.get("volume", 0)),
                end_days=end_days
            )

            return {
                "market_id": market.get("id", market.get("conditionId", "")),
                "title": title[:80],
                "market_prob": round(market_prob * 100, 1),
                "our_prob": prob_result["our_prob"],
                "edge": prob_result["edge"],
                "confidence": prob_result["confidence"],
                "bet_direction": prob_result["bet_direction"],
                "kelly_size": prob_result["kelly_size"],
                "score": score,
                "sources": {
                    "Metaculus": metaculus_info or "Not found",
                    "Base rate": f"{base_rate*100:.0f}% ({len(resolved) if isinstance(resolved, list) else 0} markets)" if base_rate else "Insufficient data",
                    "Momentum": f"{'↗️ Rising' if momentum and momentum > 0.1 else '↘️ Falling' if momentum and momentum < -0.1 else '→ Stable'}" if momentum is not None else "No data",
                    "News": f"{len(news) if isinstance(news, list) else 0} articles found"
                },
                "factors": ai_result.get("key_factors", []),
                "risks": ai_result.get("main_risk", "Unknown"),
                "reason": ai_result.get("summary", ""),
                "end_date": market.get("endDate", "Unknown"),
                "volume": float(market.get("volume", 0))
            }

        except Exception as e:
            logger.error(f"Deep analyze error: {e}")
            return None

    # ─── Ultra Deep Analysis ───────────────────────────────────

    async def ultra_deep_analyze(self, market: dict) -> Optional[dict]:
        """
        Maximum depth analysis for a single market.
        Used when user specifically requests full analysis.
        """
        result = await self.deep_analyze(market)
        if not result:
            return None

        # Add even more detail
        title = market.get("question", market.get("title", ""))
        market_prob = self._get_market_prob(market)

        extra_prompt = f"""You are an expert prediction market analyst.

Market: "{title}"
Current probability: {market_prob*100:.1f}%

Provide a comprehensive analysis including:
1. Detailed probability reasoning
2. Historical precedents
3. Key uncertainties
4. Scenario analysis (bull/bear/base case)
5. What would change your estimate
6. Comparison to similar past events

Be specific, data-driven, and calibrated."""

        extra_analysis = await self._call_ai(extra_prompt)

        result["detailed_analysis"] = extra_analysis or "Unable to generate detailed analysis"
        return result

    # ─── Answer Questions ──────────────────────────────────────

    async def answer_question(self, question: str) -> str:
        """
        Answer natural language questions about markets.
        """
        # Check if it's about a specific market
        markets = await self.fetcher.search_markets(question)

        market_context = ""
        if markets:
            market = markets[0]
            prob = self._get_market_prob(market)
            market_context = (
                f"\nRelevant Polymarket market found:\n"
                f"Title: {market.get('question', '')}\n"
                f"Current probability: {prob*100:.1f}% if known\n"
                f"Volume: ${float(market.get('volume', 0)):,.0f}\n"
            )

        prompt = f"""You are PolyGenius, an expert prediction market research assistant.

User question: "{question}"
{market_context}

Answer helpfully and concisely. If there's a relevant market:
- Give current market probability
- Your assessment of true probability
- Key factors affecting the outcome
- Whether you see value in betting YES or NO

Format in clear sections. Use emojis. Keep under 300 words.
End with a confidence level."""

        system = (
            "You are PolyGenius, an expert AI analyst specialized in prediction markets. "
            "You are calibrated, data-driven, and give honest probability estimates. "
            "You acknowledge uncertainty and never overstate confidence."
        )

        response = await self._call_ai(prompt, system=system)
        return response or "❌ Maaf, tidak bisa memproses pertanyaan ini saat ini."

    # ─── Private Helpers ───────────────────────────────────────

    async def _deep_ai_analysis(
        self,
        title: str,
        market_prob: float,
        news_summary: str,
        metaculus_info: str,
        base_rate: Optional[float],
        momentum: Optional[float],
        end_date: str
    ) -> Optional[dict]:
        """Core AI analysis with all data"""

        prompt = f"""You are an expert prediction market analyst. Analyze this market:

MARKET: "{title}"
END DATE: {end_date}
CURRENT MARKET PRICE: {market_prob*100:.1f}% (YES)

DATA SOURCES:
- Metaculus expert prediction: {metaculus_info or 'Not available'}
- Historical base rate: {f'{base_rate*100:.0f}%' if base_rate else 'Insufficient data'}
- Price momentum: {'Rising ↗️' if momentum and momentum > 0.1 else 'Falling ↘️' if momentum and momentum < -0.1 else 'Stable →' if momentum is not None else 'Unknown'}

RECENT NEWS HEADLINES:
{news_summary or 'No recent news found'}

Provide analysis in JSON format:
{{
  "our_probability": <number 0-100>,
  "sentiment_score": <number -1 to 1, based on news>,
  "key_factors": ["factor1", "factor2", "factor3"],
  "main_risk": "<main risk to your prediction>",
  "summary": "<2-3 sentence summary>",
  "market_assessment": "underpriced" or "overpriced" or "fairly priced"
}}

Be calibrated. If you're uncertain, probability should be close to 50%.
Consider all data sources and their reliability."""

        response = await self._call_ai(prompt)
        if not response:
            return None

        result = self._parse_json(response)
        if not result:
            return None

        our_prob = result.get("our_probability", 50) / 100
        result["our_prob_raw"] = our_prob

        return result

    def _get_market_prob(self, market: dict) -> Optional[float]:
        """Extract YES probability from market data"""
        # Try various fields
        for field in ["bestAsk", "best_ask", "lastTradePrice", "price"]:
            val = market.get(field)
            if val is not None:
                try:
                    p = float(val)
                    if 0 < p < 1:
                        return p
                    elif 0 < p <= 100:
                        return p / 100
                except (ValueError, TypeError):
                    pass

        # Try tokens
        tokens = market.get("tokens", [])
        for token in tokens:
            if token.get("outcome", "").lower() == "yes":
                price = token.get("price", token.get("lastTradePrice"))
                if price:
                    try:
                        p = float(price)
                        return p if p <= 1 else p / 100
                    except (ValueError, TypeError):
                        pass

        # Try outcomePrices
        outcome_prices = market.get("outcomePrices", [])
        if outcome_prices:
            try:
                p = float(outcome_prices[0])
                return p if p <= 1 else p / 100
            except (ValueError, TypeError, IndexError):
                pass

        return None

    def _extract_keyword(self, title: str) -> str:
        """Extract key search term from market title"""
        # Remove common words
        stop_words = {"will", "the", "a", "an", "be", "is", "are", "was",
                      "were", "by", "in", "of", "to", "and", "or", "for",
                      "on", "at", "from", "with", "that", "this", "it"}
        words = title.lower().split()
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        # Take first 3-4 meaningful words
        return " ".join(keywords[:4])

    def _parse_json(self, text: str) -> Optional[dict]:
        """Parse JSON from AI response"""
        try:
            # Try direct parse
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON in text
        try:
            match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except (json.JSONDecodeError, AttributeError):
            pass

        return None

    def _calculate_end_days(self, end_date: str) -> int:
        """Calculate days until market ends"""
        try:
            if not end_date:
                return 30
            # Parse ISO format
            end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = end - now
            return max(0, delta.days)
        except Exception:
            return 30

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
        await self.fetcher.close()
