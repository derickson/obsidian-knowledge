import asyncio
from unittest.mock import AsyncMock, patch

from app.sync import run_ob_sync


class TestObSync:
    def test_sync_success(self):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"synced\n", b"")
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = asyncio.get_event_loop().run_until_complete(run_ob_sync())

        assert result["returncode"] == 0
        assert result["stdout"] == "synced"

    def test_sync_failure(self):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"error: not logged in\n")
        mock_proc.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = asyncio.get_event_loop().run_until_complete(run_ob_sync())

        assert result["returncode"] == 1
        assert "not logged in" in result["stderr"]
