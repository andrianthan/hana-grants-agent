# Domain Pitfalls: Hanna Grants AI Agent

**Domain:** AI-powered grants pipeline (LangGraph + OpenAI + AWS Lambda + pgvector + Playwright scrapers)
**Researched:** 2026-03-26
**Scope:** Pitfalls specific to this project's constraints -- nonprofit handoff, $50/month budget, non-technical post-handoff staff, AWS-only infrastructure

---

## Critical Pitfalls

Mistakes that cause rewrites, pipeline failures staff cannot recover from, or project abandonment.

---

### Pitfall 1: Silent Scraper Degradation (The "Zero Grants and No One Notices" Problem)

**What goes wrong:** A government site (e.g., sonoma-county-bhs) redesigns its grants page. The Playwright scraper runs, returns HTTP 200, parses zero grants from the new DOM structure, and exits successfully. Step Functions logs the execution as "succeeded." No error, no alarm. The pipeline quietly stops finding grants from that source. Staff only notice weeks later when a colleague mentions a grant they never saw.

**Why it happens:** Scrapers that check HTTP status codes but not result counts treat empty results as success. Government sites redesign without notice, add CAPTCHAs, or move content behind JavaScript frameworks. The 12 scraper targets include 5 Sonoma County department portals -- small county sites with no API stability guarantees.

**Consequences:** Missed grant opportunities with real dollar impact. For a nonprofit with a 2-person grants team, missing a $500K CA state grant because a scraper silently broke is catastrophic relative to the system's purpose.

**Warning signs:**
- `scraper_health.consecutive_zeros >= 3` for any scraper
- Weekly grant count drops without corresponding API/source changes
- One source's grant count flatlines while others fluctuate normally

**Prevention:**
1. The `scraper_health` table with `consecutive_zeros` tracking is already designed (Architecture doc). Build it in Phase 2, not as a "nice to have" later.
2. CloudWatch alarm on `consecutive_zeros >= 3` with SNS notification to developer email AND a staff-visible flag in the weekly digest: "Warning: [Source] has not returned grants in 3+ days."
3. Each scraper must assert a minimum expected grant count (not zero) based on historical baseline. A California state portal with 200+ active grants returning zero is always a failure.
4. Store a DOM structure fingerprint (hash of key CSS selectors) per scraper. When the fingerprint changes, flag the scraper for manual review even if it still returns data -- partial structure changes cause partial data loss.

**Phase:** Phase 2 (Ingestion). This is a Phase 2 deliverable, not a Phase 4 hardening task.

**Confidence:** HIGH -- this is the most commonly reported failure mode in production scraping systems. Multiple sources confirm silent failures are more damaging than crashes.

---

### Pitfall 2: OpenAI Model Deprecation Breaking the Production Pipeline

**What goes wrong:** OpenAI deprecates the model the pipeline depends on. GPT-4o was retired March 31, 2026. GPT-4.5-preview was removed July 14, 2025. The project uses GPT-5.4-mini for pre-filter/extraction and GPT-5.4 for evaluation -- both will eventually be deprecated. When the model endpoint stops responding, the entire pipeline fails: no extraction, no scoring, no digest.

**Why it happens:** OpenAI's deprecation cadence is aggressive -- models get 3-6 months notice before removal. A nonprofit system with no active developer monitoring will miss deprecation emails. Hanna's staff cannot update model strings in Lambda environment variables.

**Consequences:** Complete pipeline outage. No grants discovered or evaluated until someone with AWS access updates the model identifier. For a system designed to run unattended, this is a single point of failure.

**Warning signs:**
- OpenAI deprecation announcements (check quarterly)
- API responses returning 404 or "model not found" errors
- CloudWatch error rate spike on extraction/evaluation Lambdas

**Prevention:**
1. Store model identifiers as environment variables in Lambda (not hardcoded in Python). CDK deploys make model swaps a one-line change.
2. Use OpenAI's model alias pattern when available (e.g., `gpt-5-mini` instead of `gpt-5.4-mini-2026-01-15`). Aliases auto-migrate to successor models.
3. Add a CloudWatch alarm on LLM API error rate > 5% that alerts the developer via SNS.
4. RUNBOOK.md must include: "How to update the AI model" with exact steps (AWS Console > Lambda > Configuration > Environment Variables > change MODEL_NAME > Save). Screenshot-level instructions.
5. Pydantic structured outputs provide schema enforcement that survives model swaps -- the new model may produce different prose but must still conform to the same schema.
6. Annual maintenance calendar event (January, alongside HyDE regeneration) to check current model deprecation status.

**Phase:** Phase 1 (env var architecture), Phase 4 (RUNBOOK documentation), ongoing maintenance.

**Confidence:** HIGH -- GPT-4o retirement on March 31, 2026 is confirmed. This is not hypothetical.

---

### Pitfall 3: RDS Connection Pool Exhaustion on t4g.micro

**What goes wrong:** The t4g.micro instance has 1 GB RAM. PostgreSQL's `max_connections` defaults to ~87 on this instance class (calculated by AWS formula: `LEAST({DBInstanceClassMemory/9531392}, 5000)`). With 17 scraper Lambdas, extraction Lambdas, the evaluation pipeline, Custom GPT API queries, and Secrets Manager rotation Lambdas all potentially connecting simultaneously, the pool saturates. New connections get "FATAL: too many connections" errors. The pipeline partially fails -- some scrapers succeed, others don't, creating inconsistent data.

**Why it happens:** Lambda functions create new database connections on cold start. Even with module-level connection caching (`_conn` pattern in db.py), a burst of cold starts (e.g., after a deployment or idle period) opens many connections simultaneously. The Map State `max_concurrency=5` helps during ingestion, but doesn't protect against concurrent ingestion + evaluation + Custom GPT queries.

**Consequences:** Partial pipeline failures that are hard to diagnose. Some grants ingested, others silently dropped. Evaluation pipeline fails if it can't read from the database.

**Warning signs:**
- CloudWatch RDS `DatabaseConnections` metric approaching 80
- Intermittent "too many connections" in Lambda logs
- Extraction failures that succeed on retry (transient connection exhaustion)

**Prevention:**
1. Map State `max_concurrency=5` is already planned -- implement it as designed, do not increase it.
2. Module-level connection caching in `db.py` (already designed) -- every Lambda must import from this shared module, never create `psycopg2.connect()` directly.
3. Add connection retry with exponential backoff (3 attempts, 1s/2s/4s) in `get_connection()`. A brief pool exhaustion resolves itself as other Lambdas release connections.
4. Schedule ingestion (EventBridge daily) and evaluation (EventBridge weekly Monday 7:30am) at different times. Never overlap the two pipeline runs.
5. Set a CloudWatch alarm on `DatabaseConnections > 60` (75% of ~80 limit) as an early warning.
6. If the problem persists at scale: RDS Proxy ($0 for the proxy itself, but requires Lambda in VPC + NAT Gateway at $32/month) is the proper solution. Defer this to v2 unless connection errors become frequent.

**Phase:** Phase 1 (db.py module), Phase 2 (Map State concurrency), Phase 4 (CloudWatch alarm).

**Confidence:** HIGH -- t4g.micro connection limits are well-documented and the concurrent Lambda pattern is a known stress point.

---

### Pitfall 4: Playwright Docker Image Cold Starts Exceeding Lambda Timeout

**What goes wrong:** Playwright requires a full Chromium browser binary. The Docker image for a Playwright Lambda is 500MB-1GB+. Cold starts on a Docker-based Lambda with this image size take 5-15 seconds. If a scraper target is slow (government sites often are), the combined cold start + page load + rendering can approach or exceed the Lambda timeout (default 15 minutes is fine, but if misconfigured to a shorter timeout, scrapers fail).

**Why it happens:** Microsoft's Playwright Docker images are designed for CI environments, not Lambda. They include multiple browsers, debugging tools, and system libraries not needed for headless scraping. Pulling this image on cold start is slow.

**Consequences:** Scraper Lambdas time out before completing. Step Functions Map State marks them as failed. If the tolerated failure threshold is not configured, one slow scraper can abort the entire ingestion pipeline.

**Warning signs:**
- Scraper Lambda duration spikes in CloudWatch (>60s on cold start vs. ~10s warm)
- Timeouts clustered after idle periods (overnight, weekends)
- Step Functions execution failures with "Lambda.Timeout" error

**Prevention:**
1. Build a custom slim Docker image: start from `python:3.12-slim`, install only `playwright` + `chromium` (not firefox/webkit), strip unnecessary locales and fonts. Target under 400MB compressed.
2. Set Lambda timeout to 300 seconds (5 minutes) per scraper. This is generous but prevents timeout failures on slow government sites.
3. Set Lambda memory to 1024MB minimum for Playwright. More memory = proportionally faster CPU = faster cold starts.
4. Use Lambda Provisioned Concurrency for the scraper function if cold starts are frequent (costs ~$5/month for 1 instance). Only add this if monitoring shows it's needed -- not default.
5. Step Functions Map State: set `ToleratedFailurePercentage` to 30% (allow up to 5 of 17 scrapers to fail without aborting the pipeline). One broken county site should not kill the entire run.

**Phase:** Phase 2 (Docker image build, Lambda config, Step Functions error tolerance).

**Confidence:** HIGH -- Playwright on Lambda cold start issues are extensively documented.

---

### Pitfall 5: LLM Extraction Hallucinating Grant Metadata (Deadlines, Award Amounts)

**What goes wrong:** GPT-5.4-mini extracts structured metadata from raw HTML/PDF. It infers a deadline of "April 30, 2026" from text that says "applications accepted on a rolling basis" or hallucinates a $500,000 award range from a page that mentions "$500,000" in an unrelated context (e.g., the funder's total annual giving). Staff see a high-scoring grant with a fabricated deadline, rush to apply, and discover the grant doesn't exist as described.

**Why it happens:** LLMs are text completion engines. When metadata fields are required (Pydantic schema enforcement), the model will generate plausible values rather than return null. "Deadline" and "funding range" are particularly susceptible because grant pages often mention multiple dates and dollar amounts in different contexts.

**Consequences:** Staff waste time on phantom deadlines. Worse, staff lose trust in the system after 2-3 hallucinated entries and stop using it entirely. For a nonprofit tool, trust loss = adoption death.

**Warning signs:**
- Grants with suspiciously round numbers ($100,000 exactly, $1,000,000 exactly)
- Deadlines that are always the last day of a month
- Multiple grants from the same source with identical metadata
- Extraction results that don't match the raw HTML when spot-checked

**Prevention:**
1. Make deadline, funding_min, and funding_max NULLABLE in the Pydantic schema. Tell the model: "If the deadline is not explicitly stated, return null. If the funding range is not explicitly stated, return null. Do NOT infer or estimate." Nullable fields with explicit "not found" are infinitely better than hallucinated values.
2. Add a `confidence` field per extracted value (high/medium/low). Flag low-confidence extractions in the digest with a visual marker so staff know to verify.
3. Store the raw S3 URL alongside every extracted grant. The digest should link to the original source so staff can verify claims in 10 seconds.
4. Implement extraction spot-checks: weekly, randomly sample 5 grants and compare extracted metadata against the raw source. Track accuracy rate. If accuracy drops below 90%, investigate the extraction prompt.
5. The retry-with-schema-reminder pattern (already in Architecture doc) handles malformed JSON. This pitfall is about VALID JSON with WRONG values -- a different failure mode that retry doesn't fix. Prompt engineering is the defense.

**Phase:** Phase 2 (extraction prompt design), Phase 3 (confidence scoring), Phase 4 (spot-check process in RUNBOOK).

**Confidence:** HIGH -- LLM extraction hallucination is the most studied failure mode in production RAG systems.

---

### Pitfall 6: Post-Handoff System Decay (The "No Developer" Problem)

**What goes wrong:** The system is handed off to Hanna's grants team (Marisa Binder, Monica Argenti). Neither has AWS, Python, or DevOps experience. Over 6-12 months: a scraper breaks and no one can fix it, OpenAI deprecates the model and no one updates the env var, the RDS password rotates and a Lambda's cached connection breaks, the SES sending domain verification expires, or AWS bills creep past $50/month without anyone noticing. The system degrades until staff stop trusting it and revert to manual grant searching.

**Why it happens:** Every software system requires maintenance. Nonprofit staff are hired for grant writing, not system administration. The developer (you) moves on to other projects. There is no IT department at Hanna to absorb maintenance responsibilities.

**Consequences:** Total system abandonment within 12-18 months. The $50/month AWS bill continues running for months after the system stops being useful, burning nonprofit budget.

**Warning signs:**
- Staff stop mentioning the system in meetings
- Weekly digest emails go unopened (SES delivery metrics)
- Grant database stops growing (no new ingestion)
- CloudWatch alarms fire but no one responds
- AWS bill increases without corresponding usage increase

**Prevention:**
1. **RUNBOOK.md** (already planned as Phase 4 deliverable) must cover every failure mode in plain English with screenshots. Test it by having a non-technical person follow each procedure. If they can't complete it, rewrite it.
2. **CloudWatch billing alarm** at $40/month (80% of budget) AND $50/month (hard limit). Alert goes to Marisa's email AND the developer's email. The developer should remain a monitoring contact even post-handoff.
3. **Quarterly health check calendar event** (Google Calendar, auto-recurring): staff open the Step Functions console, verify last execution was green, verify grant count is growing. RUNBOOK includes the exact URL and what to look for.
4. **Developer maintenance agreement**: Even 1 hour/quarter of volunteer or paid maintenance prevents cascading failures. Document this expectation explicitly with Hanna leadership before handoff.
5. **"Break glass" contact info**: RUNBOOK includes developer contact info for emergencies. Define what constitutes an emergency (pipeline down >7 days, AWS bill >$75, data loss).
6. **Auto-disable on budget breach**: Set an AWS Budget action that stops the EventBridge schedule if monthly spend exceeds $60. The pipeline pauses rather than running up costs nobody notices.

**Phase:** Phase 4 (RUNBOOK, alarms, handoff documentation). This is not optional polish -- it is a Phase 4 critical deliverable.

**Confidence:** HIGH -- nonprofit software project abandonment due to maintenance gaps is extensively documented across the sector.

---

## Moderate Pitfalls

Mistakes that cause significant rework or degraded quality but don't kill the project.

---

### Pitfall 7: HyDE Embedding Drift Across 6 Profiles

**What goes wrong:** The 6 HyDE embeddings are generated once from SEARCH-PROFILES.md. Over time, Hanna's programs evolve (new partnerships, shifted focus areas), but staff forget to update SEARCH-PROFILES.md. The HyDE embeddings become stale representations of programs that no longer match Hanna's current priorities. The system surfaces grants for last year's strategy.

**Why it happens:** HyDE is a pre-computed query -- it doesn't adapt automatically to what Hanna is actually doing. The hash-check regeneration trigger only fires if someone edits SEARCH-PROFILES.md. If nobody edits it, the embeddings never change.

**Prevention:**
1. Annual EventBridge forced regeneration (January 1st) is already planned. This is the safety net.
2. Quarterly reminder (Google Calendar) for Marisa: "Review SEARCH-PROFILES.md -- are these still our priorities?" Include the exact file location and what to edit.
3. When staff consistently skip grants from a particular profile (e.g., "recreation-enrichment" grants are always skipped), surface this pattern in a quarterly report: "80% of recreation grants were skipped in Q1. Consider updating the Recreation profile."
4. Keep HyDE generation under 30 seconds total. If regeneration is slow or complex, staff will resist triggering it.

**Phase:** Phase 1 (HyDE generation), Phase 4 (quarterly review process).

**Confidence:** MEDIUM -- HyDE staleness is a known limitation in the research literature but the hash-check mechanism mitigates it significantly.

---

### Pitfall 8: Step Functions Map State Failure Cascade

**What goes wrong:** In Inline Map State mode (used for the 17-scraper fan-out), the failure of ANY single iteration fails the ENTIRE Map State by default. One Sonoma County portal returns a 503 error, and the entire daily ingestion pipeline aborts -- including the 16 scrapers that succeeded.

**Why it happens:** Step Functions Inline Map State treats any unhandled error in any iteration as a Map State failure. If the individual scraper tasks don't have Catch/Retry blocks, a single transient error kills the run.

**Consequences:** Missed daily ingestion. If the pipeline runs once daily, one bad scraper means zero grants ingested that day from ANY source.

**Prevention:**
1. Every scraper task in the Map State must have a `Retry` block for transient errors (`Lambda.ServiceException`, `Lambda.Timeout`, `States.TaskFailed`) with `MaxAttempts: 2` and `BackoffRate: 2`.
2. Every scraper task must have a `Catch` block that routes failures to a "RecordFailure" state (writes to `scraper_health` table) instead of failing the Map State.
3. Set `ToleratedFailurePercentage: 30` on the Map State definition. Up to 5 of 17 scrapers can fail without aborting.
4. The post-Map "Health Lambda" (already designed) must run regardless of individual scraper outcomes. It processes whatever results are available.

**Phase:** Phase 2 (Step Functions definition). This is a build-time decision, not a post-launch fix.

**Confidence:** HIGH -- Step Functions Map State failure behavior is documented in AWS docs and is a common surprise for first-time users.

---

### Pitfall 9: Secrets Manager Rotation Breaking Lambda Connections

**What goes wrong:** The 90-day automatic password rotation fires. Secrets Manager updates the RDS password. Lambda functions with cached connections (the `_conn` module-level cache in db.py) still hold the OLD password. The next time a cached connection is used after rotation, it fails authentication. If the retry logic re-fetches credentials from Secrets Manager, it recovers. If it doesn't, Lambdas fail until the next cold start (which fetches fresh credentials).

**Why it happens:** The module-level connection cache pattern (designed for connection pooling efficiency) caches both the connection AND the credentials. Secrets Manager rotation invalidates the credentials but doesn't notify running Lambdas.

**Consequences:** Pipeline failures for 1-24 hours post-rotation until all Lambda instances cold-start with fresh credentials.

**Prevention:**
1. The `get_connection()` function in db.py must catch authentication errors specifically (`psycopg2.OperationalError` with "password authentication failed") and re-fetch credentials from Secrets Manager on that specific error -- not just retry with the same credentials.
2. Add a `_secret_fetched_at` timestamp alongside `_conn`. If the connection is older than 12 hours, proactively re-fetch credentials before using the connection. This creates a rolling refresh window that overlaps with rotation.
3. Test the rotation flow manually before handoff: trigger a manual rotation in Secrets Manager, verify Lambda recovers within one invocation.
4. RUNBOOK.md: "If all pipeline steps suddenly fail with authentication errors, manually restart the Lambda function (Configuration > Restart)."

**Phase:** Phase 1 (db.py module design), Phase 4 (rotation testing + RUNBOOK).

**Confidence:** HIGH -- this is a known interaction between Lambda connection caching and Secrets Manager rotation, documented in AWS re:Post.

---

### Pitfall 10: Custom GPT Actions Model Restrictions and API Fragility

**What goes wrong:** OpenAI restricts which models can be used with Custom GPT Actions. As of January 2026, o-series and Pro models are excluded. The Custom GPT auto-migrates to "the closest GPT-5 equivalent that supports Actions" -- which may behave differently (worse at following the system prompt, different JSON formatting in Action calls, different interpretation of the OpenAPI schema). Staff notice the GPT "acting weird" but can't diagnose why.

**Why it happens:** OpenAI controls the model behind Custom GPTs and can change it without user consent. The OpenAPI spec for Actions has undocumented quirks (parameter naming restrictions, authentication header limitations). API Gateway URL changes (e.g., after a CDK redeployment to a new stage) break the Action endpoint.

**Consequences:** Custom GPT stops being able to query grants, approve/skip, or export CSV. Staff lose the conversational interface and must rely solely on email digest.

**Prevention:**
1. Pin the Custom GPT to a specific model version if Enterprise allows it. Check GPT builder settings quarterly.
2. Use stable API Gateway custom domain (not the auto-generated `*.execute-api.amazonaws.com` URL) if possible. Otherwise, document in RUNBOOK how to update the Custom GPT Action URL after CDK deployments.
3. Test the full Custom GPT Action flow (list grants, approve, skip, export) after every CDK deployment.
4. Design the system so that the email digest is fully functional without Custom GPT. The GPT is a convenience layer, not a dependency. Staff must be able to approve/skip via email one-click links even if the GPT breaks.
5. Keep the OpenAPI spec minimal -- fewer endpoints and simpler schemas are less likely to break on model migrations.

**Phase:** Phase 4 (Custom GPT setup + testing), ongoing monitoring.

**Confidence:** MEDIUM -- Custom GPT Actions are supported in Enterprise as of 2026, but OpenAI's track record of breaking changes to GPT features is well-established.

---

### Pitfall 11: Pydantic Schema Incompatibility with OpenAI Structured Outputs

**What goes wrong:** OpenAI's Structured Outputs API has specific schema requirements that conflict with standard Pydantic patterns. All fields must be `required` (OpenAI doesn't support `Optional[T]` the way Pydantic does -- it requires nullable types instead). `$ref` (recursive schemas) is not supported. `minimum`/`maximum` constraints are silently ignored. A Pydantic model that validates locally fails when passed to the OpenAI API.

**Why it happens:** OpenAI implements a subset of JSON Schema, not the full spec. The `openai-python` SDK converts Pydantic models to JSON Schema, but the conversion has known compatibility issues (GitHub issue #1659 on `openai-python`).

**Consequences:** Extraction and evaluation calls fail with cryptic schema errors. Developer spends hours debugging why a valid Pydantic model breaks in production.

**Prevention:**
1. Use `openai.pydantic_function_tool()` or the SDK's built-in Pydantic conversion -- do not hand-write JSON schemas.
2. Test every Pydantic model against the OpenAI API in Phase 2 before building the full pipeline. Don't assume local Pydantic validation = API compatibility.
3. For nullable fields (e.g., `deadline: Optional[date]`), use the pattern: `deadline: date | None` with a default of `None` and mark as required in the schema with `"nullable": true`.
4. Avoid nested models with `$ref`. Flatten the schema or use inline definitions.
5. Pin the `openai` Python package version in `requirements.txt`. New SDK versions may change schema conversion behavior.

**Phase:** Phase 2 (extraction schema), Phase 3 (evaluation schema).

**Confidence:** HIGH -- OpenAI structured output schema incompatibilities are documented with open GitHub issues.

---

## Minor Pitfalls

Issues that cause friction or minor quality degradation.

---

### Pitfall 12: Email Digest Adoption Decay

**What goes wrong:** Staff enthusiastically use the email digest for the first month. By month 3, it becomes "just another email" that gets archived unread. Grant opportunities are discovered but never reviewed. The system technically works but delivers zero value.

**Why it happens:** Email fatigue is universal. A weekly digest competes with hundreds of other emails. If the signal-to-noise ratio is low (too many irrelevant grants surfaced), staff learn to ignore it.

**Prevention:**
1. Keep the digest ruthlessly short. Show only grants scoring 6.0+ (tunable threshold). A digest with 3 high-quality grants beats one with 20 marginal ones.
2. Put the most urgent grant (closest deadline + highest score) in the email subject line: "Grant Digest: [Grant Name] - deadline Apr 15 - Score 8.7"
3. Track SES open rates and click rates. If open rate drops below 50%, the digest needs redesign (too long, too many entries, not useful enough).
4. The Google Sheets tracker provides a backup surface -- staff who ignore email may still check a shared sheet.

**Phase:** Phase 4 (digest design), ongoing monitoring.

**Confidence:** MEDIUM -- email engagement decay is a well-studied UX pattern but the one-click approve/skip mechanism helps maintain engagement.

---

### Pitfall 13: pgvector Index Choice (IVFFlat vs. HNSW)

**What goes wrong:** The schema uses `ivfflat` index. IVFFlat requires periodic reindexing after significant data changes (the `nlist` parameter determines cluster count, and adding many new vectors without reindexing degrades recall). On the initial backfill of 500-900 grants, the index may be built on too few vectors and perform poorly at steady state, or vice versa.

**Why it happens:** IVFFlat is faster to build but has worse recall than HNSW for small-to-medium datasets. At Hanna's scale (500-2000 grants total), HNSW is likely the better choice -- it provides better recall without requiring reindexing.

**Prevention:**
1. Switch to HNSW index: `CREATE INDEX ON grants USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)`. HNSW has no reindexing requirement and better recall at this data scale.
2. At Hanna's volume (<5000 vectors), the performance difference between IVFFlat and HNSW is negligible. Correctness (recall) matters more than speed.
3. If using IVFFlat, set `nlist` conservatively (e.g., `sqrt(n)` where n is expected total grants). Rebuild the index after the initial backfill completes.

**Phase:** Phase 1 (schema definition).

**Confidence:** MEDIUM -- pgvector index recommendations are available in the pgvector documentation; at this scale, either works, but HNSW is simpler to maintain.

---

### Pitfall 14: Budget Creep Past $50/Month

**What goes wrong:** Costs are estimated at $16-19/month steady state. But: Secrets Manager rotation Lambdas have a hidden cost, CloudWatch Logs storage grows indefinitely, S3 raw document storage accumulates, and an accidental increase in Lambda memory or OpenAI API calls (e.g., a bug that retries extraction infinitely) pushes costs past the nonprofit's budget.

**Why it happens:** AWS billing is opaque. Individual services are cheap, but the long tail of dozens of small charges adds up. Nobody monitors until the monthly bill arrives.

**Prevention:**
1. AWS Budget alarm at $40/month (warning) and $50/month (critical) -- already planned.
2. AWS Budget action at $60/month that auto-disables the EventBridge schedule (pipeline pauses rather than hemorrhaging money).
3. CloudWatch Logs: set retention to 14 days on all Lambda log groups. Default is "never expire" -- logs accumulate indefinitely and cost $0.03/GB/month.
4. S3 raw documents: set a lifecycle rule to transition to S3 Glacier after 90 days and delete after 365 days. Raw HTML from a 2025 scrape has no value in 2027.
5. OpenAI API: set a monthly spend limit in the OpenAI dashboard ($20/month is generous for this volume).
6. RUNBOOK.md: include the exact AWS Billing dashboard URL and what to look for monthly.

**Phase:** Phase 1 (log retention, S3 lifecycle, budget alarms), Phase 4 (RUNBOOK).

**Confidence:** HIGH -- AWS cost surprises for small-budget projects are extremely common.

---

### Pitfall 15: SEARCH-PROFILES.md as a Single Point of Configuration Failure

**What goes wrong:** SEARCH-PROFILES.md is a Markdown file that drives HyDE generation, evaluation weights, profile selection, and digest labeling. A malformed edit (broken YAML frontmatter, missing required field, typo in profile_id) cascades through the entire pipeline. Staff are expected to edit this file when programs change, but they are not developers and may not understand the format constraints.

**Why it happens:** Structured data in a Markdown file is fragile. There is no schema validation on file save. A missing colon, extra space, or deleted section header breaks the parser.

**Prevention:**
1. Write a `validate_profiles.py` script that parses SEARCH-PROFILES.md and validates all required fields exist, profile_ids are from the allowed set, weights sum correctly, etc. Run this in the HyDE generation script before any processing.
2. Provide a template/example at the top of the file showing the exact format for adding or editing a profile.
3. Consider a Google Form or simple web form that writes to the file -- removes the "edit a text file" requirement entirely for staff. This is a v2 enhancement.
4. Git-based edit workflow: staff edit in GitHub web UI where formatting issues are more visible than in a plain text editor.

**Phase:** Phase 1 (validation script), Phase 4 (staff documentation).

**Confidence:** MEDIUM -- this is a design choice with known tradeoffs. Validation scripts mitigate the risk adequately.

---

## Phase-Specific Warnings

| Phase | Likely Pitfall | Severity | Mitigation |
|-------|---------------|----------|------------|
| Phase 1 | pgvector index choice (IVFFlat vs HNSW) | Minor | Use HNSW from the start |
| Phase 1 | db.py connection module not handling rotation | Moderate | Build rotation-aware reconnection from day 1 |
| Phase 1 | CloudWatch log retention left at default | Minor | Set 14-day retention in CDK |
| Phase 2 | Silent scraper failures | Critical | consecutive_zeros alarm + DOM fingerprinting |
| Phase 2 | Playwright Docker image too large (cold starts) | Critical | Custom slim image, 1024MB memory |
| Phase 2 | Step Functions Map State cascade failure | Moderate | Catch blocks + ToleratedFailurePercentage |
| Phase 2 | Pydantic schema incompatibility with OpenAI | Moderate | Test every schema against API before integration |
| Phase 2 | LLM hallucinating metadata (deadlines, amounts) | Critical | Nullable fields + confidence scoring + source links |
| Phase 3 | HyDE embeddings stale for some profiles | Moderate | Hash-check trigger + quarterly review calendar |
| Phase 3 | OpenAI model deprecation | Critical | Model aliases + env vars + RUNBOOK |
| Phase 4 | Email digest ignored after month 1 | Minor | Short digests, urgency in subject line, track open rates |
| Phase 4 | Custom GPT Actions breaking on model migration | Moderate | Stable API URL + email as primary (not dependent on GPT) |
| Phase 4 | RUNBOOK insufficient for non-technical staff | Critical | Test with actual non-technical person before handoff |
| Post-handoff | System decay without developer maintenance | Critical | Quarterly health check + developer maintenance agreement |
| Post-handoff | Budget creep past $50/month | Moderate | Auto-disable budget action at $60 |
| Post-handoff | SEARCH-PROFILES.md malformed by staff edit | Moderate | Validation script + template + form (v2) |

---

## Sources

### Scraper Reliability
- [Why Most Web Scraping Systems Fail Silently](https://dev.to/anna_6c67c00f5c3f53660978/why-most-web-scraping-systems-fail-silently-and-how-to-design-around-it-40o6) -- silent failure patterns and detection strategies
- [Detecting Silent Content Changes - Hashing Strategies](https://scrapingant.com/blog/detecting-silent-content-changes-hashing-strategies-for-web) -- DOM fingerprinting approaches

### Playwright on Lambda
- [Running Playwright on AWS Lambda: Challenges & Solutions](https://www.browsercat.com/post/running-playwright-on-aws-lambda-challenges-solutions) -- Docker image approach, memory requirements
- [Playwright on Lambda Container Tips](https://developer.mamezou-tech.com/en/blogs/2024/07/19/lambda-playwright-container-tips/) -- image optimization

### OpenAI Model Deprecation
- [OpenAI Deprecations](https://developers.openai.com/api/docs/deprecations) -- official deprecation schedule
- [GPT-4o Retirement: Prompt Migration](https://www.echostash.app/blog/gpt-4o-retirement-prompt-migration-production) -- migration best practices
- [OpenAI Retires GPT-4o API](https://lpcentre.com/news/openai-ends-chatgpt-four-api) -- GPT-4o retired March 31, 2026

### Pydantic + OpenAI Structured Outputs
- [How to Fix OpenAI Structured Outputs Breaking Pydantic Models](https://medium.com/@aviadr1/how-to-fix-openai-structured-outputs-breaking-your-pydantic-models-bdcd896d43bd) -- schema compatibility issues
- [openai-python Issue #1659](https://github.com/openai/openai-python/issues/1659) -- known schema conversion bugs

### Step Functions Error Handling
- [AWS Step Functions: Tolerated Failure Threshold](https://docs.aws.amazon.com/step-functions/latest/dg/maprun-fail-threshold.html) -- Map State failure configuration
- [Parallel Task Error Handling in Step Functions](https://dev.to/aws-builders/parallel-task-error-handling-in-step-functions-4f1c) -- Catch/Retry patterns

### Secrets Manager Rotation
- [Troubleshoot AWS Secrets Manager Rotation](https://docs.aws.amazon.com/secretsmanager/latest/userguide/troubleshoot_rotation.html) -- rotation failure modes

### Custom GPT Actions
- [Custom GPT Actions in 2026](https://www.lindy.ai/blog/custom-gpt-actions) -- current status and model restrictions
- [ChatGPT Enterprise Release Notes](https://help.openai.com/en/articles/10128477-chatgpt-enterprise-edu-release-notes) -- Actions model support

### HyDE Limitations
- [HyDE: Hypothetical Document Embeddings - Zilliz](https://zilliz.com/learn/improve-rag-and-information-retrieval-with-hyde-hypothetical-document-embeddings) -- hallucination and domain drift risks

### Nonprofit Software Handoff
- [9 Mistakes with Nonprofit Software](https://cathexispartners.com/mistakes-you-might-be-making-with-your-nonprofit-software/) -- training and documentation gaps
- [Software Support for Nonprofits](https://www.maxiomtech.com/software-support-for-nonprofits-ensures-growth/) -- maintenance continuity
