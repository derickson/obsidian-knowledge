import asyncio
import logging
import os
import uuid

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.search.client import ensure_index
from app.search.indexer import reindex_all
from app.sync import run_ob_sync
from app.vaults import VaultConfig, delete_vault, get_vault, list_vaults, save_vault

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory job tracker for async setup operations
_setup_jobs: dict[str, dict] = {}


def _headless_client(timeout: int = 60) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=settings.headless_url, timeout=timeout)


class VaultCreate(BaseModel):
    vault_id: str
    config: VaultConfig


class VaultSetup(BaseModel):
    vault_id: str
    name: str
    remote_vault_name: str
    local_path: str
    sync_path: str
    es_index: str
    password: str
    read_only: bool = False
    create_remote: bool = False


async def _get_file_count(vault_path: str) -> int:
    """Get current file count from headless service for progress tracking."""
    try:
        async with _headless_client(timeout=5) as client:
            resp = await client.get("/notes/count/", params={"vault": vault_path})
            if resp.status_code == 200:
                return resp.json().get("count", 0)
    except Exception:
        pass
    return 0


async def _setup_background(job_id: str, vault_id: str, vault_path: str):
    """Background task: sync + reindex with progress tracking."""
    job = _setup_jobs[job_id]
    try:
        # Step 1: Initial sync (the slow step)
        job.update(status="syncing", step="Syncing notes from Obsidian cloud...")

        sync_result = await run_ob_sync(vault_id=vault_id)

        if sync_result.get("returncode") != 0:
            job.update(
                status="error",
                step="Sync failed",
                error=sync_result.get("stderr", "Unknown sync error"),
            )
            return

        # Update file count after sync completes
        job["files_synced"] = await _get_file_count(vault_path)

        # Step 2: Reindex into ES
        job.update(status="reindexing", step="Indexing notes into Elasticsearch...")
        reindex_result = await asyncio.to_thread(reindex_all, vault_id=vault_id)

        job.update(
            status="completed",
            step="Done",
            reindex=reindex_result,
            files_synced=await _get_file_count(vault_path),
        )
    except Exception as e:
        logger.error("Setup background task failed for %s: %s", vault_id, e)
        job.update(status="error", step="Failed", error=str(e))


@router.get("/")
async def api_list_vaults():
    """List all configured vaults."""
    vaults = list_vaults()
    return {"vaults": {k: v.model_dump() for k, v in vaults.items()}}


@router.get("/remote/")
async def api_list_remote():
    """List available remote Obsidian vaults."""
    async with _headless_client() as client:
        resp = await client.get("/sync/list-remote/")
        resp.raise_for_status()
        return resp.json()


@router.get("/local/")
async def api_list_local():
    """List locally configured vault syncs."""
    async with _headless_client() as client:
        resp = await client.get("/sync/list-local/")
        resp.raise_for_status()
        return resp.json()


@router.post("/setup/")
async def api_setup_vault(request: VaultSetup):
    """Start vault setup. Fast steps run synchronously, slow steps (sync + reindex) run in background."""
    # 1. Create local directory
    os.makedirs(request.local_path, exist_ok=True)

    async with _headless_client(timeout=120) as client:
        # 2. Create remote vault if requested
        if request.create_remote:
            resp = await client.post(
                "/sync/create-remote/",
                json={"name": request.remote_vault_name, "password": request.password},
            )
            if resp.status_code != 200 or resp.json().get("status") != "ok":
                return {"status": "error", "step": "create-remote", **resp.json()}

        # 3. Set up sync (links local path to remote vault)
        resp = await client.post(
            "/sync/setup/",
            json={
                "vault_name": request.remote_vault_name,
                "local_path": request.local_path,
                "password": request.password,
            },
        )
        if resp.status_code != 200 or resp.json().get("status") != "ok":
            return {"status": "error", "step": "sync-setup", **resp.json()}

    # 4. Register in vaults.json
    config = VaultConfig(
        name=request.name,
        path=request.local_path,
        sync_path=request.sync_path or request.local_path,
        es_index=request.es_index,
        default=False,
        sync_enabled=True,
        read_only=request.read_only,
    )
    save_vault(request.vault_id, config)

    # 5. Create ES index
    ensure_index(vault_id=request.vault_id)

    # 6. Start background sync + reindex
    job_id = uuid.uuid4().hex[:12]
    _setup_jobs[job_id] = {
        "status": "started",
        "step": "Starting sync...",
        "vault_id": request.vault_id,
        "files_synced": 0,
        "error": None,
        "reindex": None,
    }
    asyncio.create_task(_setup_background(job_id, request.vault_id, request.local_path))

    return {"status": "started", "job_id": job_id, "vault_id": request.vault_id}


@router.get("/setup/status/{job_id}/")
async def api_setup_status(job_id: str):
    """Poll setup job progress."""
    if job_id not in _setup_jobs:
        raise HTTPException(404, f"Setup job not found: {job_id}")

    job = _setup_jobs[job_id]

    # If syncing, poll current file count for live progress
    if job["status"] == "syncing":
        vc = get_vault(job["vault_id"])
        job["files_synced"] = await _get_file_count(vc.path)

    return job


@router.post("/")
async def api_create_vault(request: VaultCreate):
    """Register a new vault (manual config, no sync setup)."""
    save_vault(request.vault_id, request.config)
    return {"status": "created", "vault_id": request.vault_id}


# Per-vault action routes — must come before /{vault_id}/ catch-all

@router.get("/{vault_id}/status/")
async def api_vault_status(vault_id: str):
    """Get sync status for a vault."""
    try:
        vc = get_vault(vault_id)
    except ValueError:
        raise HTTPException(404, f"Vault not found: {vault_id}")
    async with _headless_client() as client:
        resp = await client.get("/sync/status/", params={"path": vc.sync_path or vc.path})
        resp.raise_for_status()
        return resp.json()


@router.post("/{vault_id}/sync/")
async def api_vault_sync(vault_id: str):
    """Trigger sync for a specific vault."""
    try:
        get_vault(vault_id)
    except ValueError:
        raise HTTPException(404, f"Vault not found: {vault_id}")
    result = await run_ob_sync(vault_id=vault_id)
    return {"status": "ok" if result.get("returncode") == 0 else "error", **result}


@router.post("/{vault_id}/reindex/")
async def api_vault_reindex(vault_id: str):
    """Trigger ES reindex for a specific vault."""
    try:
        get_vault(vault_id)
    except ValueError:
        raise HTTPException(404, f"Vault not found: {vault_id}")
    result = reindex_all(vault_id=vault_id)
    return {"status": "ok", **result}


@router.put("/{vault_id}/")
async def api_update_vault(vault_id: str, config: VaultConfig):
    """Update a vault's configuration."""
    try:
        get_vault(vault_id)
    except ValueError:
        raise HTTPException(404, f"Vault not found: {vault_id}")
    save_vault(vault_id, config)
    return {"status": "updated", "vault_id": vault_id}


@router.get("/{vault_id}/")
async def api_get_vault(vault_id: str):
    """Get a single vault config."""
    try:
        vc = get_vault(vault_id)
        return vc.model_dump()
    except ValueError:
        raise HTTPException(404, f"Vault not found: {vault_id}")


@router.delete("/{vault_id}/")
async def api_delete_vault(vault_id: str):
    """Remove a vault registration (does not delete files)."""
    try:
        delete_vault(vault_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"status": "deleted", "vault_id": vault_id}
