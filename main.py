#!/usr/bin/env python3
# main.py
 
import sys
import os
import argparse
import json
 
# ── Fix Python path ───────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)
# ─────────────────────────────────────────────────────────────────────────────
 
from core.orchestrator import Orchestrator
from data.market_data import get_market_snapshot, TICKER_PROFILES
 
 
def main():
    parser = argparse.ArgumentParser(
        description="Synthetix Quant AI — Agentic Trading Framework"
    )
    parser.add_argument("--ticker",   default="RELIANCE", help="Any stock ticker")
    parser.add_argument("--exchange", default="",         help="NSE / NASDAQ / NYSE / CRYPTO")
    parser.add_argument("--json",     action="store_true", help="JSON output only")
    parser.add_argument("--api",      action="store_true", help="Start API server")
    parser.add_argument("--list",     action="store_true", help="List known NSE tickers")
    args = parser.parse_args()
 
    if not os.environ.get("OPENAI_API_KEY"):
        print("\n  OPENAI_API_KEY not set -- agents will use rule-based fallback.")
        print("  To enable AI reasoning, run:")
        print("  Windows:    set OPENAI_API_KEY=sk-proj-xxxx")
        print("  Mac/Linux:  export OPENAI_API_KEY=sk-proj-xxxx\n")
 
    if args.list:
        tickers = sorted(TICKER_PROFILES.keys())
        print("Known NSE tickers (exchange=NSE):")
        for i in range(0, len(tickers), 6):
            print("  " + "  ".join(tickers[i:i+6]))
        print("\nAny US ticker works too: AAPL, NVDA, TSLA, GOOGL, MSFT ...")
        print("Crypto: BTC-USD, ETH-USD, SOL-USD ...")
        return
 
    if args.api:
        from api.server import app
        print("Starting Synthetix Quant AI API -> http://localhost:5000")
        app.run(debug=True, port=5000)
        return
 
    verbose = not args.json
 
    if verbose:
        print(f"\n{'x' * 60}")
        print(f"  SYNTHETIX QUANT AI -- Agentic Trading Framework")
        print(f"{'x' * 60}\n")
 
    try:
        snapshot = get_market_snapshot(args.ticker, args.exchange)
    except (ValueError, ImportError) as e:
        print(f"\n  ERROR: {e}")
        return
 
    orchestrator = Orchestrator(verbose=verbose)
    decision = orchestrator.run_analysis(snapshot)
 
    if args.json:
        print(json.dumps(decision.to_dict(), indent=2))
 
 
if __name__ == "__main__":
    main()