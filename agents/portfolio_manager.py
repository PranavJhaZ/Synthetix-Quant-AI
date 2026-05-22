# agents/portfolio_manager.py
"""
Synthetix Quant AI — Portfolio Manager Agent
Final arbitrator. Weighs all agent signals and makes the trade decision.
"""

import json
from agents.base_agent import BaseAgent
from core.signal import AgentSignal, MarketSnapshot, SignalSource, Direction, TradeDecision
from config.settings import AGENT_CONFIGS, TRADING_CONFIG


class PortfolioManager(BaseAgent):
    """
    The Portfolio Manager is the only agent who sees ALL other agents' outputs.
    It acts as the senior PM who runs the morning meeting, listens to all
    analysts debate, then makes the final call.

    Decision logic:
    1. Weight signals by confidence and historical accuracy
    2. Check if Risk Manager has vetoed
    3. Require minimum consensus threshold
    4. Make final BUY/SELL/HOLD with exact size
    """

    # Weights for each agent's signal in the final decision
    SIGNAL_WEIGHTS = {
        SignalSource.FUNDAMENTAL: 0.30,
        SignalSource.TECHNICAL: 0.30,
        SignalSource.SENTIMENT: 0.15,
        SignalSource.RISK: 0.25,    # Risk manager has significant weight
    }

    def __init__(self):
        super().__init__(config=AGENT_CONFIGS["portfolio"])

    def analyze(self, snapshot: MarketSnapshot) -> AgentSignal:
        """Simple standalone analysis — not typically called directly."""
        return AgentSignal(
            source=SignalSource.PORTFOLIO,
            direction=Direction.HOLD,
            confidence=0.5,
            reasoning="Portfolio Manager requires peer signals to make a decision.",
            key_factors=["Awaiting agent debate completion"],
        )

    def make_final_decision(
        self,
        snapshot: MarketSnapshot,
        all_signals: list[AgentSignal],
        position_sizing: dict,
        debate_transcript: list[str],
    ) -> TradeDecision:
        """
        PRIMARY method: Makes the final trade decision after full agent debate.

        This mirrors what a real portfolio manager does:
        - Reads every analyst's report
        - Weighs their arguments by expertise
        - Makes a final call with clear conviction or stays out
        """
        # Check for Risk Manager veto first
        risk_signals = [s for s in all_signals if s.source == SignalSource.RISK]
        if risk_signals and position_sizing.get("vetoed"):
            return self._build_decision(
                snapshot, Direction.HOLD, 0.30, all_signals,
                position_sizing, debate_transcript,
                f"Risk Manager veto: {position_sizing.get('veto_reason', 'Risk limits exceeded')}",
            )

        # Compute weighted score for each direction
        direction_scores = {}
        for signal in all_signals:
            if signal.source == SignalSource.PORTFOLIO:
                continue
            weight = self.SIGNAL_WEIGHTS.get(signal.source, 0.20)
            weighted_confidence = signal.confidence * weight

            # Normalize direction (STRONG_BUY → BUY, STRONG_SELL → SELL)
            direction_key = self._normalize_direction(signal.direction)

            if direction_key not in direction_scores:
                direction_scores[direction_key] = 0.0
            direction_scores[direction_key] += weighted_confidence

        # Determine final direction
        if not direction_scores:
            final_direction = Direction.HOLD
            final_confidence = 0.30
        else:
            best_dir = max(direction_scores, key=direction_scores.get)
            final_confidence = direction_scores[best_dir]
            # Minimum confidence to trade
            if final_confidence < 0.25 or best_dir == "HOLD":
                final_direction = Direction.HOLD
                final_confidence = max(final_confidence, 0.40)
            else:
                # Check for STRONG signal (overwhelming consensus)
                total_score = sum(direction_scores.values())
                if total_score > 0:
                    dominance = direction_scores[best_dir] / total_score
                    if dominance > 0.80 and final_confidence > 0.55:
                        final_direction = Direction.STRONG_BUY if best_dir == "BUY" else Direction.STRONG_SELL if best_dir == "SELL" else Direction(best_dir)
                    else:
                        final_direction = Direction(best_dir)
                else:
                    final_direction = Direction.HOLD

        # Cap confidence
        final_confidence = min(final_confidence, 0.92)

        # Build reasoning
        reasoning = self._build_reasoning(
            final_direction, final_confidence, all_signals, direction_scores, position_sizing
        )

        return self._build_decision(
            snapshot, final_direction, final_confidence, all_signals,
            position_sizing, debate_transcript, reasoning,
        )

    def _normalize_direction(self, direction: Direction) -> str:
        mapping = {
            Direction.STRONG_BUY: "BUY",
            Direction.BUY: "BUY",
            Direction.HOLD: "HOLD",
            Direction.SELL: "SELL",
            Direction.STRONG_SELL: "SELL",
        }
        return mapping.get(direction, "HOLD")

    def _build_reasoning(
        self,
        direction: Direction,
        confidence: float,
        signals: list[AgentSignal],
        scores: dict,
        sizing: dict,
    ) -> str:
        parts = []
        aligned = [s for s in signals if self._normalize_direction(s.direction) == self._normalize_direction(direction) and s.source != SignalSource.PORTFOLIO]
        dissenting = [s for s in signals if self._normalize_direction(s.direction) != self._normalize_direction(direction) and s.source not in (SignalSource.PORTFOLIO, SignalSource.RISK)]

        if direction == Direction.HOLD:
            parts.append("Insufficient conviction for a trade at this time.")
            if dissenting:
                parts.append(f"Agents are split — no clear edge identified.")
        else:
            parts.append(f"Final decision: {direction.value} with {confidence:.0%} conviction.")
            if aligned:
                names = [s.source.value for s in aligned]
                parts.append(f"Supported by: {', '.join(names)}.")
            if dissenting:
                names = [s.source.value for s in dissenting]
                parts.append(f"Note: {', '.join(names)} disagree — position sized conservatively.")

        if sizing.get("risk_reward"):
            parts.append(f"R/R: {sizing['risk_reward']:.1f}x.")

        return " ".join(parts)

    def _build_decision(
        self,
        snapshot: MarketSnapshot,
        direction: Direction,
        confidence: float,
        signals: list[AgentSignal],
        sizing: dict,
        transcript: list[str],
        reasoning: str,
    ) -> TradeDecision:
        entry = sizing.get("entry_price", snapshot.current_price)
        stop = sizing.get("stop_loss", entry * 0.95)
        tp = sizing.get("take_profit", entry * 1.10)
        rr = sizing.get("risk_reward", 2.0)
        pos_pct = sizing.get("position_pct", 0.05) if direction != Direction.HOLD else 0.0
        pos_val = sizing.get("position_value", 0.0) if direction != Direction.HOLD else 0.0

        dissent = [
            s.source.value for s in signals
            if self._normalize_direction(s.direction) != self._normalize_direction(direction)
            and s.source != SignalSource.PORTFOLIO
        ]

        return TradeDecision(
            ticker=snapshot.ticker,
            exchange=snapshot.exchange,
            direction=direction,
            confidence=confidence,
            position_size_pct=pos_pct,
            position_size_value=pos_val,
            entry_price=entry,
            stop_loss=stop,
            take_profit=tp,
            risk_reward_ratio=rr,
            signals=signals,
            consensus_score=sizing.get("consensus_score", 0.5),
            dissent_agents=dissent,
            final_reasoning=reasoning,
            debate_transcript=transcript,
        )

    def _build_prompt(self, snapshot: MarketSnapshot) -> str:
        return ""

    def _mock_llm_response(self, prompt: str) -> str:
        return json.dumps({"direction": "HOLD", "confidence": 0.5, "reasoning": "", "key_factors": []})
