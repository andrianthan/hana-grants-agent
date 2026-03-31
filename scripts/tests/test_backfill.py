"""Tests for the backfill script."""

import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scrapers.backfill import (
    PROGRESS_FILE,
    _process_batch,
    backfill_grants_ca_gov,
    backfill_grants_gov,
    load_progress,
    save_progress,
)
from scrapers.base_scraper import RawGrant


class TestLoadProgress:
    def test_returns_defaults_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("scrapers.backfill.PROGRESS_FILE", str(tmp_path / "nonexistent.json"))
        result = load_progress()
        assert result == {"grants_ca_gov_offset": 0, "grants_gov_offset": 0, "total_processed": 0, "total_new": 0}

    def test_loads_existing_progress(self, tmp_path, monkeypatch):
        progress_file = tmp_path / "progress.json"
        data = {"grants_ca_gov_offset": 100, "grants_gov_offset": 50, "total_processed": 150, "total_new": 30}
        progress_file.write_text(json.dumps(data))
        monkeypatch.setattr("scrapers.backfill.PROGRESS_FILE", str(progress_file))
        result = load_progress()
        assert result == data


class TestSaveProgress:
    def test_creates_json_file(self, tmp_path, monkeypatch):
        progress_file = tmp_path / "progress.json"
        monkeypatch.setattr("scrapers.backfill.PROGRESS_FILE", str(progress_file))
        data = {"grants_ca_gov_offset": 50, "grants_gov_offset": 0, "total_processed": 50, "total_new": 10}
        save_progress(data)
        assert progress_file.exists()
        loaded = json.loads(progress_file.read_text())
        assert loaded == data


class TestProcessBatch:
    def test_calls_dedup_before_extract(self):
        conn = MagicMock()
        grants = [
            RawGrant(title="G1", funder="F1", description="Desc1", deadline=None, source_url="http://example.com", source_id="test"),
        ]
        progress = {"total_new": 0}
        call_order = []

        with patch("scrapers.backfill.check_duplicates_batch") as mock_dedup, \
             patch("scrapers.backfill.extract_metadata") as mock_extract, \
             patch("scrapers.backfill.embed_and_store") as mock_embed:
            mock_dedup.side_effect = lambda c, g: (call_order.append("dedup"), g)[1]
            mock_extract.side_effect = lambda d: (call_order.append("extract"), MagicMock())[1]
            mock_embed.return_value = True

            _process_batch(conn, grants, "test", progress)

        assert call_order[0] == "dedup"
        assert call_order[1] == "extract"
        assert progress["total_new"] == 1

    def test_logs_extraction_failure(self):
        conn = MagicMock()
        grants = [
            RawGrant(title="G1", funder="F1", description="Desc1", deadline=None, source_url="http://example.com", source_id="test"),
        ]
        progress = {"total_new": 0}

        with patch("scrapers.backfill.check_duplicates_batch", return_value=grants), \
             patch("scrapers.backfill.extract_metadata", side_effect=ValueError("LLM error")), \
             patch("scrapers.backfill.log_extraction_failure") as mock_log:
            _process_batch(conn, grants, "test", progress)

        mock_log.assert_called_once_with(conn, "test", "LLM error")
        assert progress["total_new"] == 0


class TestBackfillGrantsCaGov:
    @pytest.mark.asyncio
    async def test_stops_on_empty_records(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scrapers.backfill.PROGRESS_FILE", str(tmp_path / "progress.json"))
        conn = MagicMock()
        progress = {"grants_ca_gov_offset": 0, "grants_gov_offset": 0, "total_processed": 0, "total_new": 0}

        with patch("scrapers.backfill.GrantsCaGov") as MockCls:
            mock_scraper = MagicMock()
            mock_scraper._get_json = AsyncMock(return_value={"result": {"records": [], "total": 0}})
            mock_scraper.close = AsyncMock()
            MockCls.return_value = mock_scraper

            await backfill_grants_ca_gov(conn, batch_size=50, progress=progress)

        assert progress["total_processed"] == 0

    @pytest.mark.asyncio
    async def test_processes_single_batch(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scrapers.backfill.PROGRESS_FILE", str(tmp_path / "progress.json"))
        conn = MagicMock()
        progress = {"grants_ca_gov_offset": 0, "grants_gov_offset": 0, "total_processed": 0, "total_new": 0}

        api_response = {
            "result": {
                "total": 1,
                "records": [
                    {"Title": "Test Grant", "AgencyDept": "CA Dept", "Description": "Test", "ApplicationDeadline": "", "GrantURL": "http://example.com"},
                ],
            }
        }

        with patch("scrapers.backfill.GrantsCaGov") as MockCls, \
             patch("scrapers.backfill.check_duplicates_batch", return_value=[]), \
             patch("scrapers.backfill.time"):
            mock_scraper = MagicMock()
            mock_scraper._get_json = AsyncMock(return_value=api_response)
            mock_scraper.close = AsyncMock()
            MockCls.return_value = mock_scraper

            await backfill_grants_ca_gov(conn, batch_size=50, progress=progress)

        assert progress["total_processed"] == 1
        assert progress["grants_ca_gov_offset"] == 50


class TestBackfillGrantsGov:
    @pytest.mark.asyncio
    async def test_stops_on_empty_hits(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scrapers.backfill.PROGRESS_FILE", str(tmp_path / "progress.json"))
        conn = MagicMock()
        progress = {"grants_ca_gov_offset": 0, "grants_gov_offset": 0, "total_processed": 0, "total_new": 0}

        with patch("scrapers.backfill.GrantsGov") as MockCls:
            mock_scraper = MagicMock()
            mock_scraper._post_json = AsyncMock(return_value={"data": {"hitCount": 0, "oppHits": []}})
            mock_scraper.close = AsyncMock()
            MockCls.return_value = mock_scraper

            await backfill_grants_gov(conn, batch_size=50, progress=progress)

        assert progress["total_processed"] == 0
