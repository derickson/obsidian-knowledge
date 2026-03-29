import json
from pathlib import Path

from pydantic import BaseModel

# Resolve vaults.json relative to the project root (3 levels up from this file)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
VAULTS_FILE = _PROJECT_ROOT / "vaults.json"


class VaultConfig(BaseModel):
    name: str
    path: str
    sync_path: str = ""
    es_index: str
    default: bool = False
    sync_enabled: bool = True


def load_vaults() -> dict[str, VaultConfig]:
    """Load all vault configs from vaults.json."""
    if not VAULTS_FILE.exists():
        return {}
    data = json.loads(VAULTS_FILE.read_text())
    return {k: VaultConfig(**v) for k, v in data.get("vaults", {}).items()}


def get_vault(vault_id: str | None = None) -> VaultConfig:
    """Get a vault config by ID. None returns the default vault."""
    vaults = load_vaults()
    if not vaults:
        raise ValueError("No vaults configured in vaults.json")

    if vault_id is None:
        for vid, vc in vaults.items():
            if vc.default:
                return vc
        # No default marked — return first vault
        return next(iter(vaults.values()))

    if vault_id not in vaults:
        raise ValueError(f"Vault not found: {vault_id}")
    return vaults[vault_id]


def get_default_vault_id() -> str:
    """Return the ID of the default vault."""
    vaults = load_vaults()
    for vid, vc in vaults.items():
        if vc.default:
            return vid
    return next(iter(vaults.keys()))


def list_vaults() -> dict[str, VaultConfig]:
    """Return all vault configs."""
    return load_vaults()


def save_vault(vault_id: str, config: VaultConfig) -> None:
    """Add or update a vault in vaults.json."""
    data = json.loads(VAULTS_FILE.read_text()) if VAULTS_FILE.exists() else {"vaults": {}}
    data["vaults"][vault_id] = config.model_dump()
    VAULTS_FILE.write_text(json.dumps(data, indent=2) + "\n")


def delete_vault(vault_id: str) -> None:
    """Remove a vault from vaults.json."""
    data = json.loads(VAULTS_FILE.read_text()) if VAULTS_FILE.exists() else {"vaults": {}}
    if vault_id not in data.get("vaults", {}):
        raise ValueError(f"Vault not found: {vault_id}")
    if data["vaults"][vault_id].get("default"):
        raise ValueError("Cannot delete the default vault")
    del data["vaults"][vault_id]
    VAULTS_FILE.write_text(json.dumps(data, indent=2) + "\n")
