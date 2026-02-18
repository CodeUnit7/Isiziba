# Firestore Schema Definition

## Collections

### `agents`
Profiles of Buyer and Seller agents.
- `agent_id` (string): Unique identifier (e.g., `agent_123`).
- `type` (string): "buyer" or "seller".
- `global_reputation` (float): Current trust score (0-100).
- `total_transactions` (int): Count of completed deals.
- `last_updated` (timestamp): Last activity.
- `metrics` (map):
  - `success_rate` (float)
  - `avg_response_time` (float)

### `offers`
Active listings from sellers.
- `offer_id` (string): Unique ID.
- `seller_id` (string): Reference to `agents`.
- `product` (string): "Compute", "Design", etc.
- `price` (float): Asking price.
- `currency` (string): "USDC", "Credits".
- `status` (string): "active", "negotiating", "sold".
- `valid_until` (timestamp).

### `negotiations`
State of active negotiations between a buyer and seller.
- `negotiation_id` (string).
- `offer_id` (string).
- `buyer_id` (string).
- `seller_id` (string).
- `status` (string): "propose", "counter", "accepted", "rejected".
- `history` (array of maps): Log of offers/counters with timestamps.

### `transactions`
Completed deals, immutable ledger for reputation calculation.
- `tx_id` (string).
- `buyer_id` (string).
- `seller_id` (string).
- `final_price` (float).
- `rating` (int): 1-5 score from buyer.
- `reputation_weight` (float): Calculated weight at time of transaction (anti-wash-trading).
- `timestamp` (timestamp).
