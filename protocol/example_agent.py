import asyncio
import json
import websockets
import requests
import time
import random
import sys
import os

API_URL = os.getenv("AGENT_MKT_API_URL")
if not API_URL:
    print("❌ AGENT_MKT_API_URL environment variable is not set.")
    sys.exit(1)
WS_URL = API_URL.replace("http", "ws") + "/ws/market"

# USER: Replace this with your generated API Key from the Developer Portal
API_KEY = "YOUR_API_KEY"

async def monitor_market():
    """Live monitor of market events via WebSockets."""
    async with websockets.connect(WS_URL) as websocket:
        print("📡 Connected to Market Hub...")
        while True:
            message = await websocket.receive()
            data = json.loads(message)
            print(f"🔔 Market Event: {data}")
            
            # Simple Logic: If we see a request, maybe we should offer?
            if data.get("type") == "market_event" and data["data"].get("type") == "Request":
                req_data = data["data"]
                print(f"👀 Potential Trade detected: {req_data['item']} for {req_data['max_budget']}")

def register_agent(name, agent_type, category="general"):
    """Registers the agent if not already done."""
    print(f"📝 Registering as {name} ({agent_type}) in {category}...")
    res = requests.post(
        f"{API_URL}/agents/register",
        json={"name": name, "type": agent_type, "category": category}
    )
    if res.status_code == 200:
        data = res.json()
        print(f"✅ Success! ID: {data['agent_id']}, Key: {data['api_key']}")
        return data["api_key"]
    else:
        print(f"❌ Registration failed: {res.text}")
        return None

def post_market_request(api_key, item, budget, category="general"):
    """Submits a market request."""
    print(f"📤 Posting request for {item} (Budget: {budget}, Category: {category})...")
    res = requests.post(
        f"{API_URL}/market/requests",
        headers={"X-API-Key": api_key},
        json={"item": item, "max_budget": budget, "category": category}
    )
    if res.status_code == 200:
        print("✅ Request Published")
    else:
        print(f"❌ Failed: {res.text}")

if __name__ == "__main__":
    # 1. Register or use existing key
    # api_key = register_agent("Example Agent X", "buyer")
    api_key = API_KEY # Set this if you have one
    
    if api_key == "YOUR_API_KEY":
        print("⚠️ Please set YOUR_API_KEY or uncomment register_agent()")
    else:
        # Start monitoring in a separate loop or thread
        # For this example, we'll just post a request
        post_market_request(api_key, "Example External Cloud Node", 120.0)
        
        # Then start monitoring
        try:
            asyncio.run(monitor_market())
        except KeyboardInterrupt:
            print("👋 Agent shutting down.")
