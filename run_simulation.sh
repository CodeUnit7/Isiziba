#!/bin/bash
set -e

# Setup Python Virtual Environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
else
    source .venv/bin/activate
fi

echo "📦 Installing dependencies from agents..."
pip install -r agents/buyer/requirements.txt
pip install -r agents/seller/requirements.txt

# Ensure Google Auth
if ! gcloud auth print-access-token >/dev/null 2>&1; then
    echo "⚠️  gcloud auth check failed. Please run 'gcloud auth application-default login' or set GOOGLE_APPLICATION_CREDENTIALS"
    # We continue, hoping environment credentials exist
fi

export GCP_PROJECT_ID=${AGENT_MKT_PROJECT_ID:-$(gcloud config get-value project)}

echo "🏭 Starting Seller Agent (Background)..."
# Using nohup or simply backgrounding
python -u agents/seller/main.py &
SELLER_PID=$!

echo "⏳ Waiting for Seller to initialize..."
sleep 5

echo "🤖 Starting Buyer Agent..."
python -u agents/buyer/main.py &
BUYER_PID=$!

echo "✅ Simulation running. Press Ctrl+C to stop..."
trap "kill $SELLER_PID $BUYER_PID 2>/dev/null; exit" INT TERM
wait
