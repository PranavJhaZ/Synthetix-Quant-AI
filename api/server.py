import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
 
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from core.orchestrator import Orchestrator
 
app = Flask(__name__)
CORS(app)
 
def get_snapshot(ticker, exchange):
    try:
        import yfinance
        from data.market_data import get_market_snapshot
        return get_market_snapshot(ticker, exchange)
    except ImportError:
        from data.mock_market_data import get_market_snapshot
        return get_market_snapshot(ticker, exchange)
 
@app.route("/", methods=["GET"])
def index():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return send_from_directory(root, "index.html")
 
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})
 
@app.route("/analyze", methods=["POST", "OPTIONS"])
def analyze():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    data     = request.get_json() or {}
    ticker   = data.get("ticker", "AAPL").upper()
    exchange = data.get("exchange", "").upper()
    try:
        snapshot     = get_snapshot(ticker, exchange)
        orchestrator = Orchestrator(verbose=False)
        decision     = orchestrator.run_analysis(snapshot)
        result       = decision.to_dict()
        result["current_price"]   = snapshot.current_price
        result["company_name"]    = snapshot.fundamentals.get("company_name", ticker)
        result["sentiment_score"] = snapshot.sentiment_score
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": f"Ticker '{ticker}' not found. Check spelling and exchange."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
 
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  Synthetix Quant AI — http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)