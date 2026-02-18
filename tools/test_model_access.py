import google.auth
from google.cloud import aiplatform_v1

import os

PROJECT_ID = os.getenv("AGENT_MKT_PROJECT_ID", os.getenv("GCP_PROJECT"))
if not PROJECT_ID:
    print("❌ PROJECT_ID environment variable is not set.")
    exit(1)
LOCATION = os.getenv("AGENT_MKT_REGION", "us-central1")

def list_publisher_models():
    creds, project = google.auth.default()
    client_options = {"api_endpoint": f"{LOCATION}-aiplatform.googleapis.com"}
    client = aiplatform_v1.ModelServiceClient(client_options=client_options, credentials=creds)
    
    # The parent for publisher models is just the location
    parent = f"projects/{PROJECT_ID}/locations/{LOCATION}/publishers/google"
    
    print(f"🔍 Listing Google models in {LOCATION} for project {PROJECT_ID}...")
    try:
        # Note: list_models might not work for publishers the same way
        # We might need to use the Model Garden API or just check common names
        result = client.list_models(parent=f"projects/{PROJECT_ID}/locations/{LOCATION}")
        print("--- Project Models ---")
        for m in result:
            print(f"   - {m.display_name} ({m.name})")
            
        # Try to get a specific publisher model directly to see the error
        model_id = os.getenv("AGENT_MKT_MODEL", "gemini-1.5-flash-001")
        model_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/publishers/google/models/{model_id}"
        print(f"   🔮 Invoking {model_name}...")
        
        request = aiplatform.gapic.GenerateContentRequest(
            model=model_name,
            contents=[{"role": "user", "parts": [{"text": "Hi"}]}]
        )
        response = client.generate_content(request)
        print(f"✅ SUCCESS for {model_id}!")
    except Exception as e:
        if "429" in str(e):
             print("✅ QUOTA REACHED (429) - This confirms ACCESS to the model is working!")
        else:
            print(f"❌ Could not get {model_id}: {e}")

if __name__ == "__main__":
    list_publisher_models()
