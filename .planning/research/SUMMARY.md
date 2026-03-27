# Project Research Summary

**Project:** Hanna Center Grants AI Agent
**Domain:** AI-powered nonprofit grant discovery, evaluation, and HITL pipeline on AWS
**Researched:** 2026-03-26
**Confidence:** HIGH (all major decisions validated against current docs and official AWS/OpenAI sources)

---

## Executive Summary

The Hanna Center Grants AI Agent is a purpose-built AWS-native pipeline that replaces Instrumentl ($3,000/year) with a Hanna-specific grant discovery and evaluation system at under $50/month. Research confirms the system should be built as four sequential layers — ingestion (Step Functions Standard + Lambda), processing (embedded in Store Lambda), evaluation (LangGraph), and output (SES + Sheets + API Gateway + Custom GPT) — all connected through a single RDS PostgreSQL t4g.micro instance with pgvector. The technical approach is well-understood and the stack is fully validated. No decisions need to be revisited.

The most significant architectural correction from research is the orchestration type: the existing design specifies Step Functions Express, which has a hard 5-minute execution limit that the ingestion pipeline will exceed (estimated 5.5-8.5 minutes due to Playwright scraping + GPT-5.4-mini extraction). The correct choice is Step Functions Standard, which is free at Hanna's volume (4,000 state transitions/month free tier), has exactly-once semantics, and provides built-in 90-day execution history in the AWS console — all superior for a batch ETL workload. A second schema correction was identified: the database schema was missing a `pipeline_runs` audit table, which is essential for the RUNBOOK.md troubleshooting guide that non-technical staff will rely on post-handoff.

The two highest risks are operational, not technical. Silent scraper degradation — where a government site redesigns and a scraper returns zero grants without raising an error — is the top operational risk and must be addressed in Phase 2 with `consecutive_zeros` tracking and a CloudWatch alarm, not deferred to a hardening phase. Post-handoff system decay is the existential risk: the system is handed off to a 2-person grants team with no AWS or Python experience, and without a tested RUNBOOK.md and a developer maintenance agreement, the system will degrade within 12-18 months regardless of how well it is built. RUNBOOK.md is a Phase 4 critical deliverable, not optional documentation.

---

## Key Findings

### Recommended Stack

All locked decisions are validated. The stack is AWS-native, single-provider for LLMs (OpenAI), and targets <$50/month at steady state (~$18-25/month realized).

See `.planning/research/STACK.md` for full dependency lists, version compatibility matrix, and rejected alternatives.

**Core technologies:**

- **Python 3.13** on Lambda — latest GA runtime, supported through June 2029, no compatibility blockers with any dependency
- **AWS CDK (Python) ~2.244.0** — IaC for entire stack; `cdk deploy` creates everything; `grant_read`/`grant_read_write` methods enforce least-privilege IAM automatically
- **GPT-5.4-mini (`gpt-5.4-mini-2026-03-17`)** — pre-filter and metadata extraction; high-volume cheap calls (~$0.75/$4.50 per 1M tokens)
- **GPT-5.4 (`gpt-5.4-2026-03-05`)** — evaluation, HyDE generation, edge case review; ~$2.50/$15.00 per 1M tokens
- **LangGraph 1.1.0** — evaluation pipeline only (Prospector + Evaluator + Output nodes); Python 3.13 compatible; NOT used for ingestion ETL
- **RDS PostgreSQL 16.x + pgvector 0.8.0** — relational + vector in one; t4g.micro at ~$13-15/month; HNSW index with iterative scan for filtered queries
- **psycopg2-binary 2.9.10** — synchronous PostgreSQL adapter; simpler Lambda deployment than psycopg3; async not needed
- **Pydantic 2.12.0** — two-model pattern required (simple schema for OpenAI `response_format`, full validators applied after response)
- **Amazon Bedrock Titan Text Embeddings V2** — grant and HyDE embeddings; 1024 dimensions; ~$0.01/month; stays within AWS, IAM-authenticated
- **Playwright 1.50+** — headless Chromium scraping; Docker container on Lambda; 1024MB minimum memory; 300s timeout
- **Step Functions Standard** — ingestion ETL orchestration; NOT Express (5-min hard limit exceeded); free at Hanna's volume
- **Amazon SES** — weekly email digest; $0.10/1K emails; AWS-native
- **API Gateway + Lambda** — 6 REST endpoints backing Custom GPT Actions and email one-click links
- **ChatGPT Enterprise Custom GPT** — conversational staff interface; $0 additional cost (Hanna already subscribes)

**Critical version warning:** Use dated OpenAI model names (`gpt-5.4-2026-03-05`, `gpt-5.4-mini-2026-03-17`) as environment variables, never hardcoded aliases. GPT-4o was retired March 31, 2026. Aliases can roll forward on model updates, changing pipeline behavior silently.

**Cost at steady state (30-80 grants/week):** ~$18-25/month. Week 1 backfill (500-900 grants) may spike OpenAI costs to ~$15-20 one-time.

---

### Expected Features

See `.planning/research/FEATURES.md` for competitive positioning vs. Instrumentl and full feature dependency graph.

**Critical path:** T8 (org profile) → T1 (discovery) → T4 (scoring) → T6 (digest) → T7 (HITL). Everything else hangs off this spine.

**Must have (table stakes — v1):**

- T1: Automated grant discovery from CA state + federal sources (17 sources: 5 APIs + 12 Playwright scrapers)
- T2: Content-hash deduplication (SHA-256 of title + funder + deadline + description)
- T3: Hard metadata filtering (geography, deadline, eligibility, program area) before scoring
- T4: AI fit scoring 1-10 with written reasoning (GPT-5.4 Evaluator)
- T5: 7 evaluation flags (strategic alignment, program fit, staff time cost, reporting burden, relationship required, timeline fit, current vs. new programs)
- T6: Weekly SES email digest, Monday 8am PT, sorted by deadline urgency
- T7: HITL approve/skip workflow — confirmed hard requirement from discovery call; one-click email links + Custom GPT both write to same `approval_status` column
- T8: Org profile ingestion (ORG-PROFILE.md + SEARCH-PROFILES.md; 6 department profiles)
- T9: Deadline visibility + 30-day urgency flag in digest
- T10: Skip reason capture (enum: too_small, wrong_geography, already_applied, wrong_program, relationship_required, other)

**Should have (differentiators — v1):**

- D1: Multi-profile HyDE search — biggest technical differentiator; one hypothetical "ideal grant" embedding per department; Mental Health Hub and CTE education grants occupy different embedding space
- D2: Profile-specific evaluation weights (per-department scoring overrides in SEARCH-PROFILES.md)
- D3: Known funder relationship boost (cross-reference FUNDER-DIRECTORY.md; requires Hanna to provide funder history)
- D4: Custom GPT conversational layer (zero learning curve; staff already use ChatGPT Enterprise daily)
- D5: Google Sheets pipeline tracker (cumulative weekly append; Hanna uses Google Workspace for Nonprofits free)
- D6: CSV export endpoint (`GET /grants/export.csv`)
- D7: ROI estimate per grant (award range vs. estimated staff hours; pending calibration call with Marisa)
- D8: Scraper health monitoring (`consecutive_zeros` alarm; essential, not optional)
- D9: Versioned prompts as files (Marisa can tune criteria without developer involvement)
- D10: RUNBOOK.md (critical Phase 4 deliverable; non-negotiable for post-handoff sustainability)

**Defer to v2+:**

- Proposal drafting (A3) — requires extensive RAG corpus not yet available; validate discovery + eval first
- Google Calendar integration (A4) — deadline visibility handled by digest urgency sort
- Slack notifications (A5) — email sufficient for 2-3 staff
- Full funder CRM (A8) — Phase 5 Funder Match Pipeline addresses this

**Features at risk in 10-week timeline:**

- D3 (known funder boost): depends on Hanna providing funder relationship data before Phase 3
- D7 (ROI estimate): gated on 30-minute calibration call with Marisa before Week 7
- T5 flag calibration: three flags need Hanna-specific inputs; all gated on pre-Phase-3 call

---

### Architecture Approach

The system uses four layers with strict data-flow direction (sources → RDS → staff) and clear component boundaries. Each layer can be built, tested, and deployed independently. All Lambda compute is serverless; the only always-on resource is RDS. Three distinct deployment packages keep Docker image sizes manageable: scraper Docker (~1.5-2GB with Chromium), LangGraph Docker (~500-800MB with AI deps), and lightweight utility zip packages (<50MB each). Scrapers never write directly to RDS — they write raw HTML/JSON to S3 and return a pointer; all RDS writes go through Store Lambda (single-writer pattern prevents connection contention).

See `.planning/research/ARCHITECTURE.md` for complete RDS schema DDL, data flow diagram, build order dependencies, and integration risk analysis.

**Major components:**

1. **Ingestion Layer (Step Functions Standard + 17 Lambda functions)** — daily EventBridge cron at 6am PT; Map State with `max_concurrency=5`; Scrape → Extract → Dedup → Store+Embed → Health; backfill of 500-900 grants is a one-time run at end of Phase 2
2. **Agent Pipeline Layer (LangGraph on Lambda)** — weekly EventBridge cron at 7am PT Monday; single Docker Lambda runs Prospector → Evaluator → Output nodes sequentially; writes intermediate scores to RDS after each profile to survive timeout
3. **Output + HITL Layer (API Gateway + SES + Sheets)** — 6 REST endpoints; email one-click links and Custom GPT write to same `approval_status` column; Google Sheets appends scored grants weekly
4. **RDS PostgreSQL t4g.micro** — 6 tables: `grants`, `documents`, `hyde_queries`, `scraper_health`, `extraction_failures`, `pipeline_runs` (the last is a new addition from research; essential for RUNBOOK troubleshooting)

**Key architectural corrections from research:**

- Step Functions Standard (not Express) — Express has 5-min hard limit; Standard is free at Hanna's volume
- HNSW index (not IVFFlat) — HNSW can be created on empty tables; better recall; no tuning required
- `pipeline_runs` table — was missing from original schema; provides audit trail for debugging and RUNBOOK guidance

---

### Critical Pitfalls

See `.planning/research/PITFALLS.md` for all 15 pitfalls with phase-specific warnings, warning signs, and full prevention strategies.

**Top 5 (all rated HIGH confidence):**

1. **Silent scraper degradation** — government site redesigns; scraper returns HTTP 200 with zero grants; Step Functions logs success; no alarm fires; grants silently stop arriving. Prevention: `consecutive_zeros >= 3` CloudWatch alarm + SNS in Phase 2 (not deferred). Also: DOM structure fingerprint hashing per scraper to catch partial failures.

2. **OpenAI model deprecation breaking the pipeline** — GPT-4o was retired March 31, 2026; GPT-5.4 will eventually follow. Prevention: store model IDs as Lambda environment variables (not hardcoded); RUNBOOK.md must include step-by-step model update instructions with screenshots; annual maintenance calendar event in January.

3. **RDS connection pool exhaustion on t4g.micro** — ~80-100 max connections; concurrent scrapers + evaluator + Custom GPT queries can saturate it. Prevention: `max_concurrency=5` in Map State (already planned); shared `db.py` module with module-level connection caching; connection retry with exponential backoff; stagger ingestion (6am) and evaluation (7am Monday) schedules.

4. **Post-handoff system decay** — no developer; non-technical 2-person grants team; system degrades within 12-18 months without maintenance. Prevention: RUNBOOK.md tested with a non-technical person before handoff; $40/$50 billing alarms to Marisa AND developer; AWS Budget auto-disable action at $60; quarterly health check calendar event; explicit developer maintenance agreement.

5. **Pydantic + OpenAI Structured Outputs incompatibility** — OpenAI supports a subset of JSON Schema; `Field(ge=0)`, `Field(pattern=...)`, recursive `$ref` all break the API. Prevention: two-model pattern (simple `*Raw` model for `response_format`, full validators in `*Validated` model applied post-response); test every schema against the live API in Phase 2 before pipeline integration.

**Moderate pitfalls to track:**

- Step Functions Map State cascade failure (Pitfall 8) — one scraper failure aborts entire pipeline; fix: `Catch` blocks + `ToleratedFailurePercentage: 30` on Map State
- Secrets Manager rotation breaking Lambda connections (Pitfall 9) — cached connections hold stale credentials post-rotation; fix: `db.py` catches auth errors and re-fetches credentials from Secrets Manager
- LLM extraction hallucinating deadlines/amounts (Pitfall 5) — nullable fields + explicit "return null if not stated" instructions + confidence field + source URL links in digest

---

## Implications for Roadmap

The architecture research provides an explicit build-order dependency graph. The phase structure is well-determined by hard dependencies. A suggested 4-phase structure follows.

### Phase 1: Infrastructure + Org Profile

**Rationale:** Everything depends on RDS existing, the schema being deployed, and org profile materials being authored. HyDE embeddings must be generated before the Prospector can search. This phase has no external dependencies and cannot begin later without blocking all subsequent phases.

**Delivers:** CDK stack (RDS, S3, Secrets Manager, EventBridge), complete RDS schema with HNSW indexes, ORG-PROFILE.md + SEARCH-PROFILES.md authored, HyDE embeddings generated for all 6 department profiles, documents table loaded with Hanna RAG corpus, FUNDER-DIRECTORY.md populated, `validate_profiles.py` validation script, CloudWatch log retention set to 14 days, billing alarms at $40/$50

**Features from FEATURES.md:** T8 (org profile), D1 (HyDE generation — the most important technical differentiator)

**Pitfalls to avoid:** Pitfall 13 (IVFFlat vs HNSW — use HNSW from day 1; it can be created on an empty table), Pitfall 9 (Secrets Manager rotation — build rotation-aware `db.py` now, not later), Pitfall 15 (SEARCH-PROFILES.md validation — build `validate_profiles.py` before staff ever touch the file), Pitfall 14 (budget creep — set CloudWatch log retention and billing alarms in CDK)

**Research flag:** Skip deeper research. AWS CDK + RDS + pgvector setup is well-documented and the schema DDL is fully specified in ARCHITECTURE.md.

---

### Phase 2: Ingestion Pipeline + Backfill

**Rationale:** The Prospector cannot search until grants exist in the database. The backfill (500-900 grants) is a hard gate for Phase 3 — plan for it to complete by end of Week 4. Scraper health monitoring belongs here, not in a later hardening phase, because silent degradation is the top operational risk.

**Delivers:** scraper_registry.json (17 sources), Playwright Docker image in ECR, Extraction Lambda (GPT-5.4-mini), Dedup Lambda, Store Lambda (with Bedrock embedding), Health Lambda (with `consecutive_zeros` tracking), Step Functions Standard workflow definition, EventBridge daily cron, SQS DLQs per scraper, one-time backfill script, CloudWatch alarm on `consecutive_zeros >= 3`

**Features from FEATURES.md:** T1 (automated grant discovery), T2 (dedup), D8 (scraper health monitoring)

**Stack elements from STACK.md:** Playwright 1.50+, GPT-5.4-mini, Bedrock Titan V2, psycopg2-binary, Step Functions Standard

**Pitfalls to avoid:** Pitfall 1 (silent scraper degradation — `consecutive_zeros` alarm is not optional here), Pitfall 4 (Playwright cold starts — slim Docker image, 1024MB memory, 300s timeout), Pitfall 8 (Map State cascade — `Catch` blocks + `ToleratedFailurePercentage: 30`), Pitfall 5 (hallucinated metadata — nullable deadline/amounts, explicit null instructions in extraction prompt), Pitfall 11 (Pydantic + OpenAI schema — test `GrantMetadataRaw` against live API before building the pipeline)

**Research flag:** May need targeted research on specific scraper targets (Sonoma County BHS, CDSS, specific foundation portals) during implementation. The Playwright + Lambda pattern is well-documented; the per-site parsing logic is custom.

---

### Phase 3: AI Evaluation Pipeline

**Rationale:** LangGraph evaluation requires both a populated grants table (from Phase 2 backfill) and HyDE embeddings (from Phase 1). The calibration call with Marisa must happen before or during this phase to lock in flag thresholds and ROI labor rates. This is the most complex phase — all the differentiating AI logic lives here.

**Delivers:** LangGraph graph definition (Prospector → Evaluator → Output nodes), Prospector node (HyDE similarity search + hard metadata filters + GPT-5.4-mini pre-filter), Evaluator node (GPT-5.4 scoring + 7 flags + reasoning + known-funder boost), profile-specific evaluation weights from SEARCH-PROFILES.md, LangGraph Docker image, Agent Pipeline Lambda, EventBridge weekly cron (Monday 7am PT), versioned prompt files in repo, profile-by-profile intermediate persistence

**Features from FEATURES.md:** T3 (metadata filtering), T4 (fit scoring), T5 (7 flags), D1 (profile-specific HyDE search), D2 (profile weights), D3 (known funder boost — if FUNDER-DIRECTORY.md populated), D7 (ROI estimate — if calibration call complete), D9 (versioned prompts)

**Pitfalls to avoid:** Pitfall 2 (model deprecation — model IDs as env vars from the start), Pitfall 6 (Risk 6: LangGraph timeout — write scores to RDS after each profile, not at the end), Pitfall 7 (HyDE drift — log profile_hash comparison in every run), Pitfall 11 (Pydantic schema on evaluation model — same two-model pattern as extraction)

**Research flag:** Flag for research during planning. The 7-flag scoring prompt design and profile weight calibration have no standard template — they require Hanna-specific prompt engineering and a calibration call with Marisa. ROI calculation also needs her labor rate inputs.

---

### Phase 4: Output, HITL, and Handoff

**Rationale:** Output layer depends on the evaluation pipeline producing scored grants. HITL depends on API Gateway endpoints existing. RUNBOOK.md can only be written once all other phases are complete. This phase also contains the most handoff risk — every deliverable here directly determines whether Hanna can sustain the system without a developer.

**Delivers:** API Gateway + API Lambda (6 endpoints), SES email digest (HTML, Monday 8am PT, urgency sorted), email approve/skip one-click links, Custom GPT creation (system prompt + OpenAPI spec), Google Sheets pipeline tracker (Sheets API Lambda), CSV export endpoint, RUNBOOK.md (tested with non-technical person), staff onboarding session, $40/$50/$60 billing alarms + auto-disable budget action, post-handoff maintenance agreement documentation

**Features from FEATURES.md:** T6 (email digest), T7 (HITL), T9 (deadline urgency), T10 (skip reasons), D4 (Custom GPT), D5 (Google Sheets), D6 (CSV export), D10 (RUNBOOK)

**Pitfalls to avoid:** Pitfall 6 (post-handoff decay — RUNBOOK is a critical deliverable, not documentation polish; test it with a non-technical person; include developer contact info and maintenance agreement), Pitfall 12 (email digest adoption decay — ruthlessly short digest, urgent grant in subject line, track SES open rates), Pitfall 10 (Custom GPT Actions fragility — email digest must work fully without Custom GPT; GPT is convenience layer, not dependency)

**Research flag:** Flag for targeted research during planning on SES email client compatibility (Marisa likely uses Gmail via Google Workspace — test approve/skip one-click links explicitly) and Custom GPT Actions schema quirks (OpenAPI spec must be minimal to reduce migration risk).

---

### Phase Ordering Rationale

- Phase 1 before everything: RDS schema, HyDE embeddings, and org materials are hard dependencies for all subsequent phases
- Phase 2 before Phase 3: the Prospector cannot search without grants in the database; the backfill is a hard gate
- Phase 3 before Phase 4: the digest requires scored grants; the HITL requires the API endpoints; the Custom GPT requires working endpoints to test
- Phase 4 last: RUNBOOK.md can only be written once all other components exist and are tested

The calibration call with Marisa (flag thresholds, ROI labor rate, SES sending address) must occur before Phase 3 prompt design. This is the one external dependency that could block the timeline.

---

### Research Flags

**Needs deeper research during planning:**

- **Phase 3:** 7-flag prompt design and evaluation weight calibration have no standard template — Hanna-specific prompt engineering required; plan a working session with Marisa before locking prompts
- **Phase 4:** Custom GPT Actions OpenAPI schema quirks and Gmail one-click link compatibility need targeted testing before build (not just during QA)

**Standard patterns (skip research-phase):**

- **Phase 1:** AWS CDK + RDS + pgvector setup is extensively documented; schema DDL is fully specified in ARCHITECTURE.md; no research needed
- **Phase 2:** Playwright-on-Lambda Docker pattern is well-documented; Step Functions Map State error handling patterns are documented in AWS docs; no research needed beyond per-site scraper logic
- **Phase 4:** SES + API Gateway + Google Sheets API are standard integrations; no research needed

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All major versions validated against official sources as of March 2026. GPT-5.4/5.4-mini confirmed current. pgvector 0.8.0 on RDS confirmed. LangGraph 1.1.0 Python 3.13 compatibility confirmed. |
| Features | HIGH | Derived from PROJECT.md decisions + discovery call findings + competitive landscape. Table stakes and differentiators are well-defined. At-risk features (D3, D7, T5 calibration) are flagged with mitigations. |
| Architecture | HIGH | Two corrections identified and resolved (Step Functions Standard, pipeline_runs table). All component boundaries, build-order dependencies, and data flow are fully specified. Integration risks documented with mitigations. |
| Pitfalls | HIGH | All critical pitfalls have HIGH confidence ratings in source research. Silent scraper degradation and post-handoff decay are confirmed by multiple independent sources. OpenAI deprecation and Pydantic + Structured Outputs issues are documented with open GitHub issues and official announcements. |

**Overall confidence: HIGH**

### Gaps to Address During Planning

- **SES sending address:** Marisa's exact email address needed before Phase 4 planning can finalize SES verification approach (email address verification vs. domain verification). Email address verification is simpler but limits sending to verified addresses only.
- **Flag calibration values:** Three of 7 evaluation flags (ROI labor rate, reporting burden thresholds, timeline fit mechanism) require a 30-minute calibration call with Marisa before Phase 3 prompt design. Plan this call as a Phase 3 prerequisite.
- **FUNDER-DIRECTORY.md data:** The known funder boost (D3) depends on Hanna providing their funder relationship history. If this data isn't available before Phase 3, D3 ships with name-match only.
- **pgvector 0.8.2 CVE:** pgvector 0.8.2 fixes CVE-2026-3172 (buffer overflow in parallel HNSW builds). RDS may still be on 0.8.0 at deploy time. Check `SELECT extversion FROM pg_extension WHERE extname = 'vector';` at deploy and avoid parallel HNSW index builds if on 0.8.0 (single-threaded build is safe at <10K vectors).

---

## Sources

### Primary (HIGH confidence — official docs, validated March 2026)

- [AWS Step Functions Workflow Types](https://docs.aws.amazon.com/step-functions/latest/dg/choosing-workflow-type.html) — Standard vs. Express; pricing; free tier
- [AWS Step Functions Pricing](https://aws.amazon.com/step-functions/pricing/) — Standard: 4,000 transitions/month free permanent
- [AWS Lambda Python 3.13 Runtime](https://aws.amazon.com/blogs/compute/python-3-13-runtime-now-available-in-aws-lambda/) — GA confirmation
- [pgvector GitHub](https://github.com/pgvector/pgvector) — v0.8.2; HNSW vs. IVFFlat; iterative scan
- [pgvector 0.8.0 on RDS](https://aws.amazon.com/about-aws/whats-new/2024/11/amazon-rds-for-postgresql-pgvector-080/) — availability confirmation
- [AWS Blog: pgvector indexing deep dive](https://aws.amazon.com/blogs/database/optimize-generative-ai-applications-with-pgvector-indexing-a-deep-dive-into-ivfflat-and-hnsw-techniques/) — HNSW vs. IVFFlat decision criteria
- [OpenAI GPT-5.4 Model](https://developers.openai.com/api/docs/models/gpt-5.4) — current as of March 2026
- [OpenAI GPT-5.4-mini Model](https://developers.openai.com/api/docs/models/gpt-5.4-mini) — current as of March 2026
- [OpenAI Deprecations](https://developers.openai.com/api/docs/deprecations) — GPT-4o retired March 31, 2026
- [OpenAI Structured Outputs Guide](https://developers.openai.com/api/docs/guides/structured-outputs) — JSON Schema subset requirements
- [LangGraph PyPI](https://pypi.org/project/langgraph/) — v1.1.0, March 2026
- [LangGraph GitHub Releases](https://github.com/langchain-ai/langgraph/releases) — Python 3.13 compatibility
- [Amazon Bedrock Titan Embeddings](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html) — V2 1024 dimensions, pricing
- [Pydantic PyPI](https://pypi.org/project/pydantic/) — v2.12.5 stable
- [AWS Step Functions Map State failure threshold](https://docs.aws.amazon.com/step-functions/latest/dg/maprun-fail-threshold.html)
- [AWS Secrets Manager rotation troubleshooting](https://docs.aws.amazon.com/secretsmanager/latest/userguide/troubleshoot_rotation.html)

### Secondary (MEDIUM confidence — community, multiple sources agree)

- [Playwright on Lambda challenges](https://www.browsercat.com/post/running-playwright-on-aws-lambda-challenges-solutions) — Docker image approach, memory requirements
- [Playwright Lambda container tips](https://developer.mamezou-tech.com/en/blogs/2024/07/19/lambda-playwright-container-tips/) — image optimization
- [OpenAI Structured Outputs + Pydantic fix](https://medium.com/@aviadr1/how-to-fix-openai-structured-outputs-breaking-your-pydantic-models-bdcd896d43bd) — two-model pattern
- [openai-python Issue #1659](https://github.com/openai/openai-python/issues/1659) — known schema conversion bugs
- [Silent web scraping failures](https://dev.to/anna_6c67c00f5c3f53660978/why-most-web-scraping-systems-fail-silently-and-how-to-design-around-it-40o6)
- [Nonprofit software handoff gaps](https://cathexispartners.com/mistakes-you-might-be-making-with-your-nonprofit-software/)
- [HyDE limitations: domain drift](https://zilliz.com/learn/improve-rag-and-information-retrieval-with-hyde-hypothetical-document-embeddings)
- [Instrumentl features and pricing](https://www.instrumentl.com/solutions/nonprofits)

### Internal (HIGH confidence — primary project documentation)

- PROJECT.md — project constraints, budget, timeline, locked decisions
- `.planning/research/STACK.md` — full technology validation
- `.planning/research/FEATURES.md` — market analysis, feature dependency graph, competitive positioning
- `.planning/research/ARCHITECTURE.md` — complete RDS schema DDL, build order, integration risks
- `.planning/research/PITFALLS.md` — 15 pitfalls with phase-specific warnings

---

*Research completed: 2026-03-26*
*Ready for roadmap: yes*
