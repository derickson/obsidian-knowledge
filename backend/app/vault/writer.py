import httpx

from app.config import settings


def _client() -> httpx.Client:
    return httpx.Client(base_url=settings.headless_url, timeout=30)


def write_note(path: str, content: str, metadata: dict | None = None) -> dict:
    """Write a note to the vault via headless service."""
    with _client() as client:
        resp = client.post("/notes/", json={"path": path, "content": content, "metadata": metadata})
        resp.raise_for_status()
        return resp.json()


def delete_note(path: str) -> None:
    """Delete a note from the vault via headless service."""
    with _client() as client:
        resp = client.delete(f"/notes/{path}")
        if resp.status_code == 404:
            raise FileNotFoundError(f"Note not found: {path}")
        resp.raise_for_status()
