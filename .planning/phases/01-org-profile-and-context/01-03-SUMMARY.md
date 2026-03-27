---
phase: 01-org-profile-and-context
plan: 03
subsystem: database
tags: [pgvector, postgresql, embeddings, bedrock-titan, psycopg2, secrets-manager]

# Dependency graph
requires:
  - phase: 01-01
    provides: CDK infrastructure (RDS PostgreSQL, Secrets Manager)
provides:
  - "Shared config module with EMBEDDING_DIMS=1024 single source of truth"
  - "Rotation-aware db.py connection module with Secrets Manager credential refresh"
  - "Bedrock Titan V2 embeddings module importing EMBEDDING_DIMS from config"
  - "Multi-strategy chunking module (markdown headers, section labels, double-newline fallback)"
  - "Complete 6-table schema DDL with HNSW indexes and uniqueness constraints"
  - "init_db.py script for schema initialization"
affects: [01-04, 01-05, 02-01, 02-02, 02-03, 02-04, 03-01]

# Tech tracking
tech-stack:
  added: [psycopg2-binary, pgvector, boto3, pdfplumber, openai, pydantic]
  patterns: [rotation-aware-connection, single-source-embedding-dims, multi-strategy-chunking]

key-files:
  created:
    - scripts/utils/config.py
    - scripts/utils/db.py
    - scripts/utils/embeddings.py
    - scripts/utils/chunking.py
    - scripts/init_db.py
    - scripts/requirements.txt
    - scripts/utils/__init__.py
  modified: []

key-decisions:
  - "EMBEDDING_DIMS=1024 centralized in config.py as single source of truth for all embedding consumers"
  - "HNSW indexes use DO/IF NOT EXISTS blocks to be idempotent on reruns"
  - "documents table includes source_file column with UNIQUE(source_file, chunk_index) for idempotent re-ingestion"

patterns-established:
  - "All embedding consumers import EMBEDDING_DIMS from utils.config -- never hardcode dimensions"
  - "All DB connections use utils.db.get_connection -- never create psycopg2.connect() directly"
  - "Schema DDL uses f-string with EMBEDDING_DIMS for vector column definitions"

requirements-completed: [INFRA-02, INFRA-03]

# Metrics
duration: 3min
completed: 2026-03-27
---

# Phase 01 Plan 03: DB Schema + Shared Utilities Summary

**Complete 6-table pgvector schema with HNSW indexes, rotation-aware db.py, Bedrock Titan embeddings module, and multi-strategy chunking -- all using EMBEDDING_DIMS=1024 from shared config**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-27T06:13:41Z
- **Completed:** 2026-03-27T06:17:10Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Shared config module (config.py) establishing EMBEDDING_DIMS=1024 as single source of truth for all embedding consumers
- Rotation-aware db.py with 12-hour credential refresh and "password authentication failed" catch-and-retry for Secrets Manager rotation
- Multi-strategy chunking.py with 3 approaches: markdown headers, 28 grant section labels, double-newline fallback
- Complete init_db.py creating all 6 tables (grants, documents, hyde_queries, scraper_health, extraction_failures, pipeline_runs) with HNSW indexes and uniqueness constraints

## Task Commits

Each task was committed atomically:

1. **Task 1: Create shared config and utility modules** - `315f95e` (feat)
2. **Task 2: Create init_db.py with complete schema** - `878f00c` (feat)

## Files Created/Modified
- `scripts/utils/config.py` - Shared constants: EMBEDDING_DIMS=1024, EMBEDDING_MODEL_ID, AWS_REGION, HYDE_MODEL
- `scripts/utils/db.py` - Rotation-aware PostgreSQL connection via Secrets Manager with 12-hour credential refresh
- `scripts/utils/embeddings.py` - Bedrock Titan V2 embedding function importing EMBEDDING_DIMS from config
- `scripts/utils/chunking.py` - Multi-strategy text chunking (markdown headers, 28 grant section labels, double-newline fallback)
- `scripts/init_db.py` - Schema initialization: 6 tables, HNSW indexes, uniqueness constraints, post-init verification
- `scripts/requirements.txt` - Python dependencies with pinned versions
- `scripts/utils/__init__.py` - Empty package marker

## Decisions Made
- EMBEDDING_DIMS=1024 centralized in config.py -- all consumers import from there, never hardcode
- HNSW index creation wrapped in DO/IF NOT EXISTS blocks for idempotent reruns
- documents table includes source_file column (not in ARCHITECTURE.md) with UNIQUE(source_file, chunk_index) to enable idempotent re-ingestion as specified in plan

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed SyntaxWarning in chunking.py docstring**
- **Found during:** Task 1 (verification)
- **Issue:** Docstring contained `\s` which Python 3.12+ treats as invalid escape sequence
- **Fix:** Rewrote docstring text to avoid backslash escape sequences
- **Files modified:** scripts/utils/chunking.py
- **Verification:** Import succeeds without warnings
- **Committed in:** 315f95e (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor docstring fix. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. init_db.py requires a running RDS instance and valid Secrets Manager ARN (created by Plan 01-01).

## Next Phase Readiness
- All shared utility modules ready for Plan 01-04 (document ingestion) and Plan 01-05 (HyDE generation)
- init_db.py ready to run against the RDS instance deployed by Plan 01-01
- Schema supports all Phase 2-4 use cases: grant ingestion, document chunking, HyDE queries, scraper health monitoring, pipeline audit trail

## Self-Check: PASSED

- All 7 created files verified present on disk
- Commit 315f95e (Task 1) verified in git log
- Commit 878f00c (Task 2) verified in git log

---
*Phase: 01-org-profile-and-context*
*Completed: 2026-03-27*
