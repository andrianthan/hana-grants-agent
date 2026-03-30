"""Tests for scraper health monitor and pipeline logger."""
import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scrapers.processing.health_monitor import update_health, get_unhealthy_scrapers
from scrapers.processing.pipeline_logger import start_run, complete_run, fail_run


def test_update_health_resets_consecutive_zeros_on_grants():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor

    update_health(conn, "grants-ca-gov", 5)

    sql = cursor.execute.call_args[0][0]
    assert "consecutive_zeros = 0" in sql
    assert "last_grant_count" in sql
    conn.commit.assert_called_once()


def test_update_health_increments_consecutive_zeros_on_zero():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor

    update_health(conn, "grants-ca-gov", 0)

    sql = cursor.execute.call_args[0][0]
    assert "consecutive_zeros = scraper_health.consecutive_zeros + 1" in sql
    conn.commit.assert_called_once()


def test_update_health_passes_error_on_zero():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor

    update_health(conn, "grants-ca-gov", 0, error="HTTP 503")

    args = cursor.execute.call_args[0][1]
    assert args[1] == "HTTP 503"


def test_get_unhealthy_scrapers_above_threshold():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchall.return_value = [
        ("grants-ca-gov", 5, "HTTP 503"),
        ("sam-gov", 3, None),
    ]

    result = get_unhealthy_scrapers(conn, threshold=3)

    assert len(result) == 2
    assert result[0]["scraper_id"] == "grants-ca-gov"
    assert result[0]["consecutive_zeros"] == 5
    assert result[1]["scraper_id"] == "sam-gov"


def test_start_run_returns_integer_run_id():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchone.return_value = (42,)

    run_id = start_run(conn, "ingestion")

    assert run_id == 42
    sql = cursor.execute.call_args[0][0]
    assert "RETURNING id" in sql
    assert "pipeline_runs" in sql
    conn.commit.assert_called_once()


def test_complete_run_updates_status():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor

    complete_run(conn, 42, grants_found=10, grants_new=3)

    sql = cursor.execute.call_args[0][0]
    assert "completed" in sql
    assert "pipeline_runs" in sql
    args = cursor.execute.call_args[0][1]
    assert args[0] == 10  # grants_found
    assert args[1] == 3   # grants_new


def test_fail_run_updates_status_to_failed():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor

    fail_run(conn, 42, errors={"grants-ca-gov": "timeout"})

    sql = cursor.execute.call_args[0][0]
    assert "failed" in sql
    conn.commit.assert_called_once()
