import google.auth
from google.cloud import resourcemanager_v3

import os

PROJECT_ID = os.getenv("AGENT_MKT_PROJECT_ID")
if not PROJECT_ID:
    print("❌ AGENT_MKT_PROJECT_ID environment variable is not set.")
    exit(1)

def check_iam():
    creds, project = google.auth.default()
    client = resourcemanager_v3.ProjectsClient(credentials=creds)
    
    resource = f"projects/{PROJECT_ID}"
    print(f"🔐 Checking IAM policy for {PROJECT_ID}...")
    try:
        policy = client.get_iam_policy(resource=resource)
        for binding in policy.bindings:
            print(f"   Role: {binding.role}")
            for member in binding.members:
                print(f"     - {member}")
    except Exception as e:
        print(f"❌ Error getting IAM policy: {e}")

if __name__ == "__main__":
    check_iam()
