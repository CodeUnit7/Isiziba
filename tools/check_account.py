import google.auth
import os

def check_account():
    try:
        creds, project = google.auth.default()
        
        # Priority 1: Use provided PROJECT_ID if set
        # Priority 2: Use project from credentials
        PROJECT_ID = os.getenv("AGENT_MKT_PROJECT_ID", project)
        
        if not PROJECT_ID:
            print("❌ PROJECT_ID could not be determined from environment or credentials.")
            return

        print(f"✅ Credentials found for: {getattr(creds, 'service_account_email', 'User Account')}")
        print(f"✅ Using Project: {PROJECT_ID}")
        
        from google.cloud import resourcemanager_v3
        client = resourcemanager_v3.ProjectsClient(credentials=creds)
        p = client.get_project(name=f"projects/{PROJECT_ID}")
        print(f"✅ Successfully accessed project: {p.display_name}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_account()
