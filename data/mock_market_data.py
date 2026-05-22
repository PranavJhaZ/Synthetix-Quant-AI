# data/mock_market_data.py
"""
Synthetix Quant AI — Realistic Mock Market Data
Used for development/demo when Yahoo Finance API is unavailable.
Generates realistic OHLCV, fundamentals, and news data.
"""

import random
import math
from datetime import datetime, timedelta
from core.signal import MarketSnapshot


def _generate_ohlcv(
    start_price: float,
    n_days: int = 60,
    volatility: float = 0.015,
    trend: float = 0.0003,
    seed: int = 42,
) -> list[dict]:
    """
    Generates realistic OHLCV data using geometric Brownian motion.
    This is the same model quantitative finance uses for option pricing.
    """
    random.seed(seed)
    candles = []
    price = start_price
    base_date = datetime.now() - timedelta(days=n_days)

    for i in range(n_days):
        # GBM daily return
        daily_return = trend + volatility * random.gauss(0, 1)
        open_price = price
        close_price = price * (1 + daily_return)

        # Intraday range
        intraday_vol = abs(random.gauss(0, volatility * 0.8))
        high = max(open_price, close_price) * (1 + intraday_vol)
        low = min(open_price, close_price) * (1 - intraday_vol)

        # Volume — higher on big moves
        base_vol = random.randint(800_000, 2_000_000)
        volume = int(base_vol * (1 + abs(daily_return) * 20))

        candles.append({
            "date": (base_date + timedelta(days=i)).strftime("%Y-%m-%d"),
            "open": round(open_price, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close_price, 2),
            "volume": volume,
        })
        price = close_price

    return candles


def _mock_fundamentals(ticker: str) -> dict:
    """Returns realistic fundamental data for known tickers."""
    fundamentals_db = {
        "RELIANCE": {
            "company_name": "Reliance Industries Ltd",
            "sector": "Conglomerate",
            "market_cap_cr": 1_850_000,
            "pe_ratio": 27.4,
            "pb_ratio": 2.1,
            "eps_ttm": 95.2,
            "eps_growth_yoy": 12.3,
            "revenue_cr": 9_74_864,
            "revenue_growth_yoy": 8.7,
            "net_profit_cr": 67_845,
            "profit_margin_pct": 6.96,
            "roe_pct": 9.8,
            "debt_to_equity": 0.41,
            "current_ratio": 1.24,
            "free_cash_flow_cr": 45_200,
            "dividend_yield_pct": 0.34,
            "52w_high": 3217.0,
            "52w_low": 2220.3,
        },
        "TCS": {
            "company_name": "Tata Consultancy Services Ltd",
            "sector": "IT Services",
            "market_cap_cr": 1_320_000,
            "pe_ratio": 28.6,
            "pb_ratio": 11.2,
            "eps_ttm": 129.8,
            "eps_growth_yoy": 9.1,
            "revenue_cr": 2_40_893,
            "revenue_growth_yoy": 5.4,
            "net_profit_cr": 47_191,
            "profit_margin_pct": 19.6,
            "roe_pct": 52.3,
            "debt_to_equity": 0.02,
            "current_ratio": 2.87,
            "free_cash_flow_cr": 42_000,
            "dividend_yield_pct": 1.82,
            "52w_high": 4592.0,
            "52w_low": 3311.8,
        },
        "AAPL": {
            "company_name": "Apple Inc",
            "sector": "Technology",
            "market_cap_cr": None,
            "market_cap_usd_b": 3200,
            "pe_ratio": 32.1,
            "pb_ratio": 47.8,
            "eps_ttm": 6.42,
            "eps_growth_yoy": 11.2,
            "revenue_usd_b": 395.8,
            "revenue_growth_yoy": 5.1,
            "net_profit_usd_b": 96.1,
            "profit_margin_pct": 24.3,
            "roe_pct": 160.6,
            "debt_to_equity": 1.87,
            "current_ratio": 0.92,
            "free_cash_flow_usd_b": 99.6,
            "dividend_yield_pct": 0.51,
            "52w_high": 237.23,
            "52w_low": 169.94,
        },
    }
    # Fallback for unknown tickers
    return fundamentals_db.get(ticker.upper(), {
        "company_name": f"{ticker} Corp",
        "sector": "Unknown",
        "pe_ratio": round(random.uniform(12, 45), 1),
        "pb_ratio": round(random.uniform(1, 8), 1),
        "eps_growth_yoy": round(random.uniform(-5, 25), 1),
        "revenue_growth_yoy": round(random.uniform(-2, 20), 1),
        "profit_margin_pct": round(random.uniform(5, 25), 1),
        "roe_pct": round(random.uniform(8, 35), 1),
        "debt_to_equity": round(random.uniform(0, 1.5), 2),
    })


def _mock_news(ticker: str, sentiment_bias: float = 0.2) -> list[dict]:
    """
    Generates realistic news headlines with sentiment scores.
    sentiment_bias: -1 (bearish) to +1 (bullish)
    """
    bullish_templates = [
        f"{ticker} beats Q3 estimates, raises FY guidance — analysts upgrade to Buy",
        f"Institutional investors accumulate {ticker} amid sector rotation",
        f"{ticker} announces ₹5,000 Cr share buyback program",
        f"Credit Suisse raises {ticker} target price by 18%",
        f"{ticker} signs major contract worth ₹12,000 Cr with government",
        f"Promoter holding in {ticker} increases to 5-year high",
    ]
    bearish_templates = [
        f"{ticker} misses Q3 revenue estimates; margin pressure cited",
        f"Insider selling detected in {ticker} — 3 directors divest stakes",
        f"Regulatory probe launched into {ticker}'s subsidiary",
        f"Morgan Stanley downgrades {ticker} citing valuation concerns",
        f"{ticker} faces headwinds as input costs rise 12% YoY",
    ]
    neutral_templates = [
        f"{ticker} board meeting scheduled for next week; dividend decision awaited",
        f"Analyst coverage initiated on {ticker} with Neutral rating",
        f"{ticker} CEO speaks at Davos; outlines 5-year digital roadmap",
    ]

    news_items = []
    base_time = datetime.now()

    # Pick news based on bias
    if sentiment_bias > 0.2:
        pool = bullish_templates * 2 + neutral_templates
    elif sentiment_bias < -0.2:
        pool = bearish_templates * 2 + neutral_templates
    else:
        pool = bullish_templates + bearish_templates + neutral_templates

    random.shuffle(pool)
    for i, headline in enumerate(pool[:5]):
        score = sentiment_bias + random.uniform(-0.3, 0.3)
        score = max(-1.0, min(1.0, score))
        news_items.append({
            "headline": headline,
            "source": random.choice(["Economic Times", "Business Standard", "Bloomberg", "Moneycontrol", "Reuters"]),
            "published_at": (base_time - timedelta(hours=i * 4)).isoformat(),
            "sentiment_score": round(score, 3),
            "url": f"https://example.com/news/{ticker.lower()}-{i}",
        })

    return news_items


# ─── Ticker profiles: (start_price, volatility, trend, sentiment_bias) ───────
TICKER_PROFILES = {
    "RELIANCE":  (2620.0,  0.014, 0.0004, 0.25),
    "TCS":       (3750.0,  0.012, 0.0002, 0.15),
    "HDFC":      (1680.0,  0.013, 0.0003, 0.10),
    "INFY":      (1820.0,  0.013, 0.0001, 0.05),
    "NIFTY50":   (22450.0, 0.010, 0.0003, 0.20),
    "AAPL":      (195.0,   0.016, 0.0003, 0.20),
    "TSLA":      (248.0,   0.035, 0.0005, 0.10),
    "NVDA":      (875.0,   0.028, 0.0008, 0.45),
    "GOOGL":     (172.0,   0.015, 0.0003, 0.18),
}


def get_market_snapshot(ticker: str, exchange: str = "NSE") -> MarketSnapshot:
    """
    Returns a complete MarketSnapshot for any ticker.
    Uses real profiles for known tickers, generates plausible data for others.
    """
    profile = TICKER_PROFILES.get(ticker.upper(), (1000.0, 0.018, 0.0002, 0.0))
    start_price, volatility, trend, sentiment_bias = profile

    # Add some randomness so each run feels fresh
    seed = int(datetime.now().timestamp()) % 1000
    ohlcv = _generate_ohlcv(start_price, n_days=60, volatility=volatility, trend=trend, seed=seed)
    current_price = ohlcv[-1]["close"]

    fundamentals = _mock_fundamentals(ticker)
    news = _mock_news(ticker, sentiment_bias)

    # Aggregate sentiment
    if news:
        sentiment_score = sum(n["sentiment_score"] for n in news) / len(news)
    else:
        sentiment_score = 0.0

    return MarketSnapshot(
        ticker=ticker.upper(),
        exchange=exchange.upper(),
        current_price=current_price,
        timestamp=datetime.now(),
        ohlcv=ohlcv,
        fundamentals=fundamentals,
        news=news,
        sentiment_score=round(sentiment_score, 3),
    )
