---
name: dave-project-tips
description: Conventions and patterns for projects hosted on Dave's server (smaug). Covers FastAPI, Vite, Docker, nginx, Elasticsearch, Makefile organization, and common pitfalls.
user-invocable: false
---

# Project Conventions for smaug

These are Dave's established conventions for projects hosted on his Ubuntu server `smaug`. Follow these patterns unless explicitly told otherwise.

## URL and Routing

- **All endpoints must end with `/`** — the nginx reverse proxy adds trailing slashes, causing 301 redirects if the backend doesn't expect them. This applies to all FastAPI routes, fetch URLs in the frontend, and proxy rules in Vite config.
- **Configurable API prefix** — all routes live under `/{project-name}/` (e.g., `/obsidian-knowledge/`). Use `API_PREFIX` env var, never hardcode. The frontend, backend, and nginx all reference this prefix.
- **FastAPI route ordering** — define specific routes (`/recent/`, `/search/`) BEFORE catch-all `/{path:path}` routes, or the catch-all will shadow them.

## Ports

- **Dev and Docker use the same ports** — dev and prod never run simultaneously on smaug.
- **Python services**: ports 3100+ (e.g., 3104, 3105)
- **Node/frontend services**: ports 8100+ (e.g., 8104)
- Avoid ports 8000, 5173, and other common defaults that conflict with other services on the server.

## Python / Backend

- **Package manager**: `uv` (not pip, not poetry)
- **Virtual environment**: `~/.venvs/{project-name}`, symlinked as `.venv` at the repo root
- **`pyproject.toml`** lives at the repo root (not inside `backend/`)
- **Run uvicorn**: `uv run python -m uvicorn` (not `uv run uvicorn` — the latter can fail to resolve the binary through the symlinked venv)
- **pydantic-settings**: always use `model_config = {"env_file": ".env", "extra": "ignore"}` — the `extra: "ignore"` is critical because `.env` contains vars for multiple services (APM, etc.) that would otherwise cause validation errors
- **Lint**: `ruff` configured in `pyproject.toml`
- **Test**: `pytest` with `asyncio_mode = "auto"` and `pythonpath = ["backend"]`

## Elasticsearch

- **Always Elasticsearch Serverless** — connect via URL (`ES_URL`), never Cloud ID
- **Two separate ES instances**: one for data/search, one for observability/APM
- **API key auth**: `ES_API_KEY` env var
- **Date fields**: always cast `last_modified` to `int()` before indexing — float scientific notation breaks ES `epoch_second` format
- **Linear retriever**: set `rank_window_size` to at least `max(size, 100)` to avoid validation errors when `size` exceeds the default

## Elastic APM

- **Package**: `elastic-apm` with Starlette middleware
- **Per-service names**: `make_apm_client({"SERVICE_NAME": "project-name-service"})` — each service gets a distinct name in the APM UI
- **Env vars**: `ELASTIC_APM_SERVER_URL`, `ELASTIC_APM_SECRET_TOKEN`, `ELASTIC_APM_API_KEY`, `ELASTIC_APM_ENVIRONMENT` — the APM agent reads these automatically, no need to put them in pydantic Settings

## Frontend (Vite + React)

- **Vite `base`**: must match `API_PREFIX` (e.g., `base: "${apiPrefix}/"`)
- **`allowedHosts: true`** in Vite server config — required for LAN access from Dave's laptop
- **Proxy rules**: proxy `${apiPrefix}/api/` and `${apiPrefix}/mcp/` to the backend URL. Proxy paths must end with `/`.
- **`__API_PREFIX__`**: injected via Vite `define` for runtime use in fetch calls
- **Theme**: light and dark mode, defaulting to browser/OS preference via `prefers-color-scheme` media query with manual toggle
- **Responsive**: UI should work well on both mobile and desktop
- **Semantic search default**: when there's a search mode selector, default to semantic

## Docker

- **`docker-compose.yml`**: use `env_file: .env` for shared vars, `environment:` for service-specific overrides (e.g., `HEADLESS_URL` pointing to the Docker service name)
- **Frontend Dockerfile**: multi-stage build — `npm ci` + `vite build` in build stage, serve static files in final stage. In production behind nginx, nginx serves `frontend/dist/` directly as static files (no frontend container needed for serving).
- **Backend Dockerfile**: `python:3.12-slim`, copy `uv` from `ghcr.io/astral-sh/uv:latest`, `uv sync --no-dev`
- **`restart: unless-stopped`** on all services
- **`depends_on`** for service ordering

## nginx Reverse Proxy

- **Three location blocks per project** (order matters — most specific first with `^~`):
  1. `^~ /project/mcp/` — NO basic auth (FastMCP handles Bearer token). Requires `proxy_http_version 1.1;` and `proxy_set_header Connection "";` for SSE/streaming. Also: `proxy_buffering off; proxy_cache off; proxy_read_timeout 300s;`
  2. `^~ /project/api/` — basic auth via `.htpasswd`, proxy to backend
  3. `/project/` — basic auth, `alias` to `frontend/dist/`, `try_files $uri $uri/ /project/index.html;` for SPA routing
- **Never proxy frontend dev server in production** — serve built static files directly with nginx `alias`
- **Always set**: `proxy_set_header Host $host; X-Real-IP; X-Forwarded-For; X-Forwarded-Proto`
- **Run `make build-frontend`** after frontend changes, then reload nginx

## FastMCP / MCP Server

- **Mount with `http_app(path="/")`** — avoids double path (e.g., `/mcp/mcp/`)
- **Chain lifespan**: `async with mcp_app.lifespan(app): yield` inside the FastAPI lifespan — required for session manager initialization
- **Auth**: `DebugTokenVerifier` with `MCP_API_KEY` env var for Bearer token auth. When key is empty, MCP is open (local dev). nginx does NOT add basic auth to the MCP path.
- **Server instructions**: use the `instructions` parameter on `FastMCP()` to guide agents on vault organization, search tool selection, and note conventions

## Makefile

Standard targets:
- `init` — install all deps (`npm install` + `uv sync --extra dev`)
- `build-frontend` — `vite build` with `API_PREFIX` env var
- `up` / `down` / `build` / `redeploy` / `logs` — Docker lifecycle
- `dev` — start all services with `nohup`, log to `/tmp/`, print port URLs. Set `VAULT_PATH=$(CURDIR)/...` for headless service.
- `dev-stop` — `pkill -f` matching service ports
- `test` — `uv run pytest -m "not integration"` (unit tests only)
- `test-integration` — `uv run pytest tests/test_integration.py -v` (requires running services)
- `lint` — `ruff check`
- `sync` / `reindex` — admin curl commands to running services

## Environment Variables (.env)

- **`.env.example`** committed to git with placeholder values (no real secrets)
- **`.env`** in `.gitignore`
- **Group by purpose** with comments: external services, internal service URLs, server config, auth, observability
- All Docker services share the same `.env` via `env_file`

## Testing

- **Unit tests**: mock external services (ES, headless HTTP client), run with `make test`
- **Integration tests**: hit real running services, marked with `@pytest.mark.integration`, run with `make test-integration`. Works against both `make dev` and `make up`.
- **Integration test cleanup**: use `module`-scoped autouse fixture to delete test data even on failure. Verify deletion from both vault AND Elasticsearch.

## Cron Scripts

- Put cron helper scripts in `scripts/` — cron doesn't load nvm/shell profiles, so scripts must export `PATH` explicitly
- **Timestamp all output**: `echo "--- $(date '+%Y-%m-%d %H:%M:%S') ---"`
- **Conditional downstream actions**: capture output, grep for change indicators, only trigger expensive operations (reindex) when changes detected
- **Log to `/tmp/`** with project-specific log filenames

## Documentation

- **CLAUDE.md**: architecture overview, commands reference, module table, URL conventions, ingest API example
- **README.md**: mermaid architecture diagram, services table with ports, prerequisites (with exact CLI commands), setup instructions for both dev and prod, MCP client connection instructions, tech stack
