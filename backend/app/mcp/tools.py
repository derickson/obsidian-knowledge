import asyncio
import logging

from fastmcp import FastMCP

from app.config import settings
from app.search.client import search_notes, semantic_search
from app.search.indexer import delete_from_index, index_note, reindex_all
from app.sync import run_ob_sync
from app.vault.reader import get_vault_structure, list_notes, read_note
from app.vault.writer import delete_note, write_note
from app.vaults import check_writable, get_vault, list_vaults as _list_vaults

logger = logging.getLogger(__name__)

mcp_auth = None
if settings.mcp_api_key:
    from fastmcp.server.auth import DebugTokenVerifier

    mcp_auth = DebugTokenVerifier(
        validate=lambda token: token == settings.mcp_api_key,
        client_id="mcp-client",
        scopes=[],
    )

mcp = FastMCP(
    "Obsidian Knowledge",
    auth=mcp_auth,
    instructions="""You are connected to Dave Erickson's personal Obsidian-backed knowledge base.
The user is Dave Erickson. When the user says "my", "I", or "me", they mean Dave Erickson.

Notes are markdown files with YAML frontmatter for metadata and [[wikilinks]] for cross-referencing.

## Multi-vault

This server manages multiple Obsidian vaults. All tools accept an optional `vault` parameter
(vault ID string). If omitted, the default vault is used. Use `list_vaults` to discover
available vaults and their capabilities.

Some vaults are **read-only** — they accept changes only via Obsidian Sync, not through
this server. Attempting to create, update, or delete notes in a read-only vault will return
a clear error. Check the `read_only` field in `list_vaults` output before writing.

## Vault layout discovery

Use the `get_vault_layout` tool to discover the folder structure and conventions for a
specific vault before creating notes. Each vault has its own organization, naming patterns,
and daily note conventions described in its instructions.

## Writing notes

- Use `[[wikilinks]]` to link between notes (e.g., `[[Dave Erickson]]`, `[[Elasticsearch]]`)
- Add relevant tags in metadata: `{"tags": ["meeting", "elasticsearch"], "source": "zoom"}`
- Content should be markdown. Frontmatter metadata is optional but encouraged.
- When creating notes about a topic that likely has an existing entry, search first to avoid duplicates.
- Prefer linking to existing notes over repeating information.

## Searching

- Use `semantic` for natural language questions (hybrid BM25 + vector search)
- Use `search` for exact keyword matching
- Use `list_all_notes` to browse by folder
""",
)


@mcp.tool()
def list_vaults() -> dict:
    """List all configured knowledge base vaults."""
    return {k: v.model_dump() for k, v in _list_vaults().items()}


@mcp.tool()
def get_vault_layout(vault: str | None = None) -> dict:
    """Get the folder structure and organization conventions for a vault.

    Returns the vault's instruction text (folder purposes, naming conventions,
    daily note patterns) along with a live folder tree. Call this before creating
    notes to understand how the vault is organized.
    """
    vc = get_vault(vault)
    result: dict = {"vault_name": vc.name}
    if vc.instructions:
        result["instructions"] = vc.instructions
    if vc.daily_note_format:
        result["daily_note_format"] = vc.daily_note_format
    result["folder_structure"] = get_vault_structure(vault_id=vault)
    return result


@mcp.tool()
def search(query: str, size: int = 10, vault: str | None = None) -> list[dict]:
    """Full-text search across all notes in the knowledge base."""
    return search_notes(query, size, vault_id=vault)


@mcp.tool()
def semantic(query: str, size: int = 10, vault: str | None = None) -> list[dict]:
    """Semantic search across notes using Jina embeddings."""
    return semantic_search(query, size, vault_id=vault)


@mcp.tool()
def read(path: str, vault: str | None = None) -> dict:
    """Read a specific note by its path relative to the vault root."""
    return read_note(path, vault_id=vault)


@mcp.tool()
def list_all_notes(folder: str | None = None, vault: str | None = None) -> list[str]:
    """List all notes in the vault, optionally filtered by folder."""
    return list_notes(folder, vault_id=vault)


@mcp.tool()
async def create(
    path: str, content: str, metadata: dict | None = None, vault: str | None = None
) -> dict:
    """Create or update a note in the knowledge base.

    Args:
        path: Path relative to vault root (e.g., "Inbox/my-note.md")
        content: Markdown content for the note
        metadata: Optional frontmatter metadata (tags, source, etc.)
        vault: Vault ID (optional, defaults to the default vault)
    """
    check_writable(vault)
    write_note(path, content, metadata, vault_id=vault)

    async def _post_process():
        try:
            note = read_note(path, vault_id=vault)
            index_note(note, vault_id=vault)
            await run_ob_sync(vault_id=vault)
        except Exception:
            logger.exception("Post-processing failed for %s", path)

    asyncio.create_task(_post_process())
    return {"status": "created", "path": path}


@mcp.tool()
async def delete(path: str, vault: str | None = None) -> dict:
    """Delete a single note from the knowledge base.

    Args:
        path: Path of the note to delete (e.g., "People/Old Note.md")
        vault: Vault ID (optional, defaults to the default vault)
    """
    check_writable(vault)
    delete_note(path, vault_id=vault)

    async def _post_process():
        try:
            delete_from_index(path, vault_id=vault)
            await run_ob_sync(vault_id=vault)
        except Exception:
            logger.exception("Post-processing failed for delete %s", path)

    asyncio.create_task(_post_process())
    return {"status": "deleted", "path": path}


@mcp.tool()
def reindex(vault: str | None = None) -> dict:
    """Reindex all vault notes into Elasticsearch."""
    return reindex_all(vault_id=vault)
