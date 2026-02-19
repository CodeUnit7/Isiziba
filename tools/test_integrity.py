
import sys
import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Mock the firestore client BEFORE importing api_server to avoid init crashes
sys.modules["google.cloud"] = MagicMock()
sys.modules["google.cloud.firestore"] = MagicMock()
sys.modules["google.cloud.pubsub_v1"] = MagicMock()
sys.modules["vertexai"] = MagicMock()
sys.modules["vertexai.generative_models"] = MagicMock()
sys.modules["vertexai.preview.generative_models"] = MagicMock()

# Now import app
import os
os.environ["AGENT_MKT_PROJECT_ID"] = "test-project"
os.environ["AGENT_MKT_TEST_MODE"] = "true"
os.environ["AGENT_MKT_MODEL"] = "gemini-1.5-flash-001" # Dummy model for init

from api_server import app

class TestIntegrity(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        
        # Mock Firestore DB
        self.mock_db = MagicMock()
        app.state.db = self.mock_db
        
        # Mock Publisher
        app.state.publisher = MagicMock()

    def test_price_integrity_check(self):
        print("\n🔒 Testing Price Integrity Check via TestClient...")
        
        # Setup: negotiation_id, offer_id, etc.
        neg_id = "neg-123"
        offer_id = "offer-abc"
        buyer_id = "buyer-1"
        seller_id = "seller-1"
        
        # Mock API Key verification to return a valid agent
        app.dependency_overrides = {} # Reset
        # We need to bypass verify_api_key or mock get_db to return valid agent for key
        # verify_api_key queries 'agents' collection.
        
        # Let's mock the keys in cache directly to bypass DB lookup
        from api_server import auth_cache
        from datetime import datetime, timedelta
        import time
        # api_server uses datetime.utcnow() for 'now'
        auth_cache["sk-valid"] = ({"id": seller_id, "type": "seller", "name": "Seller"}, datetime.utcnow() + timedelta(seconds=300))
        
        # We need to mock the history query in 'negotiate' endpoint
        # The code calls: 
        # history_query = get_db().collection("negotiations").where(...).order_by(...).limit(2).get()
        
        # Mock the chain
        col_mock = self.mock_db.collection.return_value
        query_mock = col_mock.where.return_value.order_by.return_value.limit.return_value
        
        # SCENARIO: Malicious ACCEPT
        # History shows Buyer proposed 90. Seller accepts 1000.
        
        # Mock document snapshot for history
        def create_doc(data):
            doc = MagicMock()
            doc.to_dict.return_value = data
            return doc
            
        # Last message was Buyer proposing 90
        last_msg = create_doc({"sender_id": buyer_id, "price": 90.0})
        # Previous msg (irrelevant)
        prev_msg = create_doc({"sender_id": seller_id, "price": 1000.0}) # old proposal
        
        # The query returns these docs
        query_mock.get.return_value = [last_msg] 
        
        # Also need to mock Offer lookup if logic falls back to it? 
        # Logic: 
        # if h.get("sender_id") == action.receiver_id and h.get("price") == action.price: valid_price = True
        # Receiver of ACCEPT is Buyer. So we check if Buyer (receiver_id) proposed the price.
        # action.receiver_id = buyer_id.
        # last_msg.sender_id = buyer_id.
        # last_msg.price = 90.0
        
        # ATTACK: Action price = 1000.0
        # Check: 90.0 == 1000.0 ? False.
        
        # Payload
        payload = {
            "negotiation_id": neg_id,
            "action": "ACCEPT",
            "price": 1000.0, # TAMPERED PRICE
            "offer_id": offer_id,
            "sender_id": seller_id,
            "receiver_id": buyer_id,
            "reasoning": "Ha ha I steal your money"
        }
        
        headers = {"X-API-KEY": "sk-valid"}
        
        response = self.client.post("/market/negotiate", json=payload, headers=headers)
        
        if response.status_code == 400:
            print("✅ SUCCESS: Server rejected tampering (400 Bad Request).")
            print(f"   Response: {response.json()['detail']}")
        else:
            print(f"❌ FAILURE: Server responded with {response.status_code}")
            print(f"   Response: {response.text}")
            self.fail("Integrity check failed to catch tampering")

if __name__ == "__main__":
    unittest.main()
