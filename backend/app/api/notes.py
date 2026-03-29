from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.pipeline.runner import process_note
from app.search.client import recent_notes, search_notes, semantic_search
from app.search.indexer import delete_from_index
from app.vault.reader import list_notes, read_note
from app.vault.writer import write_note, delete_note
from app.vaults import VaultReadOnlyError, check_writable

router = APIRouter()


class NoteCreate(BaseModel):
    path: str
    content: str
    metadata: dict | None = None


class SearchQuery(BaseModel):
    query: str
    size: int = 10


@router.post("/")
async def create_note(
    note: NoteCreate, background_tasks: BackgroundTasks, vault: str | None = None
):
    """Create or update a note. Indexes to ES and syncs in the background."""
    try:
        check_writable(vault)
    except VaultReadOnlyError as e:
        raise HTTPException(status_code=403, detail=str(e))
    write_note(note.path, note.content, note.metadata, vault_id=vault)
    background_tasks.add_task(process_note, note.path, vault_id=vault)
    return {"status": "created", "path": note.path}


@router.get("/list/")
async def list_all(vault: str | None = None):
    """List all note paths in the vault."""
    return {"notes": list_notes(vault_id=vault)}


@router.get("/recent/")
async def recent(size: int = 20, vault: str | None = None):
    """Return the most recently modified notes."""
    return {"results": recent_notes(size, vault_id=vault)}


@router.post("/search/")
async def search(query: SearchQuery, vault: str | None = None):
    """Full-text search across indexed notes."""
    return {"results": search_notes(query.query, query.size, vault_id=vault)}


@router.post("/semantic-search/")
async def semantic(query: SearchQuery, vault: str | None = None):
    """Semantic search using Jina embeddings."""
    return {"results": semantic_search(query.query, query.size, vault_id=vault)}


@router.get("/{path:path}")
async def get_note(path: str, vault: str | None = None):
    """Read a note directly from the vault."""
    try:
        return read_note(path, vault_id=vault)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Note not found: {path}")


@router.delete("/{path:path}")
async def remove_note(path: str, vault: str | None = None):
    """Delete a note from the vault."""
    try:
        check_writable(vault)
    except VaultReadOnlyError as e:
        raise HTTPException(status_code=403, detail=str(e))
    try:
        read_note(path, vault_id=vault)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Note not found: {path}")
    delete_note(path, vault_id=vault)
    delete_from_index(path, vault_id=vault)
    return {"status": "deleted", "path": path}
