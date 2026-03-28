.PHONY: init up down build redeploy logs dev dev-stop sync reindex test lint

# --- Setup ---

init:
	cd frontend && npm install
	uv sync --extra dev

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
	nohup uv run uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload --app-dir obsidian-headless > /tmp/ok-headless.log 2>&1 &
	HEADLESS_URL=http://localhost:8100 nohup uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --app-dir backend > /tmp/ok-backend.log 2>&1 &
	cd frontend && nohup npx vite --host 0.0.0.0 --port 5173 > /tmp/ok-frontend.log 2>&1 &
	@echo "Logs: /tmp/ok-headless.log, /tmp/ok-backend.log, /tmp/ok-frontend.log"

dev-stop:
	@echo "Stopping dev servers..."
	-pkill -f "uvicorn app.main:app.*--port 8100"
	-pkill -f "uvicorn app.main:app.*--port 8000"
	-pkill -f "vite.*--port 5173"

# --- Admin ---

sync:
	curl -s -X POST http://localhost:8100/sync/ | python3 -m json.tool

reindex:
	curl -s -X POST http://localhost:8000/obsidian-knowledge/api/admin/reindex/ | python3 -m json.tool

# --- Testing ---

test:
	uv run pytest

lint:
	uv run ruff check backend/ obsidian-headless/ tests/
