import logging

from app.search.indexer import index_note
from app.sync import run_ob_sync
from app.vault.reader import read_note

logger = logging.getLogger(__name__)


async def process_note(path: str, vault_id: str | None = None) -> dict:
    """Post-processing pipeline for a newly created/updated note."""
    note = read_note(path, vault_id=vault_id)

    index_note(note, vault_id=vault_id)
    logger.info("Indexed note: %s", path)

    sync_result = await run_ob_sync(vault_id=vault_id)

    return {
        "path": path,
        "indexed": True,
        "synced": sync_result["returncode"] == 0,
    }
