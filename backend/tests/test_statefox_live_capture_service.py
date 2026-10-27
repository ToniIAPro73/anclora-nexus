import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


from backend.services import statefox_live_capture_service


def test_get_statefox_live_capture_reports_invalid_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    capture_path = tmp_path / "statefox-live-capture.json"
    capture_path.write_text('{"raw_text":" ","statefox_links":[],"public_property_links":[]}', encoding="utf-8")
    monkeypatch.setattr(statefox_live_capture_service, "CAPTURE_PATH", capture_path)
    monkeypatch.setattr(statefox_live_capture_service, "RUNBOOK_PATH", tmp_path / "RUNBOOK.md")

    status = statefox_live_capture_service.get_statefox_live_capture()

    assert status["available"] is True
    assert status["status"] == "invalid"
    assert status["import_ready"] is False


def test_import_latest_statefox_capture_returns_validation_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    capture_path = tmp_path / "statefox-live-capture.json"
    capture_path.write_text(
        """
        {
          "captured_at": "2026-03-10T09:00:00Z",
          "page_url": "https://web.telegram.org/",
          "target_url": "https://web.telegram.org/k/#@StateFoxBot",
          "raw_text": "sample results",
          "statefox_links": ["https://t.me/StateFoxBot?startapp=abc"],
          "public_property_links": []
        }
        """.strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(statefox_live_capture_service, "CAPTURE_PATH", capture_path)
    monkeypatch.setattr(statefox_live_capture_service, "RUNBOOK_PATH", tmp_path / "RUNBOOK.md")

    with patch.object(statefox_live_capture_service, "import_statefox_listings", new_callable=AsyncMock) as mock_import:
        mock_import.return_value = {"imported_count": 1, "skipped_count": 0}
        result = asyncio.run(
            statefox_live_capture_service.import_latest_statefox_capture(
                org_id="org-1",
                zone="palma",
                city="Palma",
            )
        )

    assert result["capture_metadata"]["validation"]["import_ready"] is True
    assert result["capture_metadata"]["handoff"]["capture_command"] == "npm run ops:statefox:capture"
    assert result["import_result"]["imported_count"] == 1
