from pathlib import Path

from elasticsearch.helpers import bulk

from app.search.client import es_client, ensure_index
from app.vault.reader import list_manifest, read_note
from app.vaults import get_vault


def delete_from_index(path: str, vault_id: str | None = None) -> None:
    """Delete a single note from the Elasticsearch index."""
    index = get_vault(vault_id).es_index
    es_client.delete(index=index, id=path, ignore=[404])


def index_note(note: dict, vault_id: str | None = None) -> None:
    """Index a single note into Elasticsearch."""
    index = get_vault(vault_id).es_index
    ensure_index(vault_id)
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
    es_client.index(index=index, id=note["path"], document=doc)


def reindex_all(vault_id: str | None = None) -> dict:
    """Incremental reindex: only read and index notes that have changed."""
    vc = get_vault(vault_id)
    ensure_index(vault_id)

    existing = _get_existing_state(vault_id)
    manifest = list_manifest(vault_id)

    indexed, skipped, deleted = 0, 0, 0
    actions = []
    seen_paths = set()

    for entry in manifest:
        rel_path = entry["path"]
        vault_mtime = entry["last_modified"]
        seen_paths.add(rel_path)

        if rel_path in existing and existing[rel_path]["last_modified"] == vault_mtime:
            skipped += 1
            continue

        note = read_note(rel_path, vault_id=vault_id)

        if rel_path in existing and existing[rel_path]["content_hash"] == note["content_hash"]:
            skipped += 1
            continue

        actions.append({
            "_index": vc.es_index,
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

    for path in existing:
        if path not in seen_paths:
            es_client.delete(index=vc.es_index, id=path, ignore=[404])
            deleted += 1

    return {"indexed": indexed, "skipped": skipped, "deleted": deleted}


def _get_existing_state(vault_id: str | None = None) -> dict[str, dict]:
    """Get path -> {content_hash, last_modified} from ES for change detection."""
    index = get_vault(vault_id).es_index
    state = {}
    try:
        resp = es_client.search(
            index=index,
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
