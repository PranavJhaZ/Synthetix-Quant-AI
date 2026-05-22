"""
setup.py — Run this ONCE to fix the folder structure.
It creates the required subfolders and moves files into the right place.

Run with:
    python setup.py
"""

import os
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))

# ── 1. Create all required folders ───────────────────────────────────────────
folders = ["agents", "core", "tools", "data", "config", "api", "logs"]
for folder in folders:
    path = os.path.join(BASE, folder)
    os.makedirs(path, exist_ok=True)
    # Create __init__.py so Python treats them as packages
    init_file = os.path.join(path, "__init__.py")
    if not os.path.exists(init_file):
        open(init_file, "w").close()
    print(f"  ✅ Created folder: {folder}/")

# ── 2. File → destination mapping ────────────────────────────────────────────
FILE_MAP = {
    # agents/
    "base_agent.py":          "agents/base_agent.py",
    "fundamental_analyst.py": "agents/fundamental_analyst.py",
    "technical_analyst.py":   "agents/technical_analyst.py",
    "sentiment_analyst.py":   "agents/sentiment_analyst.py",
    "risk_manager.py":        "agents/risk_manager.py",
    "portfolio_manager.py":   "agents/portfolio_manager.py",

    # core/
    "orchestrator.py":        "core/orchestrator.py",
    "signal.py":              "core/signal.py",

    # tools/
    "indicators.py":          "tools/indicators.py",

    # data/
    "mock_market_data.py":    "data/mock_market_data.py",

    # config/
    "settings.py":            "config/settings.py",

    # api/
    "server.py":              "api/server.py",

    # root — main.py stays where it is
}

# ── 3. Move files ─────────────────────────────────────────────────────────────
print("\nMoving files into correct folders...")
for src_name, dest_rel in FILE_MAP.items():
    src = os.path.join(BASE, src_name)
    dest = os.path.join(BASE, dest_rel)

    if not os.path.exists(src):
        print(f"  ⚠️  Not found (skip): {src_name}")
        continue

    # Don't overwrite if already in right place
    if os.path.abspath(src) == os.path.abspath(dest):
        print(f"  ✅ Already correct: {dest_rel}")
        continue

    shutil.move(src, dest)
    print(f"  ✅ Moved: {src_name} → {dest_rel}")

# ── 4. Verify ─────────────────────────────────────────────────────────────────
print("\nVerifying structure...")
required = [
    "agents/base_agent.py",
    "agents/fundamental_analyst.py",
    "agents/technical_analyst.py",
    "agents/sentiment_analyst.py",
    "agents/risk_manager.py",
    "agents/portfolio_manager.py",
    "core/orchestrator.py",
    "core/signal.py",
    "tools/indicators.py",
    "data/mock_market_data.py",
    "config/settings.py",
    "api/server.py",
    "main.py",
]

all_good = True
for rel_path in required:
    full = os.path.join(BASE, rel_path)
    if os.path.exists(full):
        print(f"  ✅ {rel_path}")
    else:
        print(f"  ❌ MISSING: {rel_path}")
        all_good = False

print()
if all_good:
    print("=" * 50)
    print("  Setup complete! Now run:")
    print()
    print("  pip install yfinance flask requests")
    print()
    print("  python main.py --ticker RELIANCE --exchange NSE")
    print("  python main.py --ticker AAPL")
    print("=" * 50)
else:
    print("Some files are missing. Make sure all downloaded")
    print("files are in the same folder as setup.py and re-run.")
