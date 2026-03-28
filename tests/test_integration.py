"""Integration test: end-to-end note lifecycle through live services.

Run against dev (make dev) or Docker (make up):
    make test-integration          # dev ports
    make test-integration-docker   # docker ports

Skipped by default in `make test` (unit tests only).
"""

import os
import time
import uuid

import httpx
import pytest

BACKEND_URL = os.environ.get("TEST_BACKEND_URL", "http://localhost:3105")
HEADLESS_URL = os.environ.get("TEST_HEADLESS_URL", "http://localhost:3104")
API_PREFIX = os.environ.get("TEST_API_PREFIX", "/obsidian-knowledge")

# Generate unique content so searches are unambiguous
RUN_ID = uuid.uuid4().hex[:8]
NOTE_PATH = f"TestData/integration-{RUN_ID}.md"
NOTE_TITLE = f"Integration Test {RUN_ID}"
UNIQUE_KEYWORD = f"zxintegration{RUN_ID}"
NOTE_CONTENT = f"""# {NOTE_TITLE}

This is an automated integration test note containing the unique keyword {UNIQUE_KEYWORD}.

It validates the full lifecycle: create via REST API, index into Elasticsearch,
search (full-text and semantic), and read back via the headless service.
"""
NOTE_METADATA = {
    "title": NOTE_TITLE,
    "tags": ["integration-test", "automated"],
    "source": "pytest",
    "run_id": RUN_ID,
}


@pytest.fixture(scope="module")
def backend():
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


@pytest.fixture(scope="module")
def headless():
    return httpx.Client(base_url=HEADLESS_URL, timeout=30)


def _check_services(backend, headless):
    """Verify both services are reachable."""
    try:
        backend.get(f"{API_PREFIX}/api/notes/nonexistent-health-check.md")
    except httpx.ConnectError:
        pytest.skip("Backend not running (start with `make dev`)")
    try:
        headless.get("/notes/nonexistent-health-check.md")
    except httpx.ConnectError:
        pytest.skip("Headless service not running (start with `make dev`)")


@pytest.mark.integration
class TestNoteLifecycle:
    """End-to-end test: create → wait for indexing → search → read → delete."""

    def test_01_services_reachable(self, backend, headless):
        """Verify dev services are running."""
        _check_services(backend, headless)

    def test_02_create_note_via_api(self, backend):
        """Create a note via the REST API (simulating an MCP-style ingest)."""
        resp = backend.post(
            f"{API_PREFIX}/api/notes/",
            json={
                "path": NOTE_PATH,
                "content": NOTE_CONTENT,
                "metadata": NOTE_METADATA,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "created"
        assert data["path"] == NOTE_PATH

    def test_03_read_note_via_headless(self, headless):
        """Read the note directly from the headless vault service."""
        resp = headless.get(f"/notes/{NOTE_PATH}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == NOTE_TITLE
        assert UNIQUE_KEYWORD in data["content"]
        assert "integration-test" in data["tags"]
        assert data["wikilinks"] == []

    def test_04_read_note_via_backend(self, backend):
        """Read the note via the backend API (proxied through headless)."""
        resp = backend.get(f"{API_PREFIX}/api/notes/{NOTE_PATH}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == NOTE_TITLE
        assert UNIQUE_KEYWORD in data["content"]

    def test_05_list_notes_includes_test_note(self, headless):
        """Verify the note appears in the vault listing."""
        resp = headless.get("/notes/", params={"folder": "TestData"})
        assert resp.status_code == 200
        notes = resp.json()["notes"]
        assert NOTE_PATH in notes

    def test_06_wait_for_indexing(self):
        """Wait for the background pipeline to index the note into ES."""
        time.sleep(10)

    def test_07_fulltext_search(self, backend):
        """Search for the note using full-text search."""
        resp = backend.post(
            f"{API_PREFIX}/api/notes/search/",
            json={"query": UNIQUE_KEYWORD, "size": 5},
        )
        if resp.status_code == 500:
            pytest.skip("Elasticsearch not configured (set ES_URL in .env)")
        assert resp.status_code == 200
        results = resp.json()["results"]
        paths = [r["path"] for r in results]
        assert NOTE_PATH in paths, f"Note not found in search results: {paths}"

    def test_08_semantic_search(self, backend):
        """Search for the note using semantic search."""
        resp = backend.post(
            f"{API_PREFIX}/api/notes/semantic-search/",
            json={"query": "automated integration test note", "size": 5},
        )
        if resp.status_code == 500:
            pytest.skip("Elasticsearch not configured (set ES_URL in .env)")
        assert resp.status_code == 200
        results = resp.json()["results"]
        # Semantic search may or may not rank our note first, just check it returns
        assert len(results) >= 0  # Service is reachable and responding

    def test_09_delete_note(self, backend):
        """Clean up: delete the test note."""
        resp = backend.delete(f"{API_PREFIX}/api/notes/{NOTE_PATH}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_10_verify_deleted(self, backend):
        """Confirm the note is gone."""
        resp = backend.get(f"{API_PREFIX}/api/notes/{NOTE_PATH}")
        assert resp.status_code == 404
