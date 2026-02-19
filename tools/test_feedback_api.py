import requests
import time
import sys

import os

API_URL = os.getenv("AGENT_MKT_API_URL")
if not API_URL:
    print("❌ AGENT_MKT_API_URL environment variable is not set.")
    sys.exit(1)

def test_feedback():
    print("🚀 Testing Feedback API...")
    
    # 1. Submit feedback
    payload = {
        "negotiation_id": "test-neg-123",
        "rating": 5,
        "comment": "Excellent execution of Voss techniques.",
        "user_id": "test-verifier"
    }
    
    try:
        response = requests.post(f"{API_URL}/feedback/submit", json=payload)
        if response.status_code == 200:
            print("✅ Feedback submitted successfully!")
            print(f"Response: {response.json()}")
        else:
            print(f"❌ Failed to submit feedback. Status: {response.status_code}")
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"❌ Error connecting to API: {e}")

if __name__ == "__main__":
    test_feedback()
