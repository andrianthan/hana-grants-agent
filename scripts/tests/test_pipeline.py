"""Tests for the evaluation pipeline orchestrator."""
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "evaluation"))

sys.modules["openai"] = MagicMock()
sys.modules["utils.embeddings"] = MagicMock()
sys.modules["utils.db"] = MagicMock()
sys.modules["dotenv"] = MagicMock()

from evaluation.pipeline import deduplicate_candidates, ALL_PROFILES


# --- deduplicate_candidates ---

def test_deduplicate_no_overlap():
    candidates = {
        "mental-health-hub": [{"grant_id": "g1"}, {"grant_id": "g2"}],
        "hanna-academy": [{"grant_id": "g3"}],
    }
    result = deduplicate_candidates(candidates)
    # All grants kept (dedup only logs, doesn't remove)
    assert len(result["mental-health-hub"]) == 2
    assert len(result["hanna-academy"]) == 1


def test_deduplicate_with_overlap():
    """Same grant in multiple profiles should stay in all (each profile scores independently)."""
    candidates = {
        "mental-health-hub": [{"grant_id": "g1"}, {"grant_id": "g2"}],
        "hanna-academy": [{"grant_id": "g1"}, {"grant_id": "g3"}],
    }
    result = deduplicate_candidates(candidates)
    assert len(result["mental-health-hub"]) == 2
    assert len(result["hanna-academy"]) == 2


def test_deduplicate_empty():
    result = deduplicate_candidates({})
    assert result == {}


# --- ALL_PROFILES ---

def test_all_profiles_has_six():
    assert len(ALL_PROFILES) == 6


def test_all_profiles_contains_expected():
    assert "mental-health-hub" in ALL_PROFILES
    assert "general-operations" in ALL_PROFILES


# --- Handler event parsing ---

def test_handler_eventbridge_detection():
    """EventBridge events have 'detail-type' key."""
    from evaluation.handler import handler

    event = {"detail-type": "Scheduled Event", "source": "aws.events"}

    with patch("pipeline.run_pipeline") as mock_pipeline:
        mock_pipeline.return_value = {"run_id": 1}
        with patch.dict(os.environ, {"DB_SECRET_ARN": "arn:test", "OPENROUTER_API_KEY": "sk-test"}):
            result = handler(event, None)

    # Should call with profile_id=None (all profiles)
    mock_pipeline.assert_called_once()
    call_kwargs = mock_pipeline.call_args[1]
    assert call_kwargs["profile_id"] is None
    assert call_kwargs["dry_run"] is False


def test_handler_step_functions_event():
    """Step Functions events pass profile_id directly."""
    from evaluation.handler import handler

    event = {"profile_id": "mental-health-hub", "dry_run": True}

    with patch("pipeline.run_pipeline") as mock_pipeline:
        mock_pipeline.return_value = {"run_id": 1}
        with patch.dict(os.environ, {"DB_SECRET_ARN": "arn:test", "OPENROUTER_API_KEY": "sk-test"}):
            result = handler(event, None)

    call_kwargs = mock_pipeline.call_args[1]
    assert call_kwargs["profile_id"] == "mental-health-hub"
    assert call_kwargs["dry_run"] is True


def test_handler_raises_without_secret_arn():
    from evaluation.handler import handler

    with patch.dict(os.environ, {"DB_SECRET_ARN": "", "OPENROUTER_API_KEY": "sk-test"}, clear=False):
        try:
            handler({}, None)
            assert False, "Should have raised"
        except RuntimeError as e:
            assert "DB_SECRET_ARN" in str(e)


def test_handler_raises_without_api_key():
    from evaluation.handler import handler

    with patch.dict(os.environ, {"DB_SECRET_ARN": "arn:test", "OPENROUTER_API_KEY": ""}, clear=False):
        try:
            handler({}, None)
            assert False, "Should have raised"
        except RuntimeError as e:
            assert "OPENROUTER_API_KEY" in str(e)
