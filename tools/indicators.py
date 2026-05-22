# tools/indicators.py
"""
Synthetix Quant AI — Technical Indicators
All indicators computed from raw OHLCV data. No external TA library needed.
"""

import math
from typing import Optional


def _closes(ohlcv: list[dict]) -> list[float]:
    return [c["close"] for c in ohlcv]

def _highs(ohlcv: list[dict]) -> list[float]:
    return [c["high"] for c in ohlcv]

def _lows(ohlcv: list[dict]) -> list[float]:
    return [c["low"] for c in ohlcv]

def _volumes(ohlcv: list[dict]) -> list[float]:
    return [float(c["volume"]) for c in ohlcv]


def sma(prices: list[float], period: int) -> Optional[float]:
    """Simple Moving Average."""
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period


def ema(prices: list[float], period: int) -> Optional[float]:
    """Exponential Moving Average."""
    if len(prices) < period:
        return None
    k = 2.0 / (period + 1)
    ema_val = sum(prices[:period]) / period
    for price in prices[period:]:
        ema_val = price * k + ema_val * (1 - k)
    return ema_val


def rsi(prices: list[float], period: int = 14) -> Optional[float]:
    """
    Relative Strength Index (Wilder's smoothing).
    Returns 0-100. >70 = overbought, <30 = oversold.
    """
    if len(prices) < period + 1:
        return None
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [max(d, 0) for d in deltas]
    losses = [abs(min(d, 0)) for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def macd(prices: list[float], fast: int = 12, slow: int = 26, signal: int = 9):
    """
    MACD — Moving Average Convergence/Divergence.
    Returns (macd_line, signal_line, histogram).
    Positive histogram = bullish momentum building.
    """
    if len(prices) < slow + signal:
        return None, None, None
    fast_ema = ema(prices, fast)
    slow_ema = ema(prices, slow)
    if fast_ema is None or slow_ema is None:
        return None, None, None
    macd_line = fast_ema - slow_ema

    # Signal line = EMA of MACD values
    macd_series = []
    for i in range(slow - 1, len(prices)):
        fe = ema(prices[:i+1], fast)
        se = ema(prices[:i+1], slow)
        if fe and se:
            macd_series.append(fe - se)

    signal_line = ema(macd_series, signal) if len(macd_series) >= signal else None
    histogram = (macd_line - signal_line) if signal_line else None

    return (
        round(macd_line, 4) if macd_line else None,
        round(signal_line, 4) if signal_line else None,
        round(histogram, 4) if histogram else None,
    )


def bollinger_bands(prices: list[float], period: int = 20, std_dev: float = 2.0):
    """
    Bollinger Bands.
    Returns (upper, middle, lower, %B position).
    %B > 1 = above upper band (overbought), %B < 0 = below lower band (oversold).
    """
    if len(prices) < period:
        return None, None, None, None
    middle = sma(prices, period)
    variance = sum((p - middle) ** 2 for p in prices[-period:]) / period
    std = math.sqrt(variance)
    upper = round(middle + std_dev * std, 2)
    lower = round(middle - std_dev * std, 2)
    middle = round(middle, 2)
    current = prices[-1]
    pct_b = round((current - lower) / (upper - lower), 3) if (upper - lower) != 0 else 0.5
    return upper, middle, lower, pct_b


def atr(ohlcv: list[dict], period: int = 14) -> Optional[float]:
    """
    Average True Range — measures volatility.
    High ATR = high volatility, useful for stop-loss placement.
    """
    if len(ohlcv) < period + 1:
        return None
    true_ranges = []
    for i in range(1, len(ohlcv)):
        high = ohlcv[i]["high"]
        low = ohlcv[i]["low"]
        prev_close = ohlcv[i-1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    if len(true_ranges) < period:
        return None
    atr_val = sum(true_ranges[:period]) / period
    for tr in true_ranges[period:]:
        atr_val = (atr_val * (period - 1) + tr) / period
    return round(atr_val, 2)


def volume_trend(ohlcv: list[dict], short: int = 5, long: int = 20) -> Optional[str]:
    """
    Compares recent volume to longer-term average.
    Returns: "INCREASING", "DECREASING", "NEUTRAL"
    """
    volumes = _volumes(ohlcv)
    if len(volumes) < long:
        return None
    recent_avg = sum(volumes[-short:]) / short
    long_avg = sum(volumes[-long:]) / long
    ratio = recent_avg / long_avg if long_avg > 0 else 1.0
    if ratio > 1.25:
        return "INCREASING"
    elif ratio < 0.80:
        return "DECREASING"
    return "NEUTRAL"


def price_position(ohlcv: list[dict]) -> dict:
    """
    Where is price relative to 52-week high/low and moving averages?
    """
    closes = _closes(ohlcv)
    current = closes[-1]
    period_high = max(_highs(ohlcv))
    period_low = min(_lows(ohlcv))
    pct_from_high = round((current - period_high) / period_high * 100, 2)
    pct_from_low = round((current - period_low) / period_low * 100, 2)

    return {
        "current": round(current, 2),
        "period_high": round(period_high, 2),
        "period_low": round(period_low, 2),
        "pct_from_high": pct_from_high,
        "pct_from_low": pct_from_low,
        "sma_20": sma(closes, 20),
        "sma_50": sma(closes, 50),
        "ema_20": ema(closes, 20),
        "above_sma20": current > (sma(closes, 20) or 0),
        "above_sma50": current > (sma(closes, 50) or 0),
    }


def compute_all_indicators(ohlcv: list[dict]) -> dict:
    """
    Master function — computes all indicators and returns a clean dict.
    This is what gets stored in MarketSnapshot.indicators.
    """
    closes = _closes(ohlcv)
    macd_line, signal_line, histogram = macd(closes)
    bb_upper, bb_mid, bb_lower, pct_b = bollinger_bands(closes)
    pos = price_position(ohlcv)

    rsi_val = rsi(closes)
    atr_val = atr(ohlcv)
    vol_trend = volume_trend(ohlcv)

    # Momentum: 5-day and 20-day returns
    mom_5 = round((closes[-1] / closes[-6] - 1) * 100, 2) if len(closes) >= 6 else None
    mom_20 = round((closes[-1] / closes[-21] - 1) * 100, 2) if len(closes) >= 21 else None

    return {
        "rsi_14": rsi_val,
        "macd": {
            "line": macd_line,
            "signal": signal_line,
            "histogram": histogram,
            "crossover": (
                "BULLISH" if histogram and histogram > 0 else
                "BEARISH" if histogram and histogram < 0 else
                "NEUTRAL"
            ),
        },
        "bollinger": {
            "upper": bb_upper,
            "middle": bb_mid,
            "lower": bb_lower,
            "pct_b": pct_b,
        },
        "atr_14": atr_val,
        "volume_trend": vol_trend,
        "momentum": {
            "5d_pct": mom_5,
            "20d_pct": mom_20,
        },
        "price_position": pos,
        "signals_summary": _summarize_signals(rsi_val, histogram, pct_b, mom_5, vol_trend),
    }


def _summarize_signals(rsi_val, macd_hist, pct_b, mom_5, vol_trend) -> dict:
    """
    Converts raw indicator values into bullish/bearish/neutral calls.
    Makes it easy for agents to reason about indicators.
    """
    signals = {}

    if rsi_val:
        if rsi_val > 70:
            signals["rsi"] = {"signal": "BEARISH", "note": f"Overbought at {rsi_val}"}
        elif rsi_val < 30:
            signals["rsi"] = {"signal": "BULLISH", "note": f"Oversold at {rsi_val}"}
        elif rsi_val > 55:
            signals["rsi"] = {"signal": "MILDLY_BULLISH", "note": f"Momentum positive at {rsi_val}"}
        else:
            signals["rsi"] = {"signal": "NEUTRAL", "note": f"RSI neutral at {rsi_val}"}

    if macd_hist is not None:
        signals["macd"] = {
            "signal": "BULLISH" if macd_hist > 0 else "BEARISH",
            "note": f"Histogram {'positive' if macd_hist > 0 else 'negative'}: {macd_hist}",
        }

    if pct_b is not None:
        if pct_b > 0.9:
            signals["bollinger"] = {"signal": "BEARISH", "note": "Price near upper band — stretched"}
        elif pct_b < 0.1:
            signals["bollinger"] = {"signal": "BULLISH", "note": "Price near lower band — mean-reversion opportunity"}
        else:
            signals["bollinger"] = {"signal": "NEUTRAL", "note": f"%B at {pct_b:.1%}"}

    if mom_5 is not None:
        signals["momentum_5d"] = {
            "signal": "BULLISH" if mom_5 > 1.5 else "BEARISH" if mom_5 < -1.5 else "NEUTRAL",
            "note": f"5-day return: {mom_5:+.2f}%",
        }

    if vol_trend:
        signals["volume"] = {
            "signal": "BULLISH" if vol_trend == "INCREASING" else "BEARISH" if vol_trend == "DECREASING" else "NEUTRAL",
            "note": f"Volume trend: {vol_trend}",
        }

    return signals
