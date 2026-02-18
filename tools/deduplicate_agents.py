import os
import sys

# P0: Fix gRPC hang on macOS forked processes
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"

from google.cloud import firestore

PROJECT_ID = os.getenv("AGENT_MKT_PROJECT_ID")
if not PROJECT_ID:
    print("❌ AGENT_MKT_PROJECT_ID environment variable is not set. Please set it before running this script.")
    sys.exit(1)

print(f"🌱 Initializing Firestore for project: {PROJECT_ID}")

try:
    db = firestore.Client(project=PROJECT_ID)
except Exception as e:
    print(f"❌ Failed to initialize Firestore: {e}")
    sys.exit(1)

def deduplicate_agents():
    print("🧹 Starting Agent Deduplication...")
    
    # 1. Fetch all agents
    docs = db.collection("agents").stream()
    all_agents = [doc.to_dict() for doc in docs]
    
    # 2. Group by Name + Type
    grouped = {}
    for agent in all_agents:
        key = f"{agent.get('name')}|{agent.get('type')}"
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(agent)
        
    print(f"🔍 Found {len(all_agents)} total agent records across {len(grouped)} unique identities.")
    
    deleted_count = 0
    
    for key, group in grouped.items():
        if len(group) > 1:
            name, type_ = key.split("|")
            print(f"\n⚠️  Found duplicates for {name} ({len(group)} records):")
            
            # Sort by total_transactions (desc), then global_reputation (desc), then created_at (asc - oldest first)
            # Actually, we want to keep the one that is most active/valuable.
            group.sort(key=lambda x: (x.get("total_transactions", 0), x.get("global_reputation", 0)), reverse=True)
            
            winner = group[0]
            losers = group[1:]
            
            print(f"   🏆 WINNER: {winner['id']} (Tx: {winner.get('total_transactions', 0)}, Rep: {winner.get('global_reputation', 0)})")
            
            for loser in losers:
                print(f"   🗑️  DELETING: {loser['id']} (Tx: {loser.get('total_transactions', 0)}, Rep: {loser.get('global_reputation', 0)})")
                try:
                    db.collection("agents").document(loser['id']).delete()
                    deleted_count += 1
                except Exception as e:
                    print(f"   ❌ Failed to delete {loser['id']}: {e}")
                    
    print(f"\n✅ Deduplication Complete. Removed {deleted_count} duplicate records.")

if __name__ == "__main__":
    deduplicate_agents()
