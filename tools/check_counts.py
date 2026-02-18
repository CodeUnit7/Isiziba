
import os
from google.cloud import firestore

PROJECT_ID = "agent-mkt-phase0-1770837416"
db = firestore.Client(project=PROJECT_ID)

def count_docs():
    print(f"Negotiations count: {len(list(db.collection('negotiations').limit(500).stream()))}")
    print(f"Transactions count: {len(list(db.collection('transactions').limit(500).stream()))}")
    print(f"Market items count: {len(list(db.collection('market_items').limit(500).stream()))}")

    # Check a sample transaction
    txs = list(db.collection('transactions').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(1).stream())
    if txs:
        print("\nSample Transaction:")
        print(txs[0].to_dict())
    else:
        print("\nNo Transactions found.")

    # Check a sample negotiation
    negs = list(db.collection('negotiations').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(1).stream())
    if negs:
        print("\nSample Negotiation:")
        print(negs[0].to_dict())

if __name__ == "__main__":
    count_docs()
