# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Agentic knowledge server that unifies knowledge across projects. Obsidian vault is the source of truth; Elasticsearch (Elastic Cloud Serverless) is a read-only search mirror kept in sync. The backend exposes both a REST API and MCP server for agentic access.

## Architecture

```
MCP Clients / Web UI / REST Clients
        │
   FastAPI + FastMCP (single service, /mcp for MCP)
        │
   ┌────┴────┐
   Vault     Elasticsearch (Elastic Cloud Serverless)
   (files)   (read-only mirror, Jina v3 small embeddings via semantic_text)
```

- **One vault**: `vaults/AgentKnowledge/` — all notes live here
- **One-way sync**: vault → ES. Writes never go to ES directly.
- **Post-processing pipeline**: runs in background after note creation (indexing, ob sync, future cross-linking)

### Service architecture (Docker)

Three containers in docker-compose (same ports for dev and Docker):

- **obsidian-headless** (port 3104): Owns the vault filesystem and `ob` CLI. Runs a FastAPI service that exposes vault read/write/delete/list and sync operations over HTTP. Only container that mounts the `vaults/` volume.
- **backend** (port 3105): FastAPI + FastMCP. REST API + MCP server. Calls obsidian-headless for vault operations, manages ES indexing, runs post-processing pipeline.
- **frontend** (port 8104): React/Vite UI.

The backend never touches vault files directly — all vault I/O goes through the obsidian-headless service via HTTP.

## Commands

```bash
# Setup
make init            # Install frontend deps + Python dev deps

# Docker (production)
make up              # Start all services
make down            # Stop all services
make build           # Rebuild containers
make redeploy        # down + build + up
make logs            # Tail logs

# Local development (bare metal)
make dev             # Start all 3 services with hot reload
make dev-stop        # Stop all dev servers

# Obsidian
ob sync              # Sync vault with Obsidian cloud
make sync            # Trigger sync via headless service

# Testing & linting
make test            # Run unit tests (excludes integration)
make test-integration # Run integration tests (requires make dev or make up)
make lint            # Run ruff
uv run pytest tests/test_vault_reader.py -v  # Run a single test file
uv run pytest -k test_read_existing_note     # Run a single test by name

# Admin
make reindex         # Full reindex vault → ES
```

## Backend (Python)

- **Runtime**: Python 3.12, FastAPI, FastMCP, uv for package management
- **Venv**: `~/.venvs/obsidian-knowledge`, symlinked as `.venv` at repo root
- **Config**: `backend/app/config.py` — pydantic-settings, reads from `.env`
- **Lint**: `ruff` — configured in `pyproject.toml` (at repo root)
- **Test**: `pytest` with asyncio auto mode — tests in `tests/` at repo root

### Key modules

| Module | Purpose |
|--------|---------|
| `backend/app/main.py` | FastAPI app setup, mounts MCP at `/mcp` |
| `backend/app/config.py` | pydantic-settings, reads from `.env` |
| `backend/app/api/notes.py` | REST endpoints: CRUD + search |
| `backend/app/api/admin.py` | Reindex and sync triggers |
| `backend/app/mcp/tools.py` | MCP tool definitions (search, read, create, reindex) |
| `backend/app/vault/reader.py` | HTTP client to headless service (read/list notes) |
| `backend/app/vault/writer.py` | HTTP client to headless service (write/delete notes) |
| `backend/app/search/client.py` | ES client (lazy init), index mapping, search/semantic queries |
| `backend/app/search/indexer.py` | Vault → ES sync with content-hash change detection |
| `backend/app/pipeline/runner.py` | Background post-processing (index + sync + future enrichment) |
| `backend/app/sync.py` | HTTP client to headless service (trigger `ob sync`) |

## Obsidian Headless Service

| Module | Purpose |
|--------|---------|
| `obsidian-headless/app/main.py` | FastAPI endpoints for vault CRUD + sync |
| `obsidian-headless/app/config.py` | pydantic-settings (`VAULT_PATH`) |
| `obsidian-headless/app/vault/reader.py` | Direct file I/O: read/parse vault markdown, extract wikilinks |
| `obsidian-headless/app/vault/writer.py` | Direct file I/O: write notes with frontmatter |
| `obsidian-headless/app/sync.py` | `ob sync` subprocess wrapper |

### URL conventions

All backend endpoints are prefixed with a configurable `API_PREFIX` (default: `/obsidian-knowledge`, set in `.env`). All endpoints end with `/` to avoid 301 redirects behind a reverse proxy.

### Ingest API

```
POST /obsidian-knowledge/api/notes/
{
  "path": "Inbox/note-title.md",
  "content": "# Markdown content here",
  "metadata": {"tags": ["topic"], "source": "system-name"}
}
```

`metadata` becomes YAML frontmatter. `content` is raw markdown, passed through as-is.

## Frontend (React/TypeScript)

- Vite + React 19 + TypeScript
- Served under `API_PREFIX` (default `/obsidian-knowledge/`)
- Proxies `API_PREFIX/api/` and `API_PREFIX/mcp/` to backend
- Search UI with full-text and hybrid semantic modes (defaults to semantic)

## Working with Obsidian Vaults

- Notes are plain Markdown with YAML frontmatter for metadata
- `[[wikilinks]]` for internal linking between notes
- The `.obsidian/` directory contains Obsidian app config — don't modify directly
- This is a headless setup (no desktop app) — use `ob sync` for cloud sync
