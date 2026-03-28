import os
import tempfile
from unittest.mock import MagicMock

import pytest

# Set env vars before any app imports
os.environ.setdefault("VAULT_PATH", tempfile.mkdtemp())
os.environ.setdefault("ES_CLOUD_ID", "")
os.environ.setdefault("ES_API_KEY", "")


@pytest.fixture(autouse=True)
def vault_dir(tmp_path, monkeypatch):
    """Provide a fresh temporary vault directory for each test."""
    monkeypatch.setattr("app.config.settings.vault_path", str(tmp_path))
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
def sample_note(vault_dir):
    """Write a sample note to the vault and return its path."""
    note_path = vault_dir / "test-note.md"
    note_path.write_text(
        "---\ntitle: Test Note\ntags:\n  - testing\n---\n\n"
        "# Test Note\n\nSome content with a [[wikilink]] and [[another|display text]].\n",
        encoding="utf-8",
    )
    return "test-note.md"


@pytest.fixture
def sample_notes(vault_dir):
    """Write multiple notes for listing/search tests."""
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
def client(monkeypatch, mock_es):
    """FastAPI test client with ES and ob sync mocked."""
    async def mock_sync():
        return {"returncode": 0, "stdout": "mocked", "stderr": ""}

    monkeypatch.setattr("app.pipeline.runner.run_ob_sync", mock_sync)

    from app.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)
