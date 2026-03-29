from elasticsearch import Elasticsearch

from app.config import settings
from app.vaults import get_vault

_es_client: Elasticsearch | None = None


def get_es_client() -> Elasticsearch:
    global _es_client
    if _es_client is None:
        _es_client = Elasticsearch(settings.es_url, api_key=settings.es_api_key)
    return _es_client


# For backwards compat — property-like access via module attribute
class _ESProxy:
    """Lazy proxy so ES client isn't created at import time."""

    def __getattr__(self, name):
        return getattr(get_es_client(), name)


es_client = _ESProxy()


def _index_name(vault_id: str | None = None) -> str:
    return get_vault(vault_id).es_index


def ensure_index(vault_id: str | None = None):
    """Create the index with mappings if it doesn't exist."""
    index = _index_name(vault_id)
    client = get_es_client()
    if client.indices.exists(index=index):
        return

    client.indices.create(
        index=index,
        mappings={
            "properties": {
                "path": {"type": "keyword"},
                "folder": {"type": "keyword"},
                "title": {"type": "text"},
                "content": {"type": "text"},
                "content_semantic": {
                    "type": "semantic_text",
                    "inference_id": settings.es_inference_id,
                },
                "tags": {"type": "keyword"},
                "wikilinks": {"type": "keyword"},
                "frontmatter": {"type": "object", "dynamic": True},
                "content_hash": {"type": "keyword"},
                "last_modified": {"type": "date", "format": "epoch_second"},
            }
        },
    )


def recent_notes(size: int = 20, vault_id: str | None = None) -> list[dict]:
    """Return the most recently modified notes."""
    index = _index_name(vault_id)
    client = get_es_client()
    try:
        resp = client.search(
            index=index,
            query={"match_all": {}},
            sort=[{"last_modified": {"order": "desc"}}],
            size=size,
        )
        return [hit["_source"] for hit in resp["hits"]["hits"]]
    except Exception:
        return []


def search_notes(query: str, size: int = 10, vault_id: str | None = None) -> list[dict]:
    """Full-text search across notes."""
    index = _index_name(vault_id)
    client = get_es_client()
    resp = client.search(
        index=index,
        query={"multi_match": {"query": query, "fields": ["title^2", "content", "tags^3"]}},
        size=size,
    )
    return [hit["_source"] | {"score": hit["_score"]} for hit in resp["hits"]["hits"]]


def semantic_search(query: str, size: int = 10, vault_id: str | None = None) -> list[dict]:
    """Hybrid search: linear fusion of keyword BM25 and semantic vector search."""
    index = _index_name(vault_id)
    client = get_es_client()
    resp = client.search(
        index=index,
        retriever={
            "linear": {
                "retrievers": [
                    {
                        "retriever": {
                            "standard": {
                                "query": {
                                    "multi_match": {
                                        "query": query,
                                        "fields": ["title^2", "content", "tags^3"],
                                    }
                                }
                            }
                        },
                        "weight": 0.3,
                    },
                    {
                        "retriever": {
                            "standard": {
                                "query": {
                                    "semantic": {
                                        "field": "content_semantic",
                                        "query": query,
                                    }
                                }
                            }
                        },
                        "weight": 0.7,
                    },
                ],
                "rank_window_size": max(size, 100),
            }
        },
        size=size,
    )
    return [hit["_source"] | {"score": hit["_score"]} for hit in resp["hits"]["hits"]]
