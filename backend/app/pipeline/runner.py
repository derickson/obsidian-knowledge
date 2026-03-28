import logging

from app.search.indexer import index_note
from app.sync import run_ob_sync
from app.vault.reader import read_note

logger = logging.getLogger(__name__)


async def process_note(path: str) -> dict:
    """Post-processing pipeline for a newly created/updated note.

    Steps:
    1. Read and index the note into ES
    2. Sync vault via ob sync
    3. (Future) Cross-link enrichment via Claude API
    """
    note = read_note(path)

    # Step 1: Index into Elasticsearch
    index_note(note)
    logger.info("Indexed note: %s", path)

    # Step 2: Sync to Obsidian cloud
    sync_result = await run_ob_sync()

    # Step 3: Future - cross-linking, tagging, summarization
    # This is where Claude API calls will go to enrich notes
    # with [[wikilinks]] to related content

    return {
        "path": path,
        "indexed": True,
        "synced": sync_result["returncode"] == 0,
    }
