#!/usr/bin/env python3
"""Evaluator: scores candidate grants using the 7-flag framework.

For each candidate grant from the Prospector, calls GPT-4.1 via OpenRouter
to score across 7 evaluation flags with weighted averages. Writes scores
to the grants table in RDS.

Flags (from EVAL-CRITERIA.md):
1. Strategic Priority Alignment (HIGH)
2. Staff Time Cost (HIGH)
3. Reporting Burden (MEDIUM)
4. Relationship Required (MEDIUM)
5. Timeline Fit (MEDIUM)
6. Current vs New Programs (HIGH)
7. Program Fit (MEDIUM) — proposed, included for data collection
"""
import json
import logging
import os
import re
import time
from datetime import date, datetime

from openai import OpenAI

logger = logging.getLogger(__name__)

# Evaluator model (higher quality scoring)
EVALUATOR_MODEL = os.environ.get("EVALUATOR_MODEL", "openai/gpt-4.1")

# Flag weights for weighted average
FLAG_WEIGHTS = {
    "strategic_priority_alignment": 3,   # HIGH
    "staff_time_cost": 3,                # HIGH
    "reporting_burden": 2,               # MEDIUM
    "relationship_required": 2,          # MEDIUM
    "timeline_fit": 2,                   # MEDIUM
    "current_vs_new_programs": 3,        # HIGH
    "program_fit": 2,                    # MEDIUM (proposed)
}

ALL_FLAG_IDS = list(FLAG_WEIGHTS.keys())

# Score threshold — grants below this are filtered from digest
SCORE_THRESHOLD = 6.0

# Retry config
MAX_RETRIES = 3
INITIAL_BACKOFF = 2

# Prompt template path
PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")

# Org materials directory — Docker layout is one level up, local is two levels up
_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
_ORG_MATERIALS_DIR = os.environ.get("ORG_MATERIALS_DIR") or (
    os.path.join(_EVAL_DIR, "..", "org-materials")
    if os.path.isdir(os.path.join(_EVAL_DIR, "..", "org-materials"))
    else os.path.join(_EVAL_DIR, "..", "..", "org-materials")
)

_ORG_PROFILE_PATH = os.path.join(_ORG_MATERIALS_DIR, "ORG-PROFILE.md")
_SEARCH_PROFILES_PATH = os.path.join(_ORG_MATERIALS_DIR, "SEARCH-PROFILES.md")


def _load_prompt_template(filename: str) -> str:
    """Load a prompt template from the prompts/ directory."""
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r") as f:
        return f.read()


def _load_org_profile() -> str:
    """Load the organization profile markdown."""
    path = os.path.normpath(_ORG_PROFILE_PATH)
    with open(path, "r") as f:
        return f.read()


def _parse_profile_sections(filepath: str) -> dict:
    """Parse SEARCH-PROFILES.md into profile_id -> section text."""
    with open(filepath, "r") as f:
        content = f.read()

    profiles = {}
    pattern = re.compile(r"^### Profile: `([^`]+)`", re.MULTILINE)
    matches = list(pattern.finditer(content))

    for i, match in enumerate(matches):
        profile_id = match.group(1)
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        profiles[profile_id] = content[start:end].strip()

    return profiles


def _call_llm_with_retry(client: OpenAI, **kwargs):
    """Call OpenAI-compatible API with exponential backoff retry."""
    for attempt in range(MAX_RETRIES):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = INITIAL_BACKOFF * (2 ** attempt)
                logger.warning("LLM API error (attempt %d/%d): %s — retrying in %ds",
                               attempt + 1, MAX_RETRIES, e, wait)
                time.sleep(wait)
            else:
                raise


def compute_weighted_score(flag_scores: dict) -> float:
    """Compute weighted average score from per-flag scores.

    Returns a float rounded to 1 decimal place.
    """
    total_weight = 0
    weighted_sum = 0

    for flag_id, weight in FLAG_WEIGHTS.items():
        score = flag_scores.get(flag_id)
        if score is not None:
            weighted_sum += score * weight
            total_weight += weight

    if total_weight == 0:
        return 0.0

    return round(weighted_sum / total_weight, 1)


def score_grant(
    client: OpenAI,
    grant: dict,
    profile_id: str,
    org_profile: str,
    profile_context: str,
    today: date | None = None,
) -> dict | None:
    """Score a single grant using the 7-flag evaluation framework.

    Calls GPT-4.1 with the grant data, org profile, and profile context.
    Returns dict with flag_scores, weighted_score, and reasoning, or None on failure.
    """
    if today is None:
        today = date.today()

    template = _load_prompt_template("evaluator_prompt.txt")

    funding_range = ""
    if grant.get("funding_min") or grant.get("funding_max"):
        lo = f"${grant['funding_min']:,}" if grant.get("funding_min") else "N/A"
        hi = f"${grant['funding_max']:,}" if grant.get("funding_max") else "N/A"
        funding_range = f"{lo} - {hi}"

    prompt = template.format(
        org_profile=org_profile[:8000],  # Truncate to avoid token limits
        profile_context=profile_context,
        grant_title=grant.get("title") or "N/A",
        grant_funder=grant.get("funder") or "N/A",
        grant_description=(grant.get("description") or "N/A")[:3000],
        grant_eligibility=grant.get("eligibility") or "N/A",
        grant_geography=grant.get("geography") or "N/A",
        grant_deadline=str(grant.get("deadline") or "N/A"),
        grant_funding_range=funding_range or "N/A",
        grant_program_area=grant.get("program_area") or "N/A",
        grant_population_served=grant.get("population_served") or "N/A",
        today_date=today.isoformat(),
    )

    try:
        response = _call_llm_with_retry(
            client,
            model=EVALUATOR_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=500,
        )
        raw_answer = response.choices[0].message.content.strip()

        # Parse JSON response — handle markdown code fences if present
        json_text = raw_answer
        if json_text.startswith("```"):
            # Strip markdown code fences
            json_text = re.sub(r"^```(?:json)?\s*\n?", "", json_text)
            json_text = re.sub(r"\n?```\s*$", "", json_text)

        scores = json.loads(json_text)

        # Validate all flags present and in range
        flag_scores = {}
        for flag_id in ALL_FLAG_IDS:
            val = scores.get(flag_id)
            if val is None:
                logger.warning("Missing flag '%s' in response for grant %s", flag_id, grant["grant_id"])
                flag_scores[flag_id] = 5  # Default to middle
            else:
                flag_scores[flag_id] = max(1, min(10, int(val)))

        reasoning = scores.get("reasoning", "No reasoning provided.")
        weighted_score = compute_weighted_score(flag_scores)

        return {
            "flag_scores": flag_scores,
            "weighted_score": weighted_score,
            "reasoning": reasoning,
        }

    except json.JSONDecodeError as e:
        logger.error("Failed to parse evaluator JSON for grant %s: %s\nRaw: %s",
                      grant["grant_id"], e, raw_answer[:500])
        return None
    except Exception as e:
        logger.error("Evaluator LLM error for grant %s: %s", grant["grant_id"], e)
        return None


def write_score_to_db(
    conn,
    grant_id: str,
    weighted_score: float,
    reasoning: str,
    flag_scores: dict,
    profile_id: str,
):
    """Write evaluation scores to the grants table.

    Updates: score, score_reasoning, score_flags (JSONB), scored_at,
    and appends profile_id to scored_by_profiles array.

    If the grant was already scored by a different profile and the new score
    is higher, the overall score/reasoning is updated. The flag_scores JSONB
    stores per-profile scores.
    """
    cur = conn.cursor()

    # Read current state
    cur.execute(
        "SELECT score, score_flags, scored_by_profiles FROM grants WHERE grant_id = %s",
        (grant_id,),
    )
    row = cur.fetchone()
    if row is None:
        logger.error("Grant %s not found in DB — cannot write score", grant_id)
        cur.close()
        return

    current_score, current_flags, current_profiles = row
    current_flags = current_flags or {}
    current_profiles = current_profiles or []

    # Store per-profile flag scores under the profile_id key
    current_flags[profile_id] = flag_scores

    # Use the highest score across all profiles as the overall score
    if current_score is None or weighted_score > current_score:
        new_score = weighted_score
        new_reasoning = reasoning
    else:
        new_score = current_score
        new_reasoning = None  # Don't overwrite existing reasoning

    # Append profile_id if not already present
    if profile_id not in current_profiles:
        current_profiles.append(profile_id)

    if new_reasoning is not None:
        cur.execute(
            """
            UPDATE grants SET
                score = %s,
                score_reasoning = %s,
                score_flags = %s,
                scored_at = NOW(),
                scored_by_profiles = %s
            WHERE grant_id = %s
            """,
            (new_score, new_reasoning, json.dumps(current_flags),
             current_profiles, grant_id),
        )
    else:
        cur.execute(
            """
            UPDATE grants SET
                score_flags = %s,
                scored_at = NOW(),
                scored_by_profiles = %s
            WHERE grant_id = %s
            """,
            (json.dumps(current_flags), current_profiles, grant_id),
        )

    conn.commit()
    cur.close()
    logger.debug("Wrote score %.1f for grant %s (profile: %s)", weighted_score, grant_id, profile_id)


def run_evaluator(
    conn,
    client: OpenAI,
    candidates: list[dict],
    profile_id: str,
    org_profile: str | None = None,
    profile_sections: dict | None = None,
) -> dict:
    """Run the evaluator on a list of candidate grants for a single profile.

    Scores each grant, writes results to DB, and returns summary stats.

    Returns dict with: scored, above_threshold, below_threshold, errors.
    """
    logger.info("=== Evaluator: %d candidates for profile '%s' ===", len(candidates), profile_id)

    if org_profile is None:
        org_profile = _load_org_profile()

    if profile_sections is None:
        profile_sections = _parse_profile_sections(_SEARCH_PROFILES_PATH)

    profile_context = profile_sections.get(profile_id, "")

    stats = {
        "scored": 0,
        "above_threshold": 0,
        "below_threshold": 0,
        "errors": 0,
    }

    for i, grant in enumerate(candidates, 1):
        grant_id = grant["grant_id"]
        logger.info("[%d/%d] Scoring grant: %s — %s",
                     i, len(candidates), grant_id, grant.get("title", "?")[:60])

        result = score_grant(
            client=client,
            grant=grant,
            profile_id=profile_id,
            org_profile=org_profile,
            profile_context=profile_context,
        )

        if result is None:
            stats["errors"] += 1
            continue

        stats["scored"] += 1

        # Write to DB immediately (intermediate save)
        write_score_to_db(
            conn=conn,
            grant_id=grant_id,
            weighted_score=result["weighted_score"],
            reasoning=result["reasoning"],
            flag_scores=result["flag_scores"],
            profile_id=profile_id,
        )

        if result["weighted_score"] >= SCORE_THRESHOLD:
            stats["above_threshold"] += 1
            logger.info("  Score: %.1f (ABOVE threshold) — %s",
                        result["weighted_score"], result["reasoning"][:100])
        else:
            stats["below_threshold"] += 1
            logger.info("  Score: %.1f (below threshold) — %s",
                        result["weighted_score"], result["reasoning"][:100])

    logger.info(
        "Evaluator complete for '%s': %d scored, %d above threshold, %d below, %d errors",
        profile_id, stats["scored"], stats["above_threshold"],
        stats["below_threshold"], stats["errors"],
    )
    return stats
