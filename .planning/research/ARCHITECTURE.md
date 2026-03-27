# Architecture Patterns: AI-Powered Grant Discovery + Evaluation + HITL Pipeline

**Domain:** AI-powered nonprofit grant pipeline on AWS
**Researched:** 2026-03-26
**Overall confidence:** HIGH

---

## Recommended Architecture

Four distinct layers with clear boundaries. Data flows one direction: sources -> RDS -> staff. Each layer can be built, tested, and deployed independently.

```
  Sources (17)          Ingestion (SFN)        Processing         Agent (LangGraph)       Output
 +-----------+     +------------------+    +--------------+    +------------------+    +-----------+
 | grants.ca |     | Map State fan-out|    | Chunker      |    | Prospector       |    | SES email |
 | grants.gov| --> | max_concurrency=5| -->| Embedder     | -->| (GPT-5.4-mini)   | -->| Sheets    |
 | 12 scrapers|    | Extract/Dedup/   |    | (Bedrock     |    | Evaluator        |    | CSV export|
 | 3 APIs     |    | Store/Health     |    |  Titan V2)   |    | (GPT-5.4)        |    | Custom GPT|
 +-----------+     +------------------+    +--------------+    +------------------+    +-----------+
                          |                      |                     |                      |
                          v                      v                     v                      v
                   +------------------------------------------------------------------+
                   |                    RDS PostgreSQL + pgvector                      |
                   |  grants | documents | hyde_queries | scraper_health | extraction_ |
                   |                                                      failures    |
                   +------------------------------------------------------------------+
```

---

## Critical Correction: Standard Workflow, Not Express

**The existing architecture specifies Step Functions Express. This is wrong.**

Express Workflows have a **hard 5-minute execution limit**. The ingestion pipeline will exceed this:

| Phase | Estimated Duration |
|-------|-------------------|
| Map State: 17 scrapers at max_concurrency=5 (4 batches) | 4-6 min (worst case: JS-heavy sites with Playwright) |
| Extraction Lambda (GPT-5.4-mini per grant) | 1-2 min (30-80 grants x 1-2s each) |
| Dedup + Store + Health | 30s |
| **Total** | **5.5-8.5 min** |

**Use Step Functions Standard instead.** The cost difference is negligible:

| Metric | Express | Standard |
|--------|---------|----------|
| Max duration | 5 minutes | 1 year |
| Pricing | $1/million executions + duration | $0.025/1,000 state transitions |
| Free tier | None permanent | **4,000 transitions/month (permanent)** |
| Hanna's usage | 1 run/day x ~25 transitions = ~750/month | **$0.00 (within free tier)** |
| Execution model | At-least-once | Exactly-once |
| Execution history | CloudWatch Logs only | Built-in console history (90 days) |

Standard is actually better for this use case: exactly-once semantics (no duplicate grant inserts from re-execution), built-in execution history in the console (no CloudWatch parsing needed), and zero cost at Hanna's volume.

**Confidence: HIGH** -- verified against [AWS official docs](https://docs.aws.amazon.com/step-functions/latest/dg/choosing-workflow-type.html) and [pricing page](https://aws.amazon.com/step-functions/pricing/).

---

## Component Boundaries

### Layer 1: Ingestion (Step Functions Standard + Lambda)

**Scope:** Get grant data from sources into RDS.
**Trigger:** EventBridge Scheduler daily cron (6am PT).
**Owner:** Step Functions Standard workflow `GrantIngestionPipeline`.

| Component | Responsibility | Talks To | Lambda Type |
|-----------|---------------|----------|-------------|
| EventBridge Scheduler | Daily trigger | Step Functions | N/A (AWS service) |
| Step Functions Standard | Orchestrate full ingestion | All ingestion Lambdas | N/A (AWS service) |
| Scraper Lambdas (x17) | Fetch raw grant data from sources | S3 (write raw), Step Functions (return metadata) | Docker (Playwright scrapers need Chromium) |
| Extraction Lambda | GPT-5.4-mini structured metadata extraction | OpenAI API, Secrets Manager | Docker (shares image with scrapers) |
| Dedup Lambda | Content hash check against RDS | RDS (read grants table) | Zip (lightweight) |
| Store Lambda | Upsert grant + raw doc to S3 | RDS (write), S3 (write) | Zip (lightweight) |
| Health Lambda | Update scraper_health, emit CloudWatch metrics | RDS (write), CloudWatch (put metric), SNS (alert) | Zip (lightweight) |

**Key boundary rule:** Scraper Lambdas never write to RDS. They write raw HTML/JSON to S3 and return a metadata pointer. All RDS writes happen in Store Lambda -- single writer pattern prevents connection contention.

### Layer 2: Processing (Embedded in Ingestion)

**Scope:** Chunk grant text, generate embeddings, store vectors.
**Note:** Processing is not a separate pipeline run. It happens inside the Store Lambda as a sub-step of ingestion. When Store Lambda upserts a new grant, it also:
1. Chunks the description text (simple paragraph splitting, no complex chunking needed at grant scale)
2. Calls Bedrock Titan V2 to generate a 1024-dim embedding
3. Stores the embedding in the grants table `embedding` column

**Why not separate:** Grant descriptions are short (500-2000 words). No need for sophisticated chunking strategies used in large-document RAG. One embedding per grant, generated at ingest time. Separating this into its own pipeline would add latency (hours between ingest and searchability) without benefit.

**The `documents` table is separate** -- it stores Hanna's org RAG corpus (past grants, program guidelines, org profile) which is loaded manually during Phase 1 setup, not during daily ingestion.

### Layer 3: Agent Pipeline (LangGraph on Lambda)

**Scope:** Score grants against Hanna's profiles and surface recommendations.
**Trigger:** EventBridge Scheduler weekly (Monday 7am PT) OR on-demand via Custom GPT.
**Owner:** Single Lambda function running LangGraph graph.

| Component | Responsibility | Talks To | Lambda Type |
|-----------|---------------|----------|-------------|
| Prospector Node | HyDE similarity search + metadata filter + GPT-5.4-mini pre-filter | RDS (pgvector query), OpenAI API | Docker (LangGraph + deps) |
| Evaluator Node | 7-flag scoring with profile-specific weights | OpenAI API, RDS (read org context) | Same Lambda |
| Output Node | Send SES digest, update Sheets, update RDS | SES, Sheets API, RDS (write scores) | Same Lambda |

**Single Lambda, single Docker image.** LangGraph nodes are Python functions within one graph -- they do not need separate Lambdas. The graph runs synchronously within one Lambda invocation.

**Cold start:** Docker image with LangGraph + langchain + openai + psycopg2 + google-api-python-client is ~500MB-1GB. Cold start ~3-5s. Acceptable for a weekly batch job.

**Timeout:** Set Lambda timeout to 15 minutes (max). Weekly eval of ~50 grants x ~3s per eval = ~2.5 min. Well within limits even with retries.

### Layer 4: Output (SES + Sheets + API Gateway)

**Scope:** Deliver results to staff and accept their decisions.

| Component | Responsibility | Talks To |
|-----------|---------------|----------|
| SES email digest | Weekly delivery, approve/skip links | Staff inbox |
| Google Sheets Lambda | Append scored grants to shared sheet | Google Sheets API |
| API Gateway + Lambda | REST endpoints for Custom GPT Actions + email callbacks | RDS (read/write) |
| Custom GPT | Conversational interface for staff | API Gateway |

**API Gateway endpoints (6 routes, 1 Lambda):**

```
GET  /grants                    -> list grants (filter: profile, week, status)
GET  /grants/{grant_id}         -> full grant detail
POST /grants/{grant_id}/approve -> set approval_status=approved
POST /grants/{grant_id}/skip    -> set approval_status=skipped + skip_reason
GET  /grants/profiles           -> list search profiles
GET  /grants/export             -> CSV download (filter: profile, week, status)
```

All routes handled by one API Lambda (zip deployment, lightweight). API Gateway validates `x-api-key` before Lambda is invoked.

---

## Data Flow: How a Grant Moves from Source to Staff

```
Step 1: SCRAPE
  EventBridge (daily 6am PT)
    -> Step Functions Standard
    -> Map State (max_concurrency=5)
    -> Scraper Lambda reads grants.ca.gov API
    -> Returns: {source: "grants-ca-gov", raw_s3_key: "s3://bucket/raw/2026-03-26/grants-ca-gov/abc123.json", grant_count: 12}

Step 2: EXTRACT
  Step Functions -> Extraction Lambda
    -> Reads raw JSON from S3
    -> GPT-5.4-mini: extract title, funder, deadline, funding range, geography, eligibility, etc.
    -> Pydantic validation (retry up to 2x on failure)
    -> Returns: list of GrantMetadata objects
    -> On persistent failure: log to extraction_failures table, continue

Step 3: DEDUP
  Step Functions -> Dedup Lambda
    -> Content hash (SHA-256 of title + funder + deadline + description)
    -> Check against grants.grant_id in RDS
    -> Skip if exists, pass through if new
    -> Returns: list of new grants only

Step 4: STORE + EMBED
  Step Functions -> Store Lambda
    -> Upsert each new grant into grants table
    -> Generate Bedrock Titan V2 embedding (1024-dim)
    -> Store embedding in grants.embedding column
    -> Upload raw doc to S3 (raw_s3_key reference)

Step 5: HEALTH
  Step Functions -> Health Lambda
    -> Upsert scraper_health row per source (grant_count, last_success_at)
    -> If consecutive_zeros >= 3 for any scraper: CloudWatch metric -> SNS alert

Step 6: PROSPECT (weekly, Monday 7am PT)
  EventBridge -> LangGraph Lambda
    -> For each of 6 profiles:
      -> Load profile HyDE embedding from hyde_queries table
      -> pgvector cosine similarity search: top 50 nearest grants
      -> Hard metadata filters (deadline > today, geography CA, eligibility nonprofit)
      -> GPT-5.4-mini pre-filter: reject obvious mismatches (~75% rejection rate)
      -> Pass ~12 candidates to Evaluator

Step 7: EVALUATE
  LangGraph Evaluator Node (same Lambda invocation)
    -> For each candidate:
      -> Load profile-specific weights from SEARCH-PROFILES.md
      -> GPT-5.4: score 1-10 with 7 flags + written reasoning
      -> Cross-reference FUNDER-DIRECTORY.md for known_funder boost
      -> Store score + reasoning + flags in grants table

Step 8: DELIVER
  LangGraph Output Node (same Lambda invocation)
    -> SES: send weekly digest email sorted by deadline ascending
    -> Sheets Lambda: append scored grants to Google Sheet
    -> Update grants.approval_status = 'pending' for all newly scored grants

Step 9: HUMAN DECISION
  Staff reads email Monday morning
    -> Clicks [Approve] link -> API Gateway -> POST /grants/{id}/approve -> RDS update
    -> Clicks [Skip] link -> API Gateway -> POST /grants/{id}/skip -> RDS update
    -> OR opens Custom GPT, asks questions, approves/skips conversationally

Step 10: DRAFT (v2, post-launch)
  Staff says "Draft the proposal" in Custom GPT
    -> API Gateway -> LangGraph Lambda (separate invocation)
    -> Load approved grant + Hanna RAG corpus from documents table
    -> GPT-5.4 generates proposal sections
    -> Output to Google Doc
```

---

## Lambda Packaging Strategy

Three distinct Lambda deployment packages, not one monolith:

### Package 1: Scraper Docker Image (ECR)

**Used by:** All 17 scraper Lambdas (same image, different config via scraper_registry.json)
**Base image:** `mcr.microsoft.com/playwright/python:v1.44.0-focal` (or latest)
**Contents:** playwright-core + Chromium, requests, beautifulsoup4, scraper_registry.json
**Estimated size:** ~1.5-2GB (Chromium is the bulk)
**Memory:** 1536MB-3072MB (Chromium needs RAM)
**Timeout:** 300s (5 min -- some JS-heavy sites are slow)
**Cold start:** 5-10s (Docker + Chromium init). Acceptable -- scrapers run daily in batch, cold start happens once per day.

**Why single image for all scrapers:** scraper_registry.json maps scraper_id to config (URL, parse strategy, selectors). The Lambda handler reads the scraper_id from the Step Functions input and dispatches to the right parser. Adding a new source = one JSON entry + one parser function. No new Lambda function, no new Docker image, no new IAM role.

**API-only scrapers** (grants.ca.gov, grants.gov, ProPublica, Grantmakers.io) do not need Playwright/Chromium. However, packaging them in the same Docker image avoids managing a second deployment package. The unused Chromium adds cold start latency but the API scrapers finish in <5s regardless. If cold start becomes an issue later, split API scrapers into a separate zip package.

### Package 2: LangGraph Docker Image (ECR)

**Used by:** Agent Pipeline Lambda (Prospector + Evaluator + Output nodes)
**Base image:** `public.ecr.aws/lambda/python:3.12`
**Contents:** langgraph, langchain-openai, openai, psycopg2-binary, boto3, google-api-python-client, pydantic
**Estimated size:** ~500MB-800MB
**Memory:** 1024MB (LLM calls are I/O-bound, not CPU/memory)
**Timeout:** 900s (15 min max -- weekly eval of ~50 grants)
**Cold start:** 3-5s (Python deps import). Acceptable -- runs once per week.

### Package 3: API + Utility Zip Packages

**Used by:** API Gateway Lambda, Dedup Lambda, Store Lambda, Health Lambda, Sheets Lambda, Extraction Lambda
**Format:** Zip deployment (no Docker needed)
**Contents:** psycopg2-binary (Lambda layer), boto3 (built-in), pydantic
**Estimated size:** <50MB per function (or shared layer)
**Memory:** 256MB-512MB
**Timeout:** 30-60s
**Cold start:** <1s (lightweight Python)

**Extraction Lambda note:** This Lambda calls GPT-5.4-mini for metadata extraction. It needs `openai` and `pydantic` but not Playwright. Could be zip with an openai layer, or could share the LangGraph Docker image. Zip is simpler and cheaper (faster cold start).

### Lambda Layer Strategy

One shared Lambda Layer for common dependencies:
- `psycopg2-binary` (RDS access)
- `pydantic` (validation)
- `openai` (Extraction Lambda only)

This layer is shared across all zip-packaged Lambdas to avoid duplicating dependencies.

---

## pgvector Index Strategy

**Use HNSW, not IVFFlat.** The existing schema specifies IVFFlat -- change this.

| Factor | HNSW | IVFFlat |
|--------|------|---------|
| Query speed | ~1.5ms | ~2.4ms |
| Recall accuracy | Higher (better for grant matching) | Lower without tuning |
| Can create on empty table | Yes | No (needs data first for centroids) |
| Build time | Slower (but irrelevant at grant scale) | Faster |
| Memory | 2-5x more | Less |
| Tuning required | Minimal | Requires tuning nlist/nprobe |

At Hanna's scale (~1,000-5,000 grants over 6 months), both indexes are trivially fast. HNSW wins because:
1. **Can be created on empty tables** -- deploy schema in Phase 1 before any data exists
2. **No tuning** -- IVFFlat requires choosing nlist and nprobe values based on data distribution
3. **Better recall** -- grant matching is a precision task; missing a good grant is worse than a 1ms speed difference

**Updated index DDL:**

```sql
-- Replace IVFFlat with HNSW
CREATE INDEX ON grants USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE INDEX ON hyde_queries USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- HNSW parameters:
-- m = 16 (default, number of neighbors per layer -- good for <100K vectors)
-- ef_construction = 64 (default, build-time search breadth -- higher = better recall, slower build)
-- At query time: SET hnsw.ef_search = 40 (default, can increase for higher recall)
```

**Confidence: HIGH** -- verified against [AWS blog on pgvector indexing](https://aws.amazon.com/blogs/database/optimize-generative-ai-applications-with-pgvector-indexing-a-deep-dive-into-ivfflat-and-hnsw-techniques/) and [pgvector GitHub docs](https://github.com/pgvector/pgvector).

---

## Build Order Dependencies

This is the critical section for roadmap phasing. Arrows mean "blocks."

```
Phase 1 (Weeks 1-2): INFRASTRUCTURE
  ├── CDK stack: RDS + pgvector + S3 + Secrets Manager + EventBridge
  │     ↓ (everything depends on RDS existing)
  ├── RDS schema: grants, documents, hyde_queries, scraper_health, extraction_failures
  │     ↓ (schema must exist before any data writes)
  ├── ORG-PROFILE.md + SEARCH-PROFILES.md authored
  │     ↓ (profiles needed before HyDE generation)
  ├── generate_hyde.py: create HyDE embeddings for 6 profiles
  │     ↓ (HyDE queries must exist before Prospector can search)
  └── documents table: load org RAG corpus (past grants, program guidelines)

Phase 2 (Weeks 3-4): INGESTION
  DEPENDS ON: RDS schema, S3 bucket, Secrets Manager secrets
  ├── scraper_registry.json (defines all 17 sources)
  │     ↓ (registry needed before scraper code)
  ├── Scraper Docker image (Playwright + Chromium + all parsers)
  │     ↓ (image must be in ECR before Step Functions can invoke)
  ├── Extraction Lambda (GPT-5.4-mini metadata extraction)
  │     ↓ (extraction needed before dedup can check hashes)
  ├── Dedup Lambda (content hash check)
  │     ↓ (dedup needed before store to avoid duplicates)
  ├── Store Lambda (RDS upsert + embedding + S3)
  │     ↓ (store needed before health can report)
  ├── Health Lambda (scraper_health upsert + CloudWatch)
  ├── Step Functions Standard workflow definition (CDK)
  │     ↓ (workflow must exist before EventBridge can trigger)
  ├── EventBridge daily cron
  └── Initial backfill script (batches of 50, separate from daily pipeline)
      NOTE: Backfill is a one-time bulk load (500-900 grants).
            Must run AFTER Store Lambda is deployed.
            Must run BEFORE Phase 3 (Prospector needs grants to search).

Phase 3 (Week 4-5): AGENT PIPELINE
  DEPENDS ON: grants table populated (backfill complete), HyDE queries in hyde_queries table
  ├── LangGraph graph definition (nodes, edges, state schema)
  ├── Prospector node: pgvector search + metadata filter + GPT-5.4-mini pre-filter
  │     ↓ (prospector outputs feed evaluator)
  ├── Evaluator node: GPT-5.4 scoring + 7 flags + reasoning
  │     ↓ (evaluator outputs feed output node)
  ├── Output node: SES digest + Sheets append + RDS score update
  ├── LangGraph Docker image (ECR)
  ├── Agent Pipeline Lambda deployment
  └── EventBridge weekly cron (Monday 7am PT)

Phase 4 (Week 5-6): OUTPUT + HITL
  DEPENDS ON: Agent pipeline scoring grants, API Gateway deployed
  ├── API Gateway + API Lambda (6 endpoints)
  │     ↓ (endpoints needed before Custom GPT can call them)
  ├── SES verification (Marisa's email address -- one-click, no DNS)
  │     ↓ (SES must be verified before digest can send)
  ├── Custom GPT creation (system prompt + OpenAPI spec for Actions)
  │     ↓ (GPT needs working endpoints to test)
  ├── Email approve/skip one-click links (point to API Gateway)
  ├── Google Sheets pipeline tracker
  ├── CSV export endpoint
  ├── RUNBOOK.md
  └── End-to-end testing + staff onboarding
```

### Key Dependency Chain (Critical Path)

```
RDS schema -> Store Lambda -> Backfill script -> grants populated
                                                        |
HyDE generation ────────────────────────────────────────┤
                                                        v
                                              Prospector can search
                                                        |
                                                        v
                                              Evaluator can score
                                                        |
                                                        v
                                              Digest can be sent
                                                        |
                                                        v
                                              Staff can approve/skip
```

**The backfill is a hard gate.** Phase 3 cannot begin meaningful testing until there are grants in the database to search. Plan for backfill to complete by end of Week 4. If scrapers slip, the Prospector has nothing to prospect.

---

## Integration Risks (Where Components Could Fail Silently)

### Risk 1: Scraper Silent Degradation (MEDIUM-HIGH)

**What:** A scraper returns 0 grants but doesn't throw an error (website changed layout, API changed schema, rate limit hit with 200 OK).

**Why silent:** The Step Functions Map State sees a successful Lambda completion (exit code 0, no exception). The scraper just returns `{grant_count: 0}`. Over time, a source dries up and nobody notices.

**Mitigation:** Already designed -- the Health Lambda tracks `consecutive_zeros` and alerts at >=3. But validate that the Health Lambda receives the grant_count from every scraper, including the zero case. Step Functions Map State output must include grant_count even for 0-result runs.

**Detection gap:** If a scraper returns *some* grants but misses new ones (partial failure), the consecutive_zeros alarm won't fire. No current mitigation for this. Possible v2 enhancement: compare grant_count against historical average and alert on significant drops.

### Risk 2: GPT-5.4-mini Extraction Drift (MEDIUM)

**What:** A model update changes GPT-5.4-mini's output format subtly (e.g., date format changes from "2026-04-15" to "April 15, 2026"). Pydantic validation catches the hard failures, but subtle schema compliance issues (valid JSON, wrong semantics) pass through.

**Why silent:** Pydantic validates structure, not semantics. A `geography: "California"` vs `geography: "CA"` difference won't trigger a validation error but will break metadata filtering downstream.

**Mitigation:**
1. Pydantic validators with explicit enum constraints where possible (geography, program_area)
2. Extraction Lambda includes a "format example" in the prompt with exact field formats
3. extraction_failures table catches hard failures; periodic manual review catches drift
4. Pin to a specific model version in the OpenAI API call (e.g., `gpt-5.4-mini-2026-01-15`) rather than the alias

### Risk 3: RDS Connection Exhaustion (LOW-MEDIUM)

**What:** 5 concurrent scraper Lambdas + Extraction + Dedup + Store + Health all hit RDS simultaneously. RDS t4g.micro supports ~80-100 connections. Under normal operation this is fine, but if Step Functions retries failed states while new executions start, connections spike.

**Why silent:** `psycopg2` raises `OperationalError` on connection failure, but if the Store Lambda can't connect, grants are silently lost (no S3 raw doc, no embedding, no RDS row).

**Mitigation:**
1. max_concurrency=5 in Map State (already designed)
2. Module-level connection caching in db.py (already designed)
3. Store Lambda should catch connection errors and write to a recovery queue (SQS DLQ) so grants can be re-processed later
4. CloudWatch alarm on RDS `DatabaseConnections` metric -- alert if >60 sustained

### Risk 4: SES Email Deliverability (LOW)

**What:** SES emails land in spam, or one-click approve/skip links are stripped by email clients.

**Why silent:** SES reports "delivered" even if the recipient's mail server accepts and then spam-filters. Staff stop seeing digests but nobody alerts the system.

**Mitigation:**
1. SES email address verification (not domain) -- simpler, but limits sending to verified address only
2. Test with Marisa's actual email client (likely Gmail via Google Workspace) before launch
3. One-click links use simple GET requests to API Gateway -- most email clients allow these, but test explicitly
4. Fallback: Custom GPT can always show the same data ("Show me this week's grants")

### Risk 5: HyDE Embedding Staleness (LOW)

**What:** SEARCH-PROFILES.md is updated but the hash check fails to detect the change (file encoding issue, whitespace change, section boundary parsing error). HyDE embeddings become stale without alerting.

**Why silent:** The pipeline runs normally with the old embedding -- it just returns slightly less relevant results. Nobody notices the quality degradation.

**Mitigation:**
1. `--force` flag on generate_hyde.py as a manual override
2. Annual EventBridge regeneration (January 1st) as a backstop
3. Log the profile_hash comparison result in every pipeline run so staleness is visible in CloudWatch

### Risk 6: LangGraph Lambda Timeout on Full-Profile Run (LOW-MEDIUM)

**What:** Running all 6 profiles ("Run a full grant search") means 6x the work: 6 HyDE queries, 6x50 similarity searches, ~72 grants through pre-filter, ~18 through evaluator. Total time could approach 10-12 minutes.

**Why problematic:** Lambda max timeout is 15 minutes. If GPT-5.4 is slow (API congestion, rate limit retry), the Lambda could timeout and all work is lost.

**Mitigation:**
1. Process profiles sequentially but write intermediate results to RDS after each profile completes. If Lambda times out, completed profiles are already persisted.
2. Consider running each profile as a separate Lambda invocation (Step Functions fan-out) if full-profile runs consistently exceed 10 minutes. This is a v1.5 optimization -- start with sequential and monitor.

---

## RDS Schema (Complete, Corrected)

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Grants table (primary data store)
CREATE TABLE grants (
    id                  SERIAL PRIMARY KEY,
    grant_id            TEXT UNIQUE NOT NULL,      -- SHA-256 content hash for dedup
    title               TEXT,
    funder              TEXT,
    deadline            DATE,
    funding_min         INTEGER,
    funding_max         INTEGER,
    geography           TEXT,
    eligibility         TEXT,
    description         TEXT,
    program_area        TEXT,
    population_served   TEXT,
    relationship_req    BOOLEAN DEFAULT FALSE,
    embedding           vector(1024),               -- Bedrock Titan V2
    source              TEXT,                        -- scraper_id from registry
    raw_s3_key          TEXT,                        -- S3 path to original doc
    approval_status     TEXT DEFAULT 'pending',      -- pending|approved|skipped|drafted
    approved_profile_id TEXT,                        -- which profile approved it
    skip_reason         TEXT,                        -- too_small|wrong_geography|already_applied|wrong_program|relationship_required|other
    score               FLOAT,                       -- highest score across profiles
    score_reasoning     TEXT,
    score_flags         JSONB,                       -- {strategic_alignment: 8, program_fit: 7, ...}
    scored_by_profiles  TEXT[],                       -- which profiles scored this grant
    ingested_at         TIMESTAMPTZ DEFAULT NOW(),
    scored_at           TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON grants (deadline);
CREATE INDEX ON grants (approval_status);
CREATE INDEX ON grants (source);
CREATE INDEX ON grants (funder);
CREATE INDEX ON grants USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Documents table (Hanna org RAG corpus -- loaded manually, not by daily pipeline)
CREATE TABLE documents (
    id          SERIAL PRIMARY KEY,
    doc_type    TEXT NOT NULL,               -- 'org_profile' | 'past_grant' | 'program_guide' | 'funder_directory'
    title       TEXT,
    content     TEXT NOT NULL,
    chunk_index INTEGER DEFAULT 0,           -- for multi-chunk documents
    embedding   vector(1024) NOT NULL,
    metadata    JSONB,                       -- flexible metadata per doc type
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON documents USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- HyDE queries (one per search profile)
CREATE TABLE hyde_queries (
    id              SERIAL PRIMARY KEY,
    profile_id      TEXT NOT NULL UNIQUE,     -- e.g. 'mental-health-hub'
    query_text      TEXT NOT NULL,            -- the generated hypothetical grant text
    embedding       vector(1024) NOT NULL,
    profile_hash    TEXT NOT NULL,            -- SHA-256 of the profile section
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Scraper health (one row per source, upserted daily)
CREATE TABLE scraper_health (
    scraper_id        TEXT PRIMARY KEY,
    last_success_at   TIMESTAMPTZ,
    last_grant_count  INTEGER DEFAULT 0,
    last_error        TEXT,
    consecutive_zeros INTEGER DEFAULT 0,
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Extraction failures (dead letter logging)
CREATE TABLE extraction_failures (
    id         SERIAL PRIMARY KEY,
    scraper_id TEXT,
    raw_s3_key TEXT,
    error      TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pipeline runs (audit trail)
CREATE TABLE pipeline_runs (
    id              SERIAL PRIMARY KEY,
    run_type        TEXT NOT NULL,            -- 'ingestion' | 'evaluation'
    profile_id      TEXT,                     -- null for ingestion, profile_id for evaluation
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    grants_ingested INTEGER DEFAULT 0,
    grants_scored   INTEGER DEFAULT 0,
    grants_new      INTEGER DEFAULT 0,        -- new grants this run (post-dedup)
    errors          JSONB,                    -- {scraper_errors: [...], extraction_errors: [...]}
    status          TEXT DEFAULT 'running'    -- running|completed|failed
);
```

**New table: `pipeline_runs`.** This was missing from the original schema. Without it, there's no audit trail of when the pipeline ran, what it processed, and whether it succeeded. Essential for debugging and for the RUNBOOK.md troubleshooting guide.

---

## Security Architecture

No changes from existing design. Validated and confirmed:

| Component | Security Control | Status |
|-----------|-----------------|--------|
| API Gateway | x-api-key header + usage plan (10 req/sec, 500 req/day) | Decided, correct |
| Lambda IAM | Least-privilege per function, specific ARNs, no wildcards | Decided, correct |
| RDS | Publicly accessible + SSL enforced + 90-day Secrets Manager rotation | Decided, acceptable trade-off |
| Secrets Manager | RDS creds, OpenAI key, API Gateway key, Google service account | Decided, correct |
| SES | Email address verification (not domain) | Pending: need Marisa's sending address |

**One addition:** The Google Sheets service account JSON credential should also be stored in Secrets Manager (not in the Lambda deployment package or environment variable). Add to Secrets Manager inventory:

| Secret | Contents | Rotation |
|--------|----------|----------|
| `hanna/google-sheets-sa` | Google service account JSON key | Manual (rotate annually) |

---

## Key Architectural Decisions (Updated)

| Decision | Rationale | Confidence |
|----------|-----------|------------|
| **Step Functions Standard (not Express)** | Express has 5-min hard limit; ingestion pipeline runs 5.5-8.5 min. Standard is free at Hanna's volume (4,000 transitions/month free tier). | HIGH |
| **HNSW index (not IVFFlat)** | Can create on empty table, better recall, less tuning. IVFFlat requires data before index creation. | HIGH |
| **3 deployment packages** (scraper Docker, LangGraph Docker, utility zips) | Scraper needs Chromium (~2GB), LangGraph needs AI deps (~800MB), utilities are lightweight (<50MB). One image for all would be 3GB+ with terrible cold starts. | HIGH |
| **Single scraper image, config-driven** | scraper_registry.json dispatches to correct parser. Adding a source = JSON entry + parser function. No new Lambda or Docker image. | HIGH |
| **Processing embedded in Store Lambda** | Grant descriptions are short. Separate chunking pipeline adds latency without benefit. One embedding per grant at ingest time. | MEDIUM |
| **pipeline_runs audit table** | New addition. No audit trail = no troubleshooting ability. Essential for RUNBOOK.md guidance. | HIGH |
| **Profile-by-profile persistence in eval** | Write scores to RDS after each profile. If Lambda times out on full-profile run, completed profiles are preserved. | MEDIUM |

---

## Patterns to Follow

### Pattern 1: Claim Check for Large Payloads

Step Functions has a 256KB payload limit. Raw grant HTML/JSON can exceed this. Write raw data to S3, pass only the S3 key between states.

```python
# In scraper Lambda
s3_key = f"raw/{date}/{scraper_id}/{hash}.json"
s3.put_object(Bucket=BUCKET, Key=s3_key, Body=raw_data)
return {"s3_key": s3_key, "scraper_id": scraper_id, "grant_count": len(grants)}
```

### Pattern 2: Idempotent Store Lambda

Store Lambda must handle being called twice with the same grant (Step Functions Standard exactly-once is per-execution, but retries can duplicate). Use `ON CONFLICT (grant_id) DO UPDATE` for all RDS writes.

```sql
INSERT INTO grants (grant_id, title, funder, ...)
VALUES ($1, $2, $3, ...)
ON CONFLICT (grant_id) DO UPDATE SET
    title = EXCLUDED.title,
    updated_at = NOW();
```

### Pattern 3: Shared db.py Module

All Lambdas that access RDS import a shared `db.py` module with module-level connection caching, SSL enforcement, and Secrets Manager credential loading. This module is included in the Lambda Layer.

```python
# db.py -- shared across all Lambdas
import psycopg2, boto3, json

_conn = None

def get_connection():
    global _conn
    if _conn and not _conn.closed:
        try:
            _conn.cursor().execute("SELECT 1")
            return _conn
        except Exception:
            pass
    secret = boto3.client("secretsmanager").get_secret_value(SecretId=SECRET_ARN)
    creds = json.loads(secret["SecretString"])
    _conn = psycopg2.connect(
        host=creds["host"], port=creds["port"],
        dbname=creds["dbname"], user=creds["username"],
        password=creds["password"], sslmode="require"
    )
    return _conn
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: One Lambda Per Scraper

**What:** Creating 17 separate Lambda functions for 17 sources.
**Why bad:** 17 IAM roles, 17 CloudWatch log groups, 17 deployment configurations. Adding source #18 requires CDK changes.
**Instead:** One scraper Lambda image, config-driven dispatch via scraper_registry.json.

### Anti-Pattern 2: LangGraph for Ingestion

**What:** Using LangGraph to orchestrate the scrape-extract-dedup-store pipeline.
**Why bad:** LangGraph adds Python dependencies, graph overhead, and opacity for a linear ETL pipeline. Step Functions provides visual debugging, native retry, and zero-dependency orchestration.
**Instead:** Step Functions Standard for ingestion, LangGraph only for agent pipeline (Phase 3).

### Anti-Pattern 3: Lambda Inside VPC

**What:** Placing Lambda in a VPC to use Security Group referencing for RDS.
**Why bad:** Requires NAT Gateway ($32/month) for Lambda to reach OpenAI API, SES, S3, etc. Exceeds $50/month budget alone.
**Instead:** RDS publicly accessible + SSL + Secrets Manager rotation. Acceptable for non-PII grant data.

### Anti-Pattern 4: Shared Mutable State Between Pipeline Runs

**What:** Using DynamoDB or Redis to share state between the daily ingestion run and the weekly evaluation run.
**Why bad:** Adds infrastructure cost, operational complexity, and a failure mode. The two pipelines should be independent.
**Instead:** RDS is the shared state. Ingestion writes grants; evaluation reads them. No coupling beyond the database.

---

## Sources

- [AWS Step Functions: Standard vs. Express](https://docs.aws.amazon.com/step-functions/latest/dg/choosing-workflow-type.html) -- HIGH confidence
- [AWS Step Functions Pricing](https://aws.amazon.com/step-functions/pricing/) -- HIGH confidence
- [Step Functions Map State documentation](https://docs.aws.amazon.com/step-functions/latest/dg/state-map.html) -- HIGH confidence
- [AWS pgvector indexing deep dive (HNSW vs IVFFlat)](https://aws.amazon.com/blogs/database/optimize-generative-ai-applications-with-pgvector-indexing-a-deep-dive-into-ivfflat-and-hnsw-techniques/) -- HIGH confidence
- [pgvector GitHub](https://github.com/pgvector/pgvector) -- HIGH confidence
- [LangGraph on AWS Lambda](https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-frameworks/langchain-langgraph.html) -- MEDIUM confidence
- [Playwright on Lambda Docker](https://developer.mamezou-tech.com/en/blogs/2024/07/19/lambda-playwright-container-tips/) -- MEDIUM confidence
- [Lambda cold start optimization 2025](https://zircon.tech/blog/aws-lambda-cold-start-optimization-in-2025-what-actually-works/) -- MEDIUM confidence
- [Lambda INIT billing change August 2025](https://edgedelta.com/company/knowledge-center/aws-lambda-cold-start-cost) -- MEDIUM confidence
