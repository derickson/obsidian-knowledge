import os
import tempfile
from unittest.mock import MagicMock

import pytest

# Set env vars before any app imports
os.environ.setdefault("VAULT_PATH", tempfile.mkdtemp())
os.environ.setdefault("ES_URL", "")
os.environ.setdefault("ES_API_KEY", "")
os.environ.setdefault("HEADLESS_URL", "http://localhost:8100")
os.environ.setdefault("MCP_API_KEY", "")


SAMPLE_NOTE = {
    "path": "test-note.md",
    "title": "Test Note",
    "content": "# Test Note\n\nSome content with a [[wikilink]] and [[another|display text]].",
    "metadata": {"title": "Test Note", "tags": ["testing"]},
    "tags": ["testing"],
    "wikilinks": ["wikilink", "another"],
    "content_hash": "abc123",
    "last_modified": 1700000000.0,
}

SAMPLE_NOTES_LIST = ["note-a.md", "Inbox/note-b.md", "Inbox/note-c.md"]

SAMPLE_MANIFEST = [
    {"path": "note-a.md", "last_modified": 1700000000},
    {"path": "Inbox/note-b.md", "last_modified": 1700000000},
    {"path": "Inbox/note-c.md", "last_modified": 1700000000},
]


@pytest.fixture(autouse=True)
def vault_dir(tmp_path):
    """Provide a fresh temporary vault directory for headless-level tests."""
    return tmp_path


@pytest.fixture(autouse=True)
def mock_es(monkeypatch):
    """Mock the ES client globally so no test hits a real cluster."""
    mock = MagicMock()
    mock.indices.exists.return_value = True
    mock.search.return_value = {"hits": {"hits": []}}
    monkeypatch.setattr("app.search.client._es_client", mock)
    monkeypatch.setattr("app.search.client.get_es_client", lambda: mock)
    return mock


@pytest.fixture
def mock_headless(monkeypatch):
    """Mock the headless HTTP client calls everywhere they're used."""
    mock_read = MagicMock(return_value=SAMPLE_NOTE)
    mock_list = MagicMock(return_value=SAMPLE_NOTES_LIST)
    mock_manifest = MagicMock(return_value=SAMPLE_MANIFEST)
    mock_write = MagicMock(return_value=SAMPLE_NOTE)
    mock_delete = MagicMock()
    mock_sync = MagicMock(
        return_value={"status": "ok", "returncode": 0, "stdout": "", "stderr": ""}
    )

    # Patch in every module that imports these functions
    for mod in [
        "app.vault.reader",
        "app.api.notes",
        "app.mcp.tools",
        "app.search.indexer",
        "app.pipeline.runner",
    ]:
        try:
            monkeypatch.setattr(f"{mod}.read_note", mock_read)
        except AttributeError:
            pass
        try:
            monkeypatch.setattr(f"{mod}.list_notes", mock_list)
        except AttributeError:
            pass
        try:
            monkeypatch.setattr(f"{mod}.list_manifest", mock_manifest)
        except AttributeError:
            pass

    mock_delete_index = MagicMock()

    for mod in ["app.vault.writer", "app.api.notes"]:
        try:
            monkeypatch.setattr(f"{mod}.write_note", mock_write)
        except AttributeError:
            pass
        try:
            monkeypatch.setattr(f"{mod}.delete_note", mock_delete)
        except AttributeError:
            pass

    for mod in ["app.search.indexer", "app.api.notes"]:
        try:
            monkeypatch.setattr(f"{mod}.delete_from_index", mock_delete_index)
        except AttributeError:
            pass

    async def async_sync():
        return mock_sync()

    monkeypatch.setattr("app.sync.run_ob_sync", async_sync)
    monkeypatch.setattr("app.pipeline.runner.run_ob_sync", async_sync)

    return {
        "read_note": mock_read,
        "list_notes": mock_list,
        "list_manifest": mock_manifest,
        "write_note": mock_write,
        "delete_note": mock_delete,
        "delete_from_index": mock_delete_index,
        "run_ob_sync": mock_sync,
    }


@pytest.fixture
def sample_note(vault_dir):
    """Write a sample note to the vault for headless-level tests."""
    note_path = vault_dir / "test-note.md"
    note_path.write_text(
        "---\ntitle: Test Note\ntags:\n  - testing\n---\n\n"
        "# Test Note\n\nSome content with a [[wikilink]] and [[another|display text]].\n",
        encoding="utf-8",
    )
    return "test-note.md"


@pytest.fixture
def sample_notes(vault_dir):
    """Write multiple notes for headless-level tests."""
    inbox = vault_dir / "Inbox"
    inbox.mkdir()

    (vault_dir / "note-a.md").write_text(
        "---\ntitle: Note A\ntags:\n  - alpha\n---\n\nContent of note A.\n",
        encoding="utf-8",
    )
    (inbox / "note-b.md").write_text(
        "---\ntitle: Note B\ntags:\n  - beta\n---\n\nContent of note B with [[note-a]].\n",
        encoding="utf-8",
    )
    (inbox / "note-c.md").write_text(
        "---\ntitle: Note C\n---\n\nContent of note C.\n",
        encoding="utf-8",
    )
    return ["note-a.md", "Inbox/note-b.md", "Inbox/note-c.md"]


@pytest.fixture
def client(monkeypatch, mock_es, mock_headless):
    """FastAPI test client with ES and headless service mocked."""
    from app.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)
