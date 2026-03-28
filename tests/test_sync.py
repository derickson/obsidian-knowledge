"""Tests for the obsidian-headless sync subprocess wrapper."""

import asyncio
import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Load obsidian-headless sync module directly to avoid app namespace collision
_headless_root = Path(__file__).resolve().parent.parent / "obsidian-headless"
_spec = importlib.util.spec_from_file_location("headless_sync", _headless_root / "app/sync.py")
_sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["headless_sync"] = _sync_mod
_spec.loader.exec_module(_sync_mod)
run_ob_sync = _sync_mod.run_ob_sync


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
