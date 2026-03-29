import httpx

from app.config import settings
from app.vaults import get_vault


def _client() -> httpx.Client:
    return httpx.Client(base_url=settings.headless_url, timeout=30)


def list_notes(folder: str | None = None, vault_id: str | None = None) -> list[str]:
    """List all markdown files in the vault via headless service."""
    vc = get_vault(vault_id)
    params = {"vault": vc.path}
    if folder:
        params["folder"] = folder
    with _client() as client:
        resp = client.get("/notes/", params=params)
        resp.raise_for_status()
        return resp.json()["notes"]


def list_manifest(vault_id: str | None = None) -> list[dict]:
    """Get path + mtime for all notes (lightweight, no content reading)."""
    vc = get_vault(vault_id)
    with _client() as client:
        resp = client.get("/notes/manifest/", params={"vault": vc.path})
        resp.raise_for_status()
        return resp.json()["notes"]


def read_note(path: str, vault_id: str | None = None) -> dict:
    """Read a note via headless service."""
    vc = get_vault(vault_id)
    with _client() as client:
        resp = client.get(f"/notes/{path}", params={"vault": vc.path})
        if resp.status_code == 404:
            raise FileNotFoundError(f"Note not found: {path}")
        resp.raise_for_status()
        return resp.json()
