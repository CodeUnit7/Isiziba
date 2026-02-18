import os
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"
import json
import time
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
logger = logging.getLogger("electronics_seller")

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

# Specialized Inventory
INVENTORY = {
    "headphones": {"price": 350.0, "desc": "Noise Cancelling Headphones"},
    "monitor": {"price": 450.0, "desc": "4K Ultra-Wide Monitor"},
    "keyboard": {"price": 180.0, "desc": "Mechanical Gaming Keyboard"}
}

vertexai.init(project=PROJECT_ID, location=REGION)
model = GenerativeModel(MODEL_NAME)

class ElectronicsSeller:
    def __init__(self):
        # Fix: agent_type="seller", name=..., category=..., api_url=API_URL
        self.client = MarketClient(
            "seller", 
            "Silicon Alley Sales", 
            os.getenv("AGENT_MKT_ELECTRONICS_SELLER_CATEGORY", "electronics"),
            api_url=API_URL
        )

        reg_token = os.getenv("AGENT_MKT_REGISTRATION_TOKEN")
        if not reg_token: raise ValueError("❌ AGENT_MKT_REGISTRATION_TOKEN is missing")
        self.client.register(registration_token=reg_token)
        self.client.start_market_listener()

        # Post initial offers to populate the Order Book
        logger.info("📢 Posting initial offers to Order Book...")
        for item_key, item_data in self.inventory.items():
            self.client.post_offer(
                item_data["desc"], 
                item_data["price"] * 1.15, # Start with a markup
                quantity=5,
                buyer_id="market" # Broadcast to all
            )
            time.sleep(0.2)

        self.active_negotiations = {}
        self.executor = ThreadPoolExecutor(max_workers=2)

    def run(self):
        logger.info("📡 Electronics Seller started.")
        while True:
            event = self.client.get_event()
            if event:
                self.process_event(event)

    def process_event(self, event):
        etype = event.get("type")
        if etype == "negotiation_concluded":
            logger.info("🎉 SOLD!")
            if os.getenv("AGENT_MKT_CONTINUOUS", "true").lower() == "false":
                logger.info("🛑 Simulation mode: Non-continuous. Exiting.")
                sys.exit(0)
        if etype == "market_event":
            data = event["data"]
            if data.get("type") == "Request":
                item = data.get("item", "").lower()
                for k, v in INVENTORY.items():
                    if k in item:
                        qty = data.get("quantity", 1)
                        # Challenger move: start high
                        self.client.post_offer(data.get("buyer_id"), v["desc"], v["price"] * 1.2, quantity=qty)
                        break
            elif data.get("type") == "Proposal" and data.get("receiver_id") == self.client.agent_id:
                # Basic response
                neg_id = data.get("negotiation_id")
                offer_id = data.get("offer_id")
                sender = data.get("sender_id")
                price = data.get("price")
                qty = data.get("quantity", 1)
                
                # Heuristic: accept if price > 90% of base
                item_hint = data.get("product", "").lower()
                base_price = 300
                for k, v in INVENTORY.items():
                    if k in item_hint: base_price = v["price"]
                
                if price >= base_price * 0.95:
                    self.client.negotiate(neg_id, offer_id, "ACCEPT", sender, price, quantity=qty, reasoning="That is a fair deal for quality gear.")
                else:
                    self.client.negotiate(neg_id, offer_id, "COUNTER", sender, base_price, quantity=qty, reasoning="Our hardware integrity justifies this price.")

if __name__ == "__main__":
    agent = ElectronicsSeller()
    agent.run()
