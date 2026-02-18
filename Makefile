-include .env.config

export

# Default Variables
# Use ?= to allow overriding from environment, but default to safe values
PROJECT_ID ?= your-gcp-project-id
API_HOST ?= 127.0.0.1
FRONTEND_PORT ?= 3005
BACKEND_PORT ?= 8005
API_URL ?= http://$(API_HOST):$(BACKEND_PORT)
MODEL ?= gemini-2.0-flash
LOG_DIR ?= /tmp/ag_logs

AGENT_MKT_MAX_HEARTBEAT_FAILURES ?= 5
PYTHON := ./.venv/bin/python

# Simulation Control
# Simulation Control
RUN_SIMULATION ?= true
CONTINUOUS ?= false
# Setup logs directory
$(shell mkdir -p $(LOG_DIR))

.PHONY: all install seed stop clean fleet-ui fleet

all: fleet-ui

fleet: fleet-ui

install:
	$(PYTHON) -m pip install -r requirements.txt
	cd frontend && npm install

clean:
	rm -rf frontend/.next

stop:
	@echo "🛑 Stopping all processes..."
	-pkill -f "agents/cloud_seller.py"
	-pkill -f "agents/cloud_buyer.py"
	-pkill -f "agents/electronics_seller.py"
	-pkill -f "agents/electronics_buyer.py"
	-pkill -f "agents/furniture_seller.py"
	-pkill -f "agents/furniture_buyer.py"
	-pkill -f "uvicorn api_server:app"
	-pkill -f "next-server"
	-lsof -ti:$(FRONTEND_PORT) | xargs kill -9 2>/dev/null
	-lsof -ti:3000 | xargs kill -9 2>/dev/null
	-lsof -ti:$(BACKEND_PORT) | xargs kill -9 2>/dev/null
	@sleep 2

seed:
	@echo "🌱 Seeding agents..."
	@AGENT_MKT_PROJECT_ID=$(PROJECT_ID) AGENT_MKT_API_URL=$(API_URL) $(PYTHON) tools/seed_agents.py

fleet-ui: stop seed
	@echo "🚀 Starting AG-UI Full Fleet (6 Agents)..."
	@echo "🔌 Starting Backend (Port $(BACKEND_PORT))..."
	@AGENT_MKT_PROJECT_ID=$(PROJECT_ID) AGENT_MKT_API_URL=$(API_URL) AGENT_MKT_MODEL=$(MODEL) AGENT_MKT_MAX_STEPS=10 $(PYTHON) -m uvicorn api_server:app --port $(BACKEND_PORT) --host $(API_HOST) > $(LOG_DIR)/api.log 2>&1 &
	@echo "📡 Setting up Pub/Sub..."
	@AGENT_MKT_PROJECT_ID=$(PROJECT_ID) AGENT_MKT_API_URL=$(API_URL) AGENT_MKT_MODEL=$(MODEL) $(PYTHON) tools/setup_pubsub.py > /dev/null 2>&1

ifeq ($(RUN_SIMULATION),true)
	@echo "🚢 Launching Full Agent Fleet (Continuous: $(CONTINUOUS))..."
	@AGENT_MKT_PROJECT_ID=$(PROJECT_ID) AGENT_MKT_API_URL=$(API_URL) AGENT_MKT_MODEL=$(MODEL) AGENT_MKT_CONTINUOUS=$(CONTINUOUS) $(PYTHON) -u agents/cloud_seller.py > $(LOG_DIR)/cloud_seller.log 2>&1 &
	@AGENT_MKT_PROJECT_ID=$(PROJECT_ID) AGENT_MKT_API_URL=$(API_URL) AGENT_MKT_MODEL=$(MODEL) AGENT_MKT_CONTINUOUS=$(CONTINUOUS) $(PYTHON) -u agents/cloud_buyer.py > $(LOG_DIR)/cloud_buyer.log 2>&1 &
	@AGENT_MKT_PROJECT_ID=$(PROJECT_ID) AGENT_MKT_API_URL=$(API_URL) AGENT_MKT_MODEL=$(MODEL) AGENT_MKT_CONTINUOUS=$(CONTINUOUS) $(PYTHON) -u agents/electronics_seller.py > $(LOG_DIR)/electronics_seller.log 2>&1 &
	@AGENT_MKT_PROJECT_ID=$(PROJECT_ID) AGENT_MKT_API_URL=$(API_URL) AGENT_MKT_MODEL=$(MODEL) AGENT_MKT_CONTINUOUS=$(CONTINUOUS) $(PYTHON) -u agents/electronics_buyer.py > $(LOG_DIR)/electronics_buyer.log 2>&1 &
	@AGENT_MKT_PROJECT_ID=$(PROJECT_ID) AGENT_MKT_API_URL=$(API_URL) AGENT_MKT_MODEL=$(MODEL) AGENT_MKT_CONTINUOUS=$(CONTINUOUS) $(PYTHON) -u agents/furniture_seller.py > $(LOG_DIR)/furniture_seller.log 2>&1 &
	@AGENT_MKT_PROJECT_ID=$(PROJECT_ID) AGENT_MKT_API_URL=$(API_URL) AGENT_MKT_MODEL=$(MODEL) AGENT_MKT_CONTINUOUS=$(CONTINUOUS) $(PYTHON) -u agents/furniture_buyer.py > $(LOG_DIR)/furniture_buyer.log 2>&1 &
else
	@echo "⏸️  Skipping Agent Fleet (RUN_SIMULATION=$(RUN_SIMULATION))"
endif



	@echo "🌐 Starting Frontend (Port $(FRONTEND_PORT))..."
	@cd frontend && PORT=$(FRONTEND_PORT) NEXT_PUBLIC_API_URL=$(API_URL) NEXT_PUBLIC_WS_URL=ws://$(API_HOST):$(BACKEND_PORT) npm run dev > $(LOG_DIR)/frontend.log 2>&1 &
	@echo "✅ Full Fleet Running."
	@echo "   - Dashboard: http://127.0.0.1:$(FRONTEND_PORT)"
	@tail -f $(LOG_DIR)/api.log
