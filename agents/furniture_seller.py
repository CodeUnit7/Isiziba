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
logger = logging.getLogger("furniture_seller")

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

# Inventory
INVENTORY = {
    "chair": {"price": 300.0, "desc": "Ergonomic Office Chair"},
    "desk": {"price": 800.0, "desc": "Electric Standing Desk"},
    "table": {"price": 150.0, "desc": "Modern Coffee Table"}
}

vertexai.init(project=PROJECT_ID, location=REGION)
model = GenerativeModel(MODEL_NAME)

class FurnitureSeller:
    def __init__(self):
        self.client = MarketClient("seller", "IKEA Style Seller", os.getenv("AGENT_MKT_FURNITURE_SELLER_CATEGORY", "furniture"), api_url=API_URL)
        reg_token = os.getenv("AGENT_MKT_REGISTRATION_TOKEN")
        if not reg_token: raise ValueError("❌ AGENT_MKT_REGISTRATION_TOKEN is missing")
        self.client.register(registration_token=reg_token)
        self.client.start_market_listener()

        # Post initial offers to populate the Order Book
        logger.info("📢 Posting initial offers to Order Book...")
        for item_key, item_data in INVENTORY.items():
            markup = random.uniform(1.05, 1.15)
            price = round(item_data["price"] * markup, 2)
            self.client.post_offer(
                item_data["desc"], 
                price, 
                quantity=8,
                buyer_id="market" # Broadcast to all
            )
            time.sleep(0.2)

        self.executor = ThreadPoolExecutor(max_workers=2)

    def run(self):
        logger.info("📡 Furniture Seller started.")
        while True:
            event = self.client.get_event()
            if event:
                self.process_event(event)

    def process_event(self, event):
        etype = event.get("type")
        if etype == "negotiation_concluded":
            logger.info("🎉 Deal concluded!")
            if os.getenv("AGENT_MKT_CONTINUOUS", "true").lower() == "false":
                logger.info("🛑 Simulation mode: Non-continuous. Exiting.")
                sys.exit(0)
        
        if etype == "market_event":
            data = event["data"]
            if data.get("type") == "Request":
                item = data.get("item", "").lower()
                for k, v in INVENTORY.items():
                    if k in item:
                        markup = random.uniform(1.05, 1.15)
                        price = round(v["price"] * markup, 2)
                        logger.info(f"📢 Request for {item}: Offering {v['desc']} at {price} (markup {markup:.2f})")
                        self.client.post_offer(v["desc"], price, quantity=data.get("quantity", 1), buyer_id=data.get("buyer_id", "market"))
                        break
            
            elif data.get("type") == "Proposal" and data.get("receiver_id") == self.client.agent_id:
                # Handle counter-offers
                neg_id = data.get("negotiation_id")
                offer_id = data.get("offer_id")
                sender = data.get("sender_id")
                price = data.get("price")
                qty = data.get("quantity", 1)
                
                # Simple logic: accept anything above 80% of base price
                item_hint = data.get("product", "").lower()
                base_price = 150 # Default low
                for k, v in INVENTORY.items():
                    if k in item_hint: base_price = v["price"]
                
                if price >= base_price * 0.95:
                    self.client.negotiate(neg_id, "ACCEPT", offer_id, sender, price, quantity=qty, reasoning="Agreed. Quality meets value.")
                else:
                    # Counter with valid variation
                    counter_price = round(base_price * random.uniform(0.95, 1.05), 2)
                    self.client.negotiate(neg_id, "COUNTER", offer_id, sender, counter_price, quantity=qty, reasoning="I can't go that low for this craftsmanship.")

if __name__ == "__main__":
    agent = FurnitureSeller()
    agent.run()
