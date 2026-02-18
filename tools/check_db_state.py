
import os
import time
from google.cloud import firestore

PROJECT_ID = "agent-mkt-phase0-1770837416"
db = firestore.Client(project=PROJECT_ID)

def check_collections():
    print("--- FIRESTORE DIAGNOSTICS ---")
    
    # 1. Check Negotiations
    neg_count = 0
    neg_docs = db.collection("negotiations").limit(5).stream()
    print("\nNegotiations (Latest 5):")
    for doc in neg_docs:
        neg_count += 1
        d = doc.to_dict()
        print(f"  - [{d.get('timestamp')}] {d.get('negotiation_id')}: {d.get('action')} ${d.get('price')} ({d.get('product')})")
    
    if neg_count == 0:
        print("  - NO NEGOTIATIONS FOUND")
        
    # 2. Check Transactions
    tx_count = 0
    tx_docs = db.collection("transactions").limit(5).stream()
    print("\nTransactions (Latest 5):")
    for doc in tx_docs:
        tx_count += 1
        d = doc.to_dict()
        print(f"  - [{d.get('timestamp')}] {d.get('id')}: {d.get('amount')} USDC for {d.get('product')}")

    if tx_count == 0:
        print("  - NO TRANSACTIONS FOUND")

    # 3. Check Agents
    agent_count = 0
    agent_docs = db.collection("agents").stream()
    print("\nAgents:")
    for doc in agent_docs:
        agent_count += 1
        d = doc.to_dict()
        print(f"  - {d.get('id')} ({d.get('name')}): Status: {d.get('status', 'N/A')}, Transactions: {d.get('total_transactions', 0)}")

if __name__ == "__main__":
    check_collections()
