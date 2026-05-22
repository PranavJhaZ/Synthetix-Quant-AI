# Synthetix Quant AI — Deployment Guide

## Backend → Railway (free)

1. Go to railway.app → New Project → Deploy from GitHub
2. Connect your GitHub repo containing this project
3. Add environment variable: OPENAI_API_KEY = sk-proj-...
4. Railway auto-deploys. Copy your Railway URL e.g. https://synthetix-production.up.railway.app

## Frontend → Update API URL

After Railway deploys, open index.html and add this line right after <body>:
  <script>window.API_URL = 'https://YOUR-RAILWAY-URL.up.railway.app/analyze'</script>

Then deploy index.html to Vercel:
1. Go to vercel.com → New Project → drag and drop the deploy/ folder
2. Done — you get a live URL like https://synthetix-quant.vercel.app

## Local development
  pip install -r requirements.txt
  set OPENAI_API_KEY=sk-proj-...   (Windows)
  python api/server.py
  open http://localhost:5000
