"""Tests for Bedrock Titan V2 embedding + grants table insert (INGEST-04)."""
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Pre-mock utils.embeddings before importing embedder (avoids boto3 dependency)
sys.modules["utils.embeddings"] = MagicMock()

from scrapers.processing.embedder import embed_and_store


def _make_raw_grant():
    grant = MagicMock()
    grant.description = "Youth development program in Sonoma County"
    grant.content_hash = "abc123def456789abcdef0123456789abcdef0123456789abcdef0123456789a"
    grant.source_id = "grants-ca-gov"
    return grant


def _make_metadata():
    meta = MagicMock()
    meta.title = "CA Youth Grant"
    meta.funder = "CA-DOE"
    meta.deadline = "2026-06-01"
    meta.funding_min = 10000
    meta.funding_max = 50000
    meta.geography = "California"
    meta.eligibility = "501(c)(3)"
    meta.program_area = "Youth Development"
    meta.population_served = "At-risk youth"
    meta.relationship_required = False
    return meta


@patch("scrapers.processing.embedder.get_embedding")
def test_embed_and_store_inserts_new_grant(mock_embed):
    mock_embed.return_value = [0.0] * 1024
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.rowcount = 1  # New insert

    raw_grant = _make_raw_grant()
    metadata = _make_metadata()

    result = embed_and_store(conn, raw_grant, metadata)

    assert result is True
    sql = cursor.execute.call_args[0][0]
    assert "ON CONFLICT (content_hash) DO NOTHING" in sql
    assert "INSERT INTO grants" in sql
    conn.commit.assert_called_once()


@patch("scrapers.processing.embedder.get_embedding")
def test_embed_and_store_returns_false_on_duplicate(mock_embed):
    mock_embed.return_value = [0.0] * 1024
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.rowcount = 0  # ON CONFLICT skipped

    result = embed_and_store(conn, _make_raw_grant(), _make_metadata())

    assert result is False


@patch("scrapers.processing.embedder.get_embedding")
def test_grant_id_format(mock_embed):
    mock_embed.return_value = [0.0] * 1024
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.rowcount = 1

    raw_grant = _make_raw_grant()
    metadata = _make_metadata()

    embed_and_store(conn, raw_grant, metadata)

    insert_args = cursor.execute.call_args[0][1]
    grant_id = insert_args[0]
    assert grant_id == f"{metadata.funder}-{raw_grant.content_hash[:12]}"


@patch("scrapers.processing.embedder.get_embedding")
def test_embed_text_combines_title_and_description(mock_embed):
    mock_embed.return_value = [0.0] * 1024
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.rowcount = 1

    raw_grant = _make_raw_grant()
    metadata = _make_metadata()

    embed_and_store(conn, raw_grant, metadata)

    expected_text = f"{metadata.title}: {raw_grant.description}"
    mock_embed.assert_called_once_with(expected_text)
