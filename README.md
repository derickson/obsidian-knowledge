# Obsidian Knowledge

Agentic knowledge server that unifies knowledge across projects. Uses an Obsidian vault as the source of truth with Elasticsearch as a searchable read-only mirror. Exposes both a REST API and MCP server for agentic access.

## Architecture

```mermaid
graph TD
    subgraph Clients
        MCP[MCP Clients<br><i>Claude, Cursor, etc.</i>]
        UI[Web UI<br><i>React / Vite · :8104</i>]
        REST[REST Clients<br><i>External systems</i>]
    end

    subgraph Backend["Backend · FastAPI + FastMCP · :3105"]
        API[REST API<br><i>/obsidian-knowledge/api/</i>]
        MCPS[MCP Server<br><i>/obsidian-knowledge/mcp/</i>]
        Pipeline[Post-Processing Pipeline<br><i>index, sync, enrich</i>]
    end

    subgraph Headless["Obsidian Headless · FastAPI · :3104"]
        VaultAPI[Vault CRUD API]
        Sync[ob sync]
    end

    subgraph Storage
        Vault[(Obsidian Vault<br><i>source of truth</i>)]
        ES[(Elasticsearch Serverless<br><i>read-only mirror · hybrid search</i>)]
        Cloud[Obsidian Cloud]
    end

    MCP -->|SSE / HTTP| MCPS
    UI -->|HTTP| API
    REST -->|HTTP| API

    API -->|HTTP| VaultAPI
    MCPS -->|HTTP| VaultAPI
    API --> ES
    MCPS --> ES

    API -->|background| Pipeline
    Pipeline -->|index| ES
    Pipeline -->|HTTP| Sync

    VaultAPI --> Vault
    Sync <-->|ob sync| Cloud
    Sync --> Vault

    Vault -->|one-way sync| ES

    style Vault fill:#7c3aed,color:#fff
    style ES fill:#f59e0b,color:#fff
    style Cloud fill:#3b82f6,color:#fff
    style Headless fill:#10b981,color:#fff
```

### Services

Same ports for both local dev (`make dev`) and Docker (`make up`):

| Service | Port | Role |
|---------|------|------|
| **obsidian-headless** | 3104 | Owns the vault filesystem and `ob` CLI. FastAPI service for vault read/write/list/delete and sync. Only container that mounts `vaults/`. |
| **backend** | 3105 | FastAPI + FastMCP. REST API + MCP server for external access. Calls headless for vault I/O, manages ES indexing and post-processing pipeline. |
| **frontend** | 8104 | React/Vite search UI served under the API prefix. |

The backend never touches vault files directly — all vault I/O goes through the obsidian-headless service via HTTP.

## Prerequisites

### Obsidian Headless

Requires an [Obsidian Sync](https://obsidian.md/sync) subscription. Install the headless client and set up vault sync per the [official docs](https://obsidian.md/help/sync/headless):

```bash
# Install the headless client
npm install -g obsidian-headless

# Log in to your Obsidian account
ob login

# Create a remote vault (first time only), or list existing ones
ob sync-create-remote --name "AgentKnowledge"
# or: ob sync-list-remote

# Link the local vault directory to the remote vault
ob sync-setup --vault AgentKnowledge --path vaults/AgentKnowledge

# Pull down existing notes (or confirm sync is working)
ob sync --path vaults/AgentKnowledge

# Check sync status
ob sync-status --path vaults/AgentKnowledge
```

After setup, `ob sync` will push and pull changes between this server and Obsidian cloud. The backend triggers `ob sync` automatically after note creation via the API.

To periodically pull changes made on other devices, add a cron job:

```bash
# Run every 5 minutes — edit the path to match your install
crontab -e
```

```
*/5 * * * * cd /home/dave/dev/obsidian-knowledge && ob sync --path vaults/AgentKnowledge >> /tmp/ok-obsidian-sync.log 2>&1
```

### Environment

```bash
cp .env.example .env
# Fill in ES_URL, ES_API_KEY, ANTHROPIC_API_KEY, ELASTIC_APM_* values
```

## Setup

```bash
make init            # Install frontend npm deps + Python dev deps
```

### Production (Docker Compose)

```bash
make build           # Build all containers
make up              # Start all services
make down            # Stop all services
make redeploy        # down + build + up
make logs            # Tail logs
```

### Local development (bare metal)

```bash
make dev             # Start all 3 services with hot reload
make dev-stop        # Stop all dev servers
```

Dev logs are written to `/tmp/ok-headless.log`, `/tmp/ok-backend.log`, `/tmp/ok-frontend.log`.

### Testing

```bash
make test            # Run unit tests (excludes integration)
make test-integration # Run integration tests (requires make dev or make up)
make lint            # Run ruff
```

`make test-integration` runs an end-to-end lifecycle test: create a note, read it via headless and backend, search it in Elasticsearch (full-text and hybrid semantic), then delete it. Works against either `make dev` or `make up` since both use the same ports.

The Python virtual environment lives at `~/.venvs/obsidian-knowledge` and is symlinked as `.venv` at the repo root.

## URL Prefix

All endpoints are served under a configurable prefix (default: `/obsidian-knowledge`) to support reverse proxy deployments. All paths end with `/` to avoid 301 redirects. Set `API_PREFIX` in `.env` to change the prefix.

## Ingest API

```bash
curl -X POST http://localhost:3105/obsidian-knowledge/api/notes/ \
  -H "Content-Type: application/json" \
  -d '{
    "path": "Inbox/meeting-notes.md",
    "content": "# Meeting Notes\n\nDiscussed project timeline.",
    "metadata": {"tags": ["meeting"], "source": "slack"}
  }'
```

`content` is raw markdown, passed through as-is. `metadata` becomes YAML frontmatter in the Obsidian note.

## MCP

The MCP server is mounted at `/obsidian-knowledge/mcp/` and exposes tools for agentic access:

- `search` — full-text BM25 search
- `semantic` — hybrid search (linear fusion of BM25 + Jina vector embeddings)
- `read` — read a specific note
- `create` — create/update a note
- `list_all_notes` — list notes, optionally by folder
- `reindex` — full vault → ES resync

### Connecting from Claude Desktop

Add this to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "obsidian-knowledge": {
      "type": "streamable-http",
      "url": "http://localhost:3105/obsidian-knowledge/mcp/"
    }
  }
}
```

### Connecting from Claude Code

Add the MCP server to your project or global settings:

```bash
claude mcp add obsidian-knowledge --transport http http://localhost:3105/obsidian-knowledge/mcp/
```

Or add it manually to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "obsidian-knowledge": {
      "type": "streamable-http",
      "url": "http://localhost:3105/obsidian-knowledge/mcp/"
    }
  }
}
```

### Connecting from other MCP clients

Any MCP client that supports Streamable HTTP transport can connect to:

```
http://localhost:3105/obsidian-knowledge/mcp/
```

Replace `localhost:3105` with your server's hostname/IP if connecting remotely.

## Tech Stack

- **Backend**: Python 3.12, FastAPI, FastMCP, Elasticsearch, Elastic APM, uv
- **Obsidian Headless**: Python 3.12, FastAPI, Elastic APM, Node.js (for `ob` CLI)
- **Frontend**: React 19, Vite, TypeScript
- **Search**: Elasticsearch Serverless, Jina v3 small embeddings via `semantic_text`, hybrid retriever with linear fusion
- **Infrastructure**: Docker Compose, Obsidian Headless (`ob sync`)
