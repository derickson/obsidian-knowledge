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
async def api_list_notes(folder: str | None = None, vault: str | None = None):
    """List all notes in the vault."""
    base = vault_path(vault)
    return {"notes": [str(p.relative_to(base)) for p in list_notes(folder, vault)]}


@app.get("/notes/manifest/")
async def api_manifest(vault: str | None = None):
    """Return path and mtime for all notes (lightweight, no content reading)."""
    base = vault_path(vault)
    manifest = []
    for p in list_notes(vault=vault):
        rel = str(p.relative_to(base))
        manifest.append({"path": rel, "last_modified": int(p.stat().st_mtime)})
    return {"notes": manifest}


@app.get("/notes/{path:path}")
async def api_read_note(path: str, vault: str | None = None):
    """Read a note from the vault."""
    try:
        return read_note(path, vault)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Note not found: {path}")


@app.post("/notes/")
async def api_write_note(note: NoteWrite, vault: str | None = None):
    """Write a note to the vault."""
    write_note(note.path, note.content, note.metadata, vault)
    return read_note(note.path, vault)


@app.delete("/notes/{path:path}")
async def api_delete_note(path: str, vault: str | None = None):
    """Delete a note from the vault."""
    try:
        read_note(path, vault)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Note not found: {path}")
    delete_note(path, vault)
    return {"status": "deleted", "path": path}


@app.post("/sync/")
async def api_sync(sync_path: str | None = None):
    """Trigger ob sync."""
    result = await run_ob_sync(sync_path)
    status = "ok" if result["returncode"] == 0 else "error"
    return {"status": status, **result}
