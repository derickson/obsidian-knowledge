from pathlib import Path

from elasticsearch.helpers import bulk

from app.config import settings
from app.search.client import es_client, ensure_index
from app.vault.reader import list_notes, read_note


def index_note(note: dict) -> None:
    """Index a single note into Elasticsearch."""
    ensure_index()
    doc = {
        "path": note["path"],
        "folder": str(Path(note["path"]).parent),
        "title": note["title"],
        "content": note["content"],
        "content_semantic": note["content"],
        "tags": note["tags"],
        "wikilinks": note["wikilinks"],
        "frontmatter": note["metadata"],
        "content_hash": note["content_hash"],
        "last_modified": note["last_modified"],
    }
    es_client.index(index=settings.es_index, id=note["path"], document=doc)


def reindex_all() -> dict:
    """Full reindex: sync all vault notes to Elasticsearch."""
    ensure_index()

    # Get current hashes from ES
    existing = _get_existing_hashes()

    note_paths = list_notes()
    indexed, skipped, deleted = 0, 0, 0

    actions = []
    seen_paths = set()

    for rel_path in note_paths:
        seen_paths.add(rel_path)

        note = read_note(rel_path)

        # Skip if content unchanged
        if rel_path in existing and existing[rel_path] == note["content_hash"]:
            skipped += 1
            continue

        actions.append({
            "_index": settings.es_index,
            "_id": rel_path,
            "_source": {
                "path": rel_path,
                "folder": str(Path(rel_path).parent),
                "title": note["title"],
                "content": note["content"],
                "content_semantic": note["content"],
                "tags": note["tags"],
                "wikilinks": note["wikilinks"],
                "frontmatter": note["metadata"],
                "content_hash": note["content_hash"],
                "last_modified": note["last_modified"],
            },
        })
        indexed += 1

    if actions:
        bulk(es_client, actions)

    # Delete docs for notes that no longer exist
    for path in existing:
        if path not in seen_paths:
            es_client.delete(index=settings.es_index, id=path, ignore=[404])
            deleted += 1

    return {"indexed": indexed, "skipped": skipped, "deleted": deleted}


def _get_existing_hashes() -> dict[str, str]:
    """Get path -> content_hash mapping from ES for change detection."""
    hashes = {}
    try:
        resp = es_client.search(
            index=settings.es_index,
            query={"match_all": {}},
            _source=["path", "content_hash"],
            size=10000,
        )
        for hit in resp["hits"]["hits"]:
            hashes[hit["_source"]["path"]] = hit["_source"]["content_hash"]
    except Exception:
        pass
    return hashes
