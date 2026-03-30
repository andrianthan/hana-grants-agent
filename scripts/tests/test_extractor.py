"""Tests for LLM metadata extraction module."""
import sys
import os
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scrapers.processing.extractor import GrantMetadata, extract_metadata, log_extraction_failure


def test_grant_metadata_valid():
    meta = GrantMetadata(
        title="CA Youth Grant",
        funder="CA Dept of Education",
        extraction_confidence=0.85,
    )
    assert meta.title == "CA Youth Grant"
    assert meta.deadline is None
    assert meta.funding_min is None
    assert meta.extraction_confidence == 0.85


def test_grant_metadata_confidence_bounds():
    with pytest.raises(Exception):
        GrantMetadata(title="X", funder="Y", extraction_confidence=1.5)
    with pytest.raises(Exception):
        GrantMetadata(title="X", funder="Y", extraction_confidence=-0.1)


def test_grant_metadata_nullable_fields():
    meta = GrantMetadata(
        title="Grant",
        funder="Funder",
        deadline=None,
        funding_min=None,
        funding_max=None,
        geography=None,
        eligibility=None,
        program_area=None,
        population_served=None,
        relationship_required=None,
        extraction_confidence=0.3,
    )
    assert meta.deadline is None
    assert meta.funding_min is None
    assert meta.relationship_required is None


@patch.dict(os.environ, {"EXTRACTION_MODEL": "openai/gpt-5.4-mini", "OPENROUTER_API_KEY": "test"})
def test_extract_metadata_calls_correct_model():
    mock_client = MagicMock()
    mock_parsed = GrantMetadata(
        title="Test", funder="Funder", extraction_confidence=0.9
    )
    mock_client.beta.chat.completions.parse.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(parsed=mock_parsed))]
    )

    result = extract_metadata("Some grant text", client=mock_client)

    call_kwargs = mock_client.beta.chat.completions.parse.call_args
    assert call_kwargs.kwargs["model"] == "openai/gpt-5.4-mini"
    assert call_kwargs.kwargs["response_format"] is GrantMetadata
    assert result.title == "Test"


def test_log_extraction_failure_inserts():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor

    log_extraction_failure(conn, "grants-ca-gov", "timeout error", raw_s3_key="s3://bucket/key")

    cursor.execute.assert_called_once()
    sql = cursor.execute.call_args[0][0]
    assert "extraction_failures" in sql
    args = cursor.execute.call_args[0][1]
    assert args[0] == "grants-ca-gov"
    assert args[2] == "timeout error"
    conn.commit.assert_called_once()


def test_log_extraction_failure_truncates_long_errors():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor

    long_error = "x" * 5000
    log_extraction_failure(conn, "test-scraper", long_error)

    args = cursor.execute.call_args[0][1]
    assert len(args[2]) <= 2000
