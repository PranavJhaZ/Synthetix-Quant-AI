# agents/fundamental_analyst.py
"""
Synthetix Quant AI — Fundamental Analyst Agent
Evaluates company financials, valuation ratios, and intrinsic value.
"""

import json
from agents.base_agent import BaseAgent
from core.signal import AgentSignal, MarketSnapshot, SignalSource, Direction
from config.settings import AGENT_CONFIGS


class FundamentalAnalyst(BaseAgent):
    """
    Analyzes: P/E ratio, EPS growth, revenue growth, profit margins,
    ROE, debt/equity, free cash flow, valuation vs. sector.

    Bullish signals: Low P/E vs. history, high EPS growth, strong FCF,
                     low debt, expanding margins.
    Bearish signals: High P/E, declining revenue, rising debt, thin margins.
    """

    def __init__(self):
        super().__init__(config=AGENT_CONFIGS["fundamental"])

    def analyze(self, snapshot: MarketSnapshot) -> AgentSignal:
        prompt = self._build_prompt(snapshot)
        raw = self._call_llm(prompt)
        signal = self._parse_llm_output(raw, snapshot, SignalSource.FUNDAMENTAL)
        self._last_signal = signal
        return signal

    def _build_prompt(self, snapshot: MarketSnapshot) -> str:
        f = snapshot.fundamentals
        price = snapshot.current_price

        # Compute derived metrics
        pe = f.get("pe_ratio", "N/A")
        pb = f.get("pb_ratio", "N/A")
        eps_growth = f.get("eps_growth_yoy", "N/A")
        rev_growth = f.get("revenue_growth_yoy", "N/A")
        margin = f.get("profit_margin_pct", "N/A")
        roe = f.get("roe_pct", "N/A")
        de_ratio = f.get("debt_to_equity", "N/A")

        return f"""
You are the Fundamental Analyst for {snapshot.ticker} ({snapshot.exchange}).

## Company: {f.get('company_name', snapshot.ticker)} | Sector: {f.get('sector', 'Unknown')}

## Key Financials
- Current Price: {price}
- P/E Ratio: {pe} (sector average ~25 for large-cap India)
- P/B Ratio: {pb}
- EPS Growth (YoY): {eps_growth}%
- Revenue Growth (YoY): {rev_growth}%
- Profit Margin: {margin}%
- Return on Equity (ROE): {roe}%
- Debt-to-Equity: {de_ratio}
- Free Cash Flow: {f.get('free_cash_flow_cr', f.get('free_cash_flow_usd_b', 'N/A'))}
- Dividend Yield: {f.get('dividend_yield_pct', 'N/A')}%
- 52W High: {f.get('52w_high', 'N/A')} | 52W Low: {f.get('52w_low', 'N/A')}

## Your Task
Analyze this company's fundamental health and provide a BUY, SELL, or HOLD signal.

Consider:
1. Is the valuation (P/E, P/B) attractive or stretched?
2. Is earnings growth accelerating or decelerating?
3. Is the balance sheet healthy (low debt, high ROE)?
4. Is there margin expansion or compression?
5. Does the business generate real free cash flow?

Respond ONLY with JSON:
{{
  "direction": "BUY" | "SELL" | "HOLD" | "STRONG_BUY" | "STRONG_SELL",
  "confidence": 0.0 to 1.0,
  "reasoning": "2-3 sentence explanation of your fundamental view",
  "key_factors": ["factor 1", "factor 2", "factor 3"],
  "price_target": estimated fair value price or null,
  "stop_loss": suggested stop loss price or null,
  "time_horizon": "medium" or "long"
}}
"""

    def _mock_llm_response(self, prompt: str) -> str:
        """
        Rule-based fundamental analysis fallback.
        Uses real financial heuristics — not random.
        """
        # Extract ticker from prompt to get the right snapshot
        # We'll use the fundamentals data already in the prompt via simple heuristics
        pe_bullish = "P/E Ratio: " in prompt and self._extract_and_check(prompt, "P/E Ratio:", threshold=25, lower_is_better=True)
        growth_bullish = self._extract_and_check(prompt, "EPS Growth (YoY):", threshold=10, lower_is_better=False)
        roe_bullish = self._extract_and_check(prompt, "Return on Equity (ROE):", threshold=15, lower_is_better=False)
        debt_ok = self._extract_and_check(prompt, "Debt-to-Equity:", threshold=1.0, lower_is_better=True)

        bullish_count = sum([pe_bullish, growth_bullish, roe_bullish, debt_ok])

        if bullish_count >= 3:
            direction = "BUY"
            confidence = 0.68 + bullish_count * 0.04
            reasoning = (
                "Fundamentals are solid: attractive valuation, strong earnings growth, "
                "and healthy balance sheet suggest the stock is undervalued at current levels."
            )
            factors = [
                f"Valuation appears {'attractive' if pe_bullish else 'fair'} relative to sector",
                f"EPS growth {'above' if growth_bullish else 'near'} 10% threshold — momentum positive",
                f"ROE {'strong' if roe_bullish else 'adequate'} indicating efficient capital use",
                f"Balance sheet {'healthy' if debt_ok else 'manageable'} with controlled leverage",
            ]
        elif bullish_count <= 1:
            direction = "SELL"
            confidence = 0.58
            reasoning = (
                "Multiple fundamental red flags: stretched valuation or decelerating growth "
                "suggest limited upside and potential downside risk."
            )
            factors = [
                "P/E ratio elevated vs. historical average",
                "Earnings growth decelerating — margin pressure likely",
                "Consider waiting for a better entry point",
            ]
        else:
            direction = "HOLD"
            confidence = 0.55
            reasoning = (
                "Mixed fundamental signals — neither compelling buy nor clear sell. "
                "Quality business but valuation leaves limited margin of safety."
            )
            factors = [
                "Valuation fair but not cheap",
                "Earnings growth stable but not accelerating",
                "Await catalyst before entering",
            ]

        return json.dumps({
            "direction": direction,
            "confidence": min(confidence, 0.90),
            "reasoning": reasoning,
            "key_factors": factors[:4],
            "price_target": None,
            "stop_loss": None,
            "time_horizon": "medium",
        })

    @staticmethod
    def _extract_and_check(text: str, label: str, threshold: float, lower_is_better: bool) -> bool:
        """Extracts a numeric value from the prompt and compares to threshold."""
        try:
            idx = text.index(label)
            snippet = text[idx + len(label):idx + len(label) + 20]
            value = float("".join(c for c in snippet.split()[0] if c in "0123456789.-"))
            return (value < threshold) if lower_is_better else (value > threshold)
        except (ValueError, IndexError):
            return False
