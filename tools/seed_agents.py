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

def seed_agents():
    print("🧹 Cleaning up existing market data (Optional/Debug)...")
    # For now, we'll just log and proceed.
    
    agents = []

    if not agents:
        print("ℹ️ No static agents to seed. System will rely on dynamic registration.")
        return

    for agent in agents:
        try:
            db.collection("agents").document(agent["id"]).set(agent)
            print(f"✅ Seeded agent: {agent['id']}")
        except Exception as e:
            print(f"⚠️ Failed to seed agent {agent['id']}: {e}")

if __name__ == "__main__":
    seed_agents()
