---
phase: 01-org-profile-and-context
plan: 04
subsystem: database
tags: [pdfplumber, pgvector, bedrock, embeddings, rag, chunking]

# Dependency graph
requires:
  - phase: 01-03
    provides: "Shared utils (config.py, db.py, embeddings.py, chunking.py) and documents table schema"
provides:
  - "PDF extraction script (extract_pdfs.py) for org-materials/ corpus"
  - "Document ingestion pipeline (ingest_documents.py) with metadata derivation and ON CONFLICT upserts"
affects: [phase-02-ingestion, phase-03-evaluation, generate-hyde]

# Tech tracking
tech-stack:
  added: [pdfplumber]
  patterns: [filename-metadata-derivation, retry-backoff-for-api, on-conflict-upsert, two-phase-ingestion]

key-files:
  created:
    - scripts/extract_pdfs.py
    - scripts/ingest_documents.py
  modified: []

key-decisions:
  - "Filename-based metadata derivation: first underscore token as funder, 20XX regex as year, with unknown/current-year fallback"
  - "Two-phase ingestion: extracted PDF text first, then supplementary markdown files"
  - "Retry with exponential backoff (3 attempts, starting 1s) for Bedrock embedding calls"

patterns-established:
  - "Filename convention: FUNDER_YEAR_Description.txt for metadata derivation"
  - "Idempotent ingestion via ON CONFLICT (source_file, chunk_index) DO UPDATE"
  - "Embedding dimension verification: assert len(embedding) == EMBEDDING_DIMS at runtime"

requirements-completed: [PROF-02]

# Metrics
duration: 2min
completed: 2026-03-27
---

# Phase 1 Plan 4: Document Extraction and Ingestion Summary

**PDF extraction via pdfplumber and RAG ingestion pipeline with filename-derived metadata, Bedrock Titan embeddings, and ON CONFLICT upserts into pgvector**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-27T06:14:16Z
- **Completed:** 2026-03-27T06:16:24Z
- **Tasks:** 2
- **Files created:** 2

## Accomplishments
- PDF extraction script that scans all org-materials subdirectories (grant-applications, progress-reports, work-plans) and root, with skip-existing idempotency
- Document ingestion pipeline that imports EMBEDDING_DIMS from config.py (not hardcoded), derives funder/year from filenames, and upserts into pgvector
- Retry/backoff for Bedrock API calls (3 attempts, exponential backoff)
- Two-phase ingestion: extracted PDF text files, then supplementary markdown (ORG-PROFILE, FUNDER-DIRECTORY, etc.)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create PDF extraction script** - `1aa7a99` (feat)
2. **Task 2: Create document ingestion script with metadata derivation** - `56f7a0c` (feat)

## Files Created/Modified
- `scripts/extract_pdfs.py` - PDF to text extraction using pdfplumber with layout=True, skips existing files, validates output
- `scripts/ingest_documents.py` - Chunks + embeds + inserts documents with ON CONFLICT upsert, metadata from filenames, retry/backoff

## Decisions Made
- Filename metadata derivation uses first underscore-delimited token as funder and 20XX regex for year, with "unknown"/current-year fallback
- Supplementary markdown files use funder="internal" and year=current year
- Runtime assertion verifies embedding dimensions match EMBEDDING_DIMS constant
- Empty extracted PDFs still get a .txt file written to avoid re-attempting scanned images

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. Scripts require `pdfplumber` from requirements.txt (installed by plan 01-03).

## Next Phase Readiness
- extract_pdfs.py ready to run against org-materials/ corpus
- ingest_documents.py ready to populate documents table after init_db.py creates the schema
- Both scripts depend on utils from plan 01-03 (config.py, db.py, embeddings.py, chunking.py)

---
*Phase: 01-org-profile-and-context*
*Completed: 2026-03-27*
