from fastmcp import FastMCP

from app.search.client import search_notes, semantic_search
from app.search.indexer import index_note, reindex_all
from app.vault.reader import read_note, list_notes, vault_path
from app.vault.writer import write_note

mcp = FastMCP("Obsidian Knowledge")


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
    base = vault_path()
    return [str(p.relative_to(base)) for p in list_notes(folder)]


@mcp.tool()
def create(path: str, content: str, metadata: dict | None = None) -> dict:
    """Create or update a note in the knowledge base.

    Args:
        path: Path relative to vault root (e.g., "Inbox/my-note.md")
        content: Markdown content for the note
        metadata: Optional frontmatter metadata (tags, source, etc.)
    """
    write_note(path, content, metadata)
    note = read_note(path)
    index_note(note)
    return {"status": "created", "path": path}


@mcp.tool()
def reindex() -> dict:
    """Reindex all vault notes into Elasticsearch."""
    return reindex_all()
