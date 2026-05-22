# agents/sentiment_analyst.py
"""
Synthetix Quant AI — Sentiment Analyst Agent
Scores market sentiment from news, events, and macro context.
"""

import json
from agents.base_agent import BaseAgent
from core.signal import AgentSignal, MarketSnapshot, SignalSource, Direction
from config.settings import AGENT_CONFIGS


class SentimentAnalyst(BaseAgent):
    """
    Analyzes: News sentiment, headline analysis, event detection
    (earnings, FII/DII activity, sector rotation, macro news).

    Bullish signals: Positive news flow, analyst upgrades, institutional buying,
                     improving macro backdrop.
    Bearish signals: Negative headlines, downgrades, insider selling,
                     regulatory issues, macro headwinds.
    """

    def __init__(self):
        super().__init__(config=AGENT_CONFIGS["sentiment"])

    def analyze(self, snapshot: MarketSnapshot) -> AgentSignal:
        prompt = self._build_prompt(snapshot)
        raw = self._call_llm(prompt)
        signal = self._parse_llm_output(raw, snapshot, SignalSource.SENTIMENT)
        self._last_signal = signal
        return signal

    def _build_prompt(self, snapshot: MarketSnapshot) -> str:
        news = snapshot.news
        agg_sentiment = snapshot.sentiment_score

        # Format news headlines
        news_lines = ""
        for i, item in enumerate(news[:5], 1):
            score = item.get("sentiment_score", 0)
            emoji = "📈" if score > 0.2 else "📉" if score < -0.2 else "➖"
            news_lines += (
                f"  {i}. {emoji} [{item.get('source', 'Unknown')}] "
                f"{item.get('headline', 'N/A')} "
                f"(sentiment: {score:+.2f})\n"
            )

        sentiment_label = (
            "STRONGLY BULLISH" if agg_sentiment > 0.4 else
            "MILDLY BULLISH" if agg_sentiment > 0.15 else
            "NEUTRAL" if agg_sentiment > -0.15 else
            "MILDLY BEARISH" if agg_sentiment > -0.4 else
            "STRONGLY BEARISH"
        )

        return f"""
You are the Sentiment Analyst for {snapshot.ticker} ({snapshot.exchange}).
Current Price: {snapshot.current_price}

## Aggregated Sentiment Score: {agg_sentiment:+.3f} → {sentiment_label}
(Scale: -1.0 = max bearish, 0 = neutral, +1.0 = max bullish)

## Recent News Headlines (last 24h)
{news_lines if news_lines else "  No recent news available."}

## Your Task
Analyze the sentiment landscape and provide a signal.

Consider:
1. Overall tone of news coverage — positive, negative, or neutral?
2. Are there any high-impact events (earnings, regulatory, M&A, macro)?
3. Are insiders/institutions buying or selling?
4. Is there analyst consensus forming in any direction?
5. Is sentiment a leading or lagging indicator here?

Important: Sentiment is a SHORT-TERM signal. Don't override strong
fundamentals/technicals with weak sentiment alone.

Respond ONLY with JSON:
{{
  "direction": "BUY" | "SELL" | "HOLD" | "STRONG_BUY" | "STRONG_SELL",
  "confidence": 0.0 to 1.0,
  "reasoning": "2-3 sentence sentiment view",
  "key_factors": ["headline 1 impact", "headline 2 impact", "macro factor"],
  "price_target": null,
  "stop_loss": null,
  "time_horizon": "intraday" or "short"
}}
"""

    def _mock_llm_response(self, prompt: str) -> str:
        """Rule-based sentiment analysis using the aggregated score."""
        # Extract sentiment score from prompt
        score = 0.0
        try:
            for line in prompt.split("\n"):
                if "Aggregated Sentiment Score:" in line:
                    score = float(line.split("→")[0].split("Score:")[1].strip())
                    break
        except (ValueError, IndexError):
            pass

        # Count specific keywords in headlines
        bullish_keywords = ["beats", "raises", "upgrade", "buyback", "contract", "growth", "strong", "record"]
        bearish_keywords = ["misses", "probe", "downgrade", "selling", "headwinds", "loss", "decline", "concern"]

        text_lower = prompt.lower()
        bullish_hits = sum(1 for kw in bullish_keywords if kw in text_lower)
        bearish_hits = sum(1 for kw in bearish_keywords if kw in text_lower)

        # Combine score and keyword signals
        combined = score + (bullish_hits - bearish_hits) * 0.05

        if combined > 0.35:
            direction = "BUY"
            confidence = min(0.60 + combined * 0.3, 0.82)
            reasoning = (
                "News flow is predominantly positive with bullish catalysts. "
                "Market sentiment supports near-term upside momentum."
            )
            factors = [
                f"Aggregate sentiment score: {score:+.2f} — bullish",
                f"{bullish_hits} positive keyword signals in recent headlines",
                "Institutional activity and analyst commentary supportive",
            ]
        elif combined < -0.25:
            direction = "SELL"
            confidence = min(0.55 + abs(combined) * 0.25, 0.78)
            reasoning = (
                "Negative news flow creating headwinds. "
                "Sentiment deteriorating — risk of further selling pressure."
            )
            factors = [
                f"Aggregate sentiment score: {score:+.2f} — bearish",
                f"{bearish_hits} negative signals in recent news",
                "Sentiment weakness may persist short-term",
            ]
        else:
            direction = "HOLD"
            confidence = 0.48
            reasoning = (
                "Sentiment is mixed or neutral — no strong directional catalyst. "
                "Market digesting recent news without clear conviction."
            )
            factors = [
                f"Aggregate sentiment score: {score:+.2f} — near neutral",
                "No dominant bullish or bearish narrative",
                "Await clearer sentiment catalyst",
            ]

        return json.dumps({
            "direction": direction,
            "confidence": confidence,
            "reasoning": reasoning,
            "key_factors": factors,
            "price_target": None,
            "stop_loss": None,
            "time_horizon": "short",
        })
