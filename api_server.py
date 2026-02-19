from fastapi import FastAPI, HTTPException, Body, WebSocket, WebSocketDisconnect, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from google.cloud import firestore, pubsub_v1
import os
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"
import json
import time
import uuid
import asyncio
from datetime import datetime, timedelta
import sys
import vertexai
from vertexai.generative_models import GenerativeModel
import logging

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("api_server")

# Configuration
PROJECT_ID = os.getenv("AGENT_MKT_PROJECT_ID")
if not PROJECT_ID:
    logger.error("❌ AGENT_MKT_PROJECT_ID environment variable is not set.")
    sys.exit(1)

REGISTRATION_TOKEN = os.getenv("AGENT_MKT_REGISTRATION_TOKEN")
if not REGISTRATION_TOKEN:
    logger.warning("⚠️ AGENT_MKT_REGISTRATION_TOKEN is not set. Registration will be unsecured (not recommended).")
TOPIC_ID = os.getenv("AGENT_MKT_TOPIC_ID", "market.discovery")
NEG_TOPIC_ID = os.getenv("AGENT_MKT_NEG_TOPIC_ID", "market.negotiation")
REGION = os.getenv("AGENT_MKT_REGION", "us-central1")
ALLOWED_ORIGINS = os.getenv("AGENT_MKT_ALLOWED_ORIGINS", "*").split(",")
DEFAULT_CATEGORY = os.getenv("AGENT_MKT_DEFAULT_CATEGORY", "general")

# Initialize Vertex AI for the Platform Coach (Lazy Loaded)
MODEL_NAME = os.getenv("AGENT_MKT_MODEL")
if not MODEL_NAME:
    logger.error("❌ AGENT_MKT_MODEL environment variable is not set.")
    sys.exit(1)

# Max Steps Configuration (Strict)
MAX_STEPS_ENV = os.getenv("AGENT_MKT_MAX_STEPS")
if not MAX_STEPS_ENV:
    logger.error("❌ AGENT_MKT_MAX_STEPS environment variable is not set.")
    sys.exit(1)
MAX_NEGOTIATION_STEPS = int(MAX_STEPS_ENV)

def get_coach_model():
    """Lazy loads the Vertex AI model to prevent import crashes if creds are missing."""
    if not hasattr(app.state, "coach_model") or app.state.coach_model is None:
        try:
             vertexai.init(project=PROJECT_ID, location=REGION)
             app.state.coach_model = GenerativeModel(MODEL_NAME)
             logger.info(f"🧠 Coach model initialized")
        except Exception as e:
             logger.warning(f"⚠️ Vertex AI not available: {e}. Coach will be disabled.")
             app.state.coach_model = None
    return app.state.coach_model

# API Key Cache
# Mapping Sk -> (AgentData, Expiry)
auth_cache = {}
AUTH_CACHE_TTL = 300 # 5 minutes

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.agent_map: Dict[str, WebSocket] = {}
        self.viewers: List[WebSocket] = []
        self.pending_timeouts: Dict[WebSocket, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        
        # Identification Timeout: Use a task to kick unidentified clients
        timeout_task = asyncio.create_task(self._ghost_cleanup_timeout(websocket))
        self.pending_timeouts[websocket] = timeout_task
        
        client = f"{websocket.client.host}:{websocket.client.port}"
        logger.info(f"🔌 [+] WS Connected: {client}. Total: {len(self.active_connections)}")

    async def _ghost_cleanup_timeout(self, websocket: WebSocket):
        """Closes connection if not identified within timeout (30s)."""
        await asyncio.sleep(30)
        # Check if it's an agent OR a viewer
        is_identified = websocket in self.agent_map.values() or websocket in self.viewers
        if not is_identified:
             logger.warning(f"👻 [WS] Kicking unidentified client {websocket.client.host}")
             try:
                 await websocket.close(code=1008) # Policy Violation
             except Exception as e:
                 logger.warning(f"⚠️ [WS] Error closing connection for unidentified client: {e}")
             self.disconnect(websocket)

    def identify(self, agent_id: str, websocket: WebSocket):
        self.agent_map[agent_id] = websocket
        # Cancel timeout if identified
        if websocket in self.pending_timeouts:
            self.pending_timeouts[websocket].cancel()
            del self.pending_timeouts[websocket]
            
        client = f"{websocket.client.host}:{websocket.client.port}"
        logger.info(f"🆔 WS Identified: {agent_id} at {client}")

    def identify_viewer(self, websocket: WebSocket):
        """Registers a read-only viewer interface (like the frontend)."""
        if websocket not in self.viewers:
            self.viewers.append(websocket)
        
        # Cancel timeout
        if websocket in self.pending_timeouts:
            self.pending_timeouts[websocket].cancel()
            del self.pending_timeouts[websocket]
            
        client = f"{websocket.client.host}:{websocket.client.port}"
        logger.info(f"👀 WS Viewer Registered: {client}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.viewers:
            self.viewers.remove(websocket)
            
        if websocket in self.pending_timeouts:
            self.pending_timeouts[websocket].cancel()
            del self.pending_timeouts[websocket]
            
        client = f"{websocket.client.host}:{websocket.client.port}"
        logger.info(f"🔌 [-] WS Disconnected: {client}. Remaining: {len(self.active_connections)}")
        # Remove from map if exists
        for agent_id, ws in list(self.agent_map.items()):
            if ws == websocket:
                del self.agent_map[agent_id]
                break

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return

        # Create tasks for all connections
        tasks = [connection.send_json(message) for connection in self.active_connections]
        
        # Run all tasks concurrently, return exceptions instead of raising them immediately
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        total_sent = 0
        for res in results:
            if isinstance(res, Exception):
                logger.warning(f"⚠️ Broadcast failure to a client: {res}")
            else:
                total_sent += 1

        if total_sent > 0:
            logger.info(f"📡 Broadcast of {message.get('type')} to {total_sent} listeners.")

    async def send_to_agent(self, agent_id: str, message: dict):
        if agent_id in self.agent_map:
            try:
                await self.agent_map[agent_id].send_json(message)
                logger.info(f"📤 Targeted message sent to {agent_id}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to send targeted message to {agent_id}: {e}")

manager = ConnectionManager()
app = FastAPI(title="Isiziba Marketplace API")

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global placeholders will be initialized in startup

async def verify_api_key(x_api_key: str = Header(...)):
    """Validates the API key against the Firestore agents collection with caching."""
    now = datetime.now()
    
    # Check cache first
    cached = auth_cache.get(x_api_key)
    if cached:
        agent_data, expiry = cached
        if now < expiry:
            return agent_data
        else:
            del auth_cache[x_api_key]

    try:
        # Wrap sync Firestore call in a thread to keep the event loop responsive
        query = await asyncio.to_thread(
            lambda: app.state.db.collection("agents").where("api_key", "==", x_api_key).limit(1).get()
        )
        if not query:
            raise HTTPException(status_code=403, detail="Invalid API Key")
        
        agent_data = query[0].to_dict()
        # Update cache
        auth_cache[x_api_key] = (agent_data, now + timedelta(seconds=AUTH_CACHE_TTL))
        
        return agent_data
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("❌ Auth failure")
        raise HTTPException(status_code=403, detail="Authentication failed")

# WebSocket Market Hub
@app.websocket("/ws/market")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                
                # Handle Viewer Identification
                if msg.get("type") == "identify_view":
                    manager.identify_viewer(websocket)
                    continue

                if msg.get("type") == "identify":
                    agent_id = msg.get("agent_id")
                    api_key = msg.get("api_key")
                    if not agent_id or not api_key:
                        continue
                    
                    # Verify API key asynchronously
                    agent_query = await asyncio.to_thread(
                        lambda: app.state.db.collection("agents").where("id", "==", agent_id).where("api_key", "==", api_key).limit(1).get()
                    )
                    if agent_query:
                        manager.identify(agent_id, websocket)
                    else:
                        logger.warning(f"⚠️ [WS] Identity verification failed for {agent_id}")
            except Exception as e:
                logger.warning(f"⚠️ [WS] Message error: {e}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

def setup_listeners(loop):
    app.state.main_loop = loop
    
    # Combined Transaction & Reputation Listener
    def on_transaction_snap(doc_snapshot, changes, read_time):
        for change in changes:
            data = change.document.to_dict()
            if change.type.name in ['ADDED', 'MODIFIED']:
                # 1. Broadcast to WS for real-time UI updates
                asyncio.run_coroutine_threadsafe(
                    manager.broadcast({"type": "market_event", "data": data}),
                    loop
                )
                
                # 2. Trigger reputation for completed deals exactly once
                if data.get("status") == "COMPLETED":
                    # Check if this was a transition to COMPLETED (to avoid double updates on recurring edits)
                    # We can use the 'global_reputation_applied' flag or just trust transactional idempotency
                    # if we check the DB state, but here we can check if it just became COMPLETED.
                    # For simplicity, we'll ensure update_reputation handles its own logic or use a flag.
                    logger.info(f"💰 Transaction {data.get('id')} reached COMPLETED state.")
                    # Optimized: Only seller gets reputation for now, or handle both more efficiently if needed. 
                    # Actually, let's keep both but use a single log message to reduce noise.
                    update_reputation(data["buyer_id"], 1.0, transaction_id=data.get("id"))
                    update_reputation(data["seller_id"], 1.0, transaction_id=data.get("id"))

    # Simplified Offer Listener
    def on_offer_snap(doc_snapshot, changes, read_time):
        for change in changes:
            if change.type.name == 'ADDED':
                data = change.document.to_dict()
                asyncio.run_coroutine_threadsafe(
                    manager.broadcast({"type": "market_event", "data": data}),
                    loop
                )

    get_db().collection("offers").on_snapshot(on_offer_snap)
    get_db().collection("transactions").on_snapshot(on_transaction_snap)

    # Pub/Sub Listener for Discovery (Requests) and Negotiation (Proposals)
    subscriber = pubsub_v1.SubscriberClient()
    
    def callback_pubsub(message):
        try:
            data = json.loads(message.data.decode("utf-8"))
            logger.info(f"📡 Pub/Sub Hub Broadcasting: {data.get('type')} to {len(manager.active_connections)} clients")
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({"type": "market_event", "data": data}),
                loop
            )
            message.ack()
        except Exception as e:
            logger.exception("❌ Pub/Sub callback error")
            message.ack()

    # Deterministic Subscriptions to avoid leaks
    discovery_sub_name = os.getenv("AGENT_MKT_DISCOVERY_SUB", f"projects/{PROJECT_ID}/subscriptions/api-hub-discovery-sub")
    neg_sub_name = os.getenv("AGENT_MKT_NEGOTIATION_SUB", f"projects/{PROJECT_ID}/subscriptions/api-hub-negotiation-sub")
    
    def ensure_subscription(sub_path, topic_path):
        try:
            subscriber.get_subscription(subscription=sub_path)
            logger.info(f"📡 Using existing subscription: {sub_path}")
        except Exception as e:
            # If not found, create it
            try:
                subscriber.create_subscription(name=sub_path, topic=topic_path)
                logger.info(f"📡 Created new subscription: {sub_path}")
            except Exception as e2:
                logger.error(f"⚠️ Subscription setup error for {sub_path}: {e2}")

    ensure_subscription(discovery_sub_name, app.state.topic_path)
    subscriber.subscribe(discovery_sub_name, callback=callback_pubsub)
    
    ensure_subscription(neg_sub_name, app.state.neg_topic_path)
    subscriber.subscribe(neg_sub_name, callback=callback_pubsub)
    logger.info(f"📡 API Hub Pub/Sub listeners standardized.")

def update_reputation(agent_id, change, transaction_id=None):
    """Updates agent reputation and logs history, ensuring one update per transaction."""
    try:
        agent_ref = get_db().collection("agents").document(agent_id)
        
        # Transactional update
        @firestore.transactional
        def update_in_transaction(transaction, ref):
            # 1. Idempotency Check (P0 Fix)
            if transaction_id:
                # Use a deterministic ID for the history record to prevent double-counting
                history_id = f"{agent_id}_{transaction_id}"
                hist_ref = get_db().collection("reputation_history").document(history_id)
                hist_snap = next(transaction.get(hist_ref))
                
                if hist_snap.exists:
                    logger.info(f"ℹ️ Reputation already processed for {agent_id} (TX: {transaction_id})")
                    return

            # 2. Get current agent state
            snapshot = next(transaction.get(ref))
            if not snapshot.exists:
                return
            
            new_score = snapshot.get("global_reputation") + change
            current_tx = snapshot.to_dict().get("total_transactions", 0)
            
            # 3. Update Agent
            transaction.update(ref, {
                "global_reputation": new_score, 
                "total_transactions": current_tx + 1
            })
            
            # 4. Create History Record (act as the idempotency key)
            if transaction_id:
                transaction.set(hist_ref, {
                    "agent_id": agent_id,
                    "transaction_id": transaction_id,
                    "reputation": new_score,
                    "change": change,
                    "timestamp": time.time()
                })
            else:
                # Fallback for non-transaction updates (rare)
                get_db().collection("reputation_history").document().set({
                    "agent_id": agent_id,
                    "reputation": new_score,
                    "change": change,
                    "timestamp": time.time()
                })
            
        transaction = get_db().transaction()
        update_in_transaction(transaction, agent_ref)
        logger.info(f"📈 Updated reputation for {agent_id}: +{change}")
    except Exception as e:
        logger.error(f"⚠️ Failed to update reputation: {e}")

@app.get("/agents/{agent_id}/reputation/history")
def get_reputation_history(agent_id: str):
    try:
        docs = get_db().collection("reputation_history")\
                 .where("agent_id", "==", agent_id)\
                 .stream()
        
        history = [doc.to_dict() for doc in docs]
        history.sort(key=lambda x: x["timestamp"])
        
        return {"history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class AgentStatus(BaseModel):
    status: str  # e.g., "IDLE", "NEGOTIATING", "OFFLINE"
    activity: Optional[str] = None

@app.post("/agents/status")
def update_status(req: AgentStatus, agent: dict = Depends(verify_api_key)):
    """Updates the real-time status of an agent."""
    status_msg = {
        "type": "agent_status",
        "agent_id": agent["id"],
        "name": agent["name"],
        "status": req.status,
        "activity": req.activity,
        "timestamp": time.time()
    }
    
    # Broadcast to all WebSocket clients
    target_loop = app.state.main_loop if hasattr(app.state, 'main_loop') else None
    if target_loop:
        asyncio.run_coroutine_threadsafe(
            manager.broadcast(status_msg),
            target_loop
        )
    
    return {"status": "updated"}

# Pydantic Models
class AgentRegisterRequest(BaseModel):
    type: str
    name: str
    budget: Optional[float] = None
    category: Optional[str] = DEFAULT_CATEGORY
    registration_token: Optional[str] = None

class MarketRequest(BaseModel):
    item: str = Field(..., max_length=100)
    max_budget: float
    quantity: Optional[int] = 1
    category: Optional[str] = DEFAULT_CATEGORY

class NegotiationAction(BaseModel):
    negotiation_id: Optional[str] = None
    action: str
    price: Optional[float] = None
    quantity: Optional[int] = 1
    offer_id: str
    sender_id: str
    receiver_id: str
    reasoning: Optional[str] = Field(None, max_length=1000)

class UserFeedbackRequest(BaseModel):
    negotiation_id: str
    rating: int  # 1-5
    comment: Optional[str] = Field(None, max_length=500)
    user_id: Optional[str] = "browser-user"

@app.get("/")
def read_root():
    return {"status": "Marketplace API Online", "project": PROJECT_ID}

@app.post("/agents/register")
def register_agent(agent: AgentRegisterRequest):
    # Registration Security Check
    if REGISTRATION_TOKEN and agent.registration_token != REGISTRATION_TOKEN:
        logger.warning(f"🚫 [Registration] Denied for {agent.name}. Invalid or missing token.")
        raise HTTPException(status_code=403, detail="Invalid registration token")

    # Deduplication: Check if agent with same name exists
    try:
        # We use a synchronous query via asyncio.to_thread if we were async, but this is a sync route (def, not async def wrapper?)
        # Wait, register_agent is defined as `def`, so it runs in a threadpool. We can use blocking calls directly.
        existing_docs = get_db().collection("agents")\
            .where("name", "==", agent.name)\
            .where("type", "==", agent.type)\
            .limit(1).stream()
        
        for doc in existing_docs:
            existing = doc.to_dict()
            logger.info(f"♻️ [Registration] Found existing agent {existing['name']} ({existing['id']}). Returning existing keys.")
            return {
                "agent_id": existing["id"], 
                "api_key": existing["api_key"], 
                "status": "Restored"
            }
            
    except Exception as e:
        logger.warning(f"⚠️ [Registration] Deduplication check failed: {e}")

    agent_id = f"ext-{agent.type}-{uuid.uuid4().hex[:8]}"
    api_key = f"sk-{uuid.uuid4().hex}"
    
    agent_data = {
        "id": agent_id,
        "type": agent.type,
        "name": agent.name,
        "api_key": api_key,
        "category": agent.category,
        "global_reputation": 50.0,
        "total_transactions": 0,
        "api_registered": True,
        "created_at": time.time()
    }
    
    try:
        get_db().collection("agents").document(agent_id).set(agent_data)
        logger.info(f"🆕 [Registration] Created new agent {agent.name} ({agent_id})")
        return {"agent_id": agent_id, "api_key": api_key, "status": "Registered"}
    except Exception as e:
        logger.exception("❌ Registration failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agents")
@app.get("/market/agents")
def get_agents():
    try:
        docs = get_db().collection("agents").stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/market/feed")
def get_market_feed(limit: int = 20):
    try:
        docs = get_db().collection("offers").order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit).stream()
        return {"feed": [doc.to_dict() for doc in docs]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/market/negotiations")
def get_negotiations(limit: int = 20):
    try:
        docs = get_db().collection("negotiations").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit).stream()
        return {"negotiations": [doc.to_dict() for doc in docs]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/market/requests")
async def post_request(req: MarketRequest, agent: dict = Depends(verify_api_key)):
    if agent["type"] != "buyer":
        raise HTTPException(status_code=403, detail="Only buyers can post requests")
        
    try:
        now = time.time()
        payload = {
            "type": "Request",
            "sender_id": agent["id"],
            "buyer_id": agent["id"],
            "item": req.item,
            "max_budget": req.max_budget,
            "quantity": req.quantity,
            "category": req.category,
            "timestamp": now,
            "valid_until": now + int(os.getenv("AGENT_MKT_OFFER_TTL", "300")),
            "source": "external_api",
            "agent_name": agent["name"]
        }
        
        # Persist to market_items collection for late arrivals
        get_db().collection("market_items").add(payload)

        data = json.dumps(payload).encode("utf-8")
        app.state.publisher.publish(app.state.topic_path, data)
        
        # Immediate local broadcast for speed
        await manager.broadcast({"type": "market_event", "data": payload})
            
        return {"status": "Published", "payload": payload}
    except Exception as e:
        logger.exception("❌ Failed to publish market request")
        raise HTTPException(status_code=500, detail="Failed to publish market request")

@app.post("/market/negotiate")
async def negotiate(action: NegotiationAction, agent: dict = Depends(verify_api_key)):
    # Generate ID if starting new negotiation
    if not action.negotiation_id:
        action.negotiation_id = f"neg-{uuid.uuid4().hex[:8]}"

    # Fetch product name from offer to enrich the payload
    product_name = "Unknown Service"
    try:
        offer_snap = await asyncio.to_thread(
            lambda: get_db().collection("offers").document(action.offer_id).get()
        )
        if offer_snap.exists:
            product_name = offer_snap.to_dict().get("product", "Unknown Service")
        else:
            logger.warning(f"⚠️ [Negotiation] Offer {action.offer_id} not found in DB!")
            # Fallback: Maybe it's in market_items?
            # ...
    except Exception as e:
        logger.warning(f"⚠️ Failed to fetch product for offer {action.offer_id}: {e}")

    payload = {
        "type": "Proposal",
        "negotiation_id": action.negotiation_id,
        "offer_id": action.offer_id,
        "product": product_name,
        "sender_id": agent["id"],
        "receiver_id": action.receiver_id,
        "action": action.action,
        "price": action.price,
        "quantity": action.quantity,
        "reasoning": action.reasoning,
        "timestamp": time.time(),
        "source": "external_api"
    }
    
    # Enforce Max Steps to prevent infinite loops
    try:
        # fast count query
        # Use a lambda to wrap the count query execution
        current_steps = await asyncio.to_thread(
            lambda: get_db().collection("negotiations").where("negotiation_id", "==", action.negotiation_id).count().get()[0][0].value
        )
        
        if current_steps >= MAX_NEGOTIATION_STEPS and action.action not in ["ACCEPT", "REJECT"]:
            logger.warning(f"🛑 [Negotiation] Max steps reached for {action.negotiation_id}. Rejecting further counters.")
            
            # Signal termination to both parties
            term_msg = {
                "type": "negotiation_terminated",
                "status": "FAILED",
                "negotiation_id": action.negotiation_id,
                "reason": "Max negotiation steps reached",
                "timestamp": time.time()
            }
            # We assume sender and receiver are the ones involved.
            # We can't await manager.send_to_agent easily inside this sync block if we didn't use async def? 
            # Wait, negotiate IS async def.
            await manager.send_to_agent(action.sender_id, term_msg)
            await manager.send_to_agent(action.receiver_id, term_msg)
            
            raise HTTPException(status_code=400, detail=f"Negotiation limit reached ({MAX_NEGOTIATION_STEPS} steps). You must ACCEPT or REJECT.")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"⚠️ Failed to check negotiation step count: {e}")
        # Fail open to avoid blocking valid deals on DB error, but log it

    
    try:
        # Persist to Firestore for history
        await asyncio.to_thread(
            lambda: get_db().collection("negotiations").document().set(payload)
        )
        
        # If deal is accepted, verify price integrity and create a transaction record
        if action.action == "ACCEPT":
            # P0 Fix: Verify that the accepted price matches the last negotiation state
            try:
                # Fetch last 2 messages for this negotiation to find the counterpart's price
                # Fetch all messages for this negotiation and sort in memory to avoid composite index requirement
                # distinct on "negotiation_id" + Sort "timestamp" requires an index we want to avoid.
                history_query = await asyncio.to_thread(
                    lambda: get_db().collection("negotiations")\
                                      .where("negotiation_id", "==", action.negotiation_id)\
                                      .stream()
                )
                
                # Convert to list and sort descending
                history_docs = [doc for doc in history_query]
                history_docs.sort(key=lambda x: x.to_dict().get("timestamp", 0), reverse=True)
                history_query = history_docs[:2] # Keep api compatible with loop below
                
                valid_price = False
                for doc in history_query:
                    h = doc.to_dict()
                    # It must be a price proposed by someone else (the receiver of the ACCEPT)
                    if h.get("sender_id") == action.receiver_id and h.get("price") == action.price:
                        valid_price = True
                        break
                
                # Also check the initial offer if it's the first response
                if not valid_price:
                    offer_snap = await asyncio.to_thread(
                        lambda: get_db().collection("offers").document(action.offer_id).get()
                    )
                    if offer_snap.exists and offer_snap.to_dict().get("price") == action.price:
                        valid_price = True
                
                if not valid_price:
                    logger.warning(f"⚠️ [Security] Price mismatch for {action.negotiation_id}! Accepted: {action.price}")
                    raise HTTPException(status_code=400, detail="Price integrity check failed. Accepted price must match last proposal.")
                    
            except HTTPException:
                raise
            except Exception as e:
                logger.exception(f"⚠️ [Security] Failed to verify price history")
                raise HTTPException(status_code=500, detail="Internal integrity check failure")

            tx_id = f"tx-{uuid.uuid4().hex[:8]}"
            tx_data = {
                "id": tx_id,
                "tx_id": tx_id,
                "negotiation_id": action.negotiation_id,
                "buyer_id": agent["id"] if agent["type"] == "buyer" else action.receiver_id,
                "seller_id": agent["id"] if agent["type"] == "seller" else action.receiver_id,
                "amount": action.price,
                "quantity": action.quantity,
                "product": product_name,
                "offer_id": action.offer_id,
                "timestamp": time.time(),
                "status": "COMPLETED",
                "reasoning": action.reasoning
            }
            # Swap IDs correctly based on who sent the ACCEPT
            if agent["type"] == "seller":
                tx_data["buyer_id"] = action.receiver_id
                tx_data["seller_id"] = agent["id"]
            else:
                tx_data["buyer_id"] = agent["id"]
                tx_data["seller_id"] = action.receiver_id

            await asyncio.to_thread(
                lambda: get_db().collection("transactions").document(tx_id).set(tx_data)
            )
            logger.info(f"💰 [Server] Transaction created: {tx_id} for {action.price} USDC")
            # Note: Broadast and Reputation are now handled by on_transaction_snap

        # Broadcast via Pub/Sub for real-time
        # Publisher calls are generally fast but we can thread them too if needed, usually not blocking IO in the same way
        data = json.dumps(payload).encode("utf-8")
        future = app.state.publisher.publish(app.state.neg_topic_path, data)
        # future.result() # Do NOT call result() here, let it be async
        
        # Local broadcast only if not transaction (transactions are handled by snapshots)
        if action.action != "ACCEPT":
            await manager.broadcast({"type": "market_event", "data": payload})
        
        # --- NEW: Negotiation Termination Protocol ---
        if action.action == "ACCEPT":
            # Signal success to both parties
            result_msg = {
                "type": "negotiation_concluded",
                "status": "COMPLETED",
                "negotiation_id": action.negotiation_id,
                "transaction_id": tx_id,
                "price": action.price,
                "quantity": action.quantity,
                "product": product_name,
                "timestamp": time.time()
            }
            # Use targeted messaging for strict separation
            buyer_id = tx_data["buyer_id"]
            seller_id = tx_data["seller_id"]
            await manager.send_to_agent(buyer_id, result_msg)
            await manager.send_to_agent(seller_id, result_msg)
            logger.info(f"🏁 [Protocol] Sent negotiation_concluded to {buyer_id} and {seller_id}")

        elif action.action == "REJECT":
            # Signal termination
            term_msg = {
                "type": "negotiation_terminated",
                "status": "FAILED",
                "negotiation_id": action.negotiation_id,
                "reason": "Offer Rejected",
                "timestamp": time.time()
            }
            await manager.send_to_agent(action.sender_id, term_msg)
            await manager.send_to_agent(action.receiver_id, term_msg)
            logger.info(f"🛑 [Protocol] Sent negotiation_terminated for {action.negotiation_id}")

        # Trigger analysis if terminal state
        if action.action in ["ACCEPT", "REJECT"]:
            involved = [agent["id"], action.receiver_id]
            logger.info(f"🚀 [Server] Scheduling analysis for {action.negotiation_id}...")
            
            target_loop = app.state.main_loop if hasattr(app.state, 'main_loop') else None
            # Use background tasks properly
            if target_loop:
                asyncio.run_coroutine_threadsafe(analyze_negotiation(action.negotiation_id, involved), target_loop)
            else:
                 asyncio.create_task(analyze_negotiation(action.negotiation_id, involved))

        return {"status": "Action Sent", "payload": payload}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/feedback/submit")
async def submit_feedback(req: UserFeedbackRequest):
    """Stores user feedback for a negotiation."""
    feedback_data = {
        "negotiation_id": req.negotiation_id,
        "rating": req.rating,
        "comment": req.comment,
        "user_id": req.user_id,
        "timestamp": time.time()
    }
    
    try:
        # Save to Firestore
        await asyncio.to_thread(
            lambda: get_db().collection("user_feedback").document().set(feedback_data)
        )
        logger.info(f"⭐ [Feedback] User rated negotiation {req.negotiation_id}: {req.rating}/5")
        
        # Broadcast feedback event to update UI in real-time if needed
        target_loop = app.state.main_loop if hasattr(app.state, 'main_loop') else None
        if target_loop:
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({"type": "user_feedback_received", "data": feedback_data}),
                target_loop
            )
            
        return {"status": "Feedback Received", "data": feedback_data}
    except Exception as e:
        logger.warning(f"⚠️ [Feedback] Submission failed: {e}")
        raise HTTPException(status_code=500, detail="Feedback submission failed")

@app.get("/feedback/history")
def get_feedback_history(limit: int = 20):
    """Fetches combined history of coach and user feedback (Fixed global sort)."""
    try:
        # Fetch larger buffer from both to ensure we get a neutral mix after merging
        # We fetch 'limit' from EACH to ensure we have enough even if one source is empty
        buffer_limit = limit 
        
        # Fetch Coach feedback
        coach_docs = get_db().collection("agent_feedback")\
                            .order_by("timestamp", direction=firestore.Query.DESCENDING)\
                            .limit(buffer_limit).stream()
        
        # Fetch User feedback
        user_docs = get_db().collection("user_feedback")\
                           .order_by("timestamp", direction=firestore.Query.DESCENDING)\
                           .limit(buffer_limit).stream()
        
        feedback = []
        for d in coach_docs:
            data = d.to_dict()
            data["source"] = "Market Coach"
            feedback.append(data)
            
        for d in user_docs:
            data = d.to_dict()
            data["source"] = "User"
            feedback.append(data)
            
        # Sort combined globally by timestamp
        feedback.sort(key=lambda x: x["timestamp"], reverse=True)
        return {"feedback": feedback[:limit]}
    except Exception as e:
        logger.warning(f"⚠️ [Feedback] Failed to fetch history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/market/trends")
def get_market_trends(limit: int = 500):
    """Fetches historical price data optimized via denormalization (in-memory sort for reliability)."""
    try:
        logger.info(f"📊 [Trends] Fetching limit={limit}")
        # Optimized query with server-side limit and sort
        tx_docs = get_db().collection("transactions")\
                         .order_by("timestamp", direction=firestore.Query.DESCENDING)\
                         .limit(limit)\
                         .stream()
        
        trends = []
        for doc in tx_docs:
            tx = doc.to_dict()
            # logger.info(f"Debug TX: {tx.get('id')} - {tx.get('amount')}")
            trends.append({
                "timestamp": tx.get("timestamp"),
                "price": tx.get("amount"),
                "product": tx.get("product"),
                "explanation": tx.get("reasoning") or "Market transaction finalized.",
                "tx_id": tx.get("id"),
                "buyer_id": tx.get("buyer_id"),
                "seller_id": tx.get("seller_id")
            })
        
        logger.info(f"📊 [Trends] Found {len(trends)} transactions.") 
        # UI expects sorted by timestamp ascending
        return {"trends": trends[::-1]} # Reverse the already limited latest trends
    except Exception as e:
        logger.error(f"⚠️ [Trends] Failed to fetch: {e}")
        # Log the specific error for debugging index issues
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

def get_db():
    if not hasattr(app.state, 'db') or app.state.db is None:
        app.state.db = firestore.Client(project=PROJECT_ID)
    return app.state.db

def get_coach_model():
    if not hasattr(app.state, 'coach_model') or app.state.coach_model is None:
        vertexai.init(project=PROJECT_ID, location=REGION)
        app.state.coach_model = GenerativeModel(MODEL_NAME)
    return app.state.coach_model

async def analyze_negotiation(negotiation_id: str, involved_agents: List[str]):
    """Background task to analyze a finished negotiation and send feedback."""
    logger.info(f"🎬 [Coach] Starting analysis for negotiation: {negotiation_id}")
    await asyncio.sleep(2) # Brief delay
    
    try:
        current_db = get_db()
        current_model = get_coach_model()
        if not current_model:
            logger.warning(f"⚠️ [Coach] Skipping analysis for {negotiation_id} (Model not available)")
            return

        # 1. Fetch history
        logger.info(f"🔍 [Coach] Fetching history for {negotiation_id}...")
        docs = current_db.collection("negotiations")\
                 .where("negotiation_id", "==", negotiation_id)\
                 .stream()
        
        history = [doc.to_dict() for doc in docs]
        history.sort(key=lambda x: x["timestamp"])
        
        if not history:
            logger.warning(f"⚠️ [Coach] No history found for {negotiation_id}")
            return
            
        transcript = "\n".join([
            f"{'Buyer' if 'buyer' in h['sender_id'] else 'Seller'}: {h['action']} ${h.get('price')} - reasoning: {h.get('reasoning')}"
            for h in history
        ])
        
        # 2. Consult Gemini Coach
        prompt = f"""
        You are a neutral 'Marketplace Coach'. 
        Analyze the following negotiation transcript between a Buyer and a Seller.
        
        Transcript:
        {transcript}
        
        Goals:
        - Identify if the Buyer overpaid or if the Seller left money on the table.
        - Critique their negotiation tactics (e.g. anchoring, mirroring, concessions).
        - Provide one specific improvement tip for EACH agent.
        
        Output strict JSON:
        {{
          "buyer_feedback": "Short critique for the buyer",
          "seller_feedback": "Short critique for the seller",
          "strategy_score": 1-10
        }}
        """
        
        # FIX: Offload blocking synchronous call to a thread
        response = await asyncio.to_thread(current_model.generate_content, prompt)
        
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        try:
            analysis = json.loads(clean_text)
        except json.JSONDecodeError:
            logger.warning(f"⚠️ [Coach] JSON Parse Error. Raw: {clean_text}")
            analysis = {
                "buyer_feedback": "Could not parse feedback.",
                "seller_feedback": "Could not parse feedback.",
                "strategy_score": 5
            }
        
        # 2.5 Fetch Transaction Details (Product, Price, ID)
        tx_details = {}
        try:
            # Run blocking Firestore query in thread
            tx_docs = await asyncio.to_thread(
                lambda: list(current_db.collection("transactions")
                             .where("negotiation_id", "==", negotiation_id)
                             .limit(1)
                             .stream())
            )
            if tx_docs:
                tx_data = tx_docs[0].to_dict()
                tx_details = {
                    "product": tx_data.get("product"),
                    "price": tx_data.get("amount"),
                    "transaction_id": tx_data.get("id")
                }
            else:
                 logger.warning(f"⚠️ [Coach] No transaction found for {negotiation_id}")
        except Exception as e:
            logger.warning(f"⚠️ [Coach] Failed to fetch transaction details: {e}")

        # 3. Prepare Report
        report = {
            "type": "feedback_report",
            "negotiation_id": negotiation_id,
            "involved_agents": involved_agents,
            "feedback": analysis,
            "timestamp": time.time(),
            **tx_details
        }

        # 4. Save to Firestore (Coach Persistence)
        await asyncio.to_thread(
            lambda: get_db().collection("agent_feedback").document().set(report)
        )
        logger.info(f"💾 [Coach] Feedback persisted to Firestore for {negotiation_id}")

        # 5. Hybrid Feedback Delivery
        target_loop = app.state.main_loop if hasattr(app.state, 'main_loop') else None
        if target_loop:
            # A. Private Signal (Targeted to Agents)
            for agent_id in involved_agents:
                 asyncio.run_coroutine_threadsafe(
                    manager.send_to_agent(agent_id, report),
                    target_loop
                )
            
            # B. Public Signal (Broadcast to Dashboard)
            asyncio.run_coroutine_threadsafe(
                manager.broadcast(report),
                target_loop
            )
            
            logger.info(f"📡 [Coach] Feedback Sent: Private->{involved_agents}, Public->Dashboard for {negotiation_id}")

    except Exception as e:
        logger.exception(f"⚠️ [Coach] Analysis failed for {negotiation_id}")
        
        # Broadcast failure to UI
        target_loop = app.state.main_loop if hasattr(app.state, 'main_loop') else None
        if target_loop:
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({
                    "type": "analysis_error", 
                    "negotiation_id": negotiation_id,
                    "error": "Negotiation analysis encountered an internal error."
                }),
                target_loop
            )

class MarketOffer(BaseModel):
    buyer_id: str
    product: str
    price: float
    quantity: Optional[int] = 1
    category: Optional[str] = DEFAULT_CATEGORY
    currency: Optional[str] = os.getenv("AGENT_MKT_CURRENCY", "USDC")

@app.post("/market/offers")
async def post_offer(req: MarketOffer, agent: dict = Depends(verify_api_key)):
    if agent["type"] != "seller":
        raise HTTPException(status_code=403, detail="Only sellers can post offers")
        
    offer_id = f"off-{uuid.uuid4().hex[:8]}"
    offer_data = {
        "offer_id": offer_id,
        "sender_id": agent["id"],
        "receiver_id": req.buyer_id,
        "seller_id": agent["id"],
        "buyer_id": req.buyer_id,
        "product": req.product,
        "price": req.price,
        "category": req.category,
        "currency": req.currency,
        "status": "OPEN",
        "created_at": time.time(),
        "valid_until": time.time() + 3600,
        "agent_name": agent["name"]
    }
    
    try:
        # Also persist to market_items for consistency (though offers are targeted)
        # We can query them later if needed.
        offer_data["type"] = "Offer" # Ensure type is set for consistency
        get_db().collection("market_items").document(offer_id).set(offer_data)

        get_db().collection("offers").document(offer_id).set(offer_data)
        
        # Immediate local broadcast for speed
        await manager.broadcast({"type": "market_event", "data": offer_data})
            
        return {"status": "Offer Created", "offer_id": offer_id, "data": offer_data}
    except Exception as e:
        logger.exception("❌ Failed to create offer")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/market/active")
async def get_active_market_items():
    """Returns currently active requests and offers."""
    try:
        now = time.time()
        # Query for items that are valid_until > now
        docs = get_db().collection("market_items")\
            .where("valid_until", ">", now)\
            .stream()
            
        items = [doc.to_dict() for doc in docs]
        return {"items": items}
    except Exception as e:
         logger.exception("❌ Failed to fetch active market items")
         raise HTTPException(status_code=500, detail="Failed to fetch active items")

@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_running_loop()
    app.state.main_loop = loop
    
    # Initialize GCP/Vertex inside the loop process
    try:
        app.state.db = firestore.Client(project=PROJECT_ID)
        
        # Initialize Pub/Sub
        TEST_MODE = os.getenv("AGENT_MKT_TEST_MODE", "false").lower() == "true"

        if TEST_MODE:
            logger.info("🧪 Test Mode: Using Mock Publisher")
            from unittest.mock import MagicMock
            app.state.publisher = MagicMock()
            app.state.topic_path = "projects/test/topics/market-events"
            app.state.neg_topic_path = "projects/test/topics/negotiation-events"
        else:
            app.state.publisher = pubsub_v1.PublisherClient()
            app.state.topic_path = app.state.publisher.topic_path(PROJECT_ID, TOPIC_ID)
            app.state.neg_topic_path = app.state.publisher.topic_path(PROJECT_ID, NEG_TOPIC_ID)
        
        vertexai.init(project=PROJECT_ID, location=REGION)
        app.state.coach_model = GenerativeModel(MODEL_NAME)
        
        logger.info(f"✅ GCP and Vertex AI ({MODEL_NAME}) initialized successfully.")
    except Exception as e:
        logger.warning(f"⚠️ Warning: GCP/Vertex initialization failed: {e}")

    # Run setup_listeners in background
    loop.run_in_executor(None, setup_listeners, loop)

@app.get("/debug/connections")
def debug_connections():
    return {
        "active_count": len(manager.active_connections),
        "agent_mapped_count": len(manager.agent_map),
        "clients": [f"{ws.client.host}:{ws.client.port}" for ws in manager.active_connections]
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8005))
    logger.info(f"🚀 Starting Marketplace Platform on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
