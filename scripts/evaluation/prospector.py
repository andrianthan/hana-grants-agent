#!/usr/bin/env python3
"""Prospector: per-profile grant search using HyDE embeddings + LLM pre-filter.

Loads the HyDE embedding for each search profile, runs pgvector cosine
similarity against the grants table (top 50), applies hard filters
(deadline, geography, eligibility), then uses GPT-4.1-mini via OpenRouter
for a quick pre-filter pass to reject obvious mismatches.

Returns candidate grants (typically 10-15 per profile) for the Evaluator.
"""
import json
import logging
import os
import re
import time
from datetime import date

from openai import OpenAI

logger = logging.getLogger(__name__)

# Pre-filter model (cheap, fast)
PREFILTER_MODEL = os.environ.get("PREFILTER_MODEL", "openai/gpt-4.1-mini")

# Vector search candidates per profile before filtering
VECTOR_TOP_K = 50

# Retry config for LLM calls
MAX_RETRIES = 3
INITIAL_BACKOFF = 1

# Path to prompt template
PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")

# Profile context extracted from SEARCH-PROFILES.md (loaded once at init)
_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
_ORG_MATERIALS_DIR = os.environ.get("ORG_MATERIALS_DIR") or (
    os.path.join(_EVAL_DIR, "..", "org-materials")
    if os.path.isdir(os.path.join(_EVAL_DIR, "..", "org-materials"))
    else os.path.join(_EVAL_DIR, "..", "..", "org-materials")
)
_SEARCH_PROFILES_PATH = os.path.join(_ORG_MATERIALS_DIR, "SEARCH-PROFILES.md")


def _load_prompt_template(filename: str) -> str:
    """Load a prompt template from the prompts/ directory."""
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r") as f:
        return f.read()


def _parse_profile_sections(filepath: str) -> dict:
    """Parse SEARCH-PROFILES.md and extract profile sections.

    Returns dict mapping profile_id -> full section text (for prompt context).
    """
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


# ---- Geography keywords for hard filter ----
# Grants matching ANY of these are considered geographically eligible
CA_GEO_KEYWORDS = [
    "california", "ca", "sonoma", "northern california", "bay area",
    "north bay", "napa", "marin", "national", "nationwide", "united states",
    "all states", "u.s.", "usa", "statewide",
]


def _passes_geography_filter(geography: str | None) -> bool:
    """Check if a grant's geography field is compatible with Hanna's location.

    Returns True if geography is None/empty (assume national) or if it
    contains any CA-compatible keyword.
    """
    if not geography:
        return True  # No geo restriction = eligible
    geo_lower = geography.lower()
    return any(kw in geo_lower for kw in CA_GEO_KEYWORDS)


def get_hyde_embedding(conn, profile_id: str) -> list[float] | None:
    """Load the HyDE embedding vector for a profile from the hyde_queries table."""
    cur = conn.cursor()
    cur.execute(
        "SELECT embedding FROM hyde_queries WHERE profile_id = %s",
        (profile_id,),
    )
    row = cur.fetchone()
    cur.close()
    if row is None:
        return None
    # pgvector returns the embedding as a numpy array or list
    embedding = row[0]
    if hasattr(embedding, "tolist"):
        return embedding.tolist()
    return list(embedding)


def vector_search(conn, embedding: list[float], top_k: int = VECTOR_TOP_K) -> list[dict]:
    """Run pgvector cosine similarity search against the grants table.

    Returns top_k grants ordered by similarity (most similar first).
    Only returns grants that have an embedding.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            id, grant_id, title, funder, deadline,
            funding_min, funding_max, geography, eligibility,
            description, program_area, population_served,
            source,
            1 - (embedding <=> %s::vector) AS similarity
        FROM grants
        WHERE embedding IS NOT NULL
          AND score IS NULL
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """,
        (str(embedding), str(embedding), top_k),
    )
    columns = [
        "id", "grant_id", "title", "funder", "deadline",
        "funding_min", "funding_max", "geography", "eligibility",
        "description", "program_area", "population_served",
        "source", "similarity",
    ]
    results = []
    for row in cur.fetchall():
        results.append(dict(zip(columns, row)))
    cur.close()
    return results


def apply_hard_filters(grants: list[dict], today: date | None = None) -> list[dict]:
    """Apply hard eligibility filters: deadline > today, geography = CA/national.

    Returns grants that pass all hard filters.
    """
    if today is None:
        today = date.today()

    filtered = []
    for g in grants:
        # Deadline filter: must be in the future (or None = rolling/unknown)
        if g["deadline"] is not None and g["deadline"] < today:
            logger.debug("Filtered out %s: deadline %s is past", g["grant_id"], g["deadline"])
            continue

        # Geography filter
        if not _passes_geography_filter(g.get("geography")):
            logger.debug("Filtered out %s: geography '%s' not CA-eligible", g["grant_id"], g["geography"])
            continue

        filtered.append(g)

    logger.info(
        "Hard filters: %d -> %d grants (removed %d)",
        len(grants), len(filtered), len(grants) - len(filtered),
    )
    return filtered


def llm_prefilter(
    client: OpenAI,
    grants: list[dict],
    profile_context: str,
) -> list[dict]:
    """Use GPT-4.1-mini to pre-filter grants, rejecting obvious mismatches.

    Calls the LLM once per grant with a quick keep/reject decision.
    Returns only grants marked KEEP.
    """
    template = _load_prompt_template("prefilter_prompt.txt")
    kept = []

    for g in grants:
        funding_range = ""
        if g.get("funding_min") or g.get("funding_max"):
            lo = f"${g['funding_min']:,}" if g.get("funding_min") else "N/A"
            hi = f"${g['funding_max']:,}" if g.get("funding_max") else "N/A"
            funding_range = f"{lo} - {hi}"

        prompt = template.format(
            profile_context=profile_context,
            grant_title=g.get("title") or "N/A",
            grant_funder=g.get("funder") or "N/A",
            grant_description=(g.get("description") or "N/A")[:2000],
            grant_eligibility=g.get("eligibility") or "N/A",
            grant_geography=g.get("geography") or "N/A",
            grant_deadline=str(g.get("deadline") or "N/A"),
            grant_funding_range=funding_range or "N/A",
        )

        try:
            response = _call_llm_with_retry(
                client,
                model=PREFILTER_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=100,
            )
            answer = response.choices[0].message.content.strip()

            if answer.upper().startswith("KEEP"):
                kept.append(g)
                logger.debug("KEEP: %s — %s", g["grant_id"], answer)
            elif answer.upper().startswith("REJECT"):
                logger.info("REJECT: %s — %s", g["grant_id"], answer)
            else:
                # Ambiguous response — keep to be safe
                kept.append(g)
                logger.warning("Ambiguous pre-filter response for %s, keeping: %s", g["grant_id"], answer)

        except Exception as e:
            # On error, keep the grant (fail open)
            kept.append(g)
            logger.error("Pre-filter LLM error for %s, keeping: %s", g["grant_id"], e)

    logger.info(
        "LLM pre-filter: %d -> %d grants (rejected %d)",
        len(grants), len(kept), len(grants) - len(kept),
    )
    return kept


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


def run_prospector(
    conn,
    client: OpenAI,
    profile_id: str,
    profile_sections: dict | None = None,
) -> list[dict]:
    """Run the full prospector pipeline for a single search profile.

    1. Load HyDE embedding for the profile
    2. Vector search (top 50)
    3. Hard filters (deadline, geography)
    4. LLM pre-filter (reject obvious mismatches)

    Returns list of candidate grant dicts.
    """
    logger.info("=== Prospector: profile '%s' ===", profile_id)

    # Load profile context for LLM prompts
    if profile_sections is None:
        profile_sections = _parse_profile_sections(_SEARCH_PROFILES_PATH)

    profile_context = profile_sections.get(profile_id, "")
    if not profile_context:
        logger.warning("No profile section found for '%s' in SEARCH-PROFILES.md", profile_id)

    # Step 1: Load HyDE embedding
    embedding = get_hyde_embedding(conn, profile_id)
    if embedding is None:
        logger.error("No HyDE embedding found for profile '%s'. Run generate_hyde.py first.", profile_id)
        return []

    logger.info("Loaded HyDE embedding (%d dims) for '%s'", len(embedding), profile_id)

    # Step 2: Vector search
    candidates = vector_search(conn, embedding, top_k=VECTOR_TOP_K)
    logger.info("Vector search returned %d candidates", len(candidates))

    if not candidates:
        return []

    # Step 3: Hard filters
    candidates = apply_hard_filters(candidates)

    if not candidates:
        logger.warning("All candidates filtered out by hard filters for '%s'", profile_id)
        return []

    # Step 4: LLM pre-filter
    candidates = llm_prefilter(client, candidates, profile_context)

    logger.info("Prospector complete for '%s': %d candidates", profile_id, len(candidates))
    return candidates
