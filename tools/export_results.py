import requests
import json
import os
import time

# Configuration
API_URL = os.getenv("AGENT_MKT_API_URL")
if not API_URL:
    raise ValueError("❌ AGENT_MKT_API_URL environment variable is not set.")

def export_market_data():
    """Fetches and saves market data to a JSON file."""
    print(f"📡 Connecting to Market API at {API_URL}...")
    
    try:
        # 1. Fetch Market Trends (Finalized Transactions)
        # This endpoint returns the history of all successful deals (Price, Product, Time, Reasoning)
        print(f"   Fetching trends from {API_URL}/market/trends...")
        trends_resp = requests.get(f"{API_URL}/market/trends?limit=100")
        if trends_resp.status_code != 200:
             print(f"❌ Failed to fetch trends: {trends_resp.text}")
             return
             
        data = trends_resp.json()
        transactions = data.get("trends", [])
        
        # 2. Compile Report
        report = {
            "generated_at": time.time(),
            "data_source": "Platform API /market/trends",
            "count": len(transactions),
            "transactions": transactions, # List of {timestamp, price, product, explanation, tx_id}
            "export_note": "This file contains the final results of successful negotiations."
        }
        
        filename = f"market_export_{int(time.time())}.json"
        with open(filename, "w") as f:
            json.dump(report, f, indent=2)
            
        print(f"✅ Data exported to {filename}")
        print(f"   - Contains {len(transactions)} transaction records")
        print(f"   - You can load this JSON into pandas or Excel for analysis.")

    except Exception as e:
        print(f"❌ Export failed: {e}")

if __name__ == "__main__":
    export_market_data()
