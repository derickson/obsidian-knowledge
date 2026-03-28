import asyncio
from unittest.mock import MagicMock, patch

from app.pipeline.runner import process_note


class TestPipeline:
    def test_process_note_indexes_and_syncs(self, sample_note):
        mock_index = MagicMock()

        async def mock_sync():
            return {"returncode": 0, "stdout": "", "stderr": ""}

        with (
            patch("app.pipeline.runner.index_note", mock_index),
            patch("app.pipeline.runner.run_ob_sync", mock_sync),
        ):
            result = asyncio.get_event_loop().run_until_complete(process_note(sample_note))

        assert result["indexed"] is True
        assert result["synced"] is True
        mock_index.assert_called_once()
        note_arg = mock_index.call_args[0][0]
        assert note_arg["path"] == sample_note

    def test_process_note_reports_sync_failure(self, sample_note):
        async def mock_sync():
            return {"returncode": 1, "stdout": "", "stderr": "fail"}

        with (
            patch("app.pipeline.runner.index_note", MagicMock()),
            patch("app.pipeline.runner.run_ob_sync", mock_sync),
        ):
            result = asyncio.get_event_loop().run_until_complete(process_note(sample_note))

        assert result["synced"] is False
