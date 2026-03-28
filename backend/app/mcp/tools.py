from fastmcp import FastMCP

from app.config import settings
from app.search.client import search_notes, semantic_search
from app.search.indexer import index_note, reindex_all
from app.sync import run_ob_sync
from app.search.indexer import delete_from_index
from app.vault.reader import read_note, list_notes
from app.vault.writer import write_note, delete_note

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

## Vault organization

- **Root level**: Primary entries on people, concepts, or tools (e.g., `Dave Erickson.md`, `Elasticsearch.md`)
- **Meetings/**: Time-driven meeting notes as `Meetings/YYYY-MM-DD-Meeting-Name.md`
- **Observations/**: Journal entries, thoughts, and general observations as `Observations/YYYY-MM-DD-Topic.md`
- **Content/**: Notes on consumed content (videos, articles, books) as `Content/Title.md`
- **Inbox/**: Staging area for unsorted or auto-ingested notes
- **TestData/**: Reserved for automated tests — do not use

## Daily notes

- Daily notes live in `Observations/` with the naming pattern `YYYY-MM-DD-Daily.md` (e.g., `Observations/2026-03-28-Daily.md`).
- They use the tags `daily` and `observation` in frontmatter.
- A daily note captures the day's plans, reflections, and links to other vault entries (meetings, content, people).
- When the user asks about "today", "yesterday", or a specific date without specifying a note, check the corresponding daily note first.

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
async def delete(path: str) -> dict:
    """Delete a single note from the knowledge base.

    Removes the note from both the vault and the Elasticsearch index,
    then syncs the change to Obsidian cloud.

    Args:
        path: Path of the note to delete (e.g., "People/Old Note.md")
    """
    delete_note(path)
    delete_from_index(path)
    await run_ob_sync()
    return {"status": "deleted", "path": path}


@mcp.tool()
def reindex() -> dict:
    """Reindex all vault notes into Elasticsearch."""
    return reindex_all()
