from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.pipeline.runner import process_note
from app.search.client import recent_notes, search_notes, semantic_search
from app.search.indexer import delete_from_index
from app.vault.reader import list_notes, read_note
from app.vault.writer import write_note, delete_note

router = APIRouter()


class NoteCreate(BaseModel):
    path: str
    content: str
    metadata: dict | None = None


class SearchQuery(BaseModel):
    query: str
    size: int = 10


@router.post("/")
async def create_note(note: NoteCreate, background_tasks: BackgroundTasks):
    """Create or update a note. Indexes to ES and syncs in the background."""
    write_note(note.path, note.content, note.metadata)
    background_tasks.add_task(process_note, note.path)
    return {"status": "created", "path": note.path}


@router.get("/list/")
async def list_all():
    """Return all note paths in the vault."""
    return {"notes": list_notes()}


@router.get("/recent/")
async def recent(size: int = 20):
    """Return the most recently modified notes."""
    return {"results": recent_notes(size)}


@router.post("/search/")
async def search(query: SearchQuery):
    """Full-text search across indexed notes."""
    return {"results": search_notes(query.query, query.size)}


@router.post("/semantic-search/")
async def semantic(query: SearchQuery):
    """Semantic search using Jina embeddings."""
    return {"results": semantic_search(query.query, query.size)}


@router.get("/{path:path}")
async def get_note(path: str):
    """Read a note directly from the vault."""
    try:
        return read_note(path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Note not found: {path}")


@router.delete("/{path:path}")
async def remove_note(path: str):
    """Delete a note from the vault."""
    try:
        read_note(path)  # Verify it exists
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Note not found: {path}")
    delete_note(path)
    delete_from_index(path)
    return {"status": "deleted", "path": path}
