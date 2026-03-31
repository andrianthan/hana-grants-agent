"""Tests for the grant prospector (HyDE search + hard filters + LLM pre-filter)."""
import sys
import os
from unittest.mock import MagicMock, patch
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "evaluation"))

sys.modules["openai"] = MagicMock()
sys.modules["utils.embeddings"] = MagicMock()

from evaluation.prospector import (
    _passes_geography_filter,
    apply_hard_filters,
    CA_GEO_KEYWORDS,
)


# --- Geography filter ---

def test_geo_filter_accepts_california():
    assert _passes_geography_filter("California") is True


def test_geo_filter_accepts_national():
    assert _passes_geography_filter("National / Nationwide") is True


def test_geo_filter_accepts_sonoma():
    assert _passes_geography_filter("Sonoma County, CA") is True


def test_geo_filter_accepts_none():
    """No geography = assume national = eligible."""
    assert _passes_geography_filter(None) is True


def test_geo_filter_accepts_empty():
    assert _passes_geography_filter("") is True


def test_geo_filter_rejects_new_york_only():
    assert _passes_geography_filter("New York State only") is False


def test_geo_filter_rejects_florida():
    assert _passes_geography_filter("Florida") is False


def test_geo_filter_case_insensitive():
    assert _passes_geography_filter("CALIFORNIA") is True
    assert _passes_geography_filter("Bay Area") is True


def test_geo_filter_accepts_usa():
    assert _passes_geography_filter("United States") is True
    assert _passes_geography_filter("U.S.") is True
    assert _passes_geography_filter("USA") is True


# --- Hard filters ---

def _make_candidate(**overrides):
    base = {
        "grant_id": "test-001",
        "title": "Test Grant",
        "deadline": date(2026, 12, 1),
        "geography": "California",
    }
    base.update(overrides)
    return base


def test_hard_filter_keeps_future_deadline():
    grants = [_make_candidate(deadline=date(2026, 12, 1))]
    result = apply_hard_filters(grants, today=date(2026, 3, 31))
    assert len(result) == 1


def test_hard_filter_removes_past_deadline():
    grants = [_make_candidate(deadline=date(2026, 1, 1))]
    result = apply_hard_filters(grants, today=date(2026, 3, 31))
    assert len(result) == 0


def test_hard_filter_keeps_none_deadline():
    """None deadline = rolling/unknown = keep."""
    grants = [_make_candidate(deadline=None)]
    result = apply_hard_filters(grants, today=date(2026, 3, 31))
    assert len(result) == 1


def test_hard_filter_removes_non_ca_geography():
    grants = [_make_candidate(geography="Texas only")]
    result = apply_hard_filters(grants, today=date(2026, 3, 31))
    assert len(result) == 0


def test_hard_filter_combined():
    """Only grants passing both deadline AND geography should survive."""
    grants = [
        _make_candidate(grant_id="good", deadline=date(2026, 12, 1), geography="California"),
        _make_candidate(grant_id="past", deadline=date(2025, 1, 1), geography="California"),
        _make_candidate(grant_id="wrong-geo", deadline=date(2026, 12, 1), geography="Florida"),
        _make_candidate(grant_id="both-bad", deadline=date(2025, 1, 1), geography="Texas"),
    ]
    result = apply_hard_filters(grants, today=date(2026, 3, 31))
    assert len(result) == 1
    assert result[0]["grant_id"] == "good"


# --- LLM pre-filter ---

@patch("evaluation.prospector._load_prompt_template")
@patch("evaluation.prospector._call_llm_with_retry")
def test_prefilter_keeps_on_keep_response(mock_llm, mock_template):
    from evaluation.prospector import llm_prefilter

    mock_template.return_value = "{profile_context} {grant_title} {grant_funder} {grant_description} {grant_eligibility} {grant_geography} {grant_deadline} {grant_funding_range}"
    msg = MagicMock()
    msg.content = "KEEP: Relevant to youth mental health."
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    mock_llm.return_value = response

    grants = [_make_candidate()]
    result = llm_prefilter(MagicMock(), grants, "Mental health profile")
    assert len(result) == 1


@patch("evaluation.prospector._load_prompt_template")
@patch("evaluation.prospector._call_llm_with_retry")
def test_prefilter_removes_on_reject_response(mock_llm, mock_template):
    from evaluation.prospector import llm_prefilter

    mock_template.return_value = "{profile_context} {grant_title} {grant_funder} {grant_description} {grant_eligibility} {grant_geography} {grant_deadline} {grant_funding_range}"
    msg = MagicMock()
    msg.content = "REJECT: Agricultural research, no connection to Hanna."
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    mock_llm.return_value = response

    grants = [_make_candidate()]
    result = llm_prefilter(MagicMock(), grants, "Mental health profile")
    assert len(result) == 0


@patch("evaluation.prospector._load_prompt_template")
@patch("evaluation.prospector._call_llm_with_retry")
def test_prefilter_keeps_on_ambiguous_response(mock_llm, mock_template):
    """Ambiguous LLM response should keep the grant (fail open)."""
    from evaluation.prospector import llm_prefilter

    mock_template.return_value = "{profile_context} {grant_title} {grant_funder} {grant_description} {grant_eligibility} {grant_geography} {grant_deadline} {grant_funding_range}"
    msg = MagicMock()
    msg.content = "Maybe relevant, not sure."
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    mock_llm.return_value = response

    grants = [_make_candidate()]
    result = llm_prefilter(MagicMock(), grants, "Mental health profile")
    assert len(result) == 1


@patch("evaluation.prospector._load_prompt_template")
@patch("evaluation.prospector._call_llm_with_retry")
def test_prefilter_keeps_on_llm_error(mock_llm, mock_template):
    """LLM errors should keep the grant (fail open)."""
    from evaluation.prospector import llm_prefilter

    mock_template.return_value = "{profile_context} {grant_title} {grant_funder} {grant_description} {grant_eligibility} {grant_geography} {grant_deadline} {grant_funding_range}"
    mock_llm.side_effect = Exception("API timeout")

    grants = [_make_candidate()]
    result = llm_prefilter(MagicMock(), grants, "Mental health profile")
    assert len(result) == 1
