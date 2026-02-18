import requests
import time

API_URL = os.getenv("AGENT_MKT_API_URL")
if not API_URL:
    print("❌ AGENT_MKT_API_URL environment variable is not set.")
    import sys
    sys.exit(1)
API_KEY = "sk-buyer-static-key" # Using the buyer's key

def trigger():
    # 1. Post a dummy negotiation to ensure something is in history
    neg_id = "neg-testing-coach"
    offer_id = "off-dummy"
    
    print("📡 Sending dummy proposal...")
    requests.post(
        f"{API_URL}/market/negotiate",
        headers={"X-API-Key": API_KEY},
        json={
            "negotiation_id": neg_id,
            "offer_id": offer_id,
            "action": "COUNTER",
            "price": 50.0,
            "receiver_id": "seller-reference",
            "sender_id": "buyer-reference",
            "reasoning": "Standard testing proposal."
        }
    )
    
    time.sleep(1)
    
    print("🎬 Sending REJECT to trigger Coach...")
    res = requests.post(
        f"{API_URL}/market/negotiate",
        headers={"X-API-Key": API_KEY},
        json={
            "negotiation_id": neg_id,
            "offer_id": offer_id,
            "action": "REJECT",
            "price": 0.0,
            "receiver_id": "seller-reference",
            "sender_id": "buyer-reference",
            "reasoning": "Price is way too high. Rejecting."
        }
    )
    print(f"✅ Trigger response: {res.status_code}")

if __name__ == "__main__":
    trigger()
