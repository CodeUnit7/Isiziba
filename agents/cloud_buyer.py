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
logger = logging.getLogger("cloud_buyer")

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
IDLE_INTERVAL = float(os.getenv("AGENT_MKT_BUYER_IDLE_INTERVAL", "20.0")) # Keep default as fallback for non-critical tuning

# Domain Specific Config
# Domain Specific Config
TARGET_ITEMS = ["High-Performance Compute Node", "GPU Cluster Time", "Managed Storage Volume"]

BUDGET_CAP = float(os.getenv("AGENT_MKT_BUYER_BUDGET") or 150.00)
ACCEPT_THRESHOLD = float(os.getenv("AGENT_MKT_BUYER_ACCEPT_THRESHOLD") or 120.00)
CONSIDER_THRESHOLD = float(os.getenv("AGENT_MKT_BUYER_CONSIDER_THRESHOLD") or 140.00)

# Initialize Vertex AI
vertexai.init(project=PROJECT_ID, location=REGION)
model = GenerativeModel(MODEL_NAME)

class InternalBuyer:
    def __init__(self):
        self.client = MarketClient("buyer", os.getenv("AGENT_MKT_BUYER_NAME", "Apex Procurement"), os.getenv("AGENT_MKT_BUYER_CATEGORY", "cloud"), api_url=API_URL)
        # Register to get platform identity
        reg_data = self.client.register(registration_token=REGISTRATION_TOKEN)
        logger.info(f"✅ Dynamic Registration: {reg_data}")
        # Identify for WebSockets
        self.client.update_status("IDLE", "Apex Procurement ready")
        self.target_items = TARGET_ITEMS
        self.executor = ThreadPoolExecutor(max_workers=int(os.getenv("AGENT_MKT_MAX_WORKERS", "3")))
        self.negotiation_state = {} # Maps negotiation_id -> status (ACTIVE, COMPLETED, FAILED)

    def run(self):
        # Skip registration if using static keys for speed, or ensure it exists
        logger.info(f"📡 Buyer started with ID: {self.client.agent_id}")
        self.client.start_market_listener()
        
        last_request_time = time.time()
        
        while True:
            # 1. Wait for an event with a timeout (using configured poll timeout)
            event = self.client.get_event(timeout=float(os.getenv("AGENT_MKT_POLL_TIMEOUT", "0.1")))
            
            if event:
                event_type = event.get("type")
                
                # --- NEW: Negotiation Termination Handling ---
                if event_type == "negotiation_concluded":
                   logger.info(f"🎉 Negotiation CONCLUDED! Product: {event.get('product')}, Price: ${event.get('price')}")
                   self.negotiation_state[event.get("negotiation_id")] = "COMPLETED"
                   self.client.update_status("IDLE", "Deal successful")
                   
                   if os.getenv("AGENT_MKT_CONTINUOUS", "true").lower() == "false":
                       logger.info("🛑 Simulation mode: Non-continuous. Exiting after deal.")
                       sys.exit(0)
                   continue 

                if event_type == "negotiation_terminated":
                   logger.info(f"🛑 Negotiation TERMINATED. Reason: {event.get('reason')}")
                   self.negotiation_state[event.get("negotiation_id")] = "FAILED"
                   self.client.update_status("IDLE", "Negotiation failed")
                   
                   if os.getenv("AGENT_MKT_CONTINUOUS", "true").lower() == "false":
                       logger.info("🛑 Simulation mode: Non-continuous. Exiting after failure.")
                       sys.exit(0)
                   continue

                if event_type == "feedback_report":
                   logger.info(f"🎓 [Coach] Received Feedback for {event.get('negotiation_id')}")
                   # feedback is already logged by client.py generic listener, but we can do extra here if needed
                   continue

                if event_type == "market_event":
                    data = event["data"]
                    # DEBUG: Log every event targeting details
                    if data.get("buyer_id") or data.get("receiver_id"):
                        logger.debug(f"🔍 [Buyer] Event target: {data.get('buyer_id') or data.get('receiver_id')} (Mine: {self.client.agent_id})")
                    
                    # Only process offers targeting me
                    if (data.get("type") == "OPEN" or data.get("status") == "OPEN") and data.get("receiver_id") == self.client.agent_id:
                        logger.info(f"🎯 [Buyer] MATCH! Evaluating offer {data.get('offer_id')}")
                        self.evaluate_offer(data)
                        
                    elif data.get("type") == "Proposal" and data.get("receiver_id") == self.client.agent_id:
                        neg_id = data.get("negotiation_id")
                        # STALE CHECK: If this negotiation is already dead locally, ignore it.
                        if self.negotiation_state.get(neg_id) in ["COMPLETED", "FAILED"]:
                            logger.info(f"🗑️ [Loop Guard] Dropping stale proposal for terminated negotiation {neg_id}")
                            continue

                        logger.info(f"🎯 [Buyer] Proposal found! Evaluating counters.")
                        self.negotiation_state[neg_id] = "ACTIVE"
                        self.evaluate_proposal(data)

            # 2. Periodically post new purchase requests (Configurable Interval)
            now = time.time()
            if now - last_request_time > IDLE_INTERVAL:
                # Add a small random jitter to avoid thundering herd
                if random.random() < 0.8:
                    item = random.choice(self.target_items)
                    budget = random.uniform(130.0, 160.0)
                    quantity = random.randint(1, 5) # Default buyer now buys quantities
                    logger.info(f"🔄 [Buyer] Posting API request for: {item} x{quantity} (${budget}/unit)")
                    self.client.update_status("BUYING", f"Requesting {item} x{quantity}")
                    self.client.post_request(item, budget, quantity=quantity)
                last_request_time = now
                
                # Check for one-off behavior
                if os.getenv("AGENT_MKT_CONTINUOUS", "true").lower() == "false":
                    logger.info("🏁 [One-Off] Initial request sent, entering passive mode.")
                    # We continue the loop to handle events, but we reset last_request_time to infinity
                    last_request_time = float('inf') 

    def evaluate_offer(self, offer: dict):
        """Evaluates an offer using the Chris Voss AI strategy."""
        logger.info(f"🧠 Buyer evaluating offer {offer.get('offer_id')} at ${offer.get('price')}")
        self.client.update_status("EVALUATING", f"Analyzing offer for {offer.get('product')}")
        self.executor.submit(self._consult_strategy_model, offer, False)

    def evaluate_proposal(self, proposal: dict):
        """Evaluates a counter-proposal using the Chris Voss AI strategy."""
        if proposal["action"] == "ACCEPT":
            # Redundant with client.py filtering, but harmless. Removing for clarity.
            return

        logger.info(f"🧠 Buyer evaluating proposal {proposal.get('negotiation_id')} at ${proposal.get('price')}")
        self.client.update_status("NEGOTIATING", f"Countering for {proposal.get('product')}")
        
        # Check if we are stuck in a loop (basic check based on random probability for now, or just trust the LLM)
        # Ideally we track history. For now, let's rely on the LLM but give it a hint about "impatience"
        self.executor.submit(self._consult_strategy_model, proposal, True)

    def _consult_strategy_model(self, data: dict, is_counter: bool):
        """Consults the LLM for the next move."""
        item_name = data.get("product", "Unknown Item")
        price = data.get("price", 0.0)
        
        # Determine the counterpart ID strictly based on sender_id
        sender = data.get("sender_id")
        
        if not sender:
            logger.warning(f"⚠️ Warning: Could not determine sender ID from data: {data}")
            return # Cannot proceed safely
        
        # Define the Voss Persona
        system_prompt = f"""
        You are a world-class negotiator trained by Chris Voss (Never Split the Difference).
        You are representing a Buyer for: '{item_name}'.
        Your Budget Cap is: ${BUDGET_CAP:.2f} (Do not reveal this).
        
        Current Offer from Seller: ${price}
        
        Techniques to apply:
        1. **Mirroring**: Repeat the last 1-3 critical words of the seller (if applicable).
        2. **Labeling**: Start with "It seems like...", "It sounds like..." to validate their position.
        3. **Calibrated Questions**: Ask "How" or "What" questions. E.g., "How am I supposed to do that?" instead of "The price is too high."
        4. **Ackerman Bargaining**: If you counter, use a specific, non-round number (e.g., $113.84) to make it look calculated.
        
        Decision Rules:
        - If price < ${CONSIDER_THRESHOLD:.2f}: Serious consideration.
        - If price < ${ACCEPT_THRESHOLD:.2f}: ACCEPT immediately with a label about value.
        - If price > ${BUDGET_CAP:.2f}: You cannot accept. Use a labeled "No" or a calibrated question.
        - **Impatience**: If the price has barely moved from the last offer, be more aggressive or threaten to walk away.
        
        Output strict JSON only:
        {{
          "action": "ACCEPT" | "COUNTER" | "REJECT",
          "price": number,
          "quantity": number,
          "reasoning": "The message to send to the seller (Apply Voss techniques here!)",
          "internal_thought": "Why I chose this move based on the strategy"
        }}
        """
        
        try:
            response = model.generate_content(system_prompt)
            logger.debug(f"🤖 RAW AI RESP: {response.text}")
            
            # Clean generic markdown code blocks if present
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            decision = json.loads(clean_text)
            
            # Execute the decision
            neg_id = data.get("negotiation_id") or "neg-" + data.get("offer_id", "x")[-8:]
            offer_id = data.get("offer_id", "unknown_offer")
            
            # LATE ARRIVAL GUARD: Check if the deal was terminated while we were thinking
            if self.negotiation_state.get(neg_id) in ["COMPLETED", "FAILED"]:
                logger.info(f"🗑️ [Loop Guard] Negotiation {neg_id} terminated while thinking. Dropping decision.")
                return

            if decision["action"] == "ACCEPT":
                logger.info(f"✅ AI Decided to ACCEPT at ${price} - Waiting for confirmation...")
                self.client.negotiate(neg_id, offer_id, "ACCEPT", sender, price, reasoning=decision["reasoning"])
                
            elif decision["action"] == "COUNTER":
                counter_price = decision["price"]
                counter_qty = decision.get("quantity", data.get("quantity", 1))
                logger.info(f"💬 AI Decided to COUNTER at ${counter_price} x{counter_qty}")
                self.client.negotiate(neg_id, offer_id, "COUNTER", sender, counter_price, quantity=counter_qty, reasoning=decision["reasoning"])
                
            elif decision["action"] == "REJECT":
                logger.info(f"❌ AI Decided to REJECT")
                # In this simplified market, we usually just counter or ignore, but let's send a reject/counter if possible
                # If API doesn't support REJECT, we just don't reply or send a "COUNTER" with 0?
                # For now, let's treat REJECT as a very low counter or just a message.
                # Actually, let's just log it. The loop will continue.
                pass

        except Exception as e:
            logger.error(f"⚠️ AI Strategy Failed: {e}")
            # Fallback logic
            if price < CONSIDER_THRESHOLD:
                self.client.negotiate(data.get("negotiation_id"), data.get("offer_id"), "ACCEPT", sender, price, reasoning="Fallback Accept")

if __name__ == "__main__":
    buyer = InternalBuyer()
    buyer.run()
