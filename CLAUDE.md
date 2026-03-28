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

## Commands

```bash
# Docker
make up              # Start all services
make down            # Stop all services
make build           # Rebuild containers
make logs            # Tail logs

# Local development
make dev-backend     # Run backend with hot reload (port 8000)
make dev-frontend    # Run frontend dev server (port 5173)

# Obsidian
ob sync              # Sync vault with Obsidian cloud
make sync            # Same as above

# Testing & linting
make test            # Run pytest
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
| `backend/app/vault/reader.py` | Read/parse vault markdown files, extract wikilinks |
| `backend/app/vault/writer.py` | Write notes with frontmatter to vault |
| `backend/app/search/client.py` | ES client (lazy init), index mapping, search/semantic queries |
| `backend/app/search/indexer.py` | Vault → ES sync with content-hash change detection |
| `backend/app/pipeline/runner.py` | Background post-processing (index + sync + future enrichment) |
| `backend/app/sync.py` | `ob sync` subprocess wrapper |

### Ingest API

```
POST /api/notes
{
  "path": "Inbox/note-title.md",
  "content": "# Markdown content here",
  "metadata": {"tags": ["topic"], "source": "system-name"}
}
```

`metadata` becomes YAML frontmatter. `content` is raw markdown, passed through as-is.

## Frontend (React/TypeScript)

- Vite + React 19 + TypeScript
- Proxies `/api` to backend in dev mode
- Minimal search UI (full-text and semantic modes)

## Working with Obsidian Vaults

- Notes are plain Markdown with YAML frontmatter for metadata
- `[[wikilinks]]` for internal linking between notes
- The `.obsidian/` directory contains Obsidian app config — don't modify directly
- This is a headless setup (no desktop app) — use `ob sync` for cloud sync
