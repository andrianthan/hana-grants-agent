# Roadmap: Hanna Center Grants AI Agent

## Overview

This project delivers a 4-phase automated grants pipeline for Hanna Center. Phase 1 builds the org knowledge foundation — the structured profile and vector store that all AI agents read. Phase 2 builds the data pipeline that discovers and ingests grants daily via Grants.gov and web scraping. Phase 3 builds the two AI agents (Prospector and Evaluator) that find and score the best matches. Phase 4 delivers the output that grant staff actually see: a weekly email digest of top-scored opportunities.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Org Profile and Context** - Build Hanna Center's structured profile and vector store foundation
- [ ] **Phase 2: Grant Ingestion Pipeline** - Discover, extract, deduplicate, embed, and schedule daily grant data
- [ ] **Phase 3: Prospecting and Evaluation Agents** - Semantic search, metadata filtering, fit scoring, and ROI analysis
- [ ] **Phase 4: Notifications and Weekly Digest** - Email grant staff the top matched opportunities each week

## Phase Details

### Phase 1: Org Profile and Context
**Goal**: Hanna Center's mission, programs, and past grants are encoded as structured context that the AI agents can reliably query and reason over.
**Depends on**: Nothing (first phase)
**Requirements**: PROF-01, PROF-02, PROF-03
**Success Criteria** (what must be TRUE):
  1. Running the system loads Hanna's org profile (mission, programs, geography, NTEE codes, budget) from a structured file without errors
  2. Past grant application documents are chunked and stored as retrievable RAG documents in the vector database
  3. The system generates a HyDE query (hypothetical ideal grant description) from the org profile that can be used for semantic search
**Plans:** 4 plans
Plans:
- [ ] 01-01-PLAN.md — CDK Infrastructure Stack (RDS, Lambda, API GW, S3, CloudWatch, EventBridge)
- [ ] 01-02-PLAN.md — Org Context Files (ORG-PROFILE.md extension, EVAL-CRITERIA.md, scraper_registry.json)
- [ ] 01-03-PLAN.md — DB Init + Document Ingestion (pgvector schema, PDF extraction, chunking, embedding)
- [ ] 01-04-PLAN.md — HyDE Query Generation (GPT-4o hypothetical grant, Bedrock embedding, hash storage)

### Phase 2: Grant Ingestion Pipeline
**Goal**: The system can autonomously discover new grant opportunities from federal and foundation sources, extract structured metadata, deduplicate, embed, and schedule runs — with no manual steps.
**Depends on**: Phase 1
**Requirements**: INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05, PIPE-01, PIPE-02, PIPE-03
**Success Criteria** (what must be TRUE):
  1. Running the pipeline CLI script fetches new grants from Grants.gov API and at least one foundation website with no manual steps
  2. Each ingested grant is stored with structured metadata: title, funder, deadline, funding range, geography, eligibility, description
  3. Grants already seen in a previous run are skipped via content hash deduplication — no duplicate entries in the vector database
  4. All grant records are embedded and stored in RDS PostgreSQL with pgvector and retrievable by vector similarity search
  5. The pipeline runs automatically on a daily cron schedule (GitHub Actions triggers Lambda via API Gateway) and logs grant counts, errors, and match results
**Plans**: TBD

### Phase 3: Prospecting and Evaluation Agents
**Goal**: The AI pipeline finds the top grant candidates and scores each one against Hanna's profile — returning only the highest-fit opportunities with written reasoning.
**Depends on**: Phase 2
**Requirements**: PROS-01, PROS-02, PROS-03, EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05
**Success Criteria** (what must be TRUE):
  1. The Prospector agent returns the top 50 grant candidates per run using HyDE-based semantic similarity against Hanna's profile
  2. Hard metadata filters (deadline in the future, geography includes CA/Sonoma County, eligibility includes nonprofits) are applied before any candidate is returned
  3. Every candidate is checked against Hanna's eligibility criteria (org type, geography, mission area) before scoring
  4. Every candidate receives a fit score from 1–10 with a written rationale, an ROI estimate (award range vs. staff hours), and a reporting burden flag (light/medium/heavy)
  5. Grants scoring below 6/10 are automatically filtered out and do not appear in the weekly digest
**Plans**: TBD

### Phase 4: Notifications and Weekly Digest
**Goal**: Grant staff receive a weekly email digest containing only the highest-fit opportunities — each with enough context to act without opening another tool. Staff review and approve/skip grants conversationally via Custom GPT, which connects to the AWS backend via Actions.
**Depends on**: Phase 3
**Requirements**: NOTIF-01, NOTIF-02, HITL-01, HITL-02
**Success Criteria** (what must be TRUE):
  1. Grant staff receive a weekly email digest automatically — no manual trigger required
  2. Each digest entry shows grant title, funder, deadline, award range, fit score, and a 2-sentence reasoning summary
  3. The digest only contains grants that passed the Phase 3 scoring threshold (6/10 or above)
  4. Staff can approve or skip grants conversationally inside Custom GPT (ChatGPT) — Custom GPT Actions call the AWS API Gateway backend
  5. System only proceeds to drafting for grants explicitly approved via Custom GPT
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Org Profile and Context | 0/4 | Planning complete | - |
| 2. Grant Ingestion Pipeline | 0/TBD | Not started | - |
| 3. Prospecting and Evaluation Agents | 0/TBD | Not started | - |
| 4. Notifications and Weekly Digest | 0/TBD | Not started | - |
