# core/signal.py
"""
Synthetix Quant AI — Core Data Models
All inter-agent communication uses these typed structures.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Direction(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    STRONG_BUY = "STRONG_BUY"
    STRONG_SELL = "STRONG_SELL"


class SignalSource(Enum):
    FUNDAMENTAL = "FUNDAMENTAL"
    TECHNICAL = "TECHNICAL"
    SENTIMENT = "SENTIMENT"
    RISK = "RISK"
    PORTFOLIO = "PORTFOLIO"


@dataclass
class AgentSignal:
    """
    What each agent returns after analysis.
    This is the unit of communication between agents.
    """
    source: SignalSource
    direction: Direction
    confidence: float            # 0.0 to 1.0
    reasoning: str               # Plain English explanation
    key_factors: list[str]       # 2-5 bullet points
    timestamp: datetime = field(default_factory=datetime.now)

    # Optional numeric outputs
    price_target: Optional[float] = None
    stop_loss: Optional[float] = None
    time_horizon: str = "short"  # "intraday" | "short" | "medium" | "long"

    def to_dict(self) -> dict:
        return {
            "source": self.source.value,
            "direction": self.direction.value,
            "confidence": round(self.confidence, 3),
            "reasoning": self.reasoning,
            "key_factors": self.key_factors,
            "price_target": self.price_target,
            "stop_loss": self.stop_loss,
            "time_horizon": self.time_horizon,
            "timestamp": self.timestamp.isoformat(),
        }

    def __str__(self) -> str:
        bar = "█" * int(self.confidence * 10) + "░" * (10 - int(self.confidence * 10))
        return (
            f"[{self.source.value}] {self.direction.value} | "
            f"Confidence: {bar} {self.confidence:.0%}\n"
            f"  → {self.reasoning}"
        )


@dataclass
class TradeDecision:
    """
    Final output from the PortfolioManager after the full debate.
    This is what gets sent to execution (or displayed to user).
    """
    ticker: str
    exchange: str
    direction: Direction
    confidence: float
    position_size_pct: float        # % of portfolio to allocate
    position_size_value: float      # In currency
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward_ratio: float

    # Debate summary
    signals: list[AgentSignal] = field(default_factory=list)
    consensus_score: float = 0.0    # How much agents agreed (0-1)
    dissent_agents: list[str] = field(default_factory=list)  # Who disagreed
    final_reasoning: str = ""
    debate_transcript: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "exchange": self.exchange,
            "direction": self.direction.value,
            "confidence": round(self.confidence, 3),
            "position": {
                "size_pct": round(self.position_size_pct, 4),
                "size_value": round(self.position_size_value, 2),
            },
            "levels": {
                "entry": round(self.entry_price, 2),
                "stop_loss": round(self.stop_loss, 2),
                "take_profit": round(self.take_profit, 2),
                "risk_reward": round(self.risk_reward_ratio, 2),
            },
            "meta": {
                "consensus_score": round(self.consensus_score, 3),
                "dissent_agents": self.dissent_agents,
                "final_reasoning": self.final_reasoning,
            },
            "signals": [s.to_dict() for s in self.signals],
            "debate_transcript": self.debate_transcript,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MarketSnapshot:
    """
    Standardized market data passed to all agents.
    Single source of truth — all agents see the same data.
    """
    ticker: str
    exchange: str
    current_price: float
    timestamp: datetime

    # OHLCV history (list of dicts, newest last)
    ohlcv: list[dict] = field(default_factory=list)

    # Computed indicators (filled by tools/indicators.py)
    indicators: dict = field(default_factory=dict)

    # Fundamental data
    fundamentals: dict = field(default_factory=dict)

    # News / sentiment data
    news: list[dict] = field(default_factory=list)
    sentiment_score: float = 0.0   # -1.0 (bearish) to +1.0 (bullish)
