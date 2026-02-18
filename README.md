# Isiziba Agent Marketplace 🤖🤝🤖

An autonomous agent economy where AI buyers and sellers negotiate, trade, and build reputation in a live, event-driven marketplace. Fork the future of commerce and deploy a self-governing commerce agent fleet that bargains, learns, and profits through seamless agent-to-agent transactions in real-time.

## 🌟 Key Features

*   **Autonomous Agent Economy**: Agents with distinct personalities, budgets, and inventories trade continuously without human intervention.
*   **Real-time Negotiation**: Protocol-driven negotiation with offers, counter-offers, acceptance, and rejection logic using Chris Voss-inspired strategies.
*   **Agent Identity Persistence**: Agents remember who they are across restarts. Their identity, reputation, and transaction history are persisted in Firestore.
*   **Smart Registration**: The system automatically detects and prevents duplicate agent registrations, ensuring a clean marketplace.
*   **AI Code of Conduct**: Agents are governed by an "AI Constitution" prohibiting unethical behavior (collusion, price gouging).
*   **Reputation System**: Trust is quantified. Agents earn reputation points for successful, fair transactions, displayed on a live leaderboard.
*   **Live Dashboard**: A real-time React UI visualizing market trends, active negotiations, and the "Order Book".
*   **AI Coaching**: A background "Coach" agent analyzes negotiations and provides feedback to improve agent strategies.
*   **Event-Driven Architecture**: Uses Google Cloud Pub/Sub and WebSockets for low-latency state synchronization.

## 🏗 Architecture

The platform follows a modern, event-driven architecture:

1.  **Agents (Python)**: Autonomous processes that interact with the market via the API.
2.  **API Gateway (FastAPI)**: The central hub for agent registration, market requests, and offers.
3.  **Persistence (Firestore)**: Stores agent identities, transaction history, and market items.
4.  **Messaging (Pub/Sub)**: Decouples components and enables asynchronous communication.
5.  **Frontend (Next.js)**: Connects to the API via REST and WebSockets to display real-time market data.

## 🚀 Getting Started

### Prerequisites
*   Python 3.10+
*   Node.js 18+
*   Google Cloud Project with Vertex AI & Firestore enabled.
*   `make`

### Installation & Setup

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/agent-marketplace.git
    cd agent-marketplace
    ```
    *(Note: You can open this folder in VSCode or your preferred editor)*

2.  **Configure Environment**:
    ```bash
    cp .env.example .env
    # Edit .env with your Google Cloud PROJECT_ID
    ```

3.  **Install Dependencies**:
    ```bash
    make install
    ```

### Running the Fleet

To start the full autonomous economy (API, Frontend, and 6 Agents):

```bash
make fleet
```

This will launch:
- 🔌 **API Server**: `http://localhost:8005`
- 🌐 **Frontend**: `http://localhost:3005`
- 🤖 **Agent Fleet**: A mix of buyers and sellers negotiating in real-time.

To stop everything:
```bash
make stop
```

### Simulation Control Options

### Simulation Control Options

By default, `make fleet` starts the Platform **AND** runs the agents for **one transaction cycle** (Single Trade mode).

*   **Continuous Simulation** (Agents trade indefinitely):
    ```bash
    make fleet CONTINUOUS=true
    ```
*   **Disable Agents** (API + Dashboard only):
    ```bash
    make fleet RUN_SIMULATION=false
    ```


## 🛠 Maintenance & Tools

### Deduplicating Agents
If you notice duplicate agents in the leaderboard (e.g., multiple "Nova Systems"), use the deduplication script to clean up the database:

```bash
# Ensure your environment variables are set
export AGENT_MKT_PROJECT_ID=your-project-id
python tools/deduplicate_agents.py
```
This script will keep the agent with the most transactions/reputation and remove the duplicates.

## ❓ Troubleshooting

### Quota Limits / Resource Exhausted (429)
If you see `ResourceExhausted` or `429` errors in the logs, it means you are hitting the rate limits for the underlying LLM model (e.g., Vertex AI).
*   **Solution**: The agents are designed to handle this gracefully by retrying or crashing and restarting (safe due to identity persistence). You can also request a quota increase in your Cloud Console.

### Address already in use
If `make fleet` fails because a port is already in use:
*   **Solution**: Run `make stop` to kill any lingering processes. If that doesn't work, manually kill the process using `lsof -i :8005` (or the relevant port).

## 📁 Repository Structure

*   `agents/`: Source code for autonomous agents (Buyer, Seller).
*   `api_server.py`: Main FastAPI backend orchestrating the market.
*   `frontend/`: Next.js dashboard application.
*   `tools/`: Utility scripts for maintenance and testing.
*   `protocol/`: Shared protocol definitions.

## 🤝 Contribution

We welcome contributions! Please see `CONTRIBUTING.md` for details on how to submit pull requests.

## 📄 License

MIT License.
