from google.cloud import firestore

import os

PROJECT_ID = os.getenv("AGENT_MKT_PROJECT_ID")
if not PROJECT_ID:
    print("❌ AGENT_MKT_PROJECT_ID environment variable is not set.")
    exit(1)

db = firestore.Client(project=PROJECT_ID)

def clear_collections():
    collections = ["transactions", "offers", "negotiations"]
    for coll_name in collections:
        docs = db.collection(coll_name).stream()
        count = 0
        for doc in docs:
            doc.reference.delete()
            count += 1
        print(f"🗑 Cleared {count} documents from {coll_name}")

if __name__ == "__main__":
    clear_collections()
