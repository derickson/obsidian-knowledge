from unittest.mock import patch

from app.search.indexer import index_note, reindex_all
from app.vault.reader import read_note


class TestIndexNote:
    def test_indexes_single_note(self, sample_note, mock_es):
        note = read_note(sample_note)
        index_note(note)

        mock_es.index.assert_called_once()
        doc = mock_es.index.call_args.kwargs["document"]
        assert doc["path"] == sample_note
        assert doc["title"] == "Test Note"
        assert "testing" in doc["tags"]


class TestReindexAll:
    def test_reindex_indexes_new_notes(self, sample_notes, mock_es):
        mock_es.search.return_value = {"hits": {"hits": []}}

        with patch("app.search.indexer.bulk") as mock_bulk:
            result = reindex_all()

        assert result["indexed"] == 3
        assert result["skipped"] == 0
        assert result["deleted"] == 0
        mock_bulk.assert_called_once()

    def test_reindex_skips_unchanged(self, sample_note, mock_es):
        note = read_note(sample_note)
        mock_es.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "path": sample_note,
                            "content_hash": note["content_hash"],
                        }
                    }
                ]
            }
        }

        with patch("app.search.indexer.bulk") as mock_bulk:
            result = reindex_all()

        assert result["indexed"] == 0
        assert result["skipped"] == 1
        mock_bulk.assert_not_called()

    def test_reindex_deletes_removed_notes(self, vault_dir, mock_es):
        mock_es.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "path": "deleted-note.md",
                            "content_hash": "abc",
                        }
                    }
                ]
            }
        }

        with patch("app.search.indexer.bulk"):
            result = reindex_all()

        assert result["deleted"] == 1
        mock_es.delete.assert_called_once()
