"""Tests for the obsidian-headless vault reader (direct file I/O)."""

import importlib.util
import sys
from pathlib import Path

import pytest

_headless_root = Path(__file__).resolve().parent.parent / "obsidian-headless"


def _import_headless(module_path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, _headless_root / module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Load headless config and inject it so `from app.config import settings` works
_headless_config = _import_headless("app/config.py", "headless_config")

# Save and replace app.config temporarily
_orig_config = sys.modules.get("app.config")
sys.modules["app.config"] = _headless_config
_reader = _import_headless("app/vault/reader.py", "headless_reader")
if _orig_config:
    sys.modules["app.config"] = _orig_config
else:
    del sys.modules["app.config"]

extract_wikilinks = _reader.extract_wikilinks
content_hash = _reader.content_hash
_settings = _headless_config.settings


def _read_note(path, vault_dir):
    orig = _settings.vault_path
    _settings.vault_path = str(vault_dir)
    try:
        return _reader.read_note(path)
    finally:
        _settings.vault_path = orig


def _list_notes(vault_dir, folder=None):
    orig = _settings.vault_path
    _settings.vault_path = str(vault_dir)
    try:
        return _reader.list_notes(folder)
    finally:
        _settings.vault_path = orig


class TestExtractWikilinks:
    def test_simple_link(self):
        assert extract_wikilinks("See [[my note]] for details") == ["my note"]

    def test_link_with_alias(self):
        assert extract_wikilinks("See [[my note|display text]]") == ["my note"]

    def test_multiple_links(self):
        text = "Link to [[note-a]] and [[note-b|B]] here"
        assert extract_wikilinks(text) == ["note-a", "note-b"]

    def test_no_links(self):
        assert extract_wikilinks("No links here") == []

    def test_empty_string(self):
        assert extract_wikilinks("") == []

    def test_nested_brackets_ignored(self):
        assert extract_wikilinks("[[valid]]") == ["valid"]


class TestContentHash:
    def test_deterministic(self):
        assert content_hash("hello") == content_hash("hello")

    def test_different_content_different_hash(self):
        assert content_hash("hello") != content_hash("world")

    def test_returns_16_chars(self):
        assert len(content_hash("test")) == 16


class TestReadNote:
    def test_read_existing_note(self, vault_dir, sample_note):
        note = _read_note(sample_note, vault_dir)
        assert note["path"] == "test-note.md"
        assert note["title"] == "Test Note"
        assert "testing" in note["tags"]
        assert "wikilink" in note["wikilinks"]
        assert "another" in note["wikilinks"]
        assert "# Test Note" in note["content"]
        assert note["content_hash"]
        assert note["last_modified"] > 0

    def test_read_missing_note_raises(self, vault_dir):
        with pytest.raises(FileNotFoundError):
            _read_note("nonexistent.md", vault_dir)

    def test_note_without_title_uses_stem(self, vault_dir):
        (vault_dir / "untitled.md").write_text("Just content, no frontmatter.\n")
        note = _read_note("untitled.md", vault_dir)
        assert note["title"] == "untitled"

    def test_note_with_frontmatter_metadata(self, vault_dir, sample_note):
        note = _read_note(sample_note, vault_dir)
        assert note["metadata"]["title"] == "Test Note"
        assert note["metadata"]["tags"] == ["testing"]


class TestListNotes:
    def test_list_all(self, vault_dir, sample_notes):
        notes = _list_notes(vault_dir)
        names = [n.name for n in notes]
        assert "note-a.md" in names
        assert "note-b.md" in names
        assert "note-c.md" in names

    def test_list_by_folder(self, vault_dir, sample_notes):
        notes = _list_notes(vault_dir, "Inbox")
        names = [n.name for n in notes]
        assert "note-b.md" in names
        assert "note-c.md" in names
        assert "note-a.md" not in names

    def test_empty_vault(self, vault_dir):
        assert _list_notes(vault_dir) == []
