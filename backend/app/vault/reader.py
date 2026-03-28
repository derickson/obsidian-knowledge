import httpx

from app.config import settings


def _client() -> httpx.Client:
    return httpx.Client(base_url=settings.headless_url, timeout=30)


def list_notes(folder: str | None = None) -> list[str]:
    """List all markdown files in the vault via headless service."""
    params = {"folder": folder} if folder else {}
    with _client() as client:
        resp = client.get("/notes/", params=params)
        resp.raise_for_status()
        return resp.json()["notes"]


def list_manifest() -> list[dict]:
    """Get path + mtime for all notes (lightweight, no content reading)."""
    with _client() as client:
        resp = client.get("/notes/manifest/")
        resp.raise_for_status()
        return resp.json()["notes"]


def read_note(path: str) -> dict:
    """Read a note via headless service."""
    with _client() as client:
        resp = client.get(f"/notes/{path}")
        if resp.status_code == 404:
            raise FileNotFoundError(f"Note not found: {path}")
        resp.raise_for_status()
        return resp.json()
