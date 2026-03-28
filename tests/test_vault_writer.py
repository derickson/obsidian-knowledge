import frontmatter

from app.vault.reader import read_note
from app.vault.writer import delete_note, write_note


class TestWriteNote:
    def test_write_simple_note(self, vault_dir):
        write_note("hello.md", "# Hello World")
        assert (vault_dir / "hello.md").exists()
        note = read_note("hello.md")
        assert "# Hello World" in note["content"]

    def test_write_with_metadata(self, vault_dir):
        write_note("tagged.md", "Content here", {"tags": ["a", "b"], "source": "test"})
        post = frontmatter.load(vault_dir / "tagged.md")
        assert post.metadata["tags"] == ["a", "b"]
        assert post.metadata["source"] == "test"
        assert post.content == "Content here"

    def test_write_creates_subdirectories(self, vault_dir):
        write_note("deep/nested/note.md", "Nested content")
        assert (vault_dir / "deep" / "nested" / "note.md").exists()

    def test_write_overwrites_existing(self, vault_dir):
        write_note("overwrite.md", "Original")
        write_note("overwrite.md", "Updated")
        note = read_note("overwrite.md")
        assert "Updated" in note["content"]

    def test_write_with_no_metadata(self, vault_dir):
        write_note("bare.md", "Just markdown")
        note = read_note("bare.md")
        assert note["content"] == "Just markdown"
        assert note["metadata"] == {}


class TestDeleteNote:
    def test_delete_existing(self, vault_dir, sample_note):
        assert (vault_dir / sample_note).exists()
        delete_note(sample_note)
        assert not (vault_dir / sample_note).exists()

    def test_delete_nonexistent_is_noop(self, vault_dir):
        delete_note("does-not-exist.md")  # Should not raise
