.PHONY: up down build logs backend frontend sync reindex test lint

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

backend:
	docker compose up -d backend

frontend:
	docker compose up -d frontend

sync:
	ob sync

reindex:
	curl -s -X POST http://localhost:8000/api/admin/reindex | python3 -m json.tool

dev-backend:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir backend

dev-frontend:
	cd frontend && npm run dev

test:
	uv run pytest

lint:
	uv run ruff check backend/ tests/
