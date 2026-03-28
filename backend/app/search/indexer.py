from pathlib import Path

from elasticsearch.helpers import bulk

from app.config import settings
from app.search.client import es_client, ensure_index
from app.vault.reader import list_manifest, read_note


def delete_from_index(path: str) -> None:
    """Delete a single note from the Elasticsearch index."""
    es_client.delete(index=settings.es_index, id=path, ignore=[404])


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
        "last_modified": int(note["last_modified"]),
    }
    es_client.index(index=settings.es_index, id=note["path"], document=doc)


def reindex_all() -> dict:
    """Incremental reindex: only read and index notes that have changed.

    Uses file mtime from the vault manifest to skip unchanged files.
    Only files whose mtime differs from ES last_modified are fully read
    and content-hashed. This avoids N HTTP reads on every sync.
    """
    ensure_index()

    existing = _get_existing_state()
    manifest = list_manifest()

    indexed, skipped, deleted = 0, 0, 0
    actions = []
    seen_paths = set()

    for entry in manifest:
        rel_path = entry["path"]
        vault_mtime = entry["last_modified"]
        seen_paths.add(rel_path)

        # Skip if mtime hasn't changed — file is untouched
        if rel_path in existing and existing[rel_path]["last_modified"] == vault_mtime:
            skipped += 1
            continue

        # mtime changed or new file — read full content and check hash
        note = read_note(rel_path)

        if rel_path in existing and existing[rel_path]["content_hash"] == note["content_hash"]:
            # mtime changed but content identical (e.g., touch or metadata-only change)
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
                "last_modified": int(note["last_modified"]),
            },
        })
        indexed += 1

    if actions:
        bulk(es_client, actions)

    # Delete docs for notes that no longer exist in the vault
    for path in existing:
        if path not in seen_paths:
            es_client.delete(index=settings.es_index, id=path, ignore=[404])
            deleted += 1

    return {"indexed": indexed, "skipped": skipped, "deleted": deleted}


def _get_existing_state() -> dict[str, dict]:
    """Get path -> {content_hash, last_modified} from ES for change detection."""
    state = {}
    try:
        resp = es_client.search(
            index=settings.es_index,
            query={"match_all": {}},
            _source=["path", "content_hash", "last_modified"],
            size=10000,
        )
        for hit in resp["hits"]["hits"]:
            src = hit["_source"]
            state[src["path"]] = {
                "content_hash": src["content_hash"],
                "last_modified": src.get("last_modified", 0),
            }
    except Exception:
        pass
    return state
