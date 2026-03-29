import asyncio
import logging
import re

from app.config import settings

logger = logging.getLogger(__name__)


async def _run_ob(*args: str, timeout: int = 30) -> dict:
    """Run an ob CLI command and return stdout/stderr/returncode."""
    proc = await asyncio.create_subprocess_exec(
        "ob", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    return {
        "returncode": proc.returncode,
        "stdout": stdout.decode().strip(),
        "stderr": stderr.decode().strip(),
    }


async def run_ob_sync(sync_path: str | None = None) -> dict:
    """Run `ob sync` to sync vault with Obsidian cloud."""
    path = sync_path or settings.vault_sync_path or settings.vault_path
    result = await _run_ob("sync", "--path", path, timeout=120)
    if result["returncode"] != 0:
        logger.error("ob sync failed: %s", result["stderr"])
    else:
        logger.info("ob sync completed successfully")
    return result


async def list_remote_vaults() -> list[dict]:
    """List available remote Obsidian vaults."""
    result = await _run_ob("sync-list-remote")
    if result["returncode"] != 0:
        return []
    vaults = []
    for line in result["stdout"].splitlines():
        # Format: "  <id>  "<name>"  (<region>)"
        match = re.match(r'\s+(\S+)\s+"([^"]+)"\s+\(([^)]+)\)', line)
        if match:
            vaults.append({
                "id": match.group(1),
                "name": match.group(2),
                "region": match.group(3),
            })
    return vaults


async def list_local_vaults() -> list[dict]:
    """List locally configured vault syncs."""
    result = await _run_ob("sync-list-local")
    if result["returncode"] != 0:
        return []
    vaults = []
    current = None
    for line in result["stdout"].splitlines():
        id_match = re.match(r'\s+([a-f0-9]{32})\s*$', line)
        if id_match:
            current = {"id": id_match.group(1)}
            vaults.append(current)
            continue
        if current:
            path_match = re.match(r'\s+Path:\s+(.+)', line)
            if path_match:
                current["path"] = path_match.group(1)
            host_match = re.match(r'\s+Host:\s+(.+)', line)
            if host_match:
                current["host"] = host_match.group(1)
    return vaults


async def create_remote_vault(name: str) -> dict:
    """Create a new remote Obsidian vault."""
    return await _run_ob("sync-create-remote", "--name", name)


async def setup_sync(vault_name: str, local_path: str) -> dict:
    """Set up sync from a local path to a remote vault."""
    return await _run_ob("sync-setup", "--vault", vault_name, "--path", local_path)


async def sync_status(path: str) -> dict:
    """Get sync status for a vault."""
    result = await _run_ob("sync-status", "--path", path)
    if result["returncode"] != 0:
        return {"status": "not configured", **result}
    # Parse key-value pairs from output
    config = {}
    for line in result["stdout"].splitlines():
        kv_match = re.match(r'\s+(.+?):\s+(.+)', line)
        if kv_match:
            key = kv_match.group(1).strip().lower().replace(" ", "_")
            config[key] = kv_match.group(2).strip()
    return {"status": "configured", "config": config}
