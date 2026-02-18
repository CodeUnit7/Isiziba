import os
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"
import json
import time
import random
import sys
import vertexai
from vertexai.generative_models import GenerativeModel
import logging
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.config")

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("furniture_buyer")

# Add parent dir to path for lib import
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from lib.client import MarketClient

PROJECT_ID = os.getenv("AGENT_MKT_PROJECT_ID")
REGION = os.getenv("AGENT_MKT_REGION", "us-central1")
API_URL = os.getenv("AGENT_MKT_API_URL")
if not API_URL:
    raise ValueError("❌ AGENT_MKT_API_URL environment variable is not set.")
MODEL_NAME = os.getenv("AGENT_MKT_MODEL")
if not MODEL_NAME:
    raise ValueError("❌ AGENT_MKT_MODEL environment variable is not set.")

# Specialized Items
ITEMS = ["Ergonomic Chair", "Standing Desk", "Coffee Table"]

vertexai.init(project=PROJECT_ID, location=REGION)
model = GenerativeModel(MODEL_NAME)

class FurnitureBuyer:
    def __init__(self):
        self.client = MarketClient("buyer", "Living Room Buyer", os.getenv("AGENT_MKT_FURNITURE_BUYER_CATEGORY", "furniture"), api_url=API_URL)
        reg_token = os.getenv("AGENT_MKT_REGISTRATION_TOKEN")
        if not reg_token: raise ValueError("❌ AGENT_MKT_REGISTRATION_TOKEN is missing")
        self.client.register(registration_token=reg_token)
        self.client.start_market_listener()
        self.negotiation_state = {}
        self.executor = ThreadPoolExecutor(max_workers=2)

    def run(self):
        logger.info("📡 Furniture Buyer started.")
        self.start_new_request()
        
        while True:
            event = self.client.get_event()
            if event:
                self.process_event(event)

    def start_new_request(self):
        item = random.choice(ITEMS)
        qty = 1
        budget = 600
        logger.info(f"🔄 Requesting {item} x{qty} budget {budget}")
        self.client.post_request(item, budget, quantity=qty)

    def process_event(self, event):
        etype = event.get("type")
        if etype == "negotiation_concluded":
            logger.info("🎉 SUCCESS! Furniture deal finalized. Resting before next purchase...")
            self.negotiation_state["concluded"] = True
            
            if os.getenv("AGENT_MKT_CONTINUOUS", "true").lower() == "false":
                logger.info("🛑 Simulation mode: Non-continuous. Exiting.")
                sys.exit(0)
                
            time.sleep(10) # Wait before next round
            self.start_new_request()
        if etype == "market_event":
            data = event["data"]
            if data.get("receiver_id") == self.client.agent_id:
                # Logic...
                price = data.get("price")
                budget = 850 # Increased budget to match desk price range
                
                if price <= budget:
                     self.client.negotiate(data.get("negotiation_id"), "ACCEPT", data.get("offer_id"), data.get("sender_id"), price, quantity=data.get("quantity", 1), reasoning="Price is acceptable.")
                else:
                     counter = round(budget * random.uniform(0.9, 0.98), 2)
                     self.client.negotiate(data.get("negotiation_id"), "COUNTER", data.get("offer_id"), data.get("sender_id"), counter, quantity=data.get("quantity", 1), reasoning="Can you do better?")

if __name__ == "__main__":
    agent = FurnitureBuyer()
    agent.run()
