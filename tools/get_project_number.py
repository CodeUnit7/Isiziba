import google.auth
from google.cloud import resourcemanager_v3

import os

PROJECT_ID = os.getenv("AGENT_MKT_PROJECT_ID")
if not PROJECT_ID:
    print("❌ AGENT_MKT_PROJECT_ID environment variable is not set.")
    exit(1)

def get_project_number():
    creds, project = google.auth.default()
    client = resourcemanager_v3.ProjectsClient(credentials=creds)
    name = f"projects/{PROJECT_ID}"
    p = client.get_project(name=name)
    # The name is in the format 'projects/PROJECT_NUMBER'
    print(f"✅ Project ID: {p.project_id}")
    print(f"✅ Project Name: {p.name}")

if __name__ == "__main__":
    get_project_number()
