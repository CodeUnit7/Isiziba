
import os
from google.cloud import firestore

PROJECT_ID = "agent-mkt-phase0-1770837416"
db = firestore.Client(project=PROJECT_ID)

def check_products():
    tx_docs = db.collection('transactions').stream()
    products = {}
    for doc in tx_docs:
        p = doc.to_dict().get('product', 'Unknown')
        products[p] = products.get(p, 0) + 1
    
    print("Product Distribution in Transactions:")
    for p, count in products.items():
        print(f"  - {p}: {count}")

    neg_docs = db.collection('negotiations').limit(100).stream()
    neg_products = {}
    for doc in neg_docs:
        p = doc.to_dict().get('product', 'Unknown')
        neg_products[p] = neg_products.get(p, 0) + 1
    
    print("\nProduct Distribution in Negotiations (Sample 100):")
    for p, count in neg_products.items():
        print(f"  - {p}: {count}")

if __name__ == "__main__":
    check_products()
