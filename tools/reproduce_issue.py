import os
import vertexai
from vertexai.generative_models import GenerativeModel
import google.auth
import traceback
import time

PROJECT_ID = os.getenv("AGENT_MKT_PROJECT_ID", os.getenv("GCP_PROJECT"))
if not PROJECT_ID:
    print("❌ PROJECT_ID environment variable is not set.")
    exit(1)
LOCATION = os.getenv("AGENT_MKT_REGION", "us-central1")

def test_sdk_2_0():
    print(f"DEBUG: PROJECT_ID={PROJECT_ID}")
    
    try:
        creds, project = google.auth.default()
        print(f"🔐 Credentials loaded for: {getattr(creds, 'service_account_email', 'User Account')}")
    except Exception as e:
        print(f"❌ Credential Error: {e}")

    models = ["gemini-2.0-flash", "gemini-1.5-flash-001"]
    env_model = os.getenv("AGENT_MKT_MODEL")
    if env_model and env_model not in models:
        models.insert(0, env_model)
    
    for model_id in models:
        print(f"\n🌍 Testing {LOCATION} with {model_id}")
        try:
            vertexai.init(project=PROJECT_ID, location=LOCATION)
            model = GenerativeModel(model_id)
            print(f"   🔮 Invoking {model_id}...")
            response = model.generate_content("Hi")
            print(f"✅ SUCCESS for {model_id}!")
            print(f"   Response Preview: {response.text[:50]}...")
            break
        except Exception as e:
            if "429" in str(e):
                print(f"✅ QUOTA REACHED (429) for {model_id} - This confirms ACCESS is working!")
                break
            elif "404" in str(e):
                print(f"❌ 404 NOT FOUND for {model_id}")
            else:
                print(f"❌ FAILED for {model_id}: {e}")

if __name__ == "__main__":
    test_sdk_2_0()







