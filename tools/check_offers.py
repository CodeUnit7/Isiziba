from google.cloud import firestore
import os

# Explicitly set project ID if not in env, though I pass it in command
project_id = os.getenv("AGENT_MKT_PROJECT_ID")

db = firestore.Client(project=project_id)
docs = db.collection("offers").order_by("created_at", direction=firestore.Query.DESCENDING).limit(10).stream()

print("Checking recent offers:")
for doc in docs:
    bs = doc.to_dict()
    print(f"ID: {doc.id} | Product: {bs.get('product')} | OfferID in Data: {bs.get('offer_id')}")
