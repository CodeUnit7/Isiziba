import unittest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
import sys
import os

# Mock modules
sys.modules["google.cloud"] = MagicMock()
sys.modules["google.cloud.firestore"] = MagicMock()
sys.modules["google.cloud.pubsub_v1"] = MagicMock()
sys.modules["vertexai"] = MagicMock()
sys.modules["vertexai.generative_models"] = MagicMock()

os.environ["AGENT_MKT_PROJECT_ID"] = "test-project"
os.environ["AGENT_MKT_TEST_MODE"] = "true"

from api_server import app

class TestMaxSteps(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.mock_db = MagicMock()
        app.state.db = self.mock_db
        app.state.publisher = MagicMock()

    def test_max_steps_limit(self):
        print("\n🛑 Testing MAX_NEGOTIATION_STEPS Enforcement...")
        
        # Scenario: Negotiation has 20 steps already
        # We mock the count query response
        
        # Logic in api_server:
        # count_query = get_db().collection("negotiations").where(...).count()
        # aggregates = count_query.get()
        # current_steps = aggregates[0][0].value
        
        # Mocking the chain
        col_mock = self.mock_db.collection.return_value
        # The chain is .where().count().get()
        # The result of get() is a list of AggregationResult (mocked as list of list of obj with .value)
        
        mock_agg_result = MagicMock()
        mock_agg_result.value = 20 # Hit the limit
        
        # We need to structure the return of get() to match `aggregates[0][0].value`
        # So get() returns [[mock_agg_result]]
        
        query_mock = col_mock.where.return_value
        count_query_mock = query_mock.count.return_value
        count_query_mock.get.return_value = [[mock_agg_result]]
        
        # Payload: Trying to COUNTER (not ACCEPT/REJECT)
        payload = {
            "negotiation_id": "neg-infinity",
            "action": "COUNTER",
            "price": 50.0,
            "offer_id": "off-1",
            "sender_id": "buyer-1",
            "receiver_id": "seller-1",
            "reasoning": "I can do this all day"
        }
        
        # Mock Auth
        from api_server import auth_cache, datetime, timedelta
        auth_cache["sk-valid"] = ({"id": "buyer-1", "type": "buyer", "name": "Buyer"}, datetime.utcnow() + timedelta(seconds=300))
        headers = {"X-API-KEY": "sk-valid"}
        
        response = self.client.post("/market/negotiate", json=payload, headers=headers)
        
        if response.status_code == 400 and "Negotiation limit reached" in response.text:
            print("✅ SUCCESS: Server rejected excessive steps (400 Bad Request).")
            print(f"   Response: {response.json()['detail']}")
        else:
            print(f"❌ FAILURE: Server allowed step 21? Code: {response.status_code}")
            print(f"   Response: {response.text}")
            self.fail("Max steps limit failed")

if __name__ == "__main__":
    unittest.main()
