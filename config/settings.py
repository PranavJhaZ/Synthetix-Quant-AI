# config/settings.py
"""
Synthetix Quant AI — Central Configuration
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentConfig:
    name: str
    role: str
    confidence_threshold: float = 0.6
    max_debate_rounds: int = 3


@dataclass
class RiskConfig:
    max_position_pct: float = 0.10
    max_drawdown_pct: float = 0.15
    max_portfolio_risk: float = 0.20
    min_risk_reward_ratio: float = 2.0
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.12


@dataclass
class TradingConfig:
    default_exchange: str = "NSE"
    default_ticker: str = "RELIANCE"
    portfolio_value: float = 1_000_000.0
    currency: str = "INR"
    debate_rounds: int = 2


@dataclass
class LLMConfig:
    provider: str = "openai"                # ← using OpenAI
    model: str = "gpt-4o-mini"              # cheap, fast, very capable
    api_key: Optional[str] = None           # auto-read from env below
    max_tokens: int = 1000
    temperature: float = 0.3


# ── Instantiated configs ──────────────────────────────────────────────────────

RISK_CONFIG = RiskConfig()
TRADING_CONFIG = TradingConfig()

# Auto-reads OPENAI_API_KEY from environment — no hardcoding needed
LLM_CONFIG = LLMConfig(
    api_key=os.environ.get("OPENAI_API_KEY")
)

AGENT_CONFIGS = {
    "fundamental": AgentConfig(
        name="FundamentalAnalyst",
        role="Evaluates company financials, valuation ratios, and intrinsic value",
        confidence_threshold=0.55,
    ),
    "technical": AgentConfig(
        name="TechnicalAnalyst",
        role="Reads price action, momentum indicators, and chart patterns",
        confidence_threshold=0.60,
    ),
    "sentiment": AgentConfig(
        name="SentimentAnalyst",
        role="Scores market sentiment from news, events, and macro context",
        confidence_threshold=0.50,
    ),
    "risk": AgentConfig(
        name="RiskManager",
        role="Enforces position sizing, drawdown limits, and portfolio risk",
        confidence_threshold=0.70,
    ),
    "portfolio": AgentConfig(
        name="PortfolioManager",
        role="Final arbitrator — weighs all signals and makes the trade decision",
        confidence_threshold=0.65,
    ),
}
