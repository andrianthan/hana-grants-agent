"""Tests for the grant evaluator (7-flag scoring framework)."""
import json
import sys
import os
from unittest.mock import MagicMock, patch, mock_open
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "evaluation"))

# Pre-mock external dependencies before importing evaluation modules
sys.modules["openai"] = MagicMock()
sys.modules["utils.embeddings"] = MagicMock()


from evaluation.evaluator import (
    compute_weighted_score,
    score_grant,
    write_score_to_db,
    run_evaluator,
    FLAG_WEIGHTS,
    ALL_FLAG_IDS,
    SCORE_THRESHOLD,
)


# --- Fixtures ---

def _make_grant():
    return {
        "grant_id": "CA-DOE-abc123",
        "title": "Youth Mental Health Services Grant",
        "funder": "California DHCS",
        "description": "Funding for youth mental health services in Sonoma County.",
        "eligibility": "501(c)(3)",
        "geography": "California",
        "deadline": date(2026, 8, 1),
        "funding_min": 100000,
        "funding_max": 500000,
        "program_area": "Mental Health",
        "population_served": "Youth ages 6-24",
    }


def _make_perfect_scores():
    return {flag: 9 for flag in ALL_FLAG_IDS}


def _make_low_scores():
    return {flag: 2 for flag in ALL_FLAG_IDS}


def _make_llm_response(flag_scores, reasoning="Good match for Hanna's programs."):
    """Create a mock LLM response with the given scores."""
    data = {**flag_scores, "reasoning": reasoning}
    msg = MagicMock()
    msg.content = json.dumps(data)
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


# --- compute_weighted_score ---

def test_weighted_score_all_tens():
    scores = {flag: 10 for flag in ALL_FLAG_IDS}
    assert compute_weighted_score(scores) == 10.0


def test_weighted_score_all_ones():
    scores = {flag: 1 for flag in ALL_FLAG_IDS}
    assert compute_weighted_score(scores) == 1.0


def test_weighted_score_empty():
    assert compute_weighted_score({}) == 0.0


def test_weighted_score_high_flags_matter_more():
    """HIGH-weight flags should dominate the score."""
    # All HIGH flags = 10, all MEDIUM flags = 1
    scores = {}
    for flag, weight in FLAG_WEIGHTS.items():
        scores[flag] = 10 if weight == 3 else 1
    result = compute_weighted_score(scores)
    # HIGH = 3 flags * weight 3 * score 10 = 90
    # MEDIUM = 4 flags * weight 2 * score 1 = 8
    # Total weight = 9 + 8 = 17, weighted sum = 98
    assert result > 5.0  # Should be skewed toward 10


def test_weighted_score_partial_flags():
    """Missing flags should be excluded, not treated as zero."""
    scores = {"strategic_priority_alignment": 8}
    result = compute_weighted_score(scores)
    assert result == 8.0  # Only one flag, its score is the average


# --- score_grant ---

@patch("evaluation.evaluator._load_prompt_template")
@patch("evaluation.evaluator._call_llm_with_retry")
def test_score_grant_valid_response(mock_llm, mock_template):
    mock_template.return_value = "Score this: {org_profile} {profile_context} {grant_title} {grant_funder} {grant_description} {grant_eligibility} {grant_geography} {grant_deadline} {grant_funding_range} {grant_program_area} {grant_population_served} {today_date}"
    scores = _make_perfect_scores()
    mock_llm.return_value = _make_llm_response(scores)

    client = MagicMock()
    result = score_grant(
        client=client,
        grant=_make_grant(),
        profile_id="mental-health-hub",
        org_profile="Hanna Center is a nonprofit.",
        profile_context="Mental health services.",
        today=date(2026, 3, 31),
    )

    assert result is not None
    assert result["weighted_score"] == compute_weighted_score(scores)
    assert result["flag_scores"] == scores
    assert "reasoning" in result


@patch("evaluation.evaluator._load_prompt_template")
@patch("evaluation.evaluator._call_llm_with_retry")
def test_score_grant_clamps_scores(mock_llm, mock_template):
    """Scores outside 1-10 should be clamped."""
    mock_template.return_value = "{org_profile} {profile_context} {grant_title} {grant_funder} {grant_description} {grant_eligibility} {grant_geography} {grant_deadline} {grant_funding_range} {grant_program_area} {grant_population_served} {today_date}"
    scores = {flag: 15 for flag in ALL_FLAG_IDS}  # Out of range
    mock_llm.return_value = _make_llm_response(scores)

    result = score_grant(
        client=MagicMock(),
        grant=_make_grant(),
        profile_id="mental-health-hub",
        org_profile="test",
        profile_context="test",
    )

    assert result is not None
    for flag_id, score in result["flag_scores"].items():
        assert 1 <= score <= 10


@patch("evaluation.evaluator._load_prompt_template")
@patch("evaluation.evaluator._call_llm_with_retry")
def test_score_grant_handles_markdown_fences(mock_llm, mock_template):
    """LLM sometimes wraps JSON in markdown code fences."""
    mock_template.return_value = "{org_profile} {profile_context} {grant_title} {grant_funder} {grant_description} {grant_eligibility} {grant_geography} {grant_deadline} {grant_funding_range} {grant_program_area} {grant_population_served} {today_date}"
    scores = _make_perfect_scores()
    data = {**scores, "reasoning": "Test."}
    fenced = f"```json\n{json.dumps(data)}\n```"

    msg = MagicMock()
    msg.content = fenced
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    mock_llm.return_value = response

    result = score_grant(
        client=MagicMock(),
        grant=_make_grant(),
        profile_id="mental-health-hub",
        org_profile="test",
        profile_context="test",
    )

    assert result is not None
    assert result["weighted_score"] > 0


@patch("evaluation.evaluator._load_prompt_template")
@patch("evaluation.evaluator._call_llm_with_retry")
def test_score_grant_returns_none_on_invalid_json(mock_llm, mock_template):
    mock_template.return_value = "{org_profile} {profile_context} {grant_title} {grant_funder} {grant_description} {grant_eligibility} {grant_geography} {grant_deadline} {grant_funding_range} {grant_program_area} {grant_population_served} {today_date}"
    msg = MagicMock()
    msg.content = "This is not JSON at all"
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    mock_llm.return_value = response

    result = score_grant(
        client=MagicMock(),
        grant=_make_grant(),
        profile_id="mental-health-hub",
        org_profile="test",
        profile_context="test",
    )

    assert result is None


@patch("evaluation.evaluator._load_prompt_template")
@patch("evaluation.evaluator._call_llm_with_retry")
def test_score_grant_defaults_missing_flags(mock_llm, mock_template):
    """Missing flags should default to 5."""
    mock_template.return_value = "{org_profile} {profile_context} {grant_title} {grant_funder} {grant_description} {grant_eligibility} {grant_geography} {grant_deadline} {grant_funding_range} {grant_program_area} {grant_population_served} {today_date}"
    partial_scores = {"strategic_priority_alignment": 9, "reasoning": "Good."}
    msg = MagicMock()
    msg.content = json.dumps(partial_scores)
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    mock_llm.return_value = response

    result = score_grant(
        client=MagicMock(),
        grant=_make_grant(),
        profile_id="mental-health-hub",
        org_profile="test",
        profile_context="test",
    )

    assert result is not None
    assert result["flag_scores"]["strategic_priority_alignment"] == 9
    assert result["flag_scores"]["staff_time_cost"] == 5  # defaulted


# --- write_score_to_db ---

def test_write_score_updates_grant():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchone.return_value = (None, None, None)  # No existing score

    write_score_to_db(
        conn=conn,
        grant_id="test-grant",
        weighted_score=7.5,
        reasoning="Strong match.",
        flag_scores=_make_perfect_scores(),
        profile_id="mental-health-hub",
    )

    conn.commit.assert_called_once()
    sql = cur.execute.call_args_list[-1][0][0]
    assert "UPDATE grants SET" in sql


def test_write_score_keeps_higher_existing_score():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    # Existing score of 9.0 is higher than new 5.0
    cur.fetchone.return_value = (9.0, {}, ["hanna-academy"])

    write_score_to_db(
        conn=conn,
        grant_id="test-grant",
        weighted_score=5.0,
        reasoning="Weak match.",
        flag_scores=_make_low_scores(),
        profile_id="mental-health-hub",
    )

    conn.commit.assert_called_once()
    # Should NOT update score/reasoning (existing 9.0 > new 5.0)
    sql = cur.execute.call_args_list[-1][0][0]
    assert "score_reasoning" not in sql


def test_write_score_appends_profile():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchone.return_value = (7.0, {}, ["hanna-academy"])

    write_score_to_db(
        conn=conn,
        grant_id="test-grant",
        weighted_score=8.0,
        reasoning="Great match.",
        flag_scores=_make_perfect_scores(),
        profile_id="mental-health-hub",
    )

    # Check profile list includes both
    args = cur.execute.call_args_list[-1][0][1]
    profiles_arg = [a for a in args if isinstance(a, list)]
    assert len(profiles_arg) == 1
    assert "hanna-academy" in profiles_arg[0]
    assert "mental-health-hub" in profiles_arg[0]


def test_write_score_skips_missing_grant():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchone.return_value = None  # Grant not found

    write_score_to_db(
        conn=conn,
        grant_id="nonexistent",
        weighted_score=7.0,
        reasoning="test",
        flag_scores={},
        profile_id="test",
    )

    # Should not call commit (no update)
    conn.commit.assert_not_called()
