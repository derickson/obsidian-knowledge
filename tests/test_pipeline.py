import asyncio
from unittest.mock import MagicMock, patch

from app.pipeline.runner import process_note


class TestPipeline:
    def test_process_note_indexes_and_syncs(self, mock_headless):
        mock_index = MagicMock()

        with patch("app.pipeline.runner.index_note", mock_index):
            result = asyncio.get_event_loop().run_until_complete(
                process_note("test-note.md")
            )

        assert result["indexed"] is True
        assert result["synced"] is True
        mock_index.assert_called_once()
        note_arg = mock_index.call_args[0][0]
        assert note_arg["path"] == "test-note.md"

    def test_process_note_reports_sync_failure(self, mock_headless):
        mock_headless["run_ob_sync"].return_value = {
            "status": "error",
            "returncode": 1,
            "stdout": "",
            "stderr": "fail",
        }

        with patch("app.pipeline.runner.index_note", MagicMock()):
            result = asyncio.get_event_loop().run_until_complete(
                process_note("test-note.md")
            )

        assert result["synced"] is False
