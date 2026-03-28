from unittest.mock import patch

from tests.conftest import SAMPLE_NOTE, SAMPLE_MANIFEST

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
        """New files (not in ES) should be read and indexed."""
        mock_es.search.return_value = {"hits": {"hits": []}}

        def read_side_effect(path):
            return {**SAMPLE_NOTE, "path": path, "title": path}

        mock_headless["read_note"].side_effect = read_side_effect

        with patch("app.search.indexer.bulk") as mock_bulk:
            result = reindex_all()

        assert result["indexed"] == 3
        assert result["skipped"] == 0
        assert result["deleted"] == 0
        mock_bulk.assert_called_once()

    def test_reindex_skips_unchanged_mtime(self, mock_headless, mock_es):
        """Files with same mtime as ES should be skipped without reading."""
        mock_headless["list_manifest"].return_value = [
            {"path": "test-note.md", "last_modified": 1700000000},
        ]
        mock_es.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "path": "test-note.md",
                            "content_hash": SAMPLE_NOTE["content_hash"],
                            "last_modified": 1700000000,
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
        # read_note should NOT have been called — mtime match skips the read
        mock_headless["read_note"].assert_not_called()

    def test_reindex_reads_on_mtime_change(self, mock_headless, mock_es):
        """Files with changed mtime should be read and re-indexed."""
        mock_headless["list_manifest"].return_value = [
            {"path": "test-note.md", "last_modified": 1700000099},
        ]
        mock_es.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "path": "test-note.md",
                            "content_hash": "old-hash",
                            "last_modified": 1700000000,
                        }
                    }
                ]
            }
        }

        with patch("app.search.indexer.bulk") as mock_bulk:
            result = reindex_all()

        assert result["indexed"] == 1
        mock_headless["read_note"].assert_called_once()
        mock_bulk.assert_called_once()

    def test_reindex_deletes_removed_notes(self, mock_headless, mock_es):
        """Docs in ES whose vault files no longer exist should be deleted."""
        mock_headless["list_manifest"].return_value = []
        mock_es.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "path": "deleted-note.md",
                            "content_hash": "abc",
                            "last_modified": 1700000000,
                        }
                    }
                ]
            }
        }

        with patch("app.search.indexer.bulk"):
            result = reindex_all()

        assert result["deleted"] == 1
        mock_es.delete.assert_called_once()
