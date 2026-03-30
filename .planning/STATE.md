---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: Ready to execute
stopped_at: Completed 01-01-PLAN.md
last_updated: "2026-03-30T03:13:06.252Z"
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 15
  completed_plans: 4
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-26)

**Core value:** Grant staff receive a weekly digest of relevant, scored grant opportunities -- found automatically from 17 CA/federal/foundation sources, no manual research needed. Replaces Instrumentl ($3,000/year) at under $50/month.
**Current focus:** Phase 01 — org-profile-and-context

## Current Position

Phase: 01 (org-profile-and-context) — EXECUTING
Plan: 2 of 5

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 01 P02 | 3min | 2 tasks | 3 files |
| Phase 01 P01 | 5min | 2 tasks | 6 files |
| Phase 01 P04 | 2min | 2 tasks | 2 files |
| Phase 01 P03 | 3min | 2 tasks | 7 files |
| Phase 01 P05 | 2min | 1 tasks | 1 files |
| Phase 01 P01 | 3min | 2 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [2026-03-26]: Step Functions Standard (not Express) -- Express has 5-min hard limit; ingestion runs 5.5-8.5 min; Standard is free at Hanna's volume
- [2026-03-26]: Python 3.13 runtime on Lambda (not 3.12) -- GA, supported through June 2029
- [2026-03-26]: Dated OpenAI model names (gpt-5.4-2026-03-05, gpt-5.4-mini-2026-03-17) as Lambda env vars -- GPT-4o retired March 31, 2026
- [2026-03-26]: Three Lambda deployment packages -- scraper Docker (~2GB), LangGraph Docker (~800MB), utility zip (<50MB)
- [2026-03-26]: pipeline_runs audit table added to schema -- essential for RUNBOOK troubleshooting
- [2026-03-26]: grants table includes approval_status, skip_reason, score, score_reasoning columns
- [2026-03-26]: SEARCH-PROFILES.md requires explicit creation task with all 6 profiles
- [Pre-phase]: Custom GPT (ChatGPT Enterprise) as staff interface -- zero learning curve, $0 additional cost
- [Pre-phase]: LangGraph for evaluation pipeline only; Step Functions Standard for ingestion ETL
- [Pre-phase]: RDS PostgreSQL t4g.micro + pgvector -- publicly accessible, SSL + rotation, ~$13-15/month
- [Pre-phase]: Lambda outside VPC (saves $32/month NAT Gateway)
- [Pre-phase]: grants.ca.gov (primary) + Grants.gov + 12 Playwright scrapers + ProPublica + Grantmakers.io + USASpending.gov
- [Pre-phase]: Amazon Bedrock Titan Text Embeddings V2 -- 1024 dims, ~$0.01/month
- [Pre-phase]: OpenAI real-time API (not Batch) -- saves only $0.19/month, not worth async complexity
- [Pre-phase]: HNSW index (not IVFFlat) -- can create on empty tables, better recall, no tuning
- [Phase 01]: 6-flag evaluation framework with HIGH/MEDIUM weights; 3 flags need calibration with Marisa before Phase 3
- [Phase 01]: 10 scraper targets selected: 3 APIs (grants.ca.gov, Grants.gov, grantmakers.io) + 7 Playwright scrapers for CA/Sonoma sources
- [Phase 01]: Single CDK stack for all Phase 1 resources; Python venv for dependency isolation; 0 NAT gateways for cost savings
- [Phase 01]: Filename metadata derivation: first underscore token as funder, 20XX regex as year
- [Phase 01]: EMBEDDING_DIMS=1024 centralized in config.py as single source of truth for all embedding consumers
- [Phase 01]: SHA-256 hash of full profile section text for HyDE regeneration detection
- [Phase 01]: us-west-1 region for CDK stack (closest to Hanna Center in Sonoma County)
- [Phase 01]: Secrets Manager rotation deferred to Phase 2 with detailed TODO (Lambda-outside-VPC networking conflict)

### Critical Corrections Applied

These corrections from research are reflected in all plan files:

1. Step Functions Standard (not Express) -- 5-min hard limit exceeded by ingestion pipeline
2. pipeline_runs audit table -- added to init_db.py schema
3. Python 3.13 runtime -- in all CDK Lambda definitions
4. Dated OpenAI model names -- as Lambda environment variables
5. SEARCH-PROFILES.md creation -- explicit task in Plan 01-02
6. grants table schema -- includes approval_status, skip_reason, score columns
7. Three Lambda deployment packages -- scraper Docker, LangGraph Docker, utility zip
8. HNSW index (already correct) -- m=16, ef_construction=64

### Pending Todos

- Calibration call with Marisa before Phase 3: ROI labor rate, reporting burden thresholds, timeline fit mechanism
- SES sending address: Marisa's email needed before Phase 4 SES verification
- FUNDER-DIRECTORY.md: needs Hanna's funder relationship history data for known-funder boost (D3)
- pgvector version check at deploy: if 0.8.0, avoid parallel HNSW index builds (CVE-2026-3172)

### Blockers/Concerns

- Hanna Center's org materials (past grants, program guidelines) have been partially received -- 25 PDFs in org-materials/. Additional materials may arrive during Phase 1.
- Flag calibration values for 3 of 7 evaluation flags require 30-min call with Marisa before Phase 3 prompt design.

## Session Continuity

Last session: 2026-03-30T03:13:06.250Z
Stopped at: Completed 01-01-PLAN.md
Resume file: None
Next action: `/gsd:execute 01-01` to begin CDK infrastructure stack
