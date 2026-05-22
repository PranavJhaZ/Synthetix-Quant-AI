# agents/risk_manager.py
"""
Synthetix Quant AI — Risk Manager Agent
Enforces position sizing, drawdown limits, and portfolio risk.
The Risk Manager is the only agent that can VETO a trade.
"""

import json
from agents.base_agent import BaseAgent
from core.signal import AgentSignal, MarketSnapshot, SignalSource, Direction
from config.settings import AGENT_CONFIGS, RISK_CONFIG, TRADING_CONFIG


class RiskManager(BaseAgent):
    """
    The Risk Manager is different from other agents:
    - It receives the OTHER agents' signals as INPUT
    - It decides whether the consensus signal is SAFE to act on
    - It computes exact position size, stop loss, take profit
    - It can issue a HOLD even if all others say BUY (veto power)

    This mirrors real trading desks: risk management is independent
    and has final say on position sizing and risk limits.
    """

    def __init__(self):
        super().__init__(config=AGENT_CONFIGS["risk"])
        self.portfolio_value = TRADING_CONFIG.portfolio_value
        self.risk_config = RISK_CONFIG

    def analyze(self, snapshot: MarketSnapshot) -> AgentSignal:
        """Standalone risk analysis without peer signals."""
        prompt = self._build_prompt(snapshot)
        raw = self._call_llm(prompt)
        signal = self._parse_llm_output(raw, snapshot, SignalSource.RISK)
        self._last_signal = signal
        return signal

    def evaluate_consensus(
        self,
        snapshot: MarketSnapshot,
        peer_signals: list[AgentSignal],
    ) -> tuple[AgentSignal, dict]:
        """
        PRIMARY method: Evaluates peer signals and decides risk parameters.
        Returns (risk_signal, position_sizing_dict).

        This is called by the Orchestrator after collecting all peer signals.
        """
        # Tally peer votes
        direction_votes = {}
        total_confidence = 0.0
        for sig in peer_signals:
            d = sig.direction.value
            direction_votes[d] = direction_votes.get(d, 0) + sig.confidence
            total_confidence += sig.confidence

        # Find dominant direction
        if direction_votes:
            dominant = max(direction_votes, key=direction_votes.get)
            consensus_confidence = direction_votes.get(dominant, 0) / max(len(peer_signals), 1)
        else:
            dominant = "HOLD"
            consensus_confidence = 0.3

        # Compute consensus_score (0-1: how aligned are agents?)
        max_votes = max(direction_votes.values()) if direction_votes else 0
        consensus_score = max_votes / max(total_confidence, 1)

        # Compute risk metrics
        atr = snapshot.indicators.get("atr_14") if snapshot.indicators else None
        current_price = snapshot.current_price

        # Position sizing: Kelly-inspired, scaled by confidence
        base_pct = self.risk_config.max_position_pct
        adjusted_pct = base_pct * consensus_confidence * consensus_score
        adjusted_pct = max(0.02, min(adjusted_pct, self.risk_config.max_position_pct))
        position_value = self.portfolio_value * adjusted_pct

        # Stop loss and take profit
        if atr:
            stop_distance = atr * 2.0  # 2 ATR stop
            tp_distance = stop_distance * self.risk_config.min_risk_reward_ratio
        else:
            stop_distance = current_price * self.risk_config.stop_loss_pct
            tp_distance = current_price * self.risk_config.take_profit_pct

        if dominant in ("BUY", "STRONG_BUY"):
            stop_loss = round(current_price - stop_distance, 2)
            take_profit = round(current_price + tp_distance, 2)
        elif dominant in ("SELL", "STRONG_SELL"):
            stop_loss = round(current_price + stop_distance, 2)
            take_profit = round(current_price - tp_distance, 2)
        else:
            stop_loss = round(current_price - stop_distance, 2)
            take_profit = round(current_price + tp_distance, 2)

        risk_reward = round(tp_distance / max(stop_distance, 0.01), 2)

        # VETO: if risk/reward < minimum, block the trade
        if risk_reward < self.risk_config.min_risk_reward_ratio and dominant != "HOLD":
            veto = True
            veto_reason = f"R/R ratio {risk_reward:.1f}x below minimum {self.risk_config.min_risk_reward_ratio}x"
        elif consensus_confidence < 0.4 and dominant != "HOLD":
            veto = True
            veto_reason = f"Consensus confidence {consensus_confidence:.0%} too low to enter"
        else:
            veto = False
            veto_reason = None

        direction = Direction.HOLD if veto else Direction(dominant)
        confidence = 0.30 if veto else min(consensus_confidence * 0.9, 0.85)

        if veto:
            reasoning = f"TRADE VETOED: {veto_reason}. Protecting capital."
            factors = [
                f"Veto reason: {veto_reason}",
                f"Peer consensus: {dominant} with {consensus_confidence:.0%} confidence",
                "Risk management overrides directional signals",
            ]
        else:
            reasoning = (
                f"Risk parameters acceptable. Consensus {dominant} with {consensus_confidence:.0%} "
                f"confidence. Position size: {adjusted_pct:.1%} of portfolio. "
                f"R/R: {risk_reward:.1f}x."
            )
            factors = [
                f"Position size: {adjusted_pct:.1%} (₹{position_value:,.0f})",
                f"Stop loss: {stop_loss} | Take profit: {take_profit}",
                f"Risk/reward: {risk_reward:.1f}x — {'acceptable' if risk_reward >= 2 else 'marginal'}",
                f"Agent consensus score: {consensus_score:.0%}",
            ]

        risk_signal = AgentSignal(
            source=SignalSource.RISK,
            direction=direction,
            confidence=confidence,
            reasoning=reasoning,
            key_factors=factors,
            stop_loss=stop_loss,
            price_target=take_profit,
            time_horizon="short",
        )

        position_sizing = {
            "direction": dominant,
            "position_pct": adjusted_pct,
            "position_value": position_value,
            "entry_price": current_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk_reward": risk_reward,
            "consensus_score": round(consensus_score, 3),
            "vetoed": veto,
            "veto_reason": veto_reason,
        }

        return risk_signal, position_sizing

    def _build_prompt(self, snapshot: MarketSnapshot) -> str:
        return f"""
You are the Risk Manager for {snapshot.ticker}.
Assess whether current market conditions present acceptable risk for a new position.

Current Price: {snapshot.current_price}
Portfolio Value: ₹{self.portfolio_value:,.0f}
Max Position: {self.risk_config.max_position_pct:.0%} of portfolio
ATR(14): {snapshot.indicators.get('atr_14', 'N/A') if snapshot.indicators else 'N/A'}

Assess: Is volatility elevated? Is this a liquid, orderly market?
Should we trade with full or reduced position size?

Respond ONLY with JSON with direction (BUY/HOLD), confidence, reasoning, key_factors.
"""

    def _mock_llm_response(self, prompt: str) -> str:
        return json.dumps({
            "direction": "HOLD",
            "confidence": 0.60,
            "reasoning": "Risk parameters evaluated. Await full consensus from peer agents.",
            "key_factors": ["Evaluating peer signals", "Position sizing pending", "Risk limits checked"],
            "price_target": None,
            "stop_loss": None,
            "time_horizon": "short",
        })
