from elasticsearch import Elasticsearch

from app.config import settings

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


def ensure_index():
    """Create the index with mappings if it doesn't exist."""
    client = get_es_client()
    if client.indices.exists(index=settings.es_index):
        return

    client.indices.create(
        index=settings.es_index,
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


def search_notes(query: str, size: int = 10) -> list[dict]:
    """Full-text search across notes."""
    client = get_es_client()
    resp = client.search(
        index=settings.es_index,
        query={"multi_match": {"query": query, "fields": ["title^2", "content", "tags^3"]}},
        size=size,
    )
    return [hit["_source"] | {"score": hit["_score"]} for hit in resp["hits"]["hits"]]


def semantic_search(query: str, size: int = 10) -> list[dict]:
    """Hybrid search: linear fusion of keyword BM25 and semantic vector search."""
    client = get_es_client()
    resp = client.search(
        index=settings.es_index,
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
            }
        },
        size=size,
    )
    return [hit["_source"] | {"score": hit["_score"]} for hit in resp["hits"]["hits"]]
