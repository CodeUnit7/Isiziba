import google.auth
import google.auth.transport.requests
import requests

import os

PROJECT_ID = os.getenv("AGENT_MKT_PROJECT_ID")
if not PROJECT_ID:
    print("❌ AGENT_MKT_PROJECT_ID environment variable is not set.")
    exit(1)

def list_locations():
    creds, project = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    creds.refresh(auth_req)
        
    headers = {"Authorization": f"Bearer {creds.token}"}
    
    # Use the base AI Platform endpoint to list locations
    url = f"https://aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations"
    
    print(f"🌍 Querying locations for project {PROJECT_ID}...")
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            locations = resp.json().get("locations", [])
            if not locations:
                print("   ⚠️ No locations found for this project.")
            else:
                for loc in locations:
                    print(f"   - {loc.get('locationId')}")
        else:
            print(f"❌ API Error: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    list_locations()
