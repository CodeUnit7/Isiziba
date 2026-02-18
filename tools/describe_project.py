import google.auth
from google.cloud import resourcemanager_v3

import os

PROJECT_ID = os.getenv("AGENT_MKT_PROJECT_ID")
if not PROJECT_ID:
    print("❌ AGENT_MKT_PROJECT_ID environment variable is not set.")
    exit(1)

def describe_project():
    creds, project = google.auth.default()
    client = resourcemanager_v3.ProjectsClient(credentials=creds)
    
    name = f"projects/{PROJECT_ID}"
    print(f"🔍 Describing project {PROJECT_ID}...")
    try:
        project = client.get_project(name=name)
        print(f"✅ Project Found:")
        print(f"   - Display Name: {project.display_name}")
        print(f"   - State: {project.state}")
        print(f"   - Create Time: {project.create_time}")
    except Exception as e:
        print(f"❌ Error getting project: {e}")

if __name__ == "__main__":
    describe_project()
