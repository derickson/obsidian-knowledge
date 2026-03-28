from app.vault.reader import (
    content_hash,
    extract_wikilinks,
    list_notes,
    read_note,
)


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
    def test_read_existing_note(self, sample_note):
        note = read_note(sample_note)
        assert note["path"] == "test-note.md"
        assert note["title"] == "Test Note"
        assert "testing" in note["tags"]
        assert "wikilink" in note["wikilinks"]
        assert "another" in note["wikilinks"]
        assert "# Test Note" in note["content"]
        assert note["content_hash"]
        assert note["last_modified"] > 0

    def test_read_missing_note_raises(self, vault_dir):
        import pytest

        with pytest.raises(FileNotFoundError):
            read_note("nonexistent.md")

    def test_note_without_title_uses_stem(self, vault_dir):
        (vault_dir / "untitled.md").write_text("Just content, no frontmatter.\n")
        note = read_note("untitled.md")
        assert note["title"] == "untitled"

    def test_note_with_frontmatter_metadata(self, sample_note):
        note = read_note(sample_note)
        assert note["metadata"]["title"] == "Test Note"
        assert note["metadata"]["tags"] == ["testing"]


class TestListNotes:
    def test_list_all(self, sample_notes):
        notes = list_notes()
        names = [n.name for n in notes]
        assert "note-a.md" in names
        assert "note-b.md" in names
        assert "note-c.md" in names

    def test_list_by_folder(self, sample_notes):
        notes = list_notes("Inbox")
        names = [n.name for n in notes]
        assert "note-b.md" in names
        assert "note-c.md" in names
        assert "note-a.md" not in names

    def test_empty_vault(self, vault_dir):
        assert list_notes() == []
