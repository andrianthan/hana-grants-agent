---
phase: 01-org-profile-and-context
plan: 05
subsystem: database
tags: [hyde, openai, gpt-5.4, bedrock-titan, pgvector, embeddings, search-profiles]

# Dependency graph
requires:
  - phase: 01-03
    provides: "Shared utils (config.py with HYDE_MODEL, db.py, embeddings.py) and hyde_queries table schema"
  - phase: 01-02
    provides: "SEARCH-PROFILES.md with 6 department profiles and HyDE seed prompts"
provides:
  - "generate_hyde.py CLI script for per-profile HyDE query generation with hash-based regeneration"
  - "Hyde queries in hyde_queries table: 6 profiles with GPT-5.4 hypothetical grants + Bedrock Titan embeddings"
affects: [phase-03-evaluation, prospector-agent]

# Tech tracking
tech-stack:
  added: [openai]
  patterns: [hyde-hypothetical-document-embedding, sha256-profile-hash-regeneration, per-profile-vector-search]

key-files:
  created:
    - scripts/generate_hyde.py
  modified: []

key-decisions:
  - "SHA-256 hash of full profile section text (not just seed prompt) for change detection -- captures funder, weight, and program changes"
  - "GPT-5.4 temperature 0.7 for realistic but varied hypothetical grant announcements (500-800 words)"
  - "Retry/backoff for both OpenAI and Bedrock API calls (3 attempts, exponential backoff starting at 1s)"

patterns-established:
  - "HyDE regeneration pattern: compute hash of source text, compare to stored hash, skip if unchanged"
  - "Profile parsing pattern: regex extraction of ### Profile: `id` sections from SEARCH-PROFILES.md"

requirements-completed: [PROF-04]

# Metrics
duration: 2min
completed: 2026-03-27
---

# Phase 01 Plan 05: HyDE Query Generation Summary

**Per-profile HyDE query generation via GPT-5.4 with Bedrock Titan embeddings and SHA-256 hash-based auto-regeneration for 6 Hanna Center department search profiles**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-27T06:21:00Z
- **Completed:** 2026-03-27T06:23:13Z
- **Tasks:** 1
- **Files created:** 1

## Accomplishments
- HyDE generation script that parses SEARCH-PROFILES.md and extracts all 6 profile definitions with seed prompts
- GPT-5.4 generates realistic hypothetical grant announcements from each profile's HyDE seed prompt
- Bedrock Titan V2 embeds each HyDE text (1024 dims from EMBEDDING_DIMS config constant)
- SHA-256 hash of profile section text enables automatic regeneration when profiles change in SEARCH-PROFILES.md
- ON CONFLICT upsert ensures idempotent re-runs without duplicate entries

## Task Commits

Each task was committed atomically:

1. **Task 1: Create HyDE query generation script** - `8367f57` (feat)

## Files Created/Modified
- `scripts/generate_hyde.py` - Per-profile HyDE query generation: parses SEARCH-PROFILES.md, calls GPT-5.4 for hypothetical grants, embeds via Bedrock Titan, stores in hyde_queries with hash-based regeneration

## Decisions Made
- SHA-256 hash covers the full profile section (not just the seed prompt) so changes to funders, evaluation weights, or programs also trigger regeneration
- Temperature 0.7 for GPT-5.4 generation balances realism with variety in hypothetical announcements
- Both OpenAI and Bedrock calls wrapped in 3-attempt exponential backoff retry for transient API failures

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - script requires `OPENAI_API_KEY` environment variable (standard for OpenAI SDK) and valid `--secret-arn` for RDS connection (created by Plan 01-01).

## Next Phase Readiness
- generate_hyde.py ready to populate hyde_queries table for all 6 department profiles
- Prospector agent (Phase 3) can load per-profile HyDE embeddings for vector similarity search
- Hash-based regeneration ensures HyDE queries stay current when staff update SEARCH-PROFILES.md

---
*Phase: 01-org-profile-and-context*
*Completed: 2026-03-27*
