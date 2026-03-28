from unittest.mock import patch

from tests.conftest import SAMPLE_NOTE, SAMPLE_NOTES_LIST

from app.search.indexer import index_note, reindex_all


class TestIndexNote:
    def test_indexes_single_note(self, mock_headless, mock_es):
        index_note(SAMPLE_NOTE)

        mock_es.index.assert_called_once()
        doc = mock_es.index.call_args.kwargs["document"]
        assert doc["path"] == "test-note.md"
        assert doc["title"] == "Test Note"
        assert "testing" in doc["tags"]


class TestReindexAll:
    def test_reindex_indexes_new_notes(self, mock_headless, mock_es):
        mock_es.search.return_value = {"hits": {"hits": []}}

        # read_note returns different notes for each path
        def read_side_effect(path):
            return {**SAMPLE_NOTE, "path": path, "title": path}

        mock_headless["read_note"].side_effect = read_side_effect

        with patch("app.search.indexer.bulk") as mock_bulk:
            result = reindex_all()

        assert result["indexed"] == 3
        assert result["skipped"] == 0
        assert result["deleted"] == 0
        mock_bulk.assert_called_once()

    def test_reindex_skips_unchanged(self, mock_headless, mock_es):
        mock_headless["list_notes"].return_value = ["test-note.md"]
        mock_es.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "path": "test-note.md",
                            "content_hash": SAMPLE_NOTE["content_hash"],
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

    def test_reindex_deletes_removed_notes(self, mock_headless, mock_es):
        mock_headless["list_notes"].return_value = []
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
