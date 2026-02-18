import google.auth
from google.cloud import service_usage_v1

import os

PROJECT_ID = os.getenv("AGENT_MKT_PROJECT_ID")
if not PROJECT_ID:
    print("❌ AGENT_MKT_PROJECT_ID environment variable is not set.")
    exit(1)

def list_enabled_services():
    creds, project = google.auth.default()
    client = service_usage_v1.ServiceUsageClient(credentials=creds)
    
    parent = f"projects/{PROJECT_ID}"
    request = service_usage_v1.ListServicesRequest(
        parent=parent,
        filter="state:ENABLED"
    )
    
    print(f"✅ Enabled services for {PROJECT_ID}:")
    for service in client.list_services(request=request):
        print(f"   - {service.config.name}")

if __name__ == "__main__":
    try:
        list_enabled_services()
    except Exception as e:
        print(f"❌ Error listing services: {e}")
