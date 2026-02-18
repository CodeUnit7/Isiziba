import os
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"
import json
import time
import random
from typing import Dict, Any
import vertexai
from vertexai.generative_models import GenerativeModel
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.config")





# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("cloud_seller")

# Add parent dir to path for lib import
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from lib.client import MarketClient

# Configuration
PROJECT_ID = os.getenv("AGENT_MKT_PROJECT_ID")
if not PROJECT_ID:
    logger.error("❌ AGENT_MKT_PROJECT_ID environment variable is not set.")
    sys.exit(1)

REGION = os.getenv("AGENT_MKT_REGION", "us-central1")
API_URL = os.getenv("AGENT_MKT_API_URL")
if not API_URL:
    raise ValueError("❌ AGENT_MKT_API_URL environment variable is not set.")
REGISTRATION_TOKEN = os.getenv("AGENT_MKT_REGISTRATION_TOKEN")
if not REGISTRATION_TOKEN:
    raise ValueError("❌ AGENT_MKT_REGISTRATION_TOKEN environment variable is not set.")
MODEL_NAME = os.getenv("AGENT_MKT_MODEL")
if not MODEL_NAME:
    raise ValueError("❌ AGENT_MKT_MODEL environment variable is not set.")

# Domain Specific Config
INVENTORY = {
    "compute": {"price": 100.0, "desc": "High Performance Compute Node (H100)"},
    "gpu": {"price": 120.0, "desc": "GPU Cluster Time"},
    "storage": {"price": 0.02, "desc": "1GB Hot Storage"}
}

DEFAULT_FLOOR_PRICE = float(os.getenv("AGENT_MKT_SELLER_FLOOR_PRICE", "100.0"))

# Initialize Vertex AI
vertexai.init(project=PROJECT_ID, location=REGION)
model = GenerativeModel(MODEL_NAME)

class InternalSeller:
    def __init__(self):
        # Fix: agent_type="seller", name=..., category=..., api_url=API_URL
        self.client = MarketClient(
            "seller", 
            os.getenv("AGENT_MKT_SELLER_NAME", "Nova Systems"), 
            os.getenv("AGENT_MKT_SELLER_CATEGORY", "cloud"), 
            api_url=API_URL
        )

        # Register to get platform identity
        reg_data = self.client.register(registration_token=REGISTRATION_TOKEN)
        logger.info(f"✅ Dynamic Registration: {reg_data}")
        # Identify for WebSockets
        self.client.update_status("IDLE", "Nova Systems ready")
        self.inventory = INVENTORY
        self.active_negotiations = {} # Maps negotiation_id -> inventory_key
        self.executor = ThreadPoolExecutor(max_workers=int(os.getenv("AGENT_MKT_MAX_WORKERS", "3")))

    def run(self):
        # Skip registration if using static keys for speed, or ensure it exists
        logger.info(f"📡 Seller started with ID: {self.client.agent_id}")
        self.client.start_market_listener()
        
        # Post initial offers to populate the Order Book
        logger.info("📢 Posting initial offers to Order Book...")
        for item_key, item_data in self.inventory.items():
            self.client.post_offer(
                item_data["desc"], 
                item_data["price"] * 1.2, # Start with a markup
                quantity=10,
                buyer_id="market" # Broadcast to all
            )
            time.sleep(0.2) # Avoid rate limits

        
        while True:
            # 1. Wait for an event with a timeout
            event = self.client.get_event(timeout=float(os.getenv("AGENT_MKT_POLL_TIMEOUT", "1.0")))
            
            if event:
                event_type = event.get("type")
                
                # --- NEW: Negotiation Termination Handling ---
                if event_type == "negotiation_concluded":
                    logger.info(f"🎉 Negotiation CONCLUDED! Sold {event.get('product')} for ${event.get('price')}")
                    # Mark as dead but keep in cache briefly to reject stragglers? 
                    # Actually better to just remove from active_negotiations which implies "no inventory lock", 
                    # but we need a "Dead" set to know to ignore it.
                    neg_id = event.get("negotiation_id")
                    if neg_id:
                        # Use a sentinel value in active_negotiations to mean "DEAD" instead of deleting?
                        # Or just delete. If deleted, evaluate_proposal falls back to heuristic.
                        # We need explicit ignore. active_negotiations was mapping to inventory key.
                        # Let's use a separate set for TERMINATED IDs.
                        self.active_negotiations[neg_id] = "TERMINATED" 
                        
                    self.client.update_status("IDLE", "Deal successful")
                    
                    if os.getenv("AGENT_MKT_CONTINUOUS", "true").lower() == "false":
                        logger.info("🛑 Simulation mode: Non-continuous. Exiting after deal.")
                        sys.exit(0)
                    continue

                if event_type == "negotiation_terminated":
                    logger.info(f"🛑 Negotiation TERMINATED. Reason: {event.get('reason')}")
                    neg_id = event.get("negotiation_id")
                    if neg_id:
                        self.active_negotiations[neg_id] = "TERMINATED"
                        
                    self.client.update_status("IDLE", "Negotiation failed")
                    
                    if os.getenv("AGENT_MKT_CONTINUOUS", "true").lower() == "false":
                        logger.info("🛑 Simulation mode: Non-continuous. Exiting after failure.")
                        sys.exit(0)
                    continue
                
                if event_type == "feedback_report":
                   logger.info(f"🎓 [Coach] Received Feedback for {event.get('negotiation_id')}")
                   continue

                if event_type == "market_event":
                    data = event["data"]
                    
                    # DEBUG: Log every event details
                    if data.get("receiver_id") or data.get("buyer_id"):
                         logger.debug(f"🔍 [Seller] Event target: {data.get('receiver_id') or data.get('buyer_id')} (Mine: {self.client.agent_id})")

                    # 1. Look for Buyer Requests
                    if data.get("type") == "Request":
                        self.process_request(data)
                    
                    # 2. Look for Proposals targeting me
                    elif data.get("type") == "Proposal" and data.get("receiver_id") == self.client.agent_id:
                        neg_id = data.get("negotiation_id")
                        if self.active_negotiations.get(neg_id) == "TERMINATED":
                             logger.info(f"🗑️ [Loop Guard] Dropping stale proposal for terminated negotiation {neg_id}")
                             continue
                             
                        self.evaluate_proposal(data)

    def process_request(self, request: dict):
        """Initial reaction to a buyer request using Challenger strategy."""
        item = request.get("item", "").lower()
        logger.info(f"👀 Seller saw request for: {item}")
        self.client.update_status("SELLING", f"Analyzing needs for {item}")
        
        # Simple match for base pricing
        match = None
        for k, v in self.inventory.items():
            if k in item: match = v
            
        if match:
            # Consult AI for the first offer too, to set a high anchor with Challenger reasoning
            self.executor.submit(self._consult_strategy_model, request, match, True)

    def evaluate_proposal(self, proposal: dict):
        """Evaluates a counter-proposal from the buyer."""
        action = proposal["action"]
        price = proposal["price"]
        
        if action == "ACCEPT":
             # Redundant with client.py filtering.
             return
            
        # Match inventory for base comparison
        neg_id = proposal.get("negotiation_id")
        match = None
        inventory_key = self.active_negotiations.get(neg_id)
        
        if inventory_key:
            match = self.inventory[inventory_key]
        else:
            # Fallback to heuristic matching if not in cache
            item_hint = (proposal.get("offer_id", "") + proposal.get("item", "") + proposal.get("product", "")).lower()
            for k, v in self.inventory.items():
                if k in item_hint: 
                    match = v
                    self.active_negotiations[neg_id] = k # Cache for future counters
                    break
        
        logger.info(f"🤔 Buyer countered with {price}. Consulting Challenger strategy...")
        self.client.update_status("NEGOTIATING", f"Evaluating counter for {proposal.get('product')}")
        self.executor.submit(self._consult_strategy_model, proposal, match, False)

    def _consult_strategy_model(self, data: dict, inventory_match: dict, is_initial: bool):
        """Consults the LLM for the Challenger move."""
        item_name = data.get("item") or data.get("product") or "Premium Asset"
        buyer_price = data.get("price") if not is_initial else "N/A (First Offer)"
        quantity = data.get("quantity", 1)
        
        # Robust floor price check
        floor_price = DEFAULT_FLOOR_PRICE
        if inventory_match and isinstance(inventory_match, dict):
            floor_price = inventory_match.get("price", DEFAULT_FLOOR_PRICE)
        
        system_prompt = f"""
        You are a high-performance B2B Sales Executive using the 'Challenger Sales' methodology.
        You are selling: '{item_name}' (Quantity: {quantity}).
        Your Floor Price per unit: ${floor_price:.2f}.
        Your Goal: Maximize margin by teaching the buyer about value, not just competing on price.
        
        Techniques to apply:
        1. **Teach for Differentiation**: Explain why your solution is technically superior (Uptime, speed, reliability).
        2. **Tailor for Resonance**: Speak to the risks of chosen "cheap" alternatives.
        3. **Take Control**: Assert the price. Don't be "agreeable"—be a "challenger". Push back if the buyer is being unreasonable.
        
        Context:
        - This is an initial offer? {is_initial}
        - Incoming Buyer Price: {buyer_price}
        - **Impatience**: If the buyer is moving too slowly (small increments), give a 'Final Offer' warning.
        
        Output strict JSON only:
        {{
          "action": "COUNTER" | "ACCEPT" | "REJECT",
          "price": number,
          "reasoning": "The message to send to the buyer (Challenger-style, educational, assertive)",
          "internal_thought": "My strategic reason for this move"
        }}
        """
        
        try:
            response = model.generate_content(system_prompt)
            # Clean generic markdown code blocks
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            decision = json.loads(clean_text)
            
            logger.info(f"💡 [Challenger Thought] {decision['internal_thought']}")
            
            neg_id = data.get("negotiation_id") or "neg-" + data.get("id", "x")[-8:]
            offer_id = data.get("offer_id") or data.get("id")
            
            # Determine the counterpart ID strictly based on sender_id
            buyer_id = data.get("sender_id")
            
            if not buyer_id:
                logger.warning(f"⚠️ Warning: Could not determine buyer ID from data: {data}")
                return # Cannot proceed safely

            # Ensure this negotiation is cached if we have an inventory match
            if inventory_match:
                for k, v in self.inventory.items():
                    if v == inventory_match:
                        self.active_negotiations[neg_id] = k
                        break

            # LATE ARRIVAL GUARD: Check if the deal was terminated while we were thinking
            if self.active_negotiations.get(neg_id) == "TERMINATED":
                 logger.info(f"🗑️ [Loop Guard] Negotiation {neg_id} terminated while thinking. Dropping decision.")
                 return

            if decision["action"] == "ACCEPT":
                logger.info(f"✅ AI Decided to ACCEPT at ${data.get('price')} (x{quantity})")
                self.client.negotiate(neg_id, offer_id, "ACCEPT", buyer_id, data.get('price'), quantity=quantity, reasoning=decision["reasoning"])
            
            elif decision["action"] == "COUNTER":
                price = decision["price"]
                # Safeguard floor
                if price < floor_price: price = floor_price * 1.1
                
                logger.info(f"💬 AI Decided to COUNTER at ${price}")
                if is_initial:
                    # Initial offers use the dedicated endpoint
                    self.client.post_offer(buyer_id, inventory_match["desc"], price, quantity=quantity)
                    # We can't send reasoning on initial post_offer in this API, but we'll follow up in negotiation
                else:
                    self.client.negotiate(neg_id, offer_id, "COUNTER", buyer_id, price, quantity=quantity, reasoning=decision["reasoning"])

        except Exception as e:
            logger.error(f"⚠️ Challenger Strategy Failed: {e}")
            # Simple fallback
            if not is_initial:
                self.client.negotiate(data.get("negotiation_id"), data.get("offer_id"), "COUNTER", data.get("sender_id"), floor_price * 1.2, reasoning="Consolidating our best technical offer.")
            else:
                self.client.post_offer(data.get("buyer_id"), inventory_match["desc"], floor_price * 1.2)

if __name__ == "__main__":
    seller = InternalSeller()
    seller.run()
