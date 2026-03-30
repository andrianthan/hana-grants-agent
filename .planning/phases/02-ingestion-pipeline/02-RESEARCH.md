# Phase 2: Ingestion Pipeline + Backfill - Research

**Researched:** 2026-03-29
**Domain:** Grant ingestion pipeline (APIs, web scraping, Step Functions, LLM extraction, embeddings)
**Confidence:** MEDIUM-HIGH

## Summary

Phase 2 builds a daily automated pipeline that pulls grant opportunities from 17 sources (5 APIs + 12 Playwright scrapers), deduplicates them, extracts structured metadata via GPT-5.4-mini through OpenRouter, embeds them with Bedrock Titan V2, and stores them in the existing RDS PostgreSQL grants table. Step Functions Standard orchestrates the pipeline with a Map state that tolerates 30% scraper failures. A one-time backfill script populates 500+ historical grants from the two API sources (grants.ca.gov and Grants.gov) before Phase 3 begins.

The core technical challenges are: (1) packaging Playwright + Chromium into a Docker Lambda image (~2GB), which requires Docker to be installed locally for CDK builds; (2) correctly interfacing with 5 distinct API schemas (grants.ca.gov/CKAN, Grants.gov REST, ProPublica, USASpending.gov, Grantmakers.io); (3) building reliable Playwright scrapers for 12 sites with stealth mode and failure tolerance; and (4) wiring the Step Functions state machine through CDK with Map state, error handling, and EventBridge scheduling.

**Primary recommendation:** Build API parsers first (Plan 02-01) since they are deterministic and testable without Playwright. Then build Playwright scrapers (Plan 02-02). Then build the processing pipeline -- dedup, extraction, embedding, health monitoring (Plan 02-03). Finally wire Step Functions + EventBridge + backfill (Plan 02-04). Docker Desktop must be installed before CDK can deploy the scraper Lambda image.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01: Silent failure logging with CloudWatch alarm after 3 consecutive zero-grant days per source
- D-02: Playwright scrapers use stealth mode (playwright-stealth) with random delays (2-8s) and rotating user agents
- D-03: GPT-5.4-mini (or nano) via OpenRouter for structured metadata extraction
- D-04: Null fields with extraction_confidence score when LLM cannot extract confidently
- D-05: Backfill from API archives only (grants.ca.gov + Grants.gov historical data)
- D-06: Backfill grants use same extraction pipeline as live grants
- D-07: Backfill in batches of 50 with pauses, resume from last successful batch
- D-08: Dedup BEFORE LLM extraction via SHA-256 content hash
- D-09: Lambda 2048MB / 10min timeout per scraper
- D-10: Scraper sources managed via scraper_registry.json
- D-11: Step Functions Map State with ToleratedFailurePercentage=30%
- D-12: Expired grants stay in database, Phase 3 filters by deadline
- D-13: HTML snapshots as test fixtures, live smoke tests per source on deploy
- D-14: OpenRouter via OPENAI_BASE_URL env var, model names like openai/gpt-5.4-mini
- D-15: All AWS resources in us-west-2
- D-16: PostgreSQL 16.12, reuse Phase 1 shared utilities

### Claude's Discretion
- Exact Playwright selectors per scraper site
- Step Functions state machine structure and naming
- Scraper base class design and inheritance hierarchy
- Batch concurrency settings for backfill script
- Test fixture organization and naming

### Deferred Ideas (OUT OF SCOPE)
- Instrumentl CSV import -- Phase 5 / backlog
- IRS 990-PF enrichment via Grantmakers.io for funder intelligence -- Phase 5 / backlog
- Scraper auto-healing (LLM re-generates selectors) -- future enhancement
- Grant detail page deep-scraping (follow links for full RFP documents) -- future enhancement
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INGEST-01 | Poll grants.ca.gov API and Grants.gov REST API daily (17 sources: 5 APIs + 12 scrapers) | grants.ca.gov CKAN API documented (resource_id, 37 fields, 1871 records). Grants.gov POST search2 endpoint documented. ProPublica GET search endpoint documented. USASpending.gov v2 awards search documented. Grantmakers.io is a website scraper not a true API. |
| INGEST-02 | Scrape 12 websites via Playwright on Lambda Docker | Playwright 1.58.0 + playwright-stealth 2.0.2 on Docker image with awslambdaric. Microsoft base image mcr.microsoft.com/playwright/python. |
| INGEST-03 | Extract structured metadata via GPT-5.4-mini (title, funder, deadline, funding range, geography, eligibility, relationship_required) | OpenRouter API compatible with openai Python SDK via base_url. Pydantic response_format for structured outputs. |
| INGEST-04 | Embed grants via Bedrock Titan V2 (1024 dims) and store with pgvector HNSW | Existing embeddings.py get_embedding() function reusable. Existing grants table has embedding column with HNSW index. |
| INGEST-05 | Deduplicate via SHA-256 content hash (title + funder + deadline + description) | Existing content_hash column with UNIQUE constraint on grants table. ON CONFLICT pattern from ingest_documents.py. |
| INGEST-06 | Step Functions Standard orchestrates pipeline (Map State, max_concurrency=5, ToleratedFailurePercentage=30, Catch/Retry) | CDK sfn.Map with max_concurrency and DistributedMap with tolerated_failure_percentage. LambdaInvoke task with add_retry/add_catch. |
| INGEST-07 | Scraper health monitoring: scraper_health table, CloudWatch alarm at >=3 consecutive zeros, SNS alert | Existing scraper_health table with consecutive_zeros column. CDK CloudWatch alarm + SNS constructs. |
| INGEST-08 | One-time backfill script (500-900 historical grants, batches of 50) | grants.ca.gov has 1871 records. Grants.gov search2 supports pagination via startRecordNum. |
| INGEST-09 | pipeline_runs audit table records every run | Existing pipeline_runs table with grants_ingested, grants_new, errors, status columns. |
| INFRA-04 | Three Lambda deployment packages: scraper Docker (~2GB), LangGraph Docker (~800MB), utility zip (<50MB) | CDK DockerImageFunction for Docker images. Docker required locally for cdk deploy. Docker NOT currently installed on dev machine. |
| PIPE-01 | EventBridge daily cron (6am PT = 13:00 UTC) triggers Step Functions | Existing EventBridge rule HannaDailyIngestion (disabled) in CDK stack. Update target from placeholder to Step Functions. |
| PIPE-03 | All pipeline runs logged to pipeline_runs table and CloudWatch | pipeline_runs table exists. CloudWatch log group with 14-day retention exists. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| playwright | 1.58.0 | Browser automation for 12 scraper sites | Industry standard for headless browser automation; built-in async, selectors, screenshots |
| playwright-stealth | 2.0.2 | Anti-detection patches for Playwright | Masks navigator.webdriver and automation signals; user decision D-02 |
| openai | 2.30.0 | LLM calls via OpenRouter (OPENAI_BASE_URL) | OpenRouter is OpenAI-API-compatible; single SDK for all LLM calls |
| pydantic | >=2.12.0 | Structured output validation for LLM extraction | Already in project requirements; enforces grant metadata schema |
| httpx | 0.28.1 | HTTP client for API calls (grants.ca.gov, Grants.gov, etc.) | Async-capable, type-safe, used by openai SDK internally |
| psycopg2-binary | >=2.9.10 | PostgreSQL driver | Already in project; used by existing db.py |
| pgvector | >=0.3.6 | pgvector extension for psycopg2 | Already in project; used by existing db.py |
| boto3 | >=1.42.0 | AWS SDK (Bedrock, Secrets Manager, S3) | Already in project; used by existing embeddings.py |
| awslambdaric | latest | Lambda runtime interface client for Docker images | Required for non-Amazon-Linux Docker images on Lambda |
| python-dotenv | latest | Load .env for local development | Already used in project for OpenRouter keys |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| aws-cdk-lib | 2.245.0 | CDK infrastructure (Step Functions, Lambda, EventBridge) | All infrastructure changes |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx | requests | httpx has async support needed for concurrent API calls; requests is sync-only |
| playwright-stealth | undetected-playwright | playwright-stealth is more maintained; undetected-playwright adds complexity |
| awslambdaric | Lambda base image | Microsoft Playwright image is Ubuntu-based, not Amazon Linux; awslambdaric bridges the gap |

**Installation (scraper Lambda requirements.txt):**
```
playwright==1.58.0
playwright-stealth==2.0.2
openai>=2.30.0,<3.0.0
pydantic>=2.12.0,<3.0.0
httpx>=0.28.0,<1.0.0
psycopg2-binary>=2.9.10,<3.0.0
pgvector>=0.3.6
boto3>=1.42.0
python-dotenv>=1.0.0
awslambdaric
```

## Architecture Patterns

### Recommended Project Structure
```
scripts/
  scrapers/
    handler.py            # Lambda entry point -- reads scraper_registry.json, dispatches
    base_scraper.py       # Abstract base class (fetch, parse, validate)
    base_api_client.py    # Base class for API sources (pagination, rate limiting)
    api/
      grants_ca_gov.py    # grants.ca.gov CKAN API client
      grants_gov.py       # Grants.gov search2 API client
      propublica.py       # ProPublica Nonprofit Explorer API client
      usaspending.py      # USASpending.gov awards API client
      grantmakers_io.py   # Grantmakers.io web scraper (no true API)
    playwright/
      base_playwright.py  # Playwright base with stealth, delays, screenshots
      ca_dhcs.py          # California DHCS scraper
      samhsa.py           # SAMHSA grants scraper
      bscc.py             # BSCC corrections grants scraper
      sonoma_community_foundation.py
      california_wellness.py
      blue_shield_ca.py
      walter_s_johnson.py
      sonoma_county_health.py
      sonoma_county_probation.py
      sonoma_county_oes.py
      sonoma_county_css.py
      sonoma_county_bhs.py
    processing/
      dedup.py            # SHA-256 content hash check against DB
      extractor.py        # GPT-5.4-mini metadata extraction via OpenRouter
      embedder.py         # Bedrock Titan V2 embedding + DB insert
      health_monitor.py   # Update scraper_health table, check consecutive zeros
    backfill.py           # One-time historical grant loader (batches of 50)
  tests/
    fixtures/             # HTML snapshots per site
    test_api_parsers.py
    test_playwright_scrapers.py
    test_dedup.py
    test_extractor.py
    smoke_test.py         # Live smoke test per source
infrastructure/
  stacks/
    hanna_stack.py        # Updated CDK stack with Step Functions, Docker Lambda
  docker/
    scraper/
      Dockerfile          # Playwright + Chromium + awslambdaric
      requirements.txt    # Scraper-specific deps
```

### Pattern 1: Scraper Base Class
**What:** Abstract base with common interface for all 17 sources
**When to use:** Every scraper inherits this pattern
**Example:**
```python
# Source: Project design decision
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import hashlib

@dataclass
class RawGrant:
    """Raw grant data before LLM extraction."""
    title: str
    funder: str
    description: str
    deadline: Optional[str]  # ISO date string or None
    source_url: str
    source_id: str  # scraper_id from registry
    raw_html: Optional[str] = None  # For S3 archival

    @property
    def content_hash(self) -> str:
        """SHA-256 of title + funder + deadline + description for dedup."""
        content = f"{self.title}|{self.funder}|{self.deadline or ''}|{self.description}"
        return hashlib.sha256(content.encode()).hexdigest()

class BaseScraper(ABC):
    def __init__(self, config: dict):
        self.scraper_id = config["scraper_id"]
        self.url = config["url"]
        self.source_type = config["type"]

    @abstractmethod
    async def fetch_grants(self) -> list[RawGrant]:
        """Fetch all current grants from this source."""
        ...

    def validate(self, grants: list[RawGrant]) -> list[RawGrant]:
        """Filter out grants with missing required fields."""
        return [g for g in grants if g.title and g.description]
```

### Pattern 2: OpenRouter LLM Extraction with Pydantic
**What:** Structured metadata extraction using OpenAI SDK pointed at OpenRouter
**When to use:** After dedup confirms grant is new
**Example:**
```python
# Source: OpenRouter docs + openai SDK docs
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Optional
import os

class GrantMetadata(BaseModel):
    title: str
    funder: str
    deadline: Optional[str] = Field(None, description="ISO date or null if uncertain")
    funding_min: Optional[int] = None
    funding_max: Optional[int] = None
    geography: Optional[str] = None
    eligibility: Optional[str] = None
    program_area: Optional[str] = None
    population_served: Optional[str] = None
    relationship_required: Optional[bool] = None
    extraction_confidence: float = Field(ge=0.0, le=1.0)

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
    default_headers={"HTTP-Referer": "https://hannacenter.org"},
)

def extract_metadata(raw_text: str) -> GrantMetadata:
    response = client.beta.chat.completions.parse(
        model="openai/gpt-5.4-mini",
        messages=[
            {"role": "system", "content": "Extract grant metadata. Set fields to null when uncertain."},
            {"role": "user", "content": raw_text},
        ],
        response_format=GrantMetadata,
    )
    return response.choices[0].message.parsed
```

### Pattern 3: Dedup Before LLM (Cost Control)
**What:** Check SHA-256 hash against DB before expensive LLM call
**When to use:** Every grant before extraction
**Example:**
```python
# Source: Existing ON CONFLICT pattern from ingest_documents.py
def is_duplicate(conn, content_hash: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM grants WHERE content_hash = %s", (content_hash,))
    return cur.fetchone() is not None
```

### Pattern 4: Step Functions Map State with CDK
**What:** Fan-out to 17 scraper invocations in parallel with failure tolerance
**When to use:** Pipeline orchestration
**Example:**
```python
# Source: AWS CDK docs
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks

scrape_task = tasks.LambdaInvoke(
    self, "ScrapeSingle",
    lambda_function=scraper_fn,
    payload=sfn.TaskInput.from_json_path_at("$"),
    retry_on_service_exceptions=True,
).add_retry(
    max_attempts=2,
    backoff_rate=2.0,
    interval=Duration.seconds(5),
)

map_state = sfn.Map(
    self, "ScrapeAllSources",
    max_concurrency=5,
    items_path="$.sources",
)
map_state.item_processor(scrape_task)
```

### Anti-Patterns to Avoid
- **Running all 17 scrapers sequentially in one Lambda:** 15-min Lambda timeout exceeded; use Step Functions fan-out
- **LLM extraction before dedup:** Wastes ~$0.001/grant on duplicates; multiply by 1000+ backfill grants
- **Hardcoding scraper URLs:** Registry pattern (scraper_registry.json) enables add/disable without code changes
- **Building custom HTTP retry logic:** httpx has built-in retry; Step Functions has built-in retry
- **Using Amazon Linux base for Playwright Docker:** Playwright needs Ubuntu dependencies; use Microsoft's playwright/python image

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Browser stealth | Custom JS injection to hide webdriver | playwright-stealth | Maintained set of patches; tracks Playwright versions |
| API pagination | Custom page-through logic per API | httpx with generator pattern | Each API has different pagination; abstract with yield |
| LLM structured output | Regex parsing of LLM text | Pydantic response_format via openai SDK | Type-safe, validates schema, handles edge cases |
| Docker Lambda packaging | Manual docker build + ECR push | CDK DockerImageFunction | CDK handles build, push, ECR repo creation automatically |
| Cron scheduling | External cron service or GitHub Actions | EventBridge Scheduler | Already in CDK stack, native AWS, no external dependency |
| Secret management | .env files on Lambda | Secrets Manager (existing) | Already set up in Phase 1; rotation-aware db.py handles it |

**Key insight:** The scraper Docker image is the single most complex packaging challenge. CDK's DockerImageFunction abstracts ECR push/pull, but requires Docker installed locally for `cdk deploy`.

## Common Pitfalls

### Pitfall 1: grants.ca.gov CKAN API Field Types Are All Text
**What goes wrong:** The CKAN datastore returns all fields as text type, including dates and amounts. Parsing EstAmounts, OpenDate, ApplicationDeadline as strings leads to comparison bugs.
**Why it happens:** CKAN stores CSV data without type inference.
**How to avoid:** Parse dates with dateutil.parser, amounts with regex extraction of dollar figures. Null-safe handling throughout.
**Warning signs:** Grants appearing with deadline=None when the data actually has a date string in unexpected format.

### Pitfall 2: Playwright Docker Image Size (~2GB)
**What goes wrong:** ECR push takes 5-10 minutes; cold starts are 10-15 seconds; dev iteration is slow.
**Why it happens:** Chromium binary is ~150-200MB uncompressed; Microsoft Playwright base image includes all browsers and system deps.
**How to avoid:** Install only chromium (not firefox/webkit). Use multi-stage Docker build. Specify `--only-shell` or `playwright install chromium` only. Set Lambda memory to 2048MB for comfortable headroom.
**Warning signs:** `cdk deploy` taking >10 minutes; Lambda cold starts >15 seconds.

### Pitfall 3: Grants.gov search2 Pagination Limits
**What goes wrong:** Default response returns limited results; historical backfill misses grants without proper pagination.
**Why it happens:** startRecordNum must be incremented manually; no next-page URL provided.
**How to avoid:** Loop with startRecordNum += rows until hitCount is reached. Set rows to 250 max per request.
**Warning signs:** Backfill yields fewer grants than expected.

### Pitfall 4: OpenRouter Rate Limits and Model Availability
**What goes wrong:** 429 errors during batch extraction; model name changes break pipeline silently.
**Why it happens:** OpenRouter rate limits vary by model and plan tier. Model names use provider prefix format.
**How to avoid:** Use exponential backoff (existing pattern from ingest_documents.py). Pin model name as Lambda env var. Monitor extraction_failures table.
**Warning signs:** extraction_failures table filling up; zero grants_new in pipeline_runs.

### Pitfall 5: Playwright Selectors Break When Sites Redesign
**What goes wrong:** Scraper returns zero grants after a site redesign.
**Why it happens:** CSS selectors are brittle; sites change layout without notice.
**How to avoid:** Use data attributes and ARIA roles over CSS classes where possible. Save HTML snapshot on every run for debugging. scraper_health consecutive_zeros alarm catches this within 3 days.
**Warning signs:** scraper_health.consecutive_zeros >= 1 for a source; empty HTML snapshots.

### Pitfall 6: Docker Not Installed on Dev Machine
**What goes wrong:** `cdk deploy` fails when trying to build DockerImageFunction assets.
**Why it happens:** CDK runs `docker build` locally to create the image before pushing to ECR.
**How to avoid:** Install Docker Desktop before Phase 2 CDK deployment. Alternatively, use `CDK_DOCKER` env var to point to a Docker-compatible tool like Finch or Colima.
**Warning signs:** CDK synth succeeds but deploy fails with "Cannot connect to Docker daemon."

### Pitfall 7: Grantmakers.io Has No True API
**What goes wrong:** Code assumes REST API exists for Grantmakers.io based on scraper_registry.json listing it as "api" type.
**Why it happens:** Grantmakers.io is a search interface over IRS 990-PF data; it has no documented REST API.
**How to avoid:** Implement Grantmakers.io as a Playwright scraper or use the underlying IRS 990-PF data directly via ProPublica. The scraper_registry already has ProPublica covering 990 data. Consider whether Grantmakers.io adds value beyond ProPublica for Phase 2.
**Warning signs:** HTTP 403/404 when trying to call non-existent API endpoints.

## Code Examples

### grants.ca.gov CKAN API Client
```python
# Source: https://data.ca.gov/api/3/action/datastore_search
import httpx

GRANTS_CA_RESOURCE_ID = "111c8c88-21f6-453c-ae2c-b4785a0624f5"
GRANTS_CA_API_URL = "https://data.ca.gov/api/3/action/datastore_search"

async def fetch_grants_ca_gov(limit: int = 100, offset: int = 0) -> list[dict]:
    """Fetch California state grants from data.ca.gov CKAN API."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            GRANTS_CA_API_URL,
            params={
                "resource_id": GRANTS_CA_RESOURCE_ID,
                "limit": limit,
                "offset": offset,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["result"]["records"]
        # Total available: data["result"]["total"]
```

**Key fields from response:** Title, Description, AgencyDept (funder), ApplicationDeadline, EstAmounts, Geography, ApplicantType, Status, GrantURL. All fields are text type.

### Grants.gov search2 API Client
```python
# Source: https://grants.gov/api/common/search2
import httpx

GRANTS_GOV_URL = "https://api.grants.gov/v1/api/search2"

async def fetch_grants_gov(keywords: str = "", rows: int = 250, start: int = 0) -> dict:
    """Search Grants.gov opportunities. No auth required."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GRANTS_GOV_URL,
            json={
                "keywords": keywords,
                "oppStatuses": "posted",
                "rows": rows,
                "startRecordNum": start,
                "eligibilities": "25",  # 25 = nonprofits
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
        # data["data"]["hitCount"] for total
        # data["data"]["oppHits"] for results
```

### ProPublica Nonprofit Explorer API
```python
# Source: https://projects.propublica.org/nonprofits/api
import httpx

PROPUBLICA_BASE = "https://projects.propublica.org/nonprofits/api/v2"

async def search_nonprofits(query: str, state: str = "CA", page: int = 0) -> dict:
    """Search ProPublica 990 filings. No auth required. 25 results/page."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{PROPUBLICA_BASE}/search.json",
            params={"q": query, "state[id]": state, "page": page},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

async def get_organization(ein: str) -> dict:
    """Get full 990 data for a specific nonprofit by EIN."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{PROPUBLICA_BASE}/organizations/{ein}.json", timeout=30)
        resp.raise_for_status()
        return resp.json()
```

### Playwright Scraper Base with Stealth
```python
# Source: playwright-stealth PyPI docs + Playwright Python docs
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
import asyncio
import random

class PlaywrightScraper:
    """Base class for Playwright-based scrapers with stealth mode."""

    async def _create_context(self, playwright):
        browser = await playwright.chromium.launch(
            headless=True,
            args=["--disable-gpu", "--single-process", "--no-sandbox"],
        )
        context = await browser.new_context(
            user_agent=self._random_user_agent(),
            viewport={"width": 1920, "height": 1080},
        )
        return browser, context

    async def _stealth_page(self, context):
        page = await context.new_page()
        await stealth_async(page)
        return page

    async def _random_delay(self, min_s: float = 2.0, max_s: float = 8.0):
        await asyncio.sleep(random.uniform(min_s, max_s))

    def _random_user_agent(self) -> str:
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0",
        ]
        return random.choice(agents)
```

### Scraper Docker Image (Dockerfile)
```dockerfile
# Source: cloudtechsimplified.com + Playwright Docker docs
ARG FUNCTION_DIR="/function"

FROM mcr.microsoft.com/playwright/python:v1.58.0-noble AS build-image

ARG FUNCTION_DIR
RUN mkdir -p ${FUNCTION_DIR}

# Install only Chromium (not all browsers)
RUN playwright install chromium

# Install Lambda runtime interface client
RUN pip3 install --target ${FUNCTION_DIR} awslambdaric

# Copy function code
COPY scripts/scrapers/ ${FUNCTION_DIR}/scrapers/
COPY scripts/utils/ ${FUNCTION_DIR}/utils/
COPY scraper_registry.json ${FUNCTION_DIR}/
COPY scripts/scrapers/requirements.txt /tmp/requirements.txt
RUN pip3 install --target ${FUNCTION_DIR} -r /tmp/requirements.txt

FROM mcr.microsoft.com/playwright/python:v1.58.0-noble

ARG FUNCTION_DIR
WORKDIR ${FUNCTION_DIR}
COPY --from=build-image ${FUNCTION_DIR} ${FUNCTION_DIR}

ENTRYPOINT [ "python", "-m", "awslambdaric" ]
CMD [ "scrapers.handler.handler" ]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Selenium on Lambda | Playwright on Lambda Docker | 2023+ | Playwright is faster, more reliable, better async support |
| Lambda Layers for Chromium | Docker container images | 2024+ | Layers hit 250MB limit; Docker images support up to 10GB |
| puppeteer-stealth (Node) | playwright-stealth 2.0.2 (Python) | 2026-02 | Python port of puppeteer-stealth; compatible with async API |
| Grants.gov XML API | Grants.gov REST search2 (v1) | 2025-03 | Two new RESTful APIs released March 2025; no auth required |
| Manual Chromium binary management | playwright install chromium | 2024+ | Playwright manages browser binaries; version-locked to playwright version |

## Open Questions

1. **Grantmakers.io "API" type in scraper_registry.json**
   - What we know: Grantmakers.io is listed as type "api" in scraper_registry.json but has no documented REST API. It is a search interface over IRS 990-PF data.
   - What's unclear: Whether Grantmakers.io provides any programmatic access beyond the web interface.
   - Recommendation: Implement as Playwright scraper OR rely on ProPublica for 990 data (which has a documented API). ProPublica already covers 990-PF filings. Consider reclassifying Grantmakers.io from "api" to "scraper" in the registry.

2. **grants.ca.gov CKAN API Rate Limits**
   - What we know: The CKAN API has 1871 total records and updates daily at 8:45pm. No documented rate limit found.
   - What's unclear: Whether there's an undocumented rate limit that would affect backfill of all 1871 records.
   - Recommendation: Implement with conservative pacing (100 records per request, 1s delay between pages). Monitor for 429 responses.

3. **Playwright Docker Image Architecture**
   - What we know: Microsoft publishes amd64 images. Lambda supports arm64 for cost savings (20% cheaper). Community image sjw7444/lambda-playwright-python supports arm64.
   - What's unclear: Whether the community arm64 image is production-ready and maintained.
   - Recommendation: Start with amd64 (Microsoft official). Switch to arm64 later if cost optimization needed. Use `Architecture.X86_64` in CDK.

4. **OpenRouter Structured Output Support**
   - What we know: OpenRouter is OpenAI-API-compatible. The openai SDK supports `response_format` for structured outputs.
   - What's unclear: Whether OpenRouter fully proxies the `response_format` parameter to the underlying model.
   - Recommendation: Test structured output via OpenRouter in Plan 02-03 before committing to Pydantic parsing. Fall back to JSON mode + manual Pydantic validation if needed.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 | Local development | Yes | 3.14.3 | Lambda runs 3.13; local dev works on 3.14 |
| Docker | CDK Docker image build + deploy | **NO** | -- | Install Docker Desktop or Colima before deployment |
| AWS CLI | CDK deploy, manual operations | Yes | 2.34.16 | -- |
| CDK CLI | Infrastructure deployment | Yes | 2.1115.0 | -- |
| Node.js | CDK CLI runtime | Yes | 25.6.1 | -- |
| npm | CDK dependencies | Yes | 11.9.0 | -- |

**Missing dependencies with no fallback:**
- **Docker** -- BLOCKING for `cdk deploy` of scraper Lambda image. Must be installed before Plan 02-04 deployment. CDK runs `docker build` locally to create DockerImageFunction assets. Options: Docker Desktop (macOS), Colima (lightweight), or Finch (AWS alternative). Set `CDK_DOCKER` env var if using a non-Docker tool.

**Missing dependencies with fallback:**
- None -- all other dependencies are available.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (standard for Python projects) |
| Config file | None -- see Wave 0 |
| Quick run command | `pytest scripts/tests/ -x -q` |
| Full suite command | `pytest scripts/tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INGEST-01 | API parsers return valid RawGrant objects | unit | `pytest scripts/tests/test_api_parsers.py -x` | Wave 0 |
| INGEST-02 | Playwright scrapers extract grants from saved HTML | unit | `pytest scripts/tests/test_playwright_scrapers.py -x` | Wave 0 |
| INGEST-03 | LLM extraction produces valid GrantMetadata | unit | `pytest scripts/tests/test_extractor.py -x` | Wave 0 |
| INGEST-04 | Embedding + DB insert succeeds | integration | `pytest scripts/tests/test_embedder.py -x` | Wave 0 |
| INGEST-05 | Duplicate grants are skipped (content_hash match) | unit | `pytest scripts/tests/test_dedup.py -x` | Wave 0 |
| INGEST-06 | Step Functions state machine definition is valid | unit | `pytest scripts/tests/test_step_functions.py -x` | Wave 0 |
| INGEST-07 | Health monitor updates consecutive_zeros correctly | unit | `pytest scripts/tests/test_health_monitor.py -x` | Wave 0 |
| INGEST-08 | Backfill script processes batches with resume | integration | `pytest scripts/tests/test_backfill.py -x` | Wave 0 |
| INGEST-09 | Pipeline run logged to pipeline_runs table | integration | `pytest scripts/tests/test_pipeline_runs.py -x` | Wave 0 |
| INFRA-04 | CDK synth produces valid CloudFormation | unit | `cd infrastructure && cdk synth --quiet` | Existing |
| PIPE-01 | EventBridge rule targets Step Functions | unit | `cd infrastructure && cdk synth --quiet` | Existing |

### Sampling Rate
- **Per task commit:** `pytest scripts/tests/ -x -q` (quick: unit tests only)
- **Per wave merge:** `pytest scripts/tests/ -v` + `cd infrastructure && cdk synth --quiet`
- **Phase gate:** Full suite green + live smoke test per source

### Wave 0 Gaps
- [ ] `scripts/tests/conftest.py` -- shared fixtures (mock DB connection, mock OpenRouter, sample HTML)
- [ ] `scripts/tests/fixtures/` -- HTML snapshots from each of the 12 scraper sites
- [ ] `scripts/tests/test_api_parsers.py` -- covers INGEST-01
- [ ] `scripts/tests/test_playwright_scrapers.py` -- covers INGEST-02
- [ ] `scripts/tests/test_extractor.py` -- covers INGEST-03
- [ ] `scripts/tests/test_dedup.py` -- covers INGEST-05
- [ ] `scripts/tests/test_health_monitor.py` -- covers INGEST-07
- [ ] `pytest.ini` or `pyproject.toml` [tool.pytest] config
- [ ] Framework install: `pip install pytest pytest-asyncio`

## Sources

### Primary (HIGH confidence)
- data.ca.gov CKAN API -- verified resource_id `111c8c88-21f6-453c-ae2c-b4785a0624f5`, 37 fields, 1871 records
- Grants.gov search2 API -- verified POST endpoint `https://api.grants.gov/v1/api/search2`, no auth, JSON response
- ProPublica Nonprofit Explorer API v2 -- verified endpoints, no auth, 25 results/page
- AWS CDK Step Functions docs -- Map state, LambdaInvoke, retry/catch patterns
- Playwright Python docs -- Docker image, browser installation, async API
- OpenRouter docs -- OpenAI SDK compatibility via base_url, model name format

### Secondary (MEDIUM confidence)
- USASpending.gov API v2 -- endpoint structure documented but not deeply verified
- playwright-stealth PyPI -- version 2.0.2 confirmed, limitations documented
- AWS CDK DockerImageFunction -- Docker required locally for build

### Tertiary (LOW confidence)
- Grantmakers.io API -- no documented API found; classified as "api" in registry may be incorrect
- grants.ca.gov rate limits -- no documentation found on CKAN rate limits
- OpenRouter structured output support -- assumed from OpenAI compatibility but not verified

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all packages verified on PyPI with current versions
- Architecture: MEDIUM-HIGH -- patterns based on existing codebase + official docs; Step Functions CDK specifics need validation during implementation
- Pitfalls: HIGH -- drawn from documented limitations of each technology
- API schemas: MEDIUM -- grants.ca.gov and Grants.gov verified directly; USASpending and Grantmakers.io less deeply verified

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (30 days -- stable ecosystem, APIs unlikely to change)
