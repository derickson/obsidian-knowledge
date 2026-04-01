.PHONY: init up down build redeploy logs dev dev-stop sync sync-fix reindex test test-integration lint build-frontend

# --- Setup ---

init:
	cd frontend && npm install
	uv sync --extra dev

build-frontend:
	cd frontend && API_PREFIX=/obsidian-knowledge npm run build

# --- Docker (production) ---

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

redeploy:
	docker compose down
	docker compose build
	docker compose up -d

logs:
	docker compose logs -f

# --- Local development (bare metal) ---

dev:
	@echo "Starting dev servers..."
	VAULT_PATH=$(CURDIR)/vaults/AgentKnowledge nohup uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 3104 --reload --app-dir obsidian-headless > /tmp/ok-headless.log 2>&1 &
	HEADLESS_URL=http://localhost:3104 nohup uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 3105 --reload --app-dir backend > /tmp/ok-backend.log 2>&1 &
	cd frontend && nohup npx vite --host 0.0.0.0 --port 8104 > /tmp/ok-frontend.log 2>&1 &
	@echo "Logs: /tmp/ok-headless.log, /tmp/ok-backend.log, /tmp/ok-frontend.log"
	@echo "  headless: http://localhost:3104"
	@echo "  backend:  http://localhost:3105"
	@echo "  frontend: http://localhost:8104"

dev-stop:
	@echo "Stopping dev servers..."
	-pkill -f "uvicorn app.main:app.*--port 3104"
	-pkill -f "uvicorn app.main:app.*--port 3105"
	-pkill -f "vite.*--port 8104"

# --- Admin ---

sync:
	curl -s -X POST http://localhost:3104/sync/ | python3 -m json.tool

sync-fix:
	./sync-panic-button.sh

reindex:
	curl -s -X POST http://localhost:3105/obsidian-knowledge/api/admin/reindex/ | python3 -m json.tool

# --- Testing ---

test:
	uv run pytest -m "not integration"

test-integration:
	uv run pytest tests/test_integration.py -v

lint:
	uv run ruff check backend/ obsidian-headless/ tests/
