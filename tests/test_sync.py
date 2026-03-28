"""Tests for the obsidian-headless sync subprocess wrapper."""

import asyncio
import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

_headless_root = Path(__file__).resolve().parent.parent / "obsidian-headless"


def _import_headless(module_path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, _headless_root / module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Load headless config first, then swap app.config temporarily to load sync module
_headless_config = _import_headless("app/config.py", "headless_config")
_orig_config = sys.modules.get("app.config")
sys.modules["app.config"] = _headless_config
_sync_mod = _import_headless("app/sync.py", "headless_sync")
if _orig_config:
    sys.modules["app.config"] = _orig_config
else:
    del sys.modules["app.config"]

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
