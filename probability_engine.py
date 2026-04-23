"""
🎯 Probability Engine — Multi-factor probability calculator
Combines all data sources into a final probability estimate
"""

import math
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ProbabilityEngine:
    """
    Weighted probability calculator using multiple sources.
    
    Weights:
    - AI Analysis (Claude):     35%
    - Historical base rate:     25%
    - Metaculus prediction:     20%
    - News sentiment:           10%
    - Market momentum:          10%
    """

    WEIGHTS = {
        "ai_analysis":    0.35,
        "base_rate":      0.25,
        "metaculus":      0.20,
        "news_sentiment": 0.10,
        "momentum":       0.10,
    }

    def calculate(
        self,
        ai_prob: Optional[float],
        base_rate: Optional[float],
        metaculus_prob: Optional[float],
        news_sentiment_score: Optional[float],  # -1 to +1
        market_momentum: Optional[float],       # price change trend
        market_current_prob: float = 0.5
    ) -> dict:
        """
        Calculate final probability estimate with confidence.
        Returns dict with prob, confidence, edge, sources_used
        """
        sources = {}
        weighted_sum = 0.0
        weight_total = 0.0

        # AI Analysis
        if ai_prob is not None and 0 < ai_prob < 1:
            sources["ai"] = ai_prob
            weighted_sum += ai_prob * self.WEIGHTS["ai_analysis"]
            weight_total += self.WEIGHTS["ai_analysis"]

        # Historical base rate
        if base_rate is not None and 0 < base_rate < 1:
            sources["base_rate"] = base_rate
            weighted_sum += base_rate * self.WEIGHTS["base_rate"]
            weight_total += self.WEIGHTS["base_rate"]

        # Metaculus
        if metaculus_prob is not None and 0 < metaculus_prob < 1:
            sources["metaculus"] = metaculus_prob
            weighted_sum += metaculus_prob * self.WEIGHTS["metaculus"]
            weight_total += self.WEIGHTS["metaculus"]

        # News sentiment → convert to probability adjustment
        if news_sentiment_score is not None:
            # Sentiment -1 to +1 → prob adjustment ±15%
            sentiment_prob = 0.5 + (news_sentiment_score * 0.15)
            sentiment_prob = max(0.05, min(0.95, sentiment_prob))
            sources["sentiment"] = sentiment_prob
            weighted_sum += sentiment_prob * self.WEIGHTS["news_sentiment"]
            weight_total += self.WEIGHTS["news_sentiment"]

        # Market momentum (recent price trend)
        if market_momentum is not None:
            momentum_prob = 0.5 + (market_momentum * 0.1)
            momentum_prob = max(0.05, min(0.95, momentum_prob))
            sources["momentum"] = momentum_prob
            weighted_sum += momentum_prob * self.WEIGHTS["momentum"]
            weight_total += self.WEIGHTS["momentum"]

        # Fallback if no sources
        if weight_total == 0:
            return {
                "our_prob": market_current_prob,
                "edge": 0,
                "confidence": "Very Low",
                "sources_count": 0,
                "sources": {}
            }

        # Normalize
        final_prob = weighted_sum / weight_total
        final_prob = max(0.02, min(0.98, final_prob))

        # Calculate edge vs market
        edge = (final_prob - market_current_prob) * 100
        abs_edge = abs(edge)

        # Confidence based on sources count + agreement
        confidence = self._calculate_confidence(sources, final_prob, weight_total)

        # Kelly criterion (half Kelly for safety)
        kelly = self._kelly_criterion(final_prob, market_current_prob)

        return {
            "our_prob": round(final_prob * 100, 1),
            "our_prob_raw": final_prob,
            "edge": round(edge, 1),
            "abs_edge": round(abs_edge, 1),
            "confidence": confidence,
            "sources_count": len(sources),
            "sources": {k: round(v * 100, 1) for k, v in sources.items()},
            "kelly_size": kelly,
            "bet_direction": "YES" if final_prob > market_current_prob else "NO"
        }

    def _calculate_confidence(
        self,
        sources: dict,
        final_prob: float,
        weight_total: float
    ) -> str:
        """Calculate confidence level based on data quality"""
        n = len(sources)

        # Agreement between sources
        if n > 1:
            probs = list(sources.values())
            std = self._std_dev(probs)
            agreement = 1 - min(std / 0.3, 1)  # Low std = high agreement
        else:
            agreement = 0.5

        # Score 0-100
        score = (
            (n / 5) * 40 +           # Source count (max 40pts)
            agreement * 40 +          # Agreement (max 40pts)
            (weight_total * 20)       # Weight coverage (max 20pts)
        )

        if score >= 75:
            return "Very High 🔥"
        elif score >= 60:
            return "High ✅"
        elif score >= 45:
            return "Medium 🟡"
        elif score >= 30:
            return "Low ⚠️"
        else:
            return "Very Low ❌"

    def _kelly_criterion(
        self,
        our_prob: float,
        market_prob: float
    ) -> str:
        """
        Calculate Kelly criterion bet size.
        Using half-Kelly for safety.
        
        For binary markets:
        b = (1/market_prob) - 1  (odds in decimal - 1)
        f* = (b*p - q) / b
        """
        try:
            if our_prob <= market_prob:
                return "N/A (no edge)"

            # Market odds
            b = (1 / market_prob) - 1
            q = 1 - our_prob

            full_kelly = (b * our_prob - q) / b
            half_kelly = full_kelly / 2

            if half_kelly <= 0:
                return "N/A"
            elif half_kelly < 0.02:
                return f"~{half_kelly*100:.1f}% (very small)"
            elif half_kelly < 0.05:
                return f"~{half_kelly*100:.1f}% (small)"
            elif half_kelly < 0.15:
                return f"~{half_kelly*100:.1f}% (moderate)"
            else:
                return f"~{half_kelly*100:.1f}% (large — careful!)"
        except Exception:
            return "N/A"

    def calculate_base_rate(self, resolved_markets: list, outcome: str = "yes") -> Optional[float]:
        """
        Calculate historical base rate from resolved markets.
        outcome: 'yes' to count YES resolutions
        """
        if not resolved_markets:
            return None

        resolved_yes = sum(
            1 for m in resolved_markets
            if str(m.get("resolution", "")).lower() == "yes"
        )
        total = len(resolved_markets)
        if total == 0:
            return None

        return resolved_yes / total

    def calculate_momentum(self, price_history: list) -> Optional[float]:
        """
        Calculate price momentum from history.
        Returns -1 to +1 (negative = falling, positive = rising)
        """
        if not price_history or len(price_history) < 2:
            return None

        try:
            prices = [p.get("p", p.get("price", 0.5)) for p in price_history[-7:]]
            if len(prices) < 2:
                return None

            # Simple linear trend
            n = len(prices)
            x_mean = (n - 1) / 2
            y_mean = sum(prices) / n

            numerator = sum((i - x_mean) * (prices[i] - y_mean) for i in range(n))
            denominator = sum((i - x_mean) ** 2 for i in range(n))

            if denominator == 0:
                return 0

            slope = numerator / denominator
            # Normalize to -1 to +1
            return max(-1, min(1, slope * 10))
        except Exception:
            return None

    def _std_dev(self, values: list) -> float:
        if len(values) < 2:
            return 0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return math.sqrt(variance)

    def score_opportunity(
        self,
        edge: float,
        confidence: str,
        volume: float = 0,
        end_days: int = 30
    ) -> float:
        """
        Overall opportunity score 0-100.
        Used for ranking opportunities.
        """
        confidence_scores = {
            "Very High 🔥": 1.0,
            "High ✅": 0.8,
            "Medium 🟡": 0.6,
            "Low ⚠️": 0.4,
            "Very Low ❌": 0.2,
        }

        conf_score = confidence_scores.get(confidence, 0.5)
        abs_edge = abs(edge)

        # Edge score (max 50pts)
        edge_score = min(abs_edge / 30, 1) * 50

        # Confidence score (max 30pts)
        confidence_score = conf_score * 30

        # Volume score (max 10pts) - higher volume = more liquid
        vol_score = min(math.log10(max(volume, 1)) / 6, 1) * 10

        # Time score (max 10pts) - closer resolution = more certain
        time_score = max(0, 1 - (end_days / 90)) * 10

        return round(edge_score + confidence_score + vol_score + time_score, 1)
