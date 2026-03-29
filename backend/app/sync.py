import httpx

from app.config import settings
from app.vaults import get_vault


async def run_ob_sync(vault_id: str | None = None) -> dict:
    """Trigger ob sync via the headless service."""
    vc = get_vault(vault_id)
    async with httpx.AsyncClient(base_url=settings.headless_url, timeout=120) as client:
        resp = await client.post("/sync/", params={"sync_path": vc.sync_path})
        resp.raise_for_status()
        return resp.json()
