import asyncio
import logging

from app.config import settings

logger = logging.getLogger(__name__)


async def run_ob_sync(sync_path: str | None = None) -> dict:
    """Run `ob sync` to sync vault with Obsidian cloud."""
    path = sync_path or settings.vault_sync_path or settings.vault_path
    proc = await asyncio.create_subprocess_exec(
        "ob", "sync",
        "--path", path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    result = {
        "returncode": proc.returncode,
        "stdout": stdout.decode().strip(),
        "stderr": stderr.decode().strip(),
    }

    if proc.returncode != 0:
        logger.error("ob sync failed: %s", result["stderr"])
    else:
        logger.info("ob sync completed successfully")

    return result
