"""Tests for SHA-256 dedup module."""
import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scrapers.processing.dedup import is_duplicate, check_duplicates_batch


def _make_grant(title="Test Grant", funder="Test Funder", description="desc", deadline=None):
    """Create a mock RawGrant-like object with content_hash property."""
    import hashlib
    grant = MagicMock()
    content = f"{title}|{funder}|{deadline or ''}|{description}"
    grant.content_hash = hashlib.sha256(content.encode()).hexdigest()
    grant.title = title
    grant.funder = funder
    grant.description = description
    return grant


def test_is_duplicate_returns_true_when_hash_exists():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchone.return_value = (1,)

    assert is_duplicate(conn, "abc123hash") is True
    cursor.execute.assert_called_once()
    assert "content_hash" in cursor.execute.call_args[0][0]


def test_is_duplicate_returns_false_when_hash_missing():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchone.return_value = None

    assert is_duplicate(conn, "newhash") is False


def test_check_duplicates_batch_filters_existing():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor

    grant1 = _make_grant(title="Grant A")
    grant2 = _make_grant(title="Grant B")
    grant3 = _make_grant(title="Grant C")

    # Simulate grant1's hash already exists in DB
    cursor.fetchall.return_value = [(grant1.content_hash,)]

    result = check_duplicates_batch(conn, [grant1, grant2, grant3])

    assert len(result) == 2
    assert grant1 not in result
    assert grant2 in result
    assert grant3 in result


def test_check_duplicates_batch_empty_list():
    conn = MagicMock()
    result = check_duplicates_batch(conn, [])
    assert result == []
    conn.cursor.assert_not_called()


def test_check_duplicates_batch_all_new():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchall.return_value = []  # No existing hashes

    grant1 = _make_grant(title="New Grant 1")
    grant2 = _make_grant(title="New Grant 2")

    result = check_duplicates_batch(conn, [grant1, grant2])
    assert len(result) == 2
