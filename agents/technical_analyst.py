# agents/technical_analyst.py
"""
Synthetix Quant AI — Technical Analyst Agent
Reads price action, momentum indicators, and chart patterns.
"""

import json
from agents.base_agent import BaseAgent
from core.signal import AgentSignal, MarketSnapshot, SignalSource, Direction
from config.settings import AGENT_CONFIGS


class TechnicalAnalyst(BaseAgent):
    """
    Analyzes: RSI, MACD, Bollinger Bands, ATR, moving averages,
    volume trends, price momentum, support/resistance levels.

    Bullish signals: RSI recovering from oversold, MACD bullish crossover,
                     price above SMA20/50, increasing volume.
    Bearish signals: RSI overbought, MACD death cross, price below key MAs,
                     declining volume on rallies.
    """

    def __init__(self):
        super().__init__(config=AGENT_CONFIGS["technical"])

    def analyze(self, snapshot: MarketSnapshot) -> AgentSignal:
        # Compute indicators if not already done
        if not snapshot.indicators:
            from tools.indicators import compute_all_indicators
            snapshot.indicators = compute_all_indicators(snapshot.ohlcv)

        prompt = self._build_prompt(snapshot)
        raw = self._call_llm(prompt)
        signal = self._parse_llm_output(raw, snapshot, SignalSource.TECHNICAL)
        self._last_signal = signal
        return signal

    def _build_prompt(self, snapshot: MarketSnapshot) -> str:
        ind = snapshot.indicators
        pos = ind.get("price_position", {})
        macd = ind.get("macd", {})
        bb = ind.get("bollinger", {})
        mom = ind.get("momentum", {})
        sigs = ind.get("signals_summary", {})

        # Format signal summary
        sig_lines = "\n".join(
            f"  - {k.upper()}: {v.get('signal', 'N/A')} — {v.get('note', '')}"
            for k, v in sigs.items()
        )

        return f"""
You are the Technical Analyst for {snapshot.ticker} ({snapshot.exchange}).
Current Price: {snapshot.current_price}

## Price Position
- 60-day High: {pos.get('period_high', 'N/A')} | 60-day Low: {pos.get('period_low', 'N/A')}
- % from High: {pos.get('pct_from_high', 'N/A')}% | % from Low: {pos.get('pct_from_low', 'N/A')}%
- Above SMA20: {pos.get('above_sma20', 'N/A')} | Above SMA50: {pos.get('above_sma50', 'N/A')}
- SMA20: {pos.get('sma_20', 'N/A')} | SMA50: {pos.get('sma_50', 'N/A')}

## Momentum Indicators
- RSI(14): {ind.get('rsi_14', 'N/A')}  [<30 oversold | >70 overbought]
- MACD Line: {macd.get('line', 'N/A')} | Signal: {macd.get('signal', 'N/A')} | Histogram: {macd.get('histogram', 'N/A')}
- MACD Crossover: {macd.get('crossover', 'N/A')}
- 5-Day Return: {mom.get('5d_pct', 'N/A')}%
- 20-Day Return: {mom.get('20d_pct', 'N/A')}%

## Volatility & Volume
- Bollinger %B: {bb.get('pct_b', 'N/A')}  [0=lower band | 1=upper band]
- BB Upper: {bb.get('upper', 'N/A')} | Middle: {bb.get('middle', 'N/A')} | Lower: {bb.get('lower', 'N/A')}
- ATR(14): {ind.get('atr_14', 'N/A')}  [measures volatility]
- Volume Trend: {ind.get('volume_trend', 'N/A')}

## Pre-computed Signal Summary
{sig_lines}

## Your Task
Analyze the technical setup and give a BUY/SELL/HOLD signal.
Consider: trend direction, momentum strength, overbought/oversold conditions,
volume confirmation, and nearest support/resistance levels.

Respond ONLY with JSON:
{{
  "direction": "BUY" | "SELL" | "HOLD" | "STRONG_BUY" | "STRONG_SELL",
  "confidence": 0.0 to 1.0,
  "reasoning": "2-3 sentence technical view",
  "key_factors": ["factor 1", "factor 2", "factor 3"],
  "price_target": nearest resistance level as price target or null,
  "stop_loss": nearest support level as stop loss or null,
  "time_horizon": "intraday" or "short"
}}
"""

    def _mock_llm_response(self, prompt: str) -> str:
        """Rule-based technical analysis."""
        # Parse key indicators from prompt
        bullish_signals = 0
        bearish_signals = 0
        total_signals = 0

        for line in prompt.split("\n"):
            if "BULLISH" in line:
                bullish_signals += 1
                total_signals += 1
            elif "BEARISH" in line:
                bearish_signals += 1
                total_signals += 1
            elif "NEUTRAL" in line or "MILDLY_BULLISH" in line:
                total_signals += 1
                if "MILDLY_BULLISH" in line:
                    bullish_signals += 0.5

        # RSI special handling
        rsi_val = None
        try:
            for line in prompt.split("\n"):
                if "RSI(14):" in line:
                    val_str = line.split("RSI(14):")[1].strip().split()[0]
                    rsi_val = float(val_str)
                    break
        except (ValueError, IndexError):
            pass

        # Determine direction
        if rsi_val and rsi_val < 32:
            direction = "STRONG_BUY"
            confidence = 0.78
            reasoning = (
                f"RSI at {rsi_val:.1f} is deeply oversold, suggesting capitulation selling. "
                "High-probability mean-reversion setup. Watch for volume confirmation."
            )
            factors = [
                f"RSI {rsi_val:.1f} — extreme oversold territory",
                "Mean-reversion setup with positive risk/reward",
                "Price likely near short-term support",
            ]
        elif rsi_val and rsi_val > 72:
            direction = "SELL"
            confidence = 0.72
            reasoning = (
                f"RSI at {rsi_val:.1f} signals overbought conditions. "
                "Momentum exhaustion likely. Consider taking profits or waiting for pullback."
            )
            factors = [
                f"RSI {rsi_val:.1f} — overbought, expect consolidation",
                "Price stretched above moving averages",
                "Risk/reward unfavorable for new longs here",
            ]
        elif total_signals > 0 and (bullish_signals / max(total_signals, 1)) > 0.6:
            direction = "BUY"
            confidence = 0.63 + (bullish_signals / max(total_signals, 1)) * 0.15
            reasoning = (
                f"{int(bullish_signals)}/{total_signals} technical indicators are bullish. "
                "MACD and momentum align — trend is your friend."
            )
            factors = [
                "Multiple indicators aligned bullish",
                "Price trading above key moving averages",
                "Volume confirming price strength",
            ]
        elif total_signals > 0 and (bearish_signals / max(total_signals, 1)) > 0.6:
            direction = "SELL"
            confidence = 0.60
            reasoning = (
                "Majority of technical indicators are bearish. "
                "Trend and momentum are both negative — avoid longs."
            )
            factors = [
                "Multiple indicators aligned bearish",
                "Price below key moving averages",
                "Momentum negative — no base forming yet",
            ]
        else:
            direction = "HOLD"
            confidence = 0.52
            reasoning = (
                "Mixed technical signals — no clear directional edge. "
                "Market in consolidation. Wait for breakout or breakdown."
            )
            factors = [
                "Indicators mixed — no clear trend",
                "Price in consolidation range",
                "Await confirmation before entering",
            ]

        return json.dumps({
            "direction": direction,
            "confidence": min(confidence, 0.88),
            "reasoning": reasoning,
            "key_factors": factors,
            "price_target": None,
            "stop_loss": None,
            "time_horizon": "short",
        })
