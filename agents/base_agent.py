# agents/base_agent.py
"""
Synthetix Quant AI — Base Agent
All agents inherit from this class.

AutoGen note: In production, replace BaseAgent with autogen.AssistantAgent.
The analyze() method becomes a tool function registered with AutoGen.
The _build_prompt() output becomes the system_message.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from core.signal import AgentSignal, MarketSnapshot, SignalSource, Direction
from config.settings import AgentConfig, LLMConfig, LLM_CONFIG
import json
import os


class BaseAgent(ABC):
    """
    Abstract base class for all Synthetix Quant AI agents.

    AutoGen mapping:
        BaseAgent       →  autogen.AssistantAgent
        analyze()       →  registered tool function
        _build_prompt() →  system_message parameter
        respond()       →  agent.generate_reply()
    """

    def __init__(self, config: AgentConfig, llm_config: LLMConfig = None):
        self.config = config
        self.llm_config = llm_config or LLM_CONFIG
        self.name = config.name
        self.role = config.role
        self._message_history: list[dict] = []
        self._last_signal: AgentSignal | None = None

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    def analyze(self, snapshot: MarketSnapshot) -> AgentSignal:
        """
        Primary analysis method. Each agent implements this differently.
        Returns an AgentSignal with direction, confidence, and reasoning.
        """
        ...

    @abstractmethod
    def _build_prompt(self, snapshot: MarketSnapshot) -> str:
        """
        Builds the data-rich prompt to send to the LLM.
        Each agent focuses on its domain of expertise.
        """
        ...

    # ── LLM calling ──────────────────────────────────────────────────────────

    def _call_llm(self, prompt: str) -> str:
        """
        Calls the configured LLM provider.
        Falls back to rule-based mock if no API key is available.

        AutoGen note: In production, AutoGen handles all LLM calls.
        This method is for standalone operation.
        """
        api_key = (
            self.llm_config.api_key
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
        )

        if not api_key or self.llm_config.provider == "mock":
            return self._mock_llm_response(prompt)

        if self.llm_config.provider == "anthropic":
            return self._call_anthropic(prompt, api_key)
        elif self.llm_config.provider == "openai":
            return self._call_openai(prompt, api_key)

        return self._mock_llm_response(prompt)

    def _call_anthropic(self, prompt: str, api_key: str) -> str:
        """Call Anthropic Claude API."""
        try:
            import urllib.request
            payload = {
                "model": self.llm_config.model,
                "max_tokens": self.llm_config.max_tokens,
                "temperature": self.llm_config.temperature,
                "system": self._system_message(),
                "messages": [{"role": "user", "content": prompt}],
            }
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps(payload).encode(),
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                return data["content"][0]["text"]
        except Exception as e:
            print(f"[{self.name}] LLM call failed: {e}. Using rule-based fallback.")
            return self._mock_llm_response(prompt)

    def _call_openai(self, prompt: str, api_key: str) -> str:
        """Call OpenAI API."""
        try:
            import urllib.request
            payload = {
                "model": "gpt-4o-mini",
                "max_tokens": self.llm_config.max_tokens,
                "temperature": self.llm_config.temperature,
                "messages": [
                    {"role": "system", "content": self._system_message()},
                    {"role": "user", "content": prompt},
                ],
            }
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps(payload).encode(),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[{self.name}] LLM call failed: {e}. Using rule-based fallback.")
            return self._mock_llm_response(prompt)

    @abstractmethod
    def _mock_llm_response(self, prompt: str) -> str:
        """
        Rule-based fallback when no API key is present.
        Each agent implements its own logic.
        Makes the system fully functional offline.
        """
        ...

    def _system_message(self) -> str:
        return (
            f"You are {self.name}, a specialized AI agent in the Synthetix Quant AI trading system.\n"
            f"Your role: {self.role}\n\n"
            "Respond ONLY with valid JSON. No markdown, no preamble.\n"
            "Your JSON must contain: direction, confidence (0.0-1.0), reasoning (string), "
            "key_factors (list of 3-5 strings), price_target (float or null), "
            "stop_loss (float or null), time_horizon (string)."
        )

    # ── Parsing LLM output ────────────────────────────────────────────────────

    def _parse_llm_output(
        self,
        raw: str,
        snapshot: MarketSnapshot,
        source: SignalSource,
    ) -> AgentSignal:
        """
        Parses JSON from LLM output into a typed AgentSignal.
        Handles malformed responses gracefully.
        """
        try:
            # Strip markdown fences if present
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            data = json.loads(cleaned.strip())

            direction_map = {
                "BUY": Direction.BUY,
                "SELL": Direction.SELL,
                "HOLD": Direction.HOLD,
                "STRONG_BUY": Direction.STRONG_BUY,
                "STRONG_SELL": Direction.STRONG_SELL,
            }
            direction = direction_map.get(
                data.get("direction", "HOLD").upper(), Direction.HOLD
            )
            confidence = float(data.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))

            return AgentSignal(
                source=source,
                direction=direction,
                confidence=confidence,
                reasoning=data.get("reasoning", "No reasoning provided."),
                key_factors=data.get("key_factors", []),
                price_target=data.get("price_target"),
                stop_loss=data.get("stop_loss"),
                time_horizon=data.get("time_horizon", "short"),
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"[{self.name}] Parse error: {e}. Raw: {raw[:100]}")
            return self._fallback_signal(snapshot, source)

    def _fallback_signal(self, snapshot: MarketSnapshot, source: SignalSource) -> AgentSignal:
        """Emergency fallback if both LLM and parsing fail."""
        return AgentSignal(
            source=source,
            direction=Direction.HOLD,
            confidence=0.3,
            reasoning="Analysis inconclusive — insufficient data.",
            key_factors=["Data quality issue", "Using conservative HOLD"],
        )

    # ── Debate participation ──────────────────────────────────────────────────

    def respond_to_debate(
        self,
        other_signals: list[AgentSignal],
        my_signal: AgentSignal,
        snapshot: MarketSnapshot,
    ) -> str:
        """
        Called during the debate round.
        Agent can reinforce or modify their view based on others' arguments.

        AutoGen note: In production, this becomes part of the GroupChat message flow.
        """
        disagreements = [
            s for s in other_signals
            if s.direction != my_signal.direction and s.source != my_signal.source
        ]

        if not disagreements:
            return (
                f"[{self.name}] I maintain my {my_signal.direction.value} signal "
                f"at {my_signal.confidence:.0%} confidence. "
                f"My key concern: {my_signal.key_factors[0] if my_signal.key_factors else 'N/A'}"
            )

        dissenter = disagreements[0]
        return (
            f"[{self.name}] I acknowledge {dissenter.source.value}'s "
            f"{dissenter.direction.value} view, but my {my_signal.source.value} "
            f"analysis shows {my_signal.direction.value}. "
            f"Specifically: {my_signal.reasoning[:120]}..."
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name}>"
