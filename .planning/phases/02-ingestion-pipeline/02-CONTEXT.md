# Phase 2: Ingestion Pipeline + Backfill - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the automated grant ingestion pipeline: 17 sources (5 APIs + 12 Playwright scrapers) orchestrated by Step Functions Standard, running daily at 6am PT. Each grant is deduped, metadata-extracted via LLM, embedded, and stored in the grants table. Scraper health monitoring catches silent failures. A one-time backfill script populates 500+ historical grants for Phase 3 to evaluate.

No evaluation logic, no scoring, no email digests — this phase ends when grants flow into the database automatically.

</domain>

<decisions>
## Implementation Decisions

### Scraper Reliability
- **D-01:** Silent failure logging with CloudWatch alarm after 3 consecutive zero-grant days per source. No immediate alerts for transient failures — avoids alert fatigue for a 2-person grants team.
- **D-02:** Playwright scrapers use stealth mode (playwright-stealth) with random delays (2-8s between actions) and rotating user agents. Standard approach for low-volume daily scraping.

### Metadata Extraction
- **D-03:** GPT-5.4-mini (or nano) via OpenRouter for structured metadata extraction (title, funder, deadline, funding range, geography, eligibility, relationship_required flag).
- **D-04:** When LLM cannot confidently extract a field, set to null with extraction_confidence score. No hallucinated values — downstream evaluator handles missing data gracefully.

### Backfill Strategy
- **D-05:** Backfill from API archives only — grants.ca.gov and Grants.gov historical data. No scraping fragile archive pages on foundation sites.
- **D-06:** Backfill grants go through the same extraction pipeline as live grants (GPT-5.4-mini + Bedrock embedding). One-time cost ~$1-2 for 500 grants. Ensures consistent metadata quality.
- **D-07:** Process backfill in batches of 50 with pauses between batches. Resume from last successful batch on failure.

### Cost Control
- **D-08:** Dedup BEFORE LLM extraction — check SHA-256 content hash first, skip if grant already exists. Only pay for genuinely new grants (~5-20/day).
- **D-09:** Lambda memory 2048MB / 10min timeout per scraper. Comfortable headroom for Playwright+Chromium without excessive cost (~$1/month for daily runs).

### Registry Management
- **D-10:** Scraper sources managed via `scraper_registry.json` in the repo. Add/disable sources by editing the file and redeploying. Version-controlled and auditable.

### Pipeline Error Handling
- **D-11:** Step Functions Map State with ToleratedFailurePercentage=30%. If some scrapers fail, healthy scrapers still process. Failed scrapers logged to pipeline_runs table.

### Grant Data Freshness
- **D-12:** Expired grants (deadline passed) stay in the database for historical reference. Phase 3 evaluator applies `deadline > today` filter before scoring. No data deletion.

### Testing Strategy
- **D-13:** Save HTML snapshots from each site as test fixtures. Unit tests run against recorded responses. One live smoke test per source on deploy to verify selectors still work.

### OpenRouter Integration
- **D-14:** All LLM calls use OpenRouter via OPENAI_BASE_URL environment variable. API key from `.env` file (OPENROUTER_API_KEY). Model names use OpenRouter format (e.g., `openai/gpt-5.4-mini`).

### Region and Infrastructure
- **D-15:** All AWS resources in us-west-2 (Oregon). Bedrock Titan V2 not available in us-west-1.
- **D-16:** PostgreSQL 16.12 (16.4 retired). Shared utilities from Phase 1 (db.py, embeddings.py, config.py) reused directly.

### Claude's Discretion
- Exact Playwright selectors per scraper site
- Step Functions state machine structure and naming
- Scraper base class design and inheritance hierarchy
- Batch concurrency settings for backfill script
- Test fixture organization and naming

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scraper targets
- `scraper_registry.json` — All 17 scraper targets with URLs, types (api/scraper), priority, frequency, geography, and profile associations

### Phase 1 infrastructure (reuse)
- `scripts/utils/db.py` — Rotation-aware PostgreSQL connection via Secrets Manager (includes reconnect logic)
- `scripts/utils/embeddings.py` — Bedrock Titan V2 embedding function (1024 dims)
- `scripts/utils/config.py` — Shared constants: EMBEDDING_DIMS, AWS_REGION, HYDE_MODEL
- `scripts/utils/chunking.py` — Multi-strategy text chunking
- `scripts/init_db.py` — DB schema with all 6 tables (grants table has content_hash, approval_status, score columns)
- `infrastructure/stacks/hanna_stack.py` — CDK stack (Lambda role, API Gateway, EventBridge scaffolds)

### Project decisions
- `.planning/PROJECT.md` — All locked tech stack decisions
- `.planning/ROADMAP.md` — Phase scope, success criteria, dependencies
- `.planning/REQUIREMENTS.md` — INGEST-01 through INGEST-09, INFRA-04, PIPE-01, PIPE-03
- `.env` — OpenRouter API key and base URL (not committed to git)

### Phase 1 context
- `.planning/phases/01-org-profile-and-context/1-CONTEXT.md` — Prior decisions on infrastructure, org profile, evaluation criteria

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/utils/db.py` — Connection caching, rotation-aware reconnect, SSL enforcement. Includes fix for register_vector before pgvector extension exists.
- `scripts/utils/embeddings.py` — `get_embedding()` function wrapping Bedrock Titan V2. Ready to use for grant embeddings.
- `scripts/utils/config.py` — EMBEDDING_DIMS=1024, AWS_REGION="us-west-2". OpenRouter model name format.
- `scripts/ingest_documents.py` — Pattern for reconnect-on-failure during long ingestion runs. `_reconnect_if_needed()` function reusable for scraper pipeline.

### Established Patterns
- `.env` + `python-dotenv` for secrets (OpenRouter key, base URL)
- `--secret-arn` CLI argument for Secrets Manager ARN
- ON CONFLICT upsert for idempotent inserts (documents table)
- SHA-256 content hash for deduplication (hyde_queries table)

### Integration Points
- `grants` table in RDS — scrapers INSERT here, Phase 3 reads from here
- `scraper_health` table — health monitoring writes consecutive_zeros per source
- `pipeline_runs` table — each run logs start/end timestamps, counts, errors
- `extraction_failures` table — failed LLM extractions logged for debugging
- EventBridge `HannaDailyIngestion` rule (currently disabled, targets placeholder Lambda)

</code_context>

<specifics>
## Specific Ideas

- grants.ca.gov is Hanna's #1 grant source — this scraper should be the most robust and well-tested
- Hanna Center is in Sonoma County, CA — geography filters should include "CA", "Sonoma County", "statewide", "national"
- The scraper_registry.json already has 17 entries with all metadata — scrapers should read this at runtime, not hardcode URLs
- OpenRouter model names require provider prefix: `openai/gpt-5.4-mini` not `gpt-5.4-mini`
- Phase 1 deployment revealed PostgreSQL 16.4 is retired in us-west-2 — using 16.12 now

</specifics>

<deferred>
## Deferred Ideas

- Instrumentl CSV import as additional grant source — Phase 5 / backlog
- IRS 990-PF enrichment via Grantmakers.io for funder intelligence — Phase 5 / backlog
- Scraper auto-healing (LLM re-generates selectors when site layout changes) — future enhancement
- Grant detail page deep-scraping (follow links for full RFP documents) — future enhancement

</deferred>

---

*Phase: 02-ingestion-pipeline*
*Context gathered: 2026-03-30*
