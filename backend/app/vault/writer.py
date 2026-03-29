import httpx

from app.config import settings
from app.vaults import get_vault


def _client() -> httpx.Client:
    return httpx.Client(base_url=settings.headless_url, timeout=30)


def write_note(
    path: str, content: str, metadata: dict | None = None, vault_id: str | None = None
) -> dict:
    """Write a note to the vault via headless service."""
    vc = get_vault(vault_id)
    with _client() as client:
        resp = client.post(
            "/notes/",
            json={"path": path, "content": content, "metadata": metadata},
            params={"vault": vc.path},
        )
        resp.raise_for_status()
        return resp.json()


def delete_note(path: str, vault_id: str | None = None) -> None:
    """Delete a note from the vault via headless service."""
    vc = get_vault(vault_id)
    with _client() as client:
        resp = client.delete(f"/notes/{path}", params={"vault": vc.path})
        if resp.status_code == 404:
            raise FileNotFoundError(f"Note not found: {path}")
        resp.raise_for_status()
