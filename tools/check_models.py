import os
from google.cloud import aiplatform
import vertexai
from vertexai.generative_models import GenerativeModel

PROJECT_ID = os.getenv("AGENT_MKT_PROJECT_ID", os.getenv("GCP_PROJECT"))
if not PROJECT_ID:
    print("❌ PROJECT_ID environment variable is not set.")
    exit(1)
REGION = os.getenv("AGENT_MKT_REGION", "us-central1")

print(f"Checking models for project {PROJECT_ID} in {REGION}")

vertexai.init(project=PROJECT_ID, location=REGION)

try:
    # Try to list models using the Model Garden API or just try to instantiate common ones
    common_models = [
        os.getenv("AGENT_MKT_MODEL", "gemini-2.0-flash"),
        "gemini-1.5-flash-001",
        "gemini-1.5-pro-001",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-1.0-pro",
        "gemini-pro"
    ]
    # Deduplicate preserving order
    common_models = list(dict.fromkeys(filter(None, common_models)))
    
    print("\nTesting model instantiation:")
    for model_name in common_models:
        try:
            print(f"  Checking {model_name}...", end=" ", flush=True)
            model = GenerativeModel(model_name)
            response = model.generate_content("Hello")
            print(f"✅ AVAILABLE")
        except Exception as e:
            print(f"❌ FAILED: {str(e)}")

except Exception as e:
    print(f"Global error: {e}")
