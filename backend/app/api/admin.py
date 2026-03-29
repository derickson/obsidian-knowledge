from fastapi import APIRouter

from app.search.indexer import reindex_all
from app.sync import run_ob_sync

router = APIRouter()


@router.post("/reindex/")
async def reindex(vault: str | None = None):
    """Full reindex of all vault notes into Elasticsearch."""
    result = reindex_all(vault_id=vault)
    return {"status": "ok", **result}


@router.post("/sync/")
async def sync(vault: str | None = None):
    """Trigger an ob sync."""
    result = await run_ob_sync(vault_id=vault)
    return {"status": "ok" if result["returncode"] == 0 else "error", **result}
