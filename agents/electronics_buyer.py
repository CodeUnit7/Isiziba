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
logger = logging.getLogger("electronics_buyer")

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
ITEMS = ["Noise Cancelling Headphones", "4K Monitor", "Mechanical Keyboard"]

vertexai.init(project=PROJECT_ID, location=REGION)
model = GenerativeModel(MODEL_NAME)

class ElectronicsBuyer:
    def __init__(self):
        self.client = MarketClient("buyer", "Circuit City Buyer", os.getenv("AGENT_MKT_ELECTRONICS_BUYER_CATEGORY", "electronics"), api_url=API_URL)
        reg_token = os.getenv("AGENT_MKT_REGISTRATION_TOKEN")
        if not reg_token: raise ValueError("❌ AGENT_MKT_REGISTRATION_TOKEN is missing")
        self.client.register(registration_token=reg_token)
        self.client.start_market_listener()
        self.negotiation_state = {}
        self.executor = ThreadPoolExecutor(max_workers=2)

    def run(self):
        logger.info("📡 Electronics Buyer started.")
        # One-off request
        item = random.choice(ITEMS)
        qty = random.randint(1, 3)
        budget = random.uniform(200, 500)
        logger.info(f"🔄 Requesting {item} x{qty} target budget ${budget}")
        self.client.post_request(item, budget, quantity=qty)
        
        while True:
            # Process events
            event = self.client.get_event()
            if event:
                self.process_event(event)

    def process_event(self, event):
        etype = event.get("type")
        if etype == "negotiation_concluded":
            logger.info("🎉 SUCCESS! Electronic deal finalized.")
            # Record state to stop loop
            if os.getenv("AGENT_MKT_CONTINUOUS", "true").lower() == "false":
                logger.info("🛑 Simulation mode: Non-continuous. Exiting.")
                sys.exit(0)
            
            self.start_new_request() # Start again if continuous
        if etype == "market_event":
            data = event["data"]
            if data.get("receiver_id") == self.client.agent_id:
                neg_id = data.get("negotiation_id")
                if self.negotiation_state.get(neg_id) in ["COMPLETED", "FAILED"]: return
                
                # Logic similar to base buyer but with electronics persona
                self.executor.submit(self.consult_ai, data)

    def consult_ai(self, data):
        # AI logic would go here (omitted for brevity in this initial file creation)
        # For now, let's just use a simple accept if it's within budget
        price = data.get("price", 999)
        qty = data.get("quantity", 1)
        neg_id = data.get("negotiation_id")
        offer_id = data.get("offer_id")
        sender = data.get("sender_id")
        
        if price < 400:
            self.client.negotiate(neg_id, offer_id, "ACCEPT", sender, price, quantity=qty, reasoning="Great price for tech!")
        else:
            self.client.negotiate(neg_id, offer_id, "COUNTER", sender, 350, quantity=qty, reasoning="Can we do a tech discount?")

if __name__ == "__main__":
    agent = ElectronicsBuyer()
    agent.run()
