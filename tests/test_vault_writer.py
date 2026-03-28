"""Tests for the obsidian-headless vault writer (direct file I/O)."""

import importlib.util
import sys
from pathlib import Path

import frontmatter

_headless_root = Path(__file__).resolve().parent.parent / "obsidian-headless"


def _import_headless(module_path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, _headless_root / module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Load headless config and inject it so `from app.config import settings` works
_headless_config = _import_headless("app/config.py", "headless_config")
_settings = _headless_config.settings

_orig_config = sys.modules.get("app.config")
sys.modules["app.config"] = _headless_config
_reader = _import_headless("app/vault/reader.py", "headless_reader")
_writer = _import_headless("app/vault/writer.py", "headless_writer")
if _orig_config:
    sys.modules["app.config"] = _orig_config
else:
    del sys.modules["app.config"]


def _with_vault(fn, vault_dir, *args, **kwargs):
    orig = _settings.vault_path
    _settings.vault_path = str(vault_dir)
    try:
        return fn(*args, **kwargs)
    finally:
        _settings.vault_path = orig


class TestWriteNote:
    def test_write_simple_note(self, vault_dir):
        _with_vault(_writer.write_note, vault_dir, "hello.md", "# Hello World")
        assert (vault_dir / "hello.md").exists()
        note = _with_vault(_reader.read_note, vault_dir, "hello.md")
        assert "# Hello World" in note["content"]

    def test_write_with_metadata(self, vault_dir):
        _with_vault(
            _writer.write_note, vault_dir,
            "tagged.md", "Content here", {"tags": ["a", "b"], "source": "test"},
        )
        post = frontmatter.load(vault_dir / "tagged.md")
        assert post.metadata["tags"] == ["a", "b"]
        assert post.metadata["source"] == "test"
        assert post.content == "Content here"

    def test_write_creates_subdirectories(self, vault_dir):
        _with_vault(_writer.write_note, vault_dir, "deep/nested/note.md", "Nested content")
        assert (vault_dir / "deep" / "nested" / "note.md").exists()

    def test_write_overwrites_existing(self, vault_dir):
        _with_vault(_writer.write_note, vault_dir, "overwrite.md", "Original")
        _with_vault(_writer.write_note, vault_dir, "overwrite.md", "Updated")
        note = _with_vault(_reader.read_note, vault_dir, "overwrite.md")
        assert "Updated" in note["content"]

    def test_write_with_no_metadata(self, vault_dir):
        _with_vault(_writer.write_note, vault_dir, "bare.md", "Just markdown")
        note = _with_vault(_reader.read_note, vault_dir, "bare.md")
        assert note["content"] == "Just markdown"
        assert note["metadata"] == {}


class TestDeleteNote:
    def test_delete_existing(self, vault_dir, sample_note):
        assert (vault_dir / sample_note).exists()
        _with_vault(_writer.delete_note, vault_dir, sample_note)
        assert not (vault_dir / sample_note).exists()

    def test_delete_nonexistent_is_noop(self, vault_dir):
        _with_vault(_writer.delete_note, vault_dir, "does-not-exist.md")
