import os

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.search.client import ensure_index
from app.search.indexer import reindex_all
from app.sync import run_ob_sync
from app.vaults import VaultConfig, delete_vault, get_vault, list_vaults, save_vault

router = APIRouter()


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
    create_remote: bool = False


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
    """Full vault setup: create dir, optionally create remote, sync-setup, initial sync, register, create ES index."""
    # 1. Create local directory if it doesn't exist
    os.makedirs(request.local_path, exist_ok=True)

    async with _headless_client(timeout=600) as client:
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

        # 4. Run initial sync to pull down notes
        resp = await client.post("/sync/", params={"sync_path": request.sync_path or request.local_path})
        sync_result = resp.json() if resp.status_code == 200 else {}

    # 5. Register in vaults.json
    config = VaultConfig(
        name=request.name,
        path=request.local_path,
        sync_path=request.sync_path or request.local_path,
        es_index=request.es_index,
        default=False,
        sync_enabled=True,
    )
    save_vault(request.vault_id, config)

    # 6. Create ES index
    ensure_index(vault_id=request.vault_id)

    # 7. Initial reindex
    reindex_result = reindex_all(vault_id=request.vault_id)

    return {
        "status": "ok",
        "vault_id": request.vault_id,
        "sync": sync_result,
        "reindex": reindex_result,
    }


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
