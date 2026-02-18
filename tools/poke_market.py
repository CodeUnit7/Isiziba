import requests
import sys
import os

API_URL = os.getenv("AGENT_MKT_API_URL")
if not API_URL:
    print("❌ AGENT_MKT_API_URL environment variable is not set.")
    sys.exit(1)
# API_KEY = "sk-admin-static-key" # We need to ensure an agent with this key exists or use an existing one

# Let's find an existing buyer agent key
def get_buyer_key():
    from google.cloud import firestore
    project_id = os.getenv("AGENT_MKT_PROJECT_ID")
    if not project_id:
        print("❌ AGENT_MKT_PROJECT_ID not set.")
        return None
        
    db = firestore.Client(project=project_id)
    docs = db.collection("agents").where("type", "==", "buyer").get()
    for doc in docs:
        agent_data = doc.to_dict()
        if agent_data.get("api_key"):
            return agent_data.get("api_key")
    return None

def poke():
    key = get_buyer_key()
    if not key:
        print("❌ No buyer agent found to poke the market.")
        return

    payload = {
        "item": "GPU Cluster Time (Turbo Poke)",
        "max_budget": 200.0
    }
    
    headers = {
        "X-API-Key": key
    }
    
    print(f"🚀 Poking market with request: {payload['item']}...")
    res = requests.post(f"{API_URL}/market/requests", json=payload, headers=headers)
    if res.ok:
        print("✅ Market poked successfully!")
    else:
        print(f"❌ Failed to poke market: {res.text}")

if __name__ == "__main__":
    poke()
