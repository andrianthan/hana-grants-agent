# Requirements: Hanna Center Grants AI Agent

**Defined:** 2026-03-02
**Updated:** 2026-03-26 (expanded from research + critical corrections)
**Core Value:** Grant staff receive a weekly digest of relevant, scored grant opportunities -- found automatically, no manual research needed.

## v1 Requirements (MVP)

### Org Profile & Context

- [x] **PROF-01**: System stores Hanna Center's org profile as structured context (mission: trauma recovery + resilience; programs: mental health & wellness, residential, trauma-informed training, community support; population: youth + families impacted by trauma; geography: Sonoma County CA; budget; NTEE codes; strategic priorities)
- [x] **PROF-02**: System ingests past grant applications and reports as RAG documents for context
- [ ] **PROF-03**: System generates per-profile HyDE queries (6 department profiles: mental-health-hub, hanna-institute, residential-housing, hanna-academy, recreation-enrichment, general-operations) from SEARCH-PROFILES.md for semantic matching
- [ ] **PROF-04**: System defines 6 department search profiles in org-materials/SEARCH-PROFILES.md with profile_id, display_name, department_lead, active_programs[], target_funders[], evaluation_weight_adjustments, and HyDE seed prompt

### Infrastructure

- [x] **INFRA-01**: AWS CDK stack provisions all infrastructure: RDS PostgreSQL 16.x t4g.micro with pgvector, S3, Secrets Manager (90-day rotation), API Gateway scaffold, EventBridge, CloudWatch (14-day log retention), billing alarms ($40/$50)
- [x] **INFRA-02**: RDS schema includes all 6 tables: grants (with approval_status, skip_reason, score columns), documents, hyde_queries, scraper_health, extraction_failures, pipeline_runs
- [x] **INFRA-03**: Shared db.py module with rotation-aware connection caching, SSL enforcement, and Secrets Manager credential loading
- [ ] **INFRA-04**: Three Lambda deployment packages: scraper Docker (~2GB, Playwright+Chromium), LangGraph Docker (~800MB, AI deps), utility zip (<50MB)

### Grant Ingestion

- [ ] **INGEST-01**: System polls grants.ca.gov API and Grants.gov REST API daily for new grant opportunities (17 sources: 5 APIs + 12 Playwright scrapers)
- [ ] **INGEST-02**: System scrapes 12 Hanna-relevant websites via Playwright on Lambda Docker (CA DHCS, SAMHSA, BSCC, 3 CA foundations, Sonoma County Community Foundation, 5 Sonoma County department portals)
- [ ] **INGEST-03**: System extracts structured metadata per grant via GPT-5.4-mini: title, funder, deadline, funding range, geography, eligibility, description, relationship_required flag (nullable fields for deadline/funding to prevent hallucination)
- [ ] **INGEST-04**: System embeds all grants via Bedrock Titan V2 (1024 dims) and stores in RDS PostgreSQL with pgvector HNSW index
- [ ] **INGEST-05**: System deduplicates grants using SHA-256 content hash (title + funder + deadline + description)
- [ ] **INGEST-06**: Step Functions Standard orchestrates ingestion pipeline (Map State with max_concurrency=5, ToleratedFailurePercentage=30, Catch/Retry blocks per scraper)
- [ ] **INGEST-07**: Scraper health monitoring: scraper_health table with consecutive_zeros tracking, CloudWatch alarm at >=3, SNS alert to developer
- [ ] **INGEST-08**: One-time backfill script loads 500-900 historical grants (batches of 50) before Phase 3 begins
- [ ] **INGEST-09**: Pipeline_runs audit table records every ingestion run with grants_found, status, timestamps, and error details

### Grant Prospecting (Agent 1)

- [ ] **PROS-01**: System performs per-profile HyDE semantic similarity search against grants table (one search per active department profile)
- [ ] **PROS-02**: System applies hard metadata filters: deadline > today, geography includes CA/Sonoma County, eligibility includes nonprofits
- [ ] **PROS-03**: System returns top 50 ranked grant candidates per profile per weekly run, with GPT-5.4-mini pre-filter rejecting ~75% of obvious mismatches

### Grant Evaluation (Agent 2)

- [ ] **EVAL-01**: System checks each candidate against Hanna's hard eligibility criteria (org type: 501(c)(3) nonprofit; geography: CA/Sonoma County; mission area: trauma, mental health, youth, residential, or community resilience)
- [ ] **EVAL-02**: System assigns fit score (1-10) with written reasoning per grant via GPT-5.4, factoring in strategic priority alignment
- [ ] **EVAL-03**: System estimates ROI (award amount range vs. estimated staff hours) -- pending calibration call with Marisa
- [ ] **EVAL-04**: System flags reporting burden level per grant (light / medium / heavy)
- [ ] **EVAL-05**: System filters out grants scoring below 6/10
- [ ] **EVAL-06**: System flags whether a funder relationship is required, preferred, or not required for each grant
- [ ] **EVAL-07**: System flags whether the grant is best suited for current Hanna programs or would require building new programs
- [ ] **EVAL-08**: System flags whether the grant deadline fits Hanna's current funding timeline and staff capacity
- [ ] **EVAL-09**: LangGraph evaluation pipeline runs as single Docker Lambda with Prospector, Evaluator, and Output nodes; writes intermediate scores to RDS after each profile
- [ ] **EVAL-10**: Versioned prompt files stored in repo (prompts/) -- tunable by non-developers without code changes

### Output & Delivery

- [ ] **OUT-01**: Weekly SES email digest (Monday 8am PT) sorted by deadline urgency with 30-day flag
- [ ] **OUT-02**: Each digest entry includes: grant title, funder, deadline, award range, fit score, 2-sentence reasoning, relationship flag, current/future program flag, source link
- [ ] **OUT-03**: Google Sheets pipeline tracker: Sheets Lambda appends scored grants weekly (cumulative, filterable by profile/funder/score)
- [ ] **OUT-04**: CSV export endpoint: GET /grants/export.csv filterable by profile, week, status

### Human-in-the-Loop

- [ ] **HITL-01**: Staff approve or skip grants via one-click email links (approve/skip URLs point to API Gateway endpoints that update approval_status in RDS)
- [ ] **HITL-02**: Staff approve or skip grants conversationally inside Custom GPT (ChatGPT Enterprise) -- Custom GPT Actions call API Gateway
- [ ] **HITL-03**: Skip reason captured as enum: too_small, wrong_geography, already_applied, wrong_program, relationship_required, other
- [ ] **HITL-04**: Approved grants do not re-surface in future digests (approval_status filter)

### API & Interface

- [ ] **API-01**: API Gateway with 6 REST endpoints: GET /grants, GET /grants/{id}, POST /grants/{id}/approve, POST /grants/{id}/skip, GET /profiles, GET /grants/export
- [ ] **API-02**: API key (x-api-key header) + usage plan (10 req/sec, 500 req/day) for all endpoints
- [ ] **API-03**: Custom GPT created in ChatGPT Enterprise with system prompt + OpenAPI spec for Actions connecting to API Gateway

### Pipeline & Scheduling

- [ ] **PIPE-01**: EventBridge Scheduler daily cron (6am PT) triggers Step Functions Standard ingestion pipeline
- [ ] **PIPE-02**: EventBridge Scheduler weekly cron (Monday 7am PT) triggers LangGraph evaluation pipeline
- [ ] **PIPE-03**: All pipeline runs logged to pipeline_runs table and CloudWatch with grant counts, errors, and status

### Operations & Handoff

- [ ] **OPS-01**: RUNBOOK.md for non-technical staff: pipeline health checks, restart procedures, adding sources, updating org profile, cost monitoring, model update instructions with screenshots
- [x] **OPS-02**: CloudWatch billing alarm at $40 (warning) and $50 (critical) with SNS to Marisa + developer; AWS Budget auto-disable at $60
- [ ] **OPS-03**: End-to-end testing of full pipeline (ingest -> evaluate -> digest -> approve/skip) before handoff

## v2 Requirements (Post-MVP)

### Proposal Drafting
- **DRAFT-01**: System generates draft proposal sections for approved grants (executive summary, needs statement, project description, evaluation plan)
- **DRAFT-02**: All draft content grounded in Hanna's RAG context (no hallucinated statistics)
- **DRAFT-03**: Draft output as Google Doc using Hanna proposal template
- **DRAFT-04**: Draft export as .docx for federal portal submissions
- **DRAFT-05**: Email notification to staff when draft is ready with Google Doc link

### Deadline Tracking
- **DEAD-01**: System creates Google Calendar event per matched grant deadline
- **DEAD-02**: System sends email reminders at 30 days, 7 days, and 1 day before deadline

### Additional Channels
- **NOTIF-03**: Slack notification to #grants channel per new match
- **NOTIF-04**: USASpending.gov historical lookup to find funders of similar orgs

### Funder Intelligence (Phase 5)
- **FUND-01**: Funder database from Instrumentl CSV export
- **FUND-02**: IRS 990-PF enrichment via Grantmakers.io
- **FUND-03**: Funder-grant linkage and known_funder scoring boost
- **FUND-04**: Proactive funder monitoring

## Out of Scope

| Feature | Reason |
|---------|--------|
| Automatic grant submission | Humans must review and submit all applications |
| Web app / browser dashboard | Custom GPT + email + Google Sheets covers all interfaces |
| Real-time chat interface | Not needed for automated pipeline |
| Multi-organization support | Hanna-specific for now |
| Mobile app | Out of scope entirely |
| Grant budget builder | Requires org accounting data, high complexity |
| Funder CRM (v1) | Deferred to Phase 5 Funder Match Pipeline |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PROF-01 | Phase 1 | Complete |
| PROF-02 | Phase 1 | Complete |
| PROF-03 | Phase 1 | Pending |
| PROF-04 | Phase 1 | Pending |
| INFRA-01 | Phase 1 | Complete |
| INFRA-02 | Phase 1 | Complete |
| INFRA-03 | Phase 1 | Complete |
| INFRA-04 | Phase 2 | Pending |
| INGEST-01 | Phase 2 | Pending |
| INGEST-02 | Phase 2 | Pending |
| INGEST-03 | Phase 2 | Pending |
| INGEST-04 | Phase 2 | Pending |
| INGEST-05 | Phase 2 | Pending |
| INGEST-06 | Phase 2 | Pending |
| INGEST-07 | Phase 2 | Pending |
| INGEST-08 | Phase 2 | Pending |
| INGEST-09 | Phase 2 | Pending |
| PROS-01 | Phase 3 | Pending |
| PROS-02 | Phase 3 | Pending |
| PROS-03 | Phase 3 | Pending |
| EVAL-01 | Phase 3 | Pending |
| EVAL-02 | Phase 3 | Pending |
| EVAL-03 | Phase 3 | Pending |
| EVAL-04 | Phase 3 | Pending |
| EVAL-05 | Phase 3 | Pending |
| EVAL-06 | Phase 3 | Pending |
| EVAL-07 | Phase 3 | Pending |
| EVAL-08 | Phase 3 | Pending |
| EVAL-09 | Phase 3 | Pending |
| EVAL-10 | Phase 3 | Pending |
| OUT-01 | Phase 4 | Pending |
| OUT-02 | Phase 4 | Pending |
| OUT-03 | Phase 4 | Pending |
| OUT-04 | Phase 4 | Pending |
| HITL-01 | Phase 4 | Pending |
| HITL-02 | Phase 4 | Pending |
| HITL-03 | Phase 4 | Pending |
| HITL-04 | Phase 4 | Pending |
| API-01 | Phase 4 | Pending |
| API-02 | Phase 4 | Pending |
| API-03 | Phase 4 | Pending |
| PIPE-01 | Phase 2 | Pending |
| PIPE-02 | Phase 3 | Pending |
| PIPE-03 | Phase 2 | Pending |
| OPS-01 | Phase 4 | Pending |
| OPS-02 | Phase 1 | Complete |
| OPS-03 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 46 total (4 PROF + 4 INFRA + 9 INGEST + 3 PROS + 10 EVAL + 4 OUT + 4 HITL + 3 API + 3 PIPE + 3 OPS)
- Mapped to phases: 46
- Unmapped: 0

---
*Requirements defined: 2026-03-02*
*Last updated: 2026-03-26 -- expanded from research findings, critical corrections applied (Step Functions Standard, pipeline_runs table, Python 3.13, dated model names, SEARCH-PROFILES.md creation, grants table schema, 3 deployment packages)*
