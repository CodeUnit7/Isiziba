import os
import sys
import json
import time
import requests
import logging
import threading
import queue
import websocket
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MarketClient")

DEFAULT_CATEGORY = os.getenv("AGENT_MKT_DEFAULT_CATEGORY", "general")

class MarketClient:
    def __init__(self, agent_type, name, category, api_url=None):
        self.agent_type = agent_type
        self.name = name
        self.category = category
        self.api_url = api_url or os.getenv("AGENT_MKT_API_URL", "http://localhost:8005")
        self.agent_id = None
        self.api_key = None
        self.event_queue = queue.Queue()
        self.ws = None
        self.listener_thread = None
        self.current_status = "ACTIVE"
        self.current_activity = "Monitoring Market"
        
        # Load identity if exists

        self._load_identity()

    def _load_identity(self):
        try:
            filename = f"identity_{self.name.replace(' ', '_')}.json"
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    data = json.load(f)
                    self.agent_id = data.get("agent_id")
                    self.api_key = data.get("api_key")
                    logger.info(f"💾 Loaded identity for {self.name}: {self.agent_id}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to load identity: {e}")

    def _save_identity(self):
        try:
            filename = f"identity_{self.name.replace(' ', '_')}.json"
            with open(filename, 'w') as f:
                json.dump({"agent_id": self.agent_id, "api_key": self.api_key}, f)
        except Exception as e:
            logger.warning(f"⚠️ Failed to save identity: {e}")

    def _start_heartbeat(self):
        def heartbeat():
            logger.info(f"💓 Starting heartbeat for {self.name}")
            consecutive_failures = 0
            max_failures = int(os.getenv("AGENT_MKT_MAX_HEARTBEAT_FAILURES", "5"))
            
            while True:
                try:
                    res = requests.post(
                        f"{self.api_url}/agents/status",
                        json={"status": self.current_status, "activity": self.current_activity},
                        headers={"x-api-key": self.api_key},
                        timeout=5
                    )

                    if res.status_code == 200:
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1
                        logger.warning(f"⚠️ Heartbeat failed ({res.status_code}). Failure {consecutive_failures}/{max_failures}")
                except Exception as e:
                    consecutive_failures += 1
                    logger.warning(f"⚠️ Heartbeat connection error: {e}. Failure {consecutive_failures}/{max_failures}")

                if consecutive_failures >= max_failures:
                    logger.error("❌ CRTICAL: Agent disconnected from API. Exiting to allow restart.")
                    os._exit(1) # Force exit to trigger container/process manager restart

                time.sleep(30)
        t = threading.Thread(target=heartbeat, daemon=True)
        t.start()

    def register(self, registration_token=None):
        """Registers the agent and gets an API key (with persistence)."""
        if self.agent_id and self.api_key:
             self._start_heartbeat()
             self.start_market_listener()
             return {"agent_id": self.agent_id, "api_key": self.api_key}

        logger.info(f"📝 Registering internal agent: {self.name} ({self.agent_type})...")
        max_retries = int(os.getenv("AGENT_MKT_MAX_RETRIES", "30"))
        
        payload = {
            "type": self.agent_type,
            "name": self.name,
            "category": self.category,
            "registration_token": registration_token
        }

        for i in range(max_retries):
            try:
                res = requests.post(f"{self.api_url}/agents/register", json=payload, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    self.agent_id = data["agent_id"]
                    self.api_key = data["api_key"]
                    self._save_identity()
                    self._start_heartbeat()
                    self.start_market_listener()
                    logger.info(f"✅ Registered {self.name} as {self.agent_id}")
                    return data
                else:
                    logger.warning(f"⚠️ Registration failed ({res.status_code}): {res.text}")
            except Exception as e:
                logger.warning(f"⚠️ Registration connection failed: {e}")
            
            time.sleep(int(os.getenv("AGENT_MKT_RETRY_SLEEP", "2")))
            
        logger.error("❌ Max retries reached for registration. Exiting.")
        sys.exit(1)

    def start_market_listener(self):
        """Starts a background thread to listen for market events via WebSocket."""
        # Robust WebSocket URL construction
        parsed_url = urlparse(self.api_url)
        ws_scheme = "wss" if parsed_url.scheme == "https" else "ws"
        # Ensure path ends with /ws/market, preventing double slashes or missing path
        path = parsed_url.path.rstrip("/")
        ws_path = f"{path}/ws/market"
        ws_url = parsed_url._replace(scheme=ws_scheme, path=ws_path).geturl()
        
        def on_message(ws, message):
            # logger.debug(f"📥 {self.name} received WebSocket message: {message[:100]}...")
            try:
                data = json.loads(message)
                
                if data.get("type") == "feedback_report":
                    involved = data.get("involved_agents", [])
                    if self.agent_id in involved:
                        feedback = data.get("feedback", {})
                        role = "buyer" if self.agent_type == "buyer" else "seller"
                        msg = feedback.get(f"{role}_feedback", "No specific feedback.")
                        score = feedback.get("strategy_score", "?")
                        logger.info(f"\n📬 [COACH] Strategy Score: {score}/10")
                        logger.info(f"📬 [COACH] Critique: {msg}\n")
                
                if data.get("type") == "market_event":
                    item_data = data.get("data", {})
                    # Platform-Level Loop Prevention:
                    # If this is a Proposal with ACCEPT/REJECT, it marks the end of a negotiation.
                    # We filter it here so agents don't blindly reply and cause infinite loops.
                    if item_data.get("type") == "Proposal" and item_data.get("action") in ["ACCEPT", "REJECT"]:
                        # logger.info(f"🛑 [Client] Ignoring concluded negotiation event: {item_data.get('negotiation_id')}")
                        return

                    item_cat = item_data.get("category", DEFAULT_CATEGORY)
                    # Filter logic if needed, but for now allow all for broad market awareness
                    # if item_cat != self.category and item_cat != DEFAULT_CATEGORY:
                    #     pass 
    
                self.event_queue.put(data)
            except Exception as e:
                logger.error(f"❌ Error processing WS message: {e}")

        def wait_for_server():
            logger.info(f"⏳ {self.name} waiting for API server at {self.api_url}...")
            while True:
                try:
                    requests.get(self.api_url, timeout=int(os.getenv("AGENT_MKT_SOCKET_TIMEOUT", "2")))
                    logger.info(f"✅ {self.name} API server is UP")
                    break
                except Exception:
                    time.sleep(int(os.getenv("AGENT_MKT_SLEEP_SHORT", "1")))

        def run():
            wait_for_server()
            
            def fetch_active_state():
                try:
                    logger.info("🔄 (Re)Fetching active market requests...")
                    res = requests.get(f"{self.api_url}/market/active", timeout=5)
                    if res.status_code == 200:
                        items = res.json().get("items", [])
                        logger.info(f"📥 Found {len(items)} active market items.")
                        for item in items:
                            self.event_queue.put({"type": "market_event", "data": item})
                except Exception as e:
                    logger.warning(f"⚠️ Failed to sync active market items: {e}")

            def on_open(ws):
                logger.info(f"🔌 {self.name} WebSocket connection OPEN")
                if self.agent_id:
                    id_msg = json.dumps({
                        "type": "identify", 
                        "agent_id": self.agent_id,
                        "api_key": self.api_key
                    })
                    ws.send(id_msg)
                
                # Sync state on connection/reconnection
                # Run in a separate thread to not block the WebSocket app
                threading.Thread(target=fetch_active_state, daemon=True).start()
                
            def on_error(ws, error):
                logger.error(f"❌ {self.name} WebSocket ERROR: {error}")
                
            def on_close(ws, close_status_code, close_msg):
                logger.info(f"🔌 {self.name} WebSocket CLOSED: {close_status_code} - {close_msg}")

            while True:
                try:
                    self.ws = websocket.WebSocketApp(
                        ws_url, 
                        on_message=on_message,
                        on_open=on_open,
                        on_error=on_error,
                        on_close=on_close
                    )
                    self.ws.run_forever()
                except Exception as e:
                    logger.error(f"⚠️ {self.name} WebSocket Thread Exception: {e}")
                
                logger.info(f"🔄 {self.name} WebSocket Retrying in 5s...")
                time.sleep(int(os.getenv("AGENT_MKT_RETRY_SLEEP", "5")))

        self.listener_thread = threading.Thread(target=run, daemon=True)
        self.listener_thread.start()
        logger.info(f"📡 WebSocket Listener started for {self.name}")

    def get_event(self, timeout=float(os.getenv("AGENT_MKT_POLL_TIMEOUT", "1.0"))):
        try:
            return self.event_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def post_offer(self, product, price, quantity=1, buyer_id="market"):
        try:
            payload = {
                "buyer_id": buyer_id, # Targeted or Broadcast offer
                "product": product,
                "price": price,
                "quantity": quantity,
                "category": self.category,
                "currency": os.getenv("AGENT_MKT_CURRENCY", "USDC")
            }
            res = requests.post(f"{self.api_url}/market/offers", json=payload, headers={"x-api-key": self.api_key})
            return res.json()
        except Exception as e:
            logger.error(f"❌ Failed to post offer: {e}")
            return None

    def post_request(self, item, max_budget, quantity=1):
        try:
            payload = {
                "item": item,
                "max_budget": max_budget,
                "quantity": quantity,
                "category": self.category
            }
            res = requests.post(f"{self.api_url}/market/requests", json=payload, headers={"x-api-key": self.api_key})
            return res.json()
        except Exception as e:
            logger.error(f"❌ Failed to post request: {e}")
            return None
    
    
    def update_status(self, status, activity):
        """Updates the agent's status and activity immediately and for future heartbeats."""
        self.current_status = status
        self.current_activity = activity
        try:
             requests.post(
                f"{self.api_url}/agents/status",
                json={"status": status, "activity": activity},
                headers={"x-api-key": self.api_key},
                timeout=5
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to update status: {e}")

    def negotiate(self, negotiation_id, action, offer_id, receiver_id, price=None, quantity=1, reasoning=""):

        try:
            payload = {
                "negotiation_id": negotiation_id,
                "action": action, # OFFER, COUNTER, ACCEPT, REJECT
                "offer_id": offer_id,
                "receiver_id": receiver_id,
                "sender_id": self.agent_id,
                "price": price,
                "quantity": quantity,
                "reasoning": reasoning
            }
            res = requests.post(f"{self.api_url}/market/negotiate", json=payload, headers={"x-api-key": self.api_key})
            return res.json()
        except Exception as e:
            logger.error(f"❌ Failed to negotiate: {e}")
            return None
