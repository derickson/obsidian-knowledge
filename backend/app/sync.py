import asyncio
import logging

logger = logging.getLogger(__name__)


async def run_ob_sync() -> dict:
    """Run `ob sync` to sync vault with Obsidian cloud."""
    proc = await asyncio.create_subprocess_exec(
        "ob", "sync",
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
