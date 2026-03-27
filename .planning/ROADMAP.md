# Roadmap: Hanna Center Grants AI Agent

## Overview

This project delivers a 4-phase automated grants pipeline that replaces Instrumentl ($3,000/year) at under $50/month. Phase 1 builds the AWS infrastructure and encodes Hanna Center's org knowledge into a vector store -- the foundation everything reads from. Phase 2 builds the ingestion pipeline: 17 sources (5 APIs + 12 Playwright scrapers) orchestrated by Step Functions Standard, writing grants into RDS PostgreSQL with pgvector embeddings daily. Phase 3 builds the AI evaluation layer: LangGraph runs a Prospector (HyDE search + pre-filter) and Evaluator (7-flag scoring with GPT-5.4) that produce scored, reasoned grant recommendations per department profile. Phase 4 delivers the output staff actually see: SES weekly digest, one-click email approve/skip, Custom GPT conversational layer, Google Sheets tracker, CSV export, and the operational runbook for post-handoff sustainability.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Infrastructure + Org Profile** - AWS stack, RDS schema, org context files, RAG corpus, HyDE embeddings
- [ ] **Phase 2: Ingestion Pipeline + Backfill** - 17-source scraper fan-out, Step Functions Standard, extraction, dedup, embed, health monitoring, backfill
- [ ] **Phase 3: AI Evaluation Pipeline** - LangGraph Prospector + Evaluator, per-profile HyDE search, 7-flag scoring, versioned prompts
- [ ] **Phase 4: Output, HITL, and Handoff** - SES digest, API Gateway, Custom GPT, Google Sheets, CSV export, RUNBOOK, staff onboarding

## Phase Details

### Phase 1: Infrastructure + Org Profile
**Goal**: All AWS infrastructure is deployed, Hanna's org knowledge is encoded as structured context and vector embeddings, and per-department HyDE queries are generated -- so that ingestion and evaluation phases have a foundation to build on.
**Depends on**: Nothing (first phase)
**Requirements**: PROF-01, PROF-02, PROF-03, PROF-04, INFRA-01, INFRA-02, INFRA-03, OPS-02
**Success Criteria** (what must be TRUE):
  1. Running `cdk deploy` creates the full AWS stack (RDS PostgreSQL 16.x t4g.micro with pgvector, S3, Secrets Manager with 90-day rotation, API Gateway with API key + usage plan, EventBridge scaffolds, CloudWatch with 14-day retention, billing alarms at $40/$50)
  2. The RDS schema contains all 6 tables (grants with approval_status/skip_reason/score columns, documents, hyde_queries, scraper_health, extraction_failures, pipeline_runs) with HNSW indexes on vector columns
  3. org-materials/SEARCH-PROFILES.md defines all 6 department profiles (mental-health-hub, hanna-institute, residential-housing, hanna-academy, recreation-enrichment, general-operations) each with profile_id, display_name, department_lead, active_programs, target_funders, evaluation_weight_adjustments, and HyDE seed prompt
  4. Past grant applications and org reference documents are chunked, embedded via Bedrock Titan V2 (1024 dims), and stored in the documents table with correct metadata
  5. Per-profile HyDE queries (6 total) are generated via GPT-5.4 and stored in hyde_queries table with SHA-256 profile hashes for auto-regeneration detection
**Plans**: 5 plans

Plans:
- [ ] 01-01-PLAN.md -- CDK Infrastructure Stack (RDS, Lambda role, API GW, S3, CloudWatch, EventBridge, billing alarms)
- [ ] 01-02-PLAN.md -- Org Context Files (ORG-PROFILE.md extension, EVAL-CRITERIA.md, SEARCH-PROFILES.md with 6 profiles, scraper_registry.json)
- [ ] 01-03-PLAN.md -- DB Schema + Shared Utilities (init_db.py with all 6 tables, db.py rotation-aware module, embeddings.py, chunking.py)
- [ ] 01-04-PLAN.md -- Document Ingestion (PDF extraction, chunking, Bedrock Titan embedding, pgvector storage)
- [ ] 01-05-PLAN.md -- HyDE Query Generation (per-profile GPT-5.4 hypothetical grants, Bedrock embedding, hash-based regeneration)

### Phase 2: Ingestion Pipeline + Backfill
**Goal**: All 17 grant sources flow into the database automatically via a daily Step Functions Standard pipeline, with scraper health monitoring catching silent failures, and a one-time backfill populating 500-900 historical grants for Phase 3 to search.
**Depends on**: Phase 1
**Requirements**: INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05, INGEST-06, INGEST-07, INGEST-08, INGEST-09, INFRA-04, PIPE-01, PIPE-03
**Success Criteria** (what must be TRUE):
  1. Running the Step Functions Standard pipeline fetches grants from all 17 sources (5 APIs + 12 Playwright scrapers) with no manual steps -- one failed scraper does not abort the entire pipeline
  2. Each ingested grant has structured metadata (title, funder, deadline, funding range, geography, eligibility) extracted by GPT-5.4-mini with nullable fields for uncertain values
  3. Grants already in the database are skipped via SHA-256 content hash deduplication -- running the pipeline twice on the same day produces zero new duplicate entries
  4. The scraper_health table tracks consecutive zero-grant days per source, and a CloudWatch alarm fires after 3 consecutive zeros with an SNS alert
  5. The pipeline_runs table records every ingestion run with start/end timestamps, grants found, grants new (post-dedup), status, and any errors
  6. The one-time backfill script has populated 500+ grants in the database, making them searchable by vector similarity for Phase 3
**Plans**: 4 plans

Plans:
- [ ] 02-01-PLAN.md -- Scraper Docker Image + 5 API Parsers (handler, base class, grants.ca.gov, Grants.gov, ProPublica, Grantmakers.io, USASpending)
- [ ] 02-02-PLAN.md -- 12 Playwright Scrapers (CA DHCS, SAMHSA, BSCC, 3 foundations, Sonoma Community Foundation, 5 Sonoma County departments)
- [ ] 02-03-PLAN.md -- Processing Lambdas (Extraction with GPT-5.4-mini, Dedup SHA-256, Store with Bedrock embedding, Health monitoring)
- [ ] 02-04-PLAN.md -- Step Functions Standard Pipeline + EventBridge + Backfill Script

### Phase 3: AI Evaluation Pipeline
**Goal**: The LangGraph evaluation pipeline searches the grants database per department profile using HyDE embeddings, scores candidates with GPT-5.4 against Hanna's 7-flag evaluation framework, and writes scored results to RDS -- so that Phase 4 can deliver them to staff.
**Depends on**: Phase 2
**Requirements**: PROS-01, PROS-02, PROS-03, EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05, EVAL-06, EVAL-07, EVAL-08, EVAL-09, EVAL-10, PIPE-02
**Success Criteria** (what must be TRUE):
  1. The Prospector node performs per-profile HyDE vector similarity search against the grants table, applies hard metadata filters (deadline > today, CA/Sonoma geography, nonprofit eligibility), and GPT-5.4-mini pre-filter rejects ~75% of obvious mismatches
  2. The Evaluator node scores each candidate 1-10 with written reasoning, producing all 7 flags (strategic alignment, program fit, staff time cost, reporting burden, relationship required, timeline fit, current vs. new programs) via GPT-5.4
  3. Grants scoring below 6/10 are filtered out and do not appear in downstream output
  4. The evaluation pipeline writes intermediate scores to RDS after each profile completes -- if Lambda times out on a full-profile run, completed profiles are preserved
  5. All LLM prompt files are stored as versioned files in the prompts/ directory and are readable/editable by non-developers
**Plans**: 2 plans

Plans:
- [ ] 03-01-PLAN.md -- LangGraph Pipeline (Prospector + Evaluator + Output nodes, Docker image, versioned prompts)
- [ ] 03-02-PLAN.md -- Evaluation Deployment (CDK stack, ECR, Lambda config, EventBridge weekly cron)

### Phase 4: Output, HITL, and Handoff
**Goal**: Grant staff receive a weekly email digest with scored grants, can approve/skip via one-click email links or Custom GPT, see cumulative history in Google Sheets, export CSV for reports -- and can sustain the system post-handoff using RUNBOOK.md.
**Depends on**: Phase 3
**Requirements**: OUT-01, OUT-02, OUT-03, OUT-04, HITL-01, HITL-02, HITL-03, HITL-04, API-01, API-02, API-03, OPS-01, OPS-03
**Success Criteria** (what must be TRUE):
  1. Grant staff receive an automated weekly email digest (Monday 8am PT) containing only grants scoring 6+ sorted by deadline urgency, with the most urgent grant in the email subject line
  2. Each digest entry shows grant title, funder, deadline, award range, fit score, 2-sentence reasoning, relationship flag, program flag, and a link to the original source
  3. Staff can approve or skip grants via one-click links in the email (no login required) and via Custom GPT conversational interface -- both write to the same approval_status column in RDS
  4. Skip reason is captured as an enum (too_small, wrong_geography, already_applied, wrong_program, relationship_required, other) and approved grants do not re-surface in future digests
  5. Google Sheets pipeline tracker shows cumulative scored grants across weeks, filterable by profile/funder/score; CSV export endpoint works via bookmarked URL
  6. RUNBOOK.md covers all operational procedures (pipeline health checks, model update instructions with screenshots, adding sources, org profile updates, cost monitoring) and has been reviewed for non-technical comprehensibility
**Plans**: 4 plans
**UI hint**: yes

Plans:
- [ ] 04-01-PLAN.md -- API Lambda (6 REST endpoints: list, detail, approve, skip, profiles, export)
- [ ] 04-02-PLAN.md -- SES Digest + Google Sheets Tracker (HTML email with one-click links, Sheets append)
- [ ] 04-03-PLAN.md -- Deployment + Custom GPT (API Gateway routes, SES verification, system prompt, OpenAPI spec)
- [ ] 04-04-PLAN.md -- RUNBOOK + E2E Testing (operational runbook, end-to-end test script, budget controls)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure + Org Profile | 0/5 | Planned    |  |
| 2. Ingestion Pipeline + Backfill | 0/4 | Planning complete | - |
| 3. AI Evaluation Pipeline | 0/2 | Planning complete | - |
| 4. Output, HITL, and Handoff | 0/4 | Planning complete | - |
