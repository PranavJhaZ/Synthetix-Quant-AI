# core/orchestrator.py
"""
Synthetix Quant AI — Orchestrator (GroupChat Manager)
Runs the full agent debate and coordinates all agents.

AutoGen mapping:
    Orchestrator    →  autogen.GroupChatManager
    run_analysis()  →  groupchat.initiate_chat()
    debate loop     →  GroupChat message passing
"""

import time
from datetime import datetime
from core.signal import AgentSignal, MarketSnapshot, TradeDecision
from agents.fundamental_analyst import FundamentalAnalyst
from agents.technical_analyst import TechnicalAnalyst
from agents.sentiment_analyst import SentimentAnalyst
from agents.risk_manager import RiskManager
from agents.portfolio_manager import PortfolioManager
from tools.indicators import compute_all_indicators
from config.settings import TRADING_CONFIG


class Orchestrator:
    """
    The Orchestrator manages the full agent debate lifecycle:

    Phase 1 — Data Enrichment
        Compute technical indicators on the snapshot.

    Phase 2 — Independent Analysis (Round 1)
        Each analyst agent runs independently.
        No agent sees another's output yet.
        This prevents anchoring bias.

    Phase 3 — Debate (Round 2)
        Agents see each other's signals.
        They can reinforce or push back.
        The Risk Manager evaluates the emerging consensus.

    Phase 4 — Final Decision
        Portfolio Manager weighs all signals with their weights.
        Issues the final TradeDecision with position sizing.

    AutoGen note: In production, each Phase maps to a GroupChat round.
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.fundamental = FundamentalAnalyst()
        self.technical = TechnicalAnalyst()
        self.sentiment = SentimentAnalyst()
        self.risk = RiskManager()
        self.pm = PortfolioManager()
        self.debate_transcript: list[str] = []

    def run_analysis(self, snapshot: MarketSnapshot) -> TradeDecision:
        """
        Full pipeline: data → debate → decision.
        This is the main entry point.
        """
        self._log("=" * 60)
        self._log(f"SYNTHETIX QUANT AI — Trading Desk")
        self._log(f"Analyzing: {snapshot.ticker} @ {snapshot.exchange}")
        self._log(f"Current Price: {snapshot.current_price}")
        self._log(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self._log("=" * 60)

        # Phase 1: Enrich snapshot with indicators
        self._log("\n[PHASE 1] Computing technical indicators...")
        snapshot.indicators = compute_all_indicators(snapshot.ohlcv)
        self._log(f"  RSI(14): {snapshot.indicators.get('rsi_14', 'N/A')}")
        self._log(f"  MACD: {snapshot.indicators.get('macd', {}).get('crossover', 'N/A')}")
        self._log(f"  Volume Trend: {snapshot.indicators.get('volume_trend', 'N/A')}")

        # Phase 2: Independent analysis
        self._log("\n[PHASE 2] Independent Agent Analysis...")
        self._transcript("=== ROUND 1: INDEPENDENT ANALYSIS ===")

        fundamental_signal = self._run_agent("Fundamental Analyst", self.fundamental, snapshot)
        technical_signal = self._run_agent("Technical Analyst", self.technical, snapshot)
        sentiment_signal = self._run_agent("Sentiment Analyst", self.sentiment, snapshot)

        round1_signals = [fundamental_signal, technical_signal, sentiment_signal]

        # Phase 3: Debate
        self._log("\n[PHASE 3] Agent Debate...")
        self._transcript("\n=== ROUND 2: DEBATE ===")
        self._run_debate(round1_signals, snapshot)

        # Risk Manager evaluates consensus
        self._log("\n[PHASE 3b] Risk Manager evaluating consensus...")
        self._transcript("\n=== RISK MANAGER EVALUATION ===")
        risk_signal, position_sizing = self.risk.evaluate_consensus(snapshot, round1_signals)
        self._display_signal("Risk Manager", risk_signal)
        self._transcript(
            f"[RiskManager] {risk_signal.reasoning}\n"
            f"  Position: {position_sizing.get('position_pct', 0):.1%} | "
            f"  Stop: {position_sizing.get('stop_loss')} | "
            f"  Target: {position_sizing.get('take_profit')} | "
            f"  R/R: {position_sizing.get('risk_reward')}x"
        )

        all_signals = round1_signals + [risk_signal]

        # Phase 4: Final decision
        self._log("\n[PHASE 4] Portfolio Manager making final decision...")
        self._transcript("\n=== FINAL DECISION ===")

        decision = self.pm.make_final_decision(
            snapshot, all_signals, position_sizing, self.debate_transcript
        )

        self._print_final_decision(decision)
        return decision

    def _run_agent(self, name: str, agent, snapshot: MarketSnapshot) -> AgentSignal:
        """Run a single agent and log its output."""
        self._log(f"\n  → {name} analyzing...")
        start = time.time()
        signal = agent.analyze(snapshot)
        elapsed = time.time() - start
        self._display_signal(name, signal)
        self._transcript(
            f"[{name}] {signal.direction.value} ({signal.confidence:.0%}): {signal.reasoning}"
        )
        return signal

    def _run_debate(self, signals: list[AgentSignal], snapshot: MarketSnapshot):
        """
        Simulate a debate round where agents respond to each other.
        In AutoGen, this would be GroupChat.run().
        """
        agents = [self.fundamental, self.technical, self.sentiment]
        for agent, signal in zip(agents, signals):
            other_signals = [s for s in signals if s.source != signal.source]
            response = agent.respond_to_debate(other_signals, signal, snapshot)
            self._log(f"  {response}")
            self._transcript(response)

    def _display_signal(self, name: str, signal: AgentSignal):
        """Pretty-print a signal to console."""
        direction_colors = {
            "BUY": "📈", "STRONG_BUY": "🚀",
            "SELL": "📉", "STRONG_SELL": "💀",
            "HOLD": "⏸️ ",
        }
        emoji = direction_colors.get(signal.direction.value, "❓")
        bar = "█" * int(signal.confidence * 10) + "░" * (10 - int(signal.confidence * 10))

        self._log(f"\n  ┌─ {name} ─────────────────────────")
        self._log(f"  │  {emoji} {signal.direction.value} | [{bar}] {signal.confidence:.0%}")
        self._log(f"  │  {signal.reasoning[:80]}{'...' if len(signal.reasoning) > 80 else ''}")
        for factor in signal.key_factors[:3]:
            self._log(f"  │  • {factor}")
        self._log(f"  └─────────────────────────────────")

    def _print_final_decision(self, decision: TradeDecision):
        """Print the final trade decision in a structured format."""
        self._log("\n" + "═" * 60)
        self._log("FINAL TRADE DECISION")
        self._log("═" * 60)

        icons = {
            "BUY": "✅ BUY", "STRONG_BUY": "🚀 STRONG BUY",
            "SELL": "🔴 SELL", "STRONG_SELL": "💀 STRONG SELL",
            "HOLD": "⏸️  HOLD — No trade",
        }
        self._log(f"  Decision:    {icons.get(decision.direction.value, decision.direction.value)}")
        self._log(f"  Confidence:  {'█' * int(decision.confidence * 10)}{'░' * (10 - int(decision.confidence * 10))} {decision.confidence:.0%}")
        self._log(f"  Consensus:   {decision.consensus_score:.0%}")

        if decision.direction.value != "HOLD":
            self._log(f"\n  ── Position Sizing ──────────────────")
            self._log(f"  Size:        {decision.position_size_pct:.1%} of portfolio")
            self._log(f"  Value:       ₹{decision.position_size_value:,.0f}")
            self._log(f"  Entry:       {decision.entry_price}")
            self._log(f"  Stop Loss:   {decision.stop_loss}  (-{abs(decision.entry_price - decision.stop_loss) / decision.entry_price:.1%})")
            self._log(f"  Take Profit: {decision.take_profit}  (+{abs(decision.take_profit - decision.entry_price) / decision.entry_price:.1%})")
            self._log(f"  R/R Ratio:   {decision.risk_reward_ratio:.1f}x")

        if decision.dissent_agents:
            self._log(f"\n  ⚠️  Dissenting agents: {', '.join(decision.dissent_agents)}")

        self._log(f"\n  Reasoning: {decision.final_reasoning}")
        self._log("═" * 60)

        self._transcript(
            f"\n[PortfolioManager] FINAL: {decision.direction.value} | "
            f"{decision.confidence:.0%} confidence | {decision.final_reasoning}"
        )

    def _transcript(self, msg: str):
        self.debate_transcript.append(msg)

    def _log(self, msg: str):
        if self.verbose:
            print(msg)
