# Technology Stack: Hanna Center Grants AI Agent

**Project:** Hanna Center Grants AI Agent
**Researched:** 2026-03-26
**Overall confidence:** HIGH (all major decisions validated against current docs/releases)

---

## Recommended Stack

### Python Runtime

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.13 | Lambda runtime + local dev | Latest AWS Lambda-supported runtime (GA). Support through June 2029. Based on Amazon Linux 2023. Use `python3.13` runtime for managed Lambdas and `public.ecr.aws/lambda/python:3.13` for Docker-based scraper Lambdas. |

**Validation:** Python 3.13 is fully supported on AWS Lambda as of early 2026. LangGraph 1.1.0 supports Python 3.13 (confirmed via LangChain changelog). Pydantic v2.12+ supports Python 3.13. No compatibility blockers found.

**Why not 3.12:** 3.13 is GA on Lambda, has better performance, and longer support window. No reason to pin to 3.12 unless a dependency requires it (none do).

---

### Infrastructure as Code

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| AWS CDK (Python) | ~2.244.0 | Infrastructure definition | Native AWS IaC. Type-safe Python constructs. `grant_read`/`grant_read_write` methods enforce least-privilege IAM automatically. Single `cdk deploy` creates entire stack. |
| aws-cdk-lib | ~2.244.0 | CDK construct library | Mono-package for all AWS services. Pin to `~=2.244` (compatible releases) in requirements. |
| constructs | >=10.0.0 | CDK base constructs | Required peer dependency for aws-cdk-lib. |

**Installation:**
```bash
pip install "aws-cdk-lib>=2.244.0,<3.0.0" "constructs>=10.0.0,<11.0.0"
```

---

### LLM Layer

| Use Case | Model | API Name | Context | Pricing (per 1M tokens) | Rationale |
|----------|-------|----------|---------|--------------------------|-----------|
| Pre-filter (binary: relevant?) | GPT-5.4-mini | `gpt-5.4-mini-2026-03-17` | 400K | $0.75 in / $4.50 out | Cheapest classification. High volume (50+ grants/week). |
| Metadata extraction (HTML/PDF) | GPT-5.4-mini | `gpt-5.4-mini-2026-03-17` | 400K | $0.75 in / $4.50 out | Structured output, low cost. |
| HyDE query generation | GPT-5.4 | `gpt-5.4-2026-03-05` | 1.1M | $2.50 in / $15.00 out | Profile-aware creative writing. Run once per profile, cached. |
| Fit scoring + evaluation | GPT-5.4 | `gpt-5.4-2026-03-05` | 1.1M | $2.50 in / $15.00 out | Primary workhorse. Structured eval with 7 flags. |
| Edge case review (6-7/10 scores) | GPT-5.4 | `gpt-5.4-2026-03-05` | 1.1M | $2.50 in / $15.00 out | Same model, higher-context prompt. |
| Proposal drafting (v2) | GPT-5.4 | `gpt-5.4-2026-03-05` | 1.1M | $2.50 in / $15.00 out | Long-form grant writing. |
| Custom GPT interface | GPT-5.4 (built-in) | N/A (ChatGPT Enterprise) | N/A | $0 (Enterprise sub) | Staff already use it daily. Zero learning curve. |

**Model routing rationale:** Single provider (OpenAI) simplifies key management and error handling. GPT-5.4-mini handles high-volume cheap calls. GPT-5.4 handles all evaluation and drafting. Claude API retained as testing fallback -- LangGraph is provider-agnostic, swapping requires only the model client initialization.

**VALIDATED: GPT-5.4 and GPT-5.4-mini are current as of March 2026.** Both support OpenAI Structured Outputs (`response_format` with Pydantic models). The OpenAI SDK handles Pydantic-to-JSON-Schema conversion automatically.

**Cost estimate at steady state (30-80 grants/week):**
- GPT-5.4-mini (pre-filter + extraction): ~50-80 calls/week, short prompts = ~$0.50-1.00/month
- GPT-5.4 (evaluation + HyDE): ~15-25 calls/week, longer prompts = ~$3.00-8.00/month
- **Total OpenAI API: ~$4-9/month** (within $50 budget)

---

### OpenAI SDK

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| openai | >=2.30.0 | OpenAI API client | Official SDK. Supports Structured Outputs natively with Pydantic. Sync + async. Python 3.9+. |

**Key feature: Structured Outputs.** Pass a Pydantic model as `response_format` and the SDK handles JSON Schema conversion + response deserialization. This replaces manual JSON parsing and most retry logic for schema failures.

```python
from pydantic import BaseModel
from openai import OpenAI

class GrantMetadata(BaseModel):
    title: str
    funder: str
    deadline: str  # ISO format
    funding_min: int | None
    funding_max: int | None
    geography: str
    eligibility: str

client = OpenAI()
response = client.responses.create(
    model="gpt-5.4-mini-2026-03-17",
    input="Extract grant metadata from this HTML...",
    text={"format": {"type": "json_schema", "name": "GrantMetadata", "schema": GrantMetadata.model_json_schema()}}
)
```

**Gotcha:** OpenAI Structured Outputs support a subset of JSON Schema. Avoid Pydantic validators like `ge=`, `le=`, `pattern=` in models passed to `response_format` -- these generate unsupported JSON Schema keywords. Keep validation models simple (types + Optional), then validate business rules in a separate Pydantic model post-response.

---

### AI Orchestration

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| langgraph | >=1.1.0 | Multi-agent evaluation pipeline | Stateful graph with conditional routing. Prospector -> Evaluator -> HITL. Python 3.13 compatible. |
| langchain-openai | >=0.3.0 | OpenAI model bindings for LangGraph | Provides `ChatOpenAI` wrapper used by LangGraph nodes. |
| langchain-core | >=0.3.0 | Base abstractions | Required by langgraph. Message types, runnables. |

**VALIDATED: LangGraph 1.1.0 released March 10, 2026.** Stable 1.x API. No breaking changes from 0.x that affect this architecture.

**Scoping decision VALIDATED:** LangGraph for evaluation pipeline only (Phase 3). Step Functions Express for ingestion ETL. This is the correct split -- LangGraph adds unnecessary complexity to a deterministic ETL pipeline, but is genuinely needed for multi-agent stateful routing with HITL.

**NOT using `langgraph-checkpoint-postgres`:** The HITL design does not require LangGraph to persist state between runs. Approval is an RDS column update, not a LangGraph checkpoint resume. Two independent LangGraph runs (evaluate + draft) connected only through RDS. This avoids the checkpoint schema, the `.setup()` migration step, and the psycopg3 dependency that `langgraph-checkpoint-postgres` brings.

---

### Database / Vector Store

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| RDS PostgreSQL | 16.x | Primary database | Relational + vector in one. t4g.micro = ~$13-15/month. |
| pgvector | 0.8.0 | Vector similarity search | Available on RDS PostgreSQL 16.x. HNSW + IVFFlat indexes. Iterative scan for filtered queries (new in 0.8.0). |

**VALIDATED: pgvector 0.8.0 is available on Amazon RDS for PostgreSQL 14.14+.** Use PostgreSQL 16.x (latest major on RDS) to get pgvector 0.8.0 with iterative scan support. pgvector 0.8.2 exists upstream (fixes CVE-2026-3172 for parallel HNSW builds) but may not yet be on RDS -- check at deploy time.

**pgvector 0.8.0 new feature -- iterative scan:** `SET hnsw.iterative_scan = on;` prevents overfiltering when combining vector search with WHERE clauses (e.g., `WHERE deadline > now() AND geography ILIKE '%california%'`). Directly benefits the Prospector's filtered vector search. Enable this in the connection setup.

**Index recommendation:** Use HNSW (not IVFFlat) for the grants table. At <10K vectors, HNSW provides exact-quality results with no training step. IVFFlat requires a training corpus and degrades on small datasets.

```sql
CREATE INDEX ON grants USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
```

**RDS configuration VALIDATED:**
- t4g.micro: 2 vCPU, 1 GB RAM, $13-15/month. Sufficient for <10K grants + 6 HyDE embeddings.
- Publicly accessible + SSL enforced + 90-day password rotation via Secrets Manager. Acceptable trade-off for $32/month NAT Gateway savings. No PII stored.
- ~80-100 max connections. Step Functions `max_concurrency=5` prevents saturation.

**Alternatives REJECTED (still correct):**
- Aurora Serverless v2: $43-48/month floor. Does NOT scale to zero. Budget-killing.
- Neon: Off-AWS. Harder post-handoff for non-technical org.
- Supabase: Unnecessary third-party dependency.
- Pinecone: Unnecessary. pgvector handles this scale trivially.

---

### PostgreSQL Client

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| psycopg2-binary | >=2.9.10 | PostgreSQL adapter | Synchronous, battle-tested on Lambda. Zero-config binary install for Docker containers. No compilation needed. Module-level connection caching works perfectly for Lambda warm starts. |

**Why psycopg2-binary, not psycopg3:**
1. Lambda functions are synchronous -- psycopg3's async advantage is irrelevant.
2. `psycopg2-binary` is a single pip install with no system dependencies -- critical for Docker Lambda images.
3. The project has no Django dependency and no need for pipeline mode.
4. Connection caching via module-level `_conn` global works identically in both -- no advantage to psycopg3's built-in pooling on Lambda (one connection per container).
5. psycopg3 has reported performance regressions in batch insert scenarios -- relevant for the initial 500-900 grant backfill.

**If migrating later:** psycopg3 (`psycopg[binary]>=3.2.0`) is the future and should be considered for v2 if async Lambda or pipeline mode becomes valuable.

---

### Embeddings

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Amazon Bedrock Titan Text Embeddings V2 | `amazon.titan-embed-text-v2:0` | Grant + HyDE embeddings | Fully managed. 1024 dimensions. Up to 8,192 tokens input. ~$0.0001/1K tokens. Stays within AWS ecosystem. |

**VALIDATED:** Titan Embeddings V2 remains the correct choice. At grant volumes (~100 grants/week + 6 HyDE queries), cost is effectively $0.01/month or less.

**Invoked via boto3:**
```python
import boto3, json
bedrock = boto3.client("bedrock-runtime", region_name="us-west-2")
response = bedrock.invoke_model(
    modelId="amazon.titan-embed-text-v2:0",
    body=json.dumps({"inputText": grant_text, "dimensions": 1024})
)
```

**Why not OpenAI embeddings:** Keeps embedding generation within AWS (no external API call from Lambda). Cheaper. No API key needed -- IAM handles auth. One less external dependency.

---

### Web Scraping

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| playwright | >=1.50.0 | Headless Chromium scraping | Handles JS-rendered pages. Docker deployment on Lambda. 12 scraper targets. |

**VALIDATED: Playwright 1.50+ supports Python 3.13.** Latest is 1.58.0 (Jan 2026). Pin to `>=1.50.0,<2.0.0` for stability.

**Lambda deployment approach:** Docker container image using `public.ecr.aws/lambda/python:3.13` base + Playwright Chromium install. This is the recommended approach over Lambda Layers (size limits, dependency complexity).

**Docker configuration for scraper Lambda:**
```dockerfile
FROM public.ecr.aws/lambda/python:3.13
RUN pip install playwright psycopg2-binary boto3
RUN playwright install chromium --with-deps
COPY . ${LAMBDA_TASK_ROOT}
CMD ["handler.lambda_handler"]
```

**Key settings:**
- Lambda memory: 1024 MB minimum (Chromium needs this)
- Lambda timeout: 120 seconds per scraper (most sites resolve in 30-60s)
- Headless mode only: `browser.launch(headless=True)`
- Single browser engine (Chromium only) -- keeps image small

**Fallback:** Firecrawl API ($16/month for 3K pages) only if Playwright fails on JS-heavy foundation sites. Test during Phase 2 before committing.

---

### Data Validation

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| pydantic | >=2.12.0 | Schema validation for all LLM outputs | V2 performance (Rust core). OpenAI Structured Outputs integration. Type-safe grant metadata models. |

**VALIDATED: Pydantic 2.12.5 is current stable.** 2.13.0 in beta. Pin to `>=2.12.0,<3.0.0`.

**Two-model pattern for OpenAI Structured Outputs:**

```python
# Model 1: Simple schema for OpenAI response_format (no advanced validators)
class GrantMetadataRaw(BaseModel):
    title: str
    funder: str
    deadline: str
    funding_min: int | None = None
    funding_max: int | None = None

# Model 2: Full validation for business rules (applied after LLM response)
class GrantMetadataValidated(BaseModel):
    title: str = Field(min_length=5)
    funder: str = Field(min_length=2)
    deadline: date  # parsed from string
    funding_min: int | None = Field(default=None, ge=0)
    funding_max: int | None = Field(default=None, ge=0)
```

This avoids the known gotcha where Pydantic's rich JSON Schema (with `minimum`, `pattern`, etc.) breaks OpenAI's limited JSON Schema support.

---

### API Layer

| Technology | Purpose | Why |
|------------|---------|-----|
| Amazon API Gateway (REST) | Expose endpoints for Custom GPT Actions | Native AWS. API key validation (`x-api-key`) happens before Lambda. Usage plan rate limiting. |
| AWS Lambda | Compute behind API Gateway | Serverless, scales to zero. Well within free tier at 3 staff users. |

**Endpoints:**
```
GET  /grants                      - list/filter grants
GET  /grants/{grant_id}           - full grant detail
POST /grants/{grant_id}/approve   - set approval_status
POST /grants/{grant_id}/skip      - set approval_status + skip_reason
GET  /grants/profiles             - list search profiles
GET  /grants/export.csv           - CSV download (profile/week/status filters)
POST /grants/evaluate             - trigger LangGraph evaluation run
GET  /grants/pipeline/status      - pipeline health check
```

**Auth:** API key + usage plan. Rate: 10 req/sec, burst: 20. Quota: 500 req/day. Key stored in Secrets Manager post-deploy, configured in Custom GPT Actions as `x-api-key` header.

---

### Orchestration (Ingestion)

| Technology | Purpose | Why |
|------------|---------|-----|
| AWS Step Functions Express | Ingestion pipeline (scrape -> extract -> embed -> dedup -> store) | Map State for parallel fan-out. Built-in retry + failure visibility. ~$0/month (300 free executions). |
| AWS EventBridge Scheduler | Daily cron trigger | Native AWS cron. No external dependency. |

**VALIDATED:** Step Functions Express is the correct tool for deterministic ETL. Map State with `max_concurrency=5` handles 17 scrapers safely within RDS connection limits.

---

### Notifications and Output

| Technology | Purpose | Why |
|------------|---------|-----|
| Amazon SES | Weekly email digest (Monday 8am PT) | $0.10/1K emails. Native AWS. |
| Google Sheets API | Pipeline tracker (cumulative weekly append) | Hanna uses Google Workspace for Nonprofits (free). |
| CSV export | `GET /grants/export.csv` endpoint | Zero-maintenance. Staff open in Excel/Sheets/Numbers. |

**Google Sheets libraries:**
```
google-auth>=2.36.0
google-api-python-client>=2.160.0
```

---

### Monitoring

| Technology | Purpose | Why |
|------------|---------|-----|
| Amazon CloudWatch | Lambda logs, Step Functions execution history, API Gateway metrics | Native AWS. No additional cost at this scale. |
| CloudWatch Alarms | 0-grant-in-7-days alarm, $45 billing alarm | Catch silent failures + budget overruns. |
| SQS DLQ (per scraper) | Capture failed scraper invocations | Step Functions catches failures; dead letters to SQS -> SNS email alert. |

---

## Full Dependency List (Lambda Application)

### requirements.txt (application Lambda functions)

```
# Core
openai>=2.30.0,<3.0.0
langgraph>=1.1.0,<2.0.0
langchain-openai>=0.3.0,<1.0.0
langchain-core>=0.3.0,<1.0.0
pydantic>=2.12.0,<3.0.0

# Database
psycopg2-binary>=2.9.10,<3.0.0

# AWS (included in Lambda runtime, pin for local dev)
boto3>=1.42.0

# Google Sheets output
google-auth>=2.36.0
google-api-python-client>=2.160.0
```

### requirements-scraper.txt (scraper Docker Lambda)

```
# Scraping
playwright>=1.50.0,<2.0.0

# Database
psycopg2-binary>=2.9.10,<3.0.0

# AWS
boto3>=1.42.0

# Validation
pydantic>=2.12.0,<3.0.0

# LLM (metadata extraction)
openai>=2.30.0,<3.0.0
```

### requirements-cdk.txt (infrastructure)

```
aws-cdk-lib>=2.244.0,<3.0.0
constructs>=10.0.0,<11.0.0
```

---

## Version Compatibility Matrix

| Package | Min Version | Python 3.13 | Notes |
|---------|-------------|-------------|-------|
| openai | 2.30.0 | Yes | httpx-based, no C extensions |
| langgraph | 1.1.0 | Yes | Confirmed in LangChain changelog |
| langchain-openai | 0.3.0 | Yes | Follows langgraph compatibility |
| pydantic | 2.12.0 | Yes | pydantic-core compiled for 3.13 |
| psycopg2-binary | 2.9.10 | Yes | Pre-compiled wheels available |
| playwright | 1.50.0 | Yes | No C extensions in Python package |
| boto3 | 1.42.0 | Yes | Pure Python |
| aws-cdk-lib | 2.244.0 | Yes | jsii bridge, Python 3.9+ |

---

## Total Estimated Cost (Steady State)

| Service | Monthly Cost |
|---------|-------------|
| RDS PostgreSQL t4g.micro | ~$13-15 |
| OpenAI API (GPT-5.4 + GPT-5.4-mini) | ~$4-9 |
| AWS Secrets Manager (3 secrets) | ~$1.20 |
| Amazon S3 | ~$0.05 |
| Amazon SES | ~$0.01 |
| Amazon Bedrock Titan Embeddings | ~$0.01 |
| AWS Lambda | ~$0 (free tier) |
| AWS Step Functions Express | ~$0 (free tier) |
| Amazon API Gateway | ~$0 (free tier) |
| SQS DLQ (17 queues) | ~$0 (free tier) |
| CloudWatch | ~$0 (free tier) |
| EventBridge Scheduler | ~$0 (free tier) |
| **Total** | **~$18-25/month** |

Well within the $50/month budget. Week 1 backfill (500-900 grants) may spike OpenAI costs to ~$15-20 one-time.

---

## What NOT to Use (and Why)

| Rejected | Why |
|----------|-----|
| Aurora Serverless v2 | $43-48/month floor. Does NOT scale to zero. Kills the budget. |
| Neon / Supabase | Off-AWS. Harder post-handoff for non-technical org. |
| Pinecone / ChromaDB | Unnecessary. pgvector handles <10K vectors trivially. |
| Candid API | $3,499/year. Hanna doesn't qualify for free tier. |
| Ollama / nomic-embed-text | Requires EC2. Bedrock Titan is simpler, managed, cheaper. |
| OpenAI embeddings | Extra external API call + cost. Bedrock stays within AWS. |
| GitHub Actions (cron) | External dependency. EventBridge keeps everything in AWS. |
| Resend | Third-party. SES is cheaper and AWS-native. |
| AutoGen | Conversational loop model. Poor fit for structured pipelines. |
| Scrapy | Heavy framework. Overkill for 12 targeted scrapers. |
| psycopg3 | Async benefits irrelevant on synchronous Lambda. psycopg2-binary is simpler to deploy. |
| LangGraph for ingestion | Overkill for deterministic ETL. Step Functions is the right tool. |
| langgraph-checkpoint-postgres | HITL doesn't require checkpoint resume. Approval is an RDS column update. Avoids extra schema + migration. |
| Railway / Render | Replaced by Lambda. No always-on server needed. |
| FastAPI / Flask | No web server needed. API Gateway + Lambda handlers are sufficient. |
| Firecrawl (default) | $16/month. Only activate if Playwright fails on specific sites during Phase 2 testing. |
| OpenAI Batch API | Saves ~$0.19/month at steady state. Not worth async complexity for 30-80 grants/week. |

---

## Locked Decision Validation Summary

| Decision | Status | Notes |
|----------|--------|-------|
| RDS PostgreSQL t4g.micro + pgvector | CONFIRMED | pgvector 0.8.0 on RDS. HNSW index. Iterative scan for filtered queries. |
| Step Functions Express for ingestion | CONFIRMED | Correct tool for deterministic ETL. Map State handles fan-out. |
| LangGraph for evaluation only | CONFIRMED | 1.1.0 stable. Python 3.13 compatible. |
| OpenAI GPT-5.4 + GPT-5.4-mini | CONFIRMED | Current models (March 2026). Structured Outputs supported. |
| Bedrock Titan V2 for embeddings | CONFIRMED | 1024 dims, ~$0.01/month. No changes needed. |
| Custom GPT via ChatGPT Enterprise | CONFIRMED | Actions connect to API Gateway. $0 additional cost. |
| Lambda outside VPC | CONFIRMED | Saves $32/month NAT Gateway. SSL + rotation compensates. |
| SES for email | CONFIRMED | Cheapest option. Native AWS. |
| EventBridge Scheduler | CONFIRMED | Native AWS cron. No external dependency. |
| API key + usage plan auth | CONFIRMED | Sufficient for 3 staff users on internal tool. |
| psycopg2-binary (not psycopg3) | CONFIRMED | Simpler deployment on Lambda. Async not needed. |

**No locked decisions flagged for change.** All remain the right call for this project's constraints (budget, non-technical org, AWS-only, 3 users).

---

## Gotchas and Version Warnings

1. **pgvector 0.8.2 CVE:** pgvector 0.8.2 fixes CVE-2026-3172 (buffer overflow in parallel HNSW builds). RDS may still be on 0.8.0. Check `SELECT extversion FROM pg_extension WHERE extname = 'vector';` at deploy time. If on 0.8.0, avoid parallel HNSW index builds (use `maintenance_work_mem` defaults -- single-threaded build is fine at <10K vectors).

2. **OpenAI Structured Outputs + Pydantic:** Do NOT use `Field(ge=0)`, `Field(pattern=...)`, or other constraint validators in models passed to `response_format`. OpenAI supports a subset of JSON Schema. Use a two-model pattern (simple for LLM, validated for business rules).

3. **Playwright Docker image size:** Chromium adds ~400MB to the Docker image. Keep scraper Lambda images separate from application Lambda functions. Use ECR lifecycle policy to prune old images.

4. **boto3 bundling:** Lambda Python 3.13 runtime includes boto3, but the version lags. For Bedrock Titan V2 specifically, the bundled version should work. If you encounter `UnknownServiceError` for bedrock-runtime, bundle boto3 explicitly in requirements.txt.

5. **LangGraph + langchain version alignment:** langgraph 1.1.0 requires langchain-core >=0.3.0. Pin both in requirements.txt to avoid dependency resolution conflicts. Do NOT mix langchain 0.2.x with langgraph 1.x.

6. **RDS t4g.micro memory:** 1 GB RAM. pgvector HNSW index with <10K 1024-dim vectors fits comfortably (~40MB). If grant volume grows past 50K, consider upgrading to t4g.small (2 GB, ~$26/month).

7. **OpenAI model aliases:** Use dated model names (`gpt-5.4-2026-03-05`, `gpt-5.4-mini-2026-03-17`) in production, not aliases (`gpt-5.4`, `gpt-5.4-mini`). Aliases roll forward on model updates, which can change behavior mid-pipeline. Store model names in environment variables for easy updates.

---

## Sources

- [LangGraph PyPI](https://pypi.org/project/langgraph/) -- v1.1.0, March 2026
- [LangGraph GitHub Releases](https://github.com/langchain-ai/langgraph/releases)
- [pgvector GitHub](https://github.com/pgvector/pgvector) -- v0.8.2
- [pgvector 0.8.0 on RDS announcement](https://aws.amazon.com/about-aws/whats-new/2024/11/amazon-rds-for-postgresql-pgvector-080/)
- [AWS CDK Python Reference](https://docs.aws.amazon.com/cdk/api/v2/python/) -- v2.244.0
- [OpenAI GPT-5.4 Model](https://developers.openai.com/api/docs/models/gpt-5.4) -- March 2026
- [OpenAI GPT-5.4-mini Model](https://developers.openai.com/api/docs/models/gpt-5.4-mini) -- March 2026
- [OpenAI API Pricing](https://developers.openai.com/api/docs/pricing) -- March 2026
- [OpenAI Python SDK](https://pypi.org/project/openai/) -- v2.30.0
- [OpenAI Structured Outputs Guide](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Pydantic PyPI](https://pypi.org/project/pydantic/) -- v2.12.5
- [Amazon Bedrock Titan Embeddings](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html)
- [Amazon Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)
- [AWS Lambda Python 3.13 Runtime](https://aws.amazon.com/blogs/compute/python-3-13-runtime-now-available-in-aws-lambda/)
- [Playwright Python](https://playwright.dev/python/docs/intro) -- v1.58.0
- [psycopg2 Documentation](https://www.psycopg.org/docs/) -- v2.9.x
- [langgraph-checkpoint-postgres PyPI](https://pypi.org/project/langgraph-checkpoint-postgres/)
- [Playwright on Lambda Docker guide](https://developer.mamezou-tech.com/en/blogs/2024/07/19/lambda-playwright-container-tips/)
