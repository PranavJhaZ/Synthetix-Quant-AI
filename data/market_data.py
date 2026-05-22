# data/market_data.py
"""
Synthetix Quant AI - Real Market Data Fetcher
 
Usage:
    python main.py --ticker AAPL              # US stock (auto-detected)
    python main.py --ticker RELIANCE --exchange NSE   # Indian stock
    python main.py --ticker TCS --exchange NSE
    python main.py --ticker BTC-USD           # Crypto
    python main.py --ticker NIFTY50           # Index
"""
 
import os
import sys
 
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
 
from datetime import datetime
from core.signal import MarketSnapshot
 
# ── Known ticker sets for auto-detection ─────────────────────────────────────
 
NSE_TICKERS = {
    "RELIANCE","TCS","HDFCBANK","HDFC","INFY","INFOSYS","WIPRO",
    "ICICIBANK","SBIN","SBI","BAJFINANCE","KOTAKBANK","BHARTIARTL",
    "AIRTEL","LT","AXISBANK","ASIANPAINT","MARUTI","SUNPHARMA",
    "TITAN","ULTRACEMCO","NESTLEIND","POWERGRID","NTPC","ONGC",
    "BPCL","TATAMOTORS","TATASTEEL","JSWSTEEL","HINDALCO",
    "ADANIENT","ADANIPORTS","HINDUNILVR","ITC","BAJAJFINSV",
    "DIVISLAB","DRREDDY","CIPLA","APOLLOHOSP","EICHERMOT",
    "HEROMOTOCO","BRITANNIA","TATACONSUM","GRASIM","SHREECEM",
    "UPL","INDUSINDBK","TECHM","HCLTECH","VEDL",
}
 
US_TICKERS = {
    "AAPL","MSFT","GOOGL","GOOG","AMZN","META","NVDA","TSLA","NFLX",
    "AMD","INTC","QCOM","AVGO","TXN","MU","AMAT","KLAC","LRCX",
    "JPM","BAC","GS","MS","WFC","C","V","MA","PYPL","AXP",
    "JNJ","UNH","PFE","ABBV","MRK","LLY","BMY","AMGN","GILD",
    "XOM","CVX","COP","SLB","MCD","KO","PEP","WMT","COST","TGT",
    "DIS","CMCSA","T","VZ","TMUS","UBER","LYFT","ABNB","SNAP","PINS",
    "PLTR","RBLX","COIN","SQ","HOOD","SOFI","RIVN","LCID","F","GM",
    "BA","LMT","RTX","GE","HON","MMM","CAT","DE",
    "SPY","QQQ","IWM","GLD","SLV","USO","TLT","VTI","VOO","ARKK",
    "ORCL","CRM","NOW","ADBE","INTU","SNOW","DDOG","CRWD","ZS","NET",
    "SHOP","SE","MELI","BABA","JD","PDD","NIO","XPEV","LI",
}
 
INDEX_MAP = {
    "NIFTY50": "^NSEI",
    "NIFTY":   "^NSEI",
    "SENSEX":  "^BSESN",
    "S&P500":  "^GSPC",
    "NASDAQ":  "^IXIC",
    "DOW":     "^DJI",
}
 
 
def _resolve_ticker(ticker: str, exchange: str) -> str:
    ticker   = ticker.upper().strip()
    exchange = exchange.upper().strip()
 
    # Already a valid YF symbol
    if any(c in ticker for c in [".", "^", "-"]):
        return ticker
 
    # Known index
    if ticker in INDEX_MAP:
        return INDEX_MAP[ticker]
 
    # Explicit exchange always wins
    if exchange in ("NSE", "INDIA"):
        return ticker + ".NS"
    if exchange == "BSE":
        return ticker + ".BO"
    if exchange in ("NASDAQ", "NYSE", "US"):
        return ticker
 
    # Auto-detect: US ticker list first (most common case for unknown exchange)
    if ticker in US_TICKERS:
        return ticker
 
    # Auto-detect: known NSE ticker
    if ticker in NSE_TICKERS:
        return ticker + ".NS"
 
    # Unknown ticker, no exchange → assume US (safest default)
    return ticker
 
 
# ── Data fetchers ─────────────────────────────────────────────────────────────
 
def _fetch_ohlcv(yf_ticker) -> list[dict]:
    hist = yf_ticker.history(period="3mo")
    if hist.empty:
        return []
    candles = []
    for date, row in hist.iterrows():
        candles.append({
            "date":   date.strftime("%Y-%m-%d"),
            "open":   round(float(row["Open"]),   2),
            "high":   round(float(row["High"]),   2),
            "low":    round(float(row["Low"]),    2),
            "close":  round(float(row["Close"]),  2),
            "volume": int(row["Volume"]),
        })
    return candles
 
 
def _fetch_fundamentals(yf_ticker, ticker_display: str) -> dict:
    try:
        info = yf_ticker.info
    except Exception:
        return {"company_name": ticker_display, "sector": "Unknown"}
 
    def safe(key, default=None):
        val = info.get(key, default)
        return round(val, 2) if isinstance(val, float) else val
 
    def pct(key):
        v = info.get(key)
        return round(v * 100, 2) if isinstance(v, float) else None
 
    return {
        "company_name":         safe("longName", ticker_display),
        "sector":               safe("sector", "Unknown"),
        "industry":             safe("industry", "Unknown"),
        "market_cap":           safe("marketCap"),
        "pe_ratio":             safe("trailingPE"),
        "forward_pe":           safe("forwardPE"),
        "pb_ratio":             safe("priceToBook"),
        "eps_ttm":              safe("trailingEps"),
        "eps_growth_yoy":       pct("earningsGrowth"),
        "revenue":              safe("totalRevenue"),
        "revenue_growth_yoy":   pct("revenueGrowth"),
        "profit_margin_pct":    pct("profitMargins"),
        "operating_margin_pct": pct("operatingMargins"),
        "roe_pct":              pct("returnOnEquity"),
        "roa_pct":              pct("returnOnAssets"),
        "debt_to_equity":       safe("debtToEquity"),
        "current_ratio":        safe("currentRatio"),
        "free_cash_flow":       safe("freeCashflow"),
        "dividend_yield_pct":   pct("dividendYield"),
        "beta":                 safe("beta"),
        "52w_high":             safe("fiftyTwoWeekHigh"),
        "52w_low":              safe("fiftyTwoWeekLow"),
        "avg_volume":           safe("averageVolume"),
        "analyst_target":       safe("targetMeanPrice"),
        "analyst_recommendation": safe("recommendationKey", "N/A"),
    }
 
 
def _score_headline(headline: str) -> float:
    h = headline.lower()
    bullish = {
        "beat":0.4,"beats":0.4,"record":0.3,"upgrade":0.35,"raises":0.3,
        "growth":0.2,"profit":0.2,"strong":0.2,"surge":0.35,"rally":0.3,
        "gain":0.25,"outperform":0.35,"buyback":0.3,"dividend":0.2,
        "deal":0.15,"partnership":0.2,"breakthrough":0.4,"recovery":0.25,
    }
    bearish = {
        "miss":0.4,"misses":0.4,"cut":0.3,"downgrade":0.4,"decline":0.3,
        "loss":0.35,"probe":0.4,"investigation":0.4,"fraud":0.5,"crash":0.5,
        "fall":0.3,"drop":0.3,"weak":0.3,"concern":0.2,"lawsuit":0.35,
        "fine":0.3,"penalty":0.35,"warning":0.3,"layoff":0.35,"layoffs":0.35,
    }
    score = 0.0
    for term, w in bullish.items():
        if term in h: score += w
    for term, w in bearish.items():
        if term in h: score -= w
    return max(-1.0, min(1.0, score))
 
 
def _fetch_news(yf_ticker) -> tuple:
    try:
        news_raw = yf_ticker.news or []
    except Exception:
        return [], 0.0
 
    items, scores = [], []
    for item in news_raw[:8]:
        title = item.get("title", "")
        pub   = item.get("providerPublishTime", 0)
        score = _score_headline(title)
        scores.append(score)
        items.append({
            "headline":        title,
            "source":          item.get("publisher", "Unknown"),
            "published_at":    datetime.fromtimestamp(pub).isoformat() if pub else "",
            "sentiment_score": round(score, 3),
            "url":             item.get("link", ""),
        })
 
    agg = sum(scores) / len(scores) if scores else 0.0
    return items, round(agg, 3)
 
 
# ── Public entry point ────────────────────────────────────────────────────────
 
def get_market_snapshot(ticker: str, exchange: str = "") -> MarketSnapshot:
    """
    Fetch real market data for any ticker.
 
    Examples:
        get_market_snapshot("AAPL")                   # US - auto detected
        get_market_snapshot("NVDA")                   # US - auto detected
        get_market_snapshot("RELIANCE", "NSE")        # Indian stock
        get_market_snapshot("TCS", "NSE")             # Indian stock
        get_market_snapshot("BTC-USD")                # Crypto
        get_market_snapshot("NIFTY50")                # Index
    """
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError("Run:  pip install yfinance")
 
    yf_symbol = _resolve_ticker(ticker, exchange)
    print(f"  Fetching live data: {ticker} -> {yf_symbol}")
 
    obj   = yf.Ticker(yf_symbol)
    ohlcv = _fetch_ohlcv(obj)
 
    if not ohlcv:
        raise ValueError(
            f"No price data for '{yf_symbol}'.\n"
            f"  US stock?    python main.py --ticker AAPL\n"
            f"  NSE stock?   python main.py --ticker RELIANCE --exchange NSE\n"
            f"  Crypto?      python main.py --ticker BTC-USD"
        )
 
    fundamentals          = _fetch_fundamentals(obj, ticker)
    news, sentiment_score = _fetch_news(obj)
    current_price         = ohlcv[-1]["close"]
 
    print(f"  Got {len(ohlcv)} days of data | Price: {current_price} | "
          f"Sentiment: {sentiment_score:+.2f}")
 
    return MarketSnapshot(
        ticker          = ticker.upper(),
        exchange        = exchange.upper() if exchange else "AUTO",
        current_price   = current_price,
        timestamp       = datetime.now(),
        ohlcv           = ohlcv,
        fundamentals    = fundamentals,
        news            = news,
        sentiment_score = sentiment_score,
    )
 
 
# For --list flag compatibility
TICKER_PROFILES = {t: None for t in sorted(NSE_TICKERS)}