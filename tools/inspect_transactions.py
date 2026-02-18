import os
from google.cloud import firestore

PROJECT_ID = os.getenv("AGENT_MKT_PROJECT_ID")
if not PROJECT_ID:
    print("❌ AGENT_MKT_PROJECT_ID environment variable is not set.")
    exit(1)

db = firestore.Client(project=PROJECT_ID)

def inspect_transactions():
    print(f"🔍 Inspecting last 10 transactions in {PROJECT_ID}...")
    docs = db.collection("transactions").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).stream()
    
    for doc in docs:
        data = doc.to_dict()
        print(f"ID: {doc.id} | Amount: {data.get('amount')} | Buyer: {data.get('buyer_id')} | Status: {data.get('status')}")

if __name__ == "__main__":
    inspect_transactions()
