from elasticapm.contrib.starlette import ElasticAPM, make_apm_client
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.sync import run_ob_sync
from app.vault.reader import list_notes, read_note, vault_path
from app.vault.writer import delete_note, write_note

app = FastAPI(title="Obsidian Headless", version="0.1.0")

apm_client = make_apm_client({"SERVICE_NAME": "obsidian-knowledge-headless"})
app.add_middleware(ElasticAPM, client=apm_client)


class NoteWrite(BaseModel):
    path: str
    content: str
    metadata: dict | None = None


@app.get("/notes/")
async def api_list_notes(folder: str | None = None):
    """List all notes in the vault."""
    base = vault_path()
    return {"notes": [str(p.relative_to(base)) for p in list_notes(folder)]}


@app.get("/notes/manifest/")
async def api_manifest():
    """Return path and mtime for all notes (lightweight, no content reading)."""
    base = vault_path()
    manifest = []
    for p in list_notes():
        rel = str(p.relative_to(base))
        manifest.append({"path": rel, "last_modified": int(p.stat().st_mtime)})
    return {"notes": manifest}


@app.get("/notes/{path:path}")
async def api_read_note(path: str):
    """Read a note from the vault."""
    try:
        return read_note(path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Note not found: {path}")


@app.post("/notes/")
async def api_write_note(note: NoteWrite):
    """Write a note to the vault."""
    write_note(note.path, note.content, note.metadata)
    return read_note(note.path)


@app.delete("/notes/{path:path}")
async def api_delete_note(path: str):
    """Delete a note from the vault."""
    try:
        read_note(path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Note not found: {path}")
    delete_note(path)
    return {"status": "deleted", "path": path}


@app.post("/sync/")
async def api_sync():
    """Trigger ob sync."""
    result = await run_ob_sync()
    status = "ok" if result["returncode"] == 0 else "error"
    return {"status": status, **result}
