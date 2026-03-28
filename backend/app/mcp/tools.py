from fastmcp import FastMCP

from app.config import settings
from app.search.client import search_notes, semantic_search
from app.search.indexer import index_note, reindex_all
from app.sync import run_ob_sync
from app.vault.reader import read_note, list_notes
from app.vault.writer import write_note

mcp_auth = None
if settings.mcp_api_key:
    from fastmcp.server.auth import DebugTokenVerifier

    mcp_auth = DebugTokenVerifier(
        validate=lambda token: token == settings.mcp_api_key,
        client_id="mcp-client",
        scopes=[],
    )

mcp = FastMCP("Obsidian Knowledge", auth=mcp_auth)


@mcp.tool()
def search(query: str, size: int = 10) -> list[dict]:
    """Full-text search across all notes in the knowledge base."""
    return search_notes(query, size)


@mcp.tool()
def semantic(query: str, size: int = 10) -> list[dict]:
    """Semantic search across notes using Jina embeddings."""
    return semantic_search(query, size)


@mcp.tool()
def read(path: str) -> dict:
    """Read a specific note by its path relative to the vault root."""
    return read_note(path)


@mcp.tool()
def list_all_notes(folder: str | None = None) -> list[str]:
    """List all notes in the vault, optionally filtered by folder."""
    return list_notes(folder)


@mcp.tool()
async def create(path: str, content: str, metadata: dict | None = None) -> dict:
    """Create or update a note in the knowledge base.

    Args:
        path: Path relative to vault root (e.g., "Inbox/my-note.md")
        content: Markdown content for the note
        metadata: Optional frontmatter metadata (tags, source, etc.)
    """
    write_note(path, content, metadata)
    note = read_note(path)
    index_note(note)
    await run_ob_sync()
    return {"status": "created", "path": path}


@mcp.tool()
def reindex() -> dict:
    """Reindex all vault notes into Elasticsearch."""
    return reindex_all()
