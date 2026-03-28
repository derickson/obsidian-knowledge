from fastapi import APIRouter

from app.search.indexer import reindex_all
from app.sync import run_ob_sync

router = APIRouter()


@router.post("/reindex")
async def reindex():
    """Full reindex of all vault notes into Elasticsearch."""
    result = reindex_all()
    return {"status": "ok", **result}


@router.post("/sync")
async def sync():
    """Trigger an ob sync."""
    result = await run_ob_sync()
    return {"status": "ok" if result["returncode"] == 0 else "error", **result}
