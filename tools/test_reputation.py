import time
import uuid
from google.cloud import firestore

import os

PROJECT_ID = os.getenv("AGENT_MKT_PROJECT_ID")
if not PROJECT_ID:
    print("❌ AGENT_MKT_PROJECT_ID environment variable is not set.")
    exit(1)
db = firestore.Client(project=PROJECT_ID)

# Create dummy agents if they don't exist
buyer_id = "test-buyer-rep"
seller_id = "test-seller-rep"

db.collection("agents").document(buyer_id).set({
    "id": buyer_id,
    "global_reputation": 50.0,
    "type": "buyer"
})
db.collection("agents").document(seller_id).set({
    "id": seller_id,
    "global_reputation": 50.0,
    "type": "seller"
})

print(f"Created test agents: {buyer_id}, {seller_id}")

# Create a COMPLETED transaction
tx_id = f"tx-{uuid.uuid4().hex[:8]}"
db.collection("transactions").document(tx_id).set({
    "transaction_id": tx_id,
    "buyer_id": buyer_id,
    "seller_id": seller_id,
    "amount": 100.0,
    "status": "COMPLETED",
    "timestamp": time.time()
})

print(f"Injected COMPLETED transaction: {tx_id}")
print("Check logs for reputation update...")
