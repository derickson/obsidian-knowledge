from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.vaults import VaultConfig, delete_vault, get_vault, list_vaults, save_vault

router = APIRouter()


class VaultCreate(BaseModel):
    vault_id: str
    config: VaultConfig


@router.get("/")
async def api_list_vaults():
    """List all configured vaults."""
    vaults = list_vaults()
    return {"vaults": {k: v.model_dump() for k, v in vaults.items()}}


@router.get("/{vault_id}/")
async def api_get_vault(vault_id: str):
    """Get a single vault config."""
    try:
        vc = get_vault(vault_id)
        return vc.model_dump()
    except ValueError:
        raise HTTPException(404, f"Vault not found: {vault_id}")


@router.post("/")
async def api_create_vault(request: VaultCreate):
    """Register a new vault."""
    save_vault(request.vault_id, request.config)
    return {"status": "created", "vault_id": request.vault_id}


@router.delete("/{vault_id}/")
async def api_delete_vault(vault_id: str):
    """Remove a vault registration (does not delete files)."""
    try:
        delete_vault(vault_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"status": "deleted", "vault_id": vault_id}
