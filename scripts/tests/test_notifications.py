"""Tests for evaluation.notifications module."""
import json
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, call, patch

import pytest

# Patch boto3 before importing notifications
with patch("boto3.client"):
    from evaluation.notifications import (
        send_daily_alert,
        send_weekly_digest,
        _esc,
    )


class TestEscapeHtml:
    def test_escapes_special_chars(self):
        assert _esc('<script>alert("xss")</script>') == '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;'

    def test_escapes_ampersand(self):
        assert _esc("Tom & Jerry") == "Tom &amp; Jerry"

    def test_plain_text_unchanged(self):
        assert _esc("Hello World") == "Hello World"


class TestDailyAlert:
    def _mock_conn(self, above_grants, below_grants):
        """Mock conn where first fetchall returns above, second returns below."""
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchall.side_effect = [above_grants, below_grants]
        return conn

    @patch("evaluation.notifications._send_email")
    def test_sends_email_when_grants_above_threshold(self, mock_send):
        above = [
            ("Youth Mental Health Grant", "DHCS", 7.6, "Strong fit for Hanna", date(2026, 6, 1), "grant-123"),
            ("Trauma Care Funding", "CHFFA", 6.8, "Good alignment", date(2026, 7, 15), "grant-456"),
        ]
        conn = self._mock_conn(above, [])
        send_daily_alert(conn, {})

        mock_send.assert_called_once()
        subject = mock_send.call_args[0][0]
        assert "2 new grants" in subject
        html_body = mock_send.call_args[0][1]
        assert "Youth Mental Health Grant" in html_body
        assert "7.6" in html_body

    @patch("evaluation.notifications._send_email")
    def test_sends_email_even_with_zero_grants(self, mock_send):
        """Always sends — subject says 0 new grants."""
        conn = self._mock_conn([], [])
        send_daily_alert(conn, {})
        mock_send.assert_called_once()
        subject = mock_send.call_args[0][0]
        assert "0 new grants" in subject

    @patch("evaluation.notifications._send_email")
    def test_subject_shows_zero_when_only_below_threshold(self, mock_send):
        below = [
            ("Weak Grant", "Funder", 4.5, "Poor fit", date(2026, 5, 1), "grant-weak"),
        ]
        conn = self._mock_conn([], below)
        send_daily_alert(conn, {})
        subject = mock_send.call_args[0][0]
        assert "0 new grants" in subject
        assert "1 scored" in subject

    @patch("evaluation.notifications._send_email")
    def test_singular_grant_subject(self, mock_send):
        above = [
            ("Single Grant", "Funder", 8.0, "Great fit", date(2026, 5, 1), "grant-789"),
        ]
        conn = self._mock_conn(above, [])
        send_daily_alert(conn, {})
        subject = mock_send.call_args[0][0]
        assert "1 new grant found" in subject

    @patch("evaluation.notifications._send_email")
    def test_handles_none_deadline(self, mock_send):
        above = [
            ("Open Grant", "Funder", 7.0, "Good", None, "grant-000"),
        ]
        conn = self._mock_conn(above, [])
        send_daily_alert(conn, {})
        html_body = mock_send.call_args[0][1]
        assert "No deadline" in html_body

    @patch("evaluation.notifications._send_email")
    def test_includes_below_threshold_section(self, mock_send):
        above = [
            ("Good Grant", "F1", 7.0, "Good", date(2026, 6, 1), "g1"),
        ]
        below = [
            ("Meh Grant", "F2", 4.0, "Weak", date(2026, 6, 1), "g2"),
        ]
        conn = self._mock_conn(above, below)
        send_daily_alert(conn, {})
        html_body = mock_send.call_args[0][1]
        assert "Below Threshold" in html_body
        assert "Meh Grant" in html_body


class TestWeeklyDigest:
    def _mock_conn_with_grants(self, grants):
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchall.return_value = grants
        return conn

    @patch("evaluation.notifications._send_email")
    def test_sends_digest_with_above_and_below(self, mock_send):
        grants = [
            ("Top Grant", "DHCS", 8.0, "Excellent fit", date(2026, 6, 1),
             ["mental-health-hub"], "g1", {"mental-health-hub": {}}),
            ("Okay Grant", "Other", 5.5, "Marginal", date(2026, 7, 1),
             ["general-operations"], "g2", {"general-operations": {}}),
        ]
        conn = self._mock_conn_with_grants(grants)
        send_weekly_digest(conn)

        mock_send.assert_called_once()
        subject = mock_send.call_args[0][0]
        assert "1 promising" in subject
        html_body = mock_send.call_args[0][1]
        assert "Recommended Grants" in html_body
        assert "Below Threshold" in html_body

    @patch("evaluation.notifications._send_email")
    def test_skips_when_no_grants(self, mock_send):
        conn = self._mock_conn_with_grants([])
        send_weekly_digest(conn)
        mock_send.assert_not_called()

    @patch("evaluation.notifications._send_email")
    def test_all_above_threshold(self, mock_send):
        grants = [
            ("Grant A", "F1", 7.5, "Good", date(2026, 6, 1),
             ["mental-health-hub"], "g1", {}),
            ("Grant B", "F2", 6.5, "Decent", date(2026, 6, 15),
             ["residential-housing"], "g2", {}),
        ]
        conn = self._mock_conn_with_grants(grants)
        send_weekly_digest(conn)

        html_body = mock_send.call_args[0][1]
        assert "2 promising" in mock_send.call_args[0][0]
        assert "Below Threshold" not in html_body
