# Hanna Center Grants AI Agent

## What This Is

An end-to-end AI-powered grants pipeline for Hanna Center — a 75-year-old nonprofit based in Sonoma, California serving youth, families, and communities impacted by trauma. Hanna provides mental health services, residential housing, trauma-informed training, and community support programs to 5,500+ participants annually. The system automatically discovers eligible grant opportunities from the web, evaluates their fit against Hanna Center's mission and programs, generates draft proposals, and tracks deadlines — all surfaced to grant staff via automated reports and notifications.

## Core Value

Grant staff can discover, evaluate, and begin applying to relevant grants in a fraction of the time, with AI handling research and first drafts while humans make final decisions.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] System automatically finds new grant opportunities via web research and public grant APIs
- [ ] System evaluates each grant's fit against Hanna Center's mission, programs, and eligibility criteria
- [ ] System generates draft grant proposals based on Hanna's org profile and past submissions
- [ ] System tracks application deadlines and sends reminders to grant staff
- [ ] System runs as an automated pipeline (CLI/script) with output to email or Slack
- [ ] Grant staff can review matched grants with fit scores and reasoning
- [ ] System ingests Hanna Center's org profile, past grants, and program guidelines as context

### Out of Scope

- Full web application / browser UI — CLI/script pipeline is sufficient for v1
- Automatic grant submission — humans review and submit all applications
- Real-time chat interface — not needed for v1
- Mobile app — out of scope entirely

## Context

- **Organization**: Hanna Center, Sonoma, California — 75-year-old nonprofit serving youth, families, and communities impacted by trauma and adversity. 5,518 annual participants, 36+ partner organizations.
  - Programs: Mental health & wellness (community mental health hub), residential (housing + life skills + Hanna Academy), training & research (trauma-informed certification, national reach), community support (recreation, camps, vocational, alumni)
  - Key grant sources: SAMHSA, HHS trauma/mental health programs, California DHCS, Sonoma County Community Foundation, California Wellness Foundation, Blue Shield of California Foundation, Walter S. Johnson Foundation
- **Grant lifecycle**: Prospecting → Fit evaluation → Proposal drafting → Deadline tracking
- **Key grant terminology**: RFP (Request for Proposal), RFA (Request for Application); funders care about mission alignment, eligibility, staff capacity, reporting burden, and relationship history
- **Materials pending**: Hanna Center will provide examples of past grants received and program guidelines — these will be used to build the org profile and RAG context for proposal drafting
- **Research already done**: Full tech stack and grant domain research completed in prior session (LangGraph, Claude API, Grants.gov API, pgvector, Playwright/Firecrawl)
- **Timeline**: 1-2 months to deliver; this week focused on research prep for 1:1 meeting with Hanna Center

## Current State (Discovery Call — 2026-03-03)

**How Hanna currently finds grants:**
- **Instrumental** — paid grant database ($3,000/year); this system is intended to replace it
- **Google Search** — manual keyword searching, clicking through from one grant to related sources
- **Wells Fargo Philanthropy** — foundation grant portal
- **Pacifica Grant Foundation** — additional foundation source
- Current process is fragmented, manual, and time-intensive; no automated prospecting

**How Hanna currently evaluates grants:**
Their real evaluation framework (directly informs our scoring model):
1. Is this aligned with our **strategic priorities**? (not just mission — active focus areas)
2. What is the **true staff time cost**? (application + reporting + compliance)
3. What is the **reporting burden**? (light/medium/heavy)
4. Is **relationship-building required** or optional? (some funders require prior relationship)
5. Does this fit our **current funding timeline**? (staff capacity, deadlines, active grant load)
6. Is this for **current programs** or would it require building new programs?

**Current AI tooling:**
- Using Grant Writing GPT (now overwhelmed / overloaded) + secondary ChatGPT Grant Writing Assistant
- Have discussed multi-GPT orchestration (step 1+2 done, want step 3 with 3 separate GPTs)
- Our LangGraph 3-agent architecture directly addresses this need

**HITL confirmed as a priority:** Staff explicitly want an approval checkpoint before any drafting — not just nice-to-have, it's a workflow requirement.

**Open questions from Hanna:**
- API costs (budget concern — target <$50/month)
- Do they already have documented grant criteria anywhere?
- How to handle grants for future programs vs current programs

**Pending decisions (to resolve before Week 9):**
- **SES sending verification method**: Email address verification (Marisa clicks one link in her inbox — no IT/DNS needed) vs. domain verification (add DNS record to hannacenter.org — requires Hanna IT). Email address verification is simpler and removes the IT dependency entirely. Decide which address to send FROM and confirm with Marisa before Week 8.

**Pending decisions (to resolve before Phase 3 prompt design):**
- **Evaluator flag calibration**: Three flags need Hanna-specific inputs before prompts are written: (1) ROI estimate — need Hanna's loaded labor rate and typical application hours; (2) Reporting burden — need to calibrate what light/medium/heavy means for a 2-person grants team; (3) Timeline fit — need a mechanism to capture current staff capacity (changes weekly). Schedule 30-min call with Marisa before Week 7.

## Constraints

- **Timeline**: 1-2 months to delivery — scope must stay focused
- **Budget**: Nonprofit context — target <$50/month total infrastructure cost
- **Materials**: Org-specific context (past grants, guidelines) not yet available — system must be designed to plug them in later
- **Interface**: Custom GPT — staff already use ChatGPT daily; zero learning curve
- **Deployment**: AWS — existing infrastructure available

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Custom GPT as staff interface | Staff already use ChatGPT daily (Grant Writing GPT); zero learning curve; Actions connect to AWS backend. **Hanna has ChatGPT Enterprise — Custom GPT with Actions is fully supported at no additional cost.** | Decided |
| AWS infrastructure (Lambda + API Gateway) | Existing AWS access available; keeps everything in one ecosystem | Decided |
| **RDS PostgreSQL t4g.micro + pgvector (publicly accessible)** | Aurora Serverless v2 rejected — $43–48/month floor. Neon considered but rejected — keeps everything on one AWS platform for long-term maintainability (Hanna is non-technical org). RDS publicly accessible + password in Secrets Manager + SSL enforced = clean, $13–15/month, zero additional networking cost. | **Decided** |
| Tiered LLM routing | GPT-4o-mini for pre-filter, GPT-4o for scoring + drafting + edge cases | Decided |
| LangGraph for background pipeline | Stateful ingestion + processing pipeline; runs on Lambda triggered by EventBridge Scheduler cron | Decided |
| **grants.ca.gov API as primary source (not Candid)** | Hanna's largest grants ($2M CYBHI, $550K EYC, $614K ARPA) all came through California state programs — all on grants.ca.gov for free. Candid costs ~$3,499/year and Hanna does not qualify for free tier ($17.5M operating budget). IRS 990-PF via Grantmakers.io covers foundation discovery for free. | **Decided — replaces Candid** |
| API-first ingestion strategy | Stable APIs (grants.ca.gov, Grants.gov) preferred over scrapers; scrapers only where no API exists | Decided |
| Structured outputs (Pydantic) | All LLM responses validated against schema; immune to model updates changing output format | Decided |
| Versioned prompts as files | Prompts stored as .txt/.md in repo; tunable by non-developers without code changes | Decided |
| HITL in Custom GPT chat | Staff approve/skip grants conversationally in ChatGPT; confirmed workflow requirement | Decided |
| **OpenAI API (primary), Claude API (testing fallback)** | GPT-5.4 for production pipeline (evaluation, HyDE, drafting); GPT-5.4-mini for pre-filter and metadata extraction. Claude API used for testing/comparison. LangGraph is LLM-agnostic — swapping providers requires only changing the model client, no architecture changes. | **Decided** |
| **Real-time API (not Batch API)** | Batch API saves ~$0.19/month at steady state (30–80 grants/week) — not worth the async complexity. Real-time API keeps pipeline synchronous, fails loudly, easier to maintain post-handoff. Batch API can be added later if volumes scale significantly. | **Decided** |
| **HyDE auto-regeneration on org profile change** | HyDE query generated once in Phase 1 and reused. Stores a hash of ORG-PROFILE.md alongside the query. On each pipeline run, compares current hash to stored — if changed, regenerates HyDE automatically. Secondary EventBridge rule forces annual regeneration every January 1st. Staff update ORG-PROFILE.md when priorities shift; system adapts with no developer involvement. | **Decided** |
| EventBridge Scheduler (not GitHub Actions) | Native AWS cron; eliminates external dependency; everything stays in one ecosystem | Decided |
| Bedrock Titan Embeddings (not Ollama) | Ollama requires EC2 to run in cloud; Bedrock is fully managed, pennies at grant volumes, no server to maintain | Decided |
| Amazon SES (not Resend) | Cheaper ($0.10/1K emails), native AWS, one less external account to manage | Decided |
| Firecrawl conditional | Keep only if Playwright on Lambda can't handle a site; test in Phase 2 before committing | Decided |
| AWS Secrets Manager | All API keys (OpenAI, Claude, Firecrawl) stored in Secrets Manager; never hardcoded | Decided |
| **API Gateway auth: API key (`x-api-key` header) + usage plan** | Custom GPT Actions pass API key as `x-api-key` header; API Gateway validates natively before Lambda. Usage plan: 10 req/sec, 500 req/day — sufficient for 3 staff users, prevents runaway Custom GPT loops. Key stored in Secrets Manager post-deploy. | **Decided** |
| **Lambda execution role: least-privilege IAM** | Scoped to specific ARNs: CloudWatch Logs, one Secrets Manager secret, one S3 bucket, Bedrock Titan V2 model only. No `*` resources. CDK `grant_read`/`grant_read_write` methods enforce this automatically. | **Decided** |
| **HITL model: async email approval + Custom GPT conversational layer** | SES digest is primary weekly delivery (passive, no action required). Staff approve/skip via one-click email links → API Gateway → RDS `approval_status` update. Custom GPT is the conversational layer for grant questions, on-demand search, and drafting triggers. Two independent LangGraph runs (evaluate + draft) connected only through RDS — no checkpoint storage or callback tokens needed. | **Decided** |
| **Google Sheets pipeline tracker (read-only v1)** | After each weekly evaluation run, a Sheets Lambda appends scored grants to a shared Google Sheet. Cumulative history, filterable by profile/funder/score. Hanna uses Google Workspace for Nonprofits (free). Approval still via email/Custom GPT in v1. v1.5 upgrade: Apps Script webhook for sheet → RDS write-back. | **Decided** |
| **CSV export endpoint** | `GET /grants/export.csv` filterable by profile, week, status. Accessible via bookmarked URL or Custom GPT. Staff can open in Excel, Google Sheets, or Numbers. Zero ongoing maintenance. | **Decided** |
| **RDS password rotation: 90-day automatic via Secrets Manager** | `add_rotation_single_user(automatically_after=Duration.days(90))` — Secrets Manager replaces password and notifies Lambda. Compensates for RDS being publicly accessible (required for Lambda outside VPC to avoid $32/month NAT Gateway). | **Decided** |
| **RDS public access: accepted trade-off** | Lambda outside VPC cannot use SG-to-SG referencing — static SG restriction is not possible without NAT Gateway. Mitigated by: SSL enforced, 90-day rotation, strong password. No PII in grants table (grant text is public data). Revisit if compliance requirements change. | **Decided** |
| **Scraper architecture: fan-out Lambda** | 13 scrapers cannot run sequentially in one Lambda (15-min timeout). Fan-out: one orchestrator Lambda invokes 13 scraper Lambdas in parallel (async). Each scraper is isolated — one failure doesn't affect others. Total runtime = slowest single scraper (~75s), not sum of all 13. One scraper Lambda function accepts a config object (scraper_registry.json) — adding a new source = one JSON entry, no new Lambda function. Deployed as Docker container for local testability. | **Decided** |
| **Grant volume: backfill vs. steady state** | 500–900 grants is a one-time initial backfill (Week 1 only) — all available history pulled from APIs + scrapers. Steady state after Week 1 is 30–80 new grants/week — deduplication via content hash skips everything already in RDS. Cost estimates are accurate for steady state. Week 1 requires a dedicated bulk load script (batches of 50) separate from the daily pipeline cron. | **Decided** |

## Roadmap

### Phase 1 — Infrastructure + Embeddings (Weeks 1–2, Mar 17–30 | 20 hrs)
**Goal**: Everything is set up before a single line of pipeline code is written. The system "knows" Hanna Center.

- AWS infrastructure (RDS PostgreSQL t4g.micro + pgvector, Lambda, API Gateway scaffold, S3, CloudWatch, Secrets Manager, EventBridge)
- Org profile JSON encoded from `ORG-PROFILE.md`
- pgvector schema, Bedrock Titan embeddings, past grant chunks stored
- HyDE query generated and stored with org profile hash for auto-regeneration
- Scraper target list finalized (Grantmakers.io CA foundation filter)
- *Note: Week 2 capped at 10 hrs (finals)*

---

### Phase 2 — Data Ingestion: APIs + Scrapers (Weeks 3–4, Mar 31–Apr 13 | 40 hrs)
**Goal**: All priority grant sources flow into the database automatically, daily.

- grants.ca.gov + Grants.gov API connectors with metadata extraction
- 10 Playwright scrapers: 5 Sonoma County portals + 5 CA foundation priority sites (3 lower-priority sites deferred to v2)
- Fan-out Lambda orchestrator (one orchestrator → parallel scraper Lambdas)
- Content-hash deduplication — skip grants already in DB
- EventBridge daily cron, CloudWatch source-health alarms, error handling
- *No dedicated buffer week — pipeline hardening absorbed inline*

---

### Phase 3 — AI Pipeline: Prospector + Evaluator (Week 4, Apr 7–13 | shared with Phase 2)
**Goal**: The AI finds the best candidates and produces scored, flagged, reasoned recommendations.

- LangGraph pipeline scaffold (shared state, node definitions)
- Prospector agent: HyDE pgvector search → top 50 → gpt-5-mini pre-filter (~75% rejection)
- Evaluator agent: gpt-5 scoring (1–10 fit score, reasoning, 6 flags) + gpt-5 escalation for borderline cases
- Pydantic validation on all agent outputs
- AWS API Gateway endpoints: `GET /grants/matched`, `POST /grants/{id}/approve`, `POST /grants/{id}/skip`, `GET /grants/approved`

---

### Phase 4 — Interface: Email Digest + Custom GPT (Week 5, Apr 14–17 | ~15 hrs)
**Goal**: Staff receive weekly digest and can act on it in ChatGPT with zero learning curve.

- Amazon SES weekly email digest (Monday 8am PT): score, reasoning, flags, deadline, link to GPT
- Custom GPT in ChatGPT Enterprise: system prompt, Actions (OpenAPI spec → API Gateway)
- Approve/skip HITL flow end-to-end
- End-to-end testing, threshold tuning, staff onboarding guide, CloudWatch billing alarm
- Handoff to Hanna Center

---

### Phase 5 — Funder Match Pipeline (post-v1)
**Goal**: Build a funder intelligence layer — so the system doesn't just find grants, it tracks the funders behind them.

**Problem it solves**: Hanna's grants team manages ongoing funder relationships. When a new grant appears from a known funder (e.g. Walter S. Johnson Foundation, Blue Shield CA Foundation), it should be flagged immediately and scored higher — relationship history changes the calculus. Today this context lives only in staff memory.

**What it builds**:
- **Funder database**: Ingest Hanna's existing Instrumentl CSV export (949 funder matches + 65 opportunity matches) via Custom GPT `POST /data/import` → stored in RDS `funders` table with profile fields (focus areas, typical grant size, geography, relationship status, last award)
- **Foundation enrichment**: Pull IRS 990-PF data via Grantmakers.io API for known funders — augment profiles with historical giving amounts, grantee lists, recent filing activity
- **Funder-grant linkage**: On every new grant ingested, match funder name against the `funders` table — attach funder profile to grant record. Known/watched funders get a `known_funder` flag surfaced in evaluation and digest
- **Evaluator integration**: Evaluator agent reads `known_funder` flag — boosts score and adds funder relationship context to reasoning (e.g. "Walter S. Johnson has funded Hanna twice — strong relationship advantage")
- **Proactive funder monitoring**: EventBridge weekly job checks watched funders' foundation sites for new grant cycles — reverse prospecting (funder-first, not grant-first)
- **Custom GPT interface**: `GET /funders/watching` returns watch list with relationship status, last award, and any open grant cycles

**Data sources**:
- Instrumentl CSV export (free — Hanna already pays for Instrumentl)
- IRS 990-PF via Grantmakers.io (free, open source)
- Funder websites (existing Playwright scrapers from Phase 2)

**Why deferred to Phase 5**: Requires the ingestion pipeline (Phase 2) and evaluation agent (Phase 3) to be live first. The funder match layer enhances existing signals rather than replacing them — it's additive, not foundational. Phase 5 can be scoped and built once the v1 pipeline is running and Hanna's team has validated the core workflow.

---

## Final Tech Stack

| Layer | Tool |
|-------|------|
| LLMs (pre-filter) | GPT-4o-mini (OpenAI API) |
| LLMs (scoring + evaluation) | GPT-4o (OpenAI API) |
| LLMs (edge cases) | GPT-4o (OpenAI API) |
| AI orchestration | LangGraph (runs on Lambda) |
| Vector database | **RDS PostgreSQL t4g.micro + pgvector** |
| Embeddings | Amazon Bedrock Titan Embeddings |
| CA state grant data | **grants.ca.gov API** (free, via data.ca.gov) |
| Federal grant data | Grants.gov API (free, no key) |
| Foundation discovery | **IRS 990-PF / Grantmakers.io** (free, open source) |
| Federal award history | USASpending.gov API (free, no key) |
| Web scraping | AWS Lambda + Playwright (headless Chromium) |
| Scraping fallback | Firecrawl (only if Playwright insufficient) |
| Compute | AWS Lambda |
| API layer | AWS API Gateway |
| Cron scheduling | AWS EventBridge Scheduler |
| Email delivery | Amazon SES |
| Secrets management | AWS Secrets Manager |
| Logging + monitoring | AWS CloudWatch |

---
| **Multi-profile HyDE (6 profiles)** | A single HyDE query from the full ORG-PROFILE.md creates an averaged vector that underperforms for department-specific searches. Mental Health Hub grants and CTE education grants occupy different positions in embedding space. The system maintains one HyDE embedding per department: mental-health-hub, hanna-institute, residential-housing, hanna-academy, recreation-enrichment, general-operations. Staff select a profile in Custom GPT ("Search grants for the Academy") — the system loads that profile's HyDE, applies department-specific evaluation weights, and labels the digest accordingly. Running all profiles deduplicates by grant_id and uses the highest score. | **Decided** |
| **Step Functions Express for ingestion; LangGraph for evaluation only** | The ingestion pipeline (scrape → extract → embed → dedup → store) is linear and deterministic — no runtime branching, no LLM routing decisions. LangGraph adds complexity without benefit for ETL. Step Functions Express handles fan-out of 17 scraper Lambdas via Map State, includes built-in retry/failure visibility, and is native AWS (auditable in the console). LangGraph is reserved for Phase 3 (Prospector → Evaluator → HITL) where multi-agent stateful routing is genuinely needed. | **Decided** |
| **17 scraper targets (expanded from 13)** | Added: BSCC (bscc.ca.gov) for OJJDP/Title II pass-through; ProPublica Nonprofit Explorer API (IRS 990-PF data for foundation discovery); 5 separate Sonoma County department portals (HHSA, Probation, OES, CSS, Behavioral Health) to replace the single "Sonoma County" placeholder. HRSA and ACF/HHS already covered by grants.gov API — no separate scrapers needed. Total: 5 APIs + 12 scrapers. | **Decided** |
| **Search profiles mapped to Hanna departments** | Each profile corresponds to a real Hanna department with a distinct VP/director lead, distinct programs, and a distinct grant market. Profile definitions live in org-materials/SEARCH-PROFILES.md and are owned by Marisa Binder/Monica Argenti. The file includes: lead contact, active programs, target funders, evaluation weight adjustments (boosts and flags), and the HyDE seed prompt used by generate_hyde.py. Staff update profiles when programs change; system auto-detects and regenerates HyDE on next run. | **Decided** |
| **Approval state in RDS grants table** | `approval_status` column (pending/approved/skipped/drafted) prevents approved grants from re-surfacing in future digests. `approved_profile_id` records which profile was active when the grant was approved. This resolves the previously undefined state between HITL approval and v2 Drafter execution. | **Decided** |
| **Operational runbook as Phase 4 deliverable** | RUNBOOK.md created at project root covering: pipeline health checks (Step Functions console), digest troubleshooting, restart procedures, adding new sources, org profile update process, evaluation criteria tuning, cost monitoring, and annual maintenance checklist. Designed for Marisa Binder/Monica Argenti — no AWS or technical knowledge assumed. | **Decided** |

*Last updated: 2026-03-26 — multi-profile HyDE (6 profiles), Step Functions for ingestion, LangGraph scoped to Phase 3 evaluation only, 17 scrapers (added BSCC + ProPublica + 5 Sonoma County departments), SEARCH-PROFILES.md created, approval_status in RDS schema, RUNBOOK.md created*
