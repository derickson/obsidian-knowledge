import httpx

from app.config import settings


async def run_ob_sync() -> dict:
    """Trigger ob sync via the headless service."""
    async with httpx.AsyncClient(base_url=settings.headless_url, timeout=120) as client:
        resp = await client.post("/sync/")
        resp.raise_for_status()
        return resp.json()
