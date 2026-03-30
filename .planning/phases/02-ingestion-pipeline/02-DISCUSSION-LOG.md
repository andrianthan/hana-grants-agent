# Phase 2: Ingestion Pipeline + Backfill - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-30
**Phase:** 02-ingestion-pipeline
**Areas discussed:** Scraper reliability, Metadata extraction, Backfill strategy, Cost control, Registry management, Step Functions error handling, Grant data freshness, Testing strategy

---

## Scraper Reliability — Failure Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Silent log + alert after 3 fails | Log error, continue. CloudWatch alarm after 3 zero-grant days. | ✓ |
| Immediate alert on any failure | SNS email on every failure. | |
| Weekly failure summary | Batch failures into weekly digest. | |

**User's choice:** Silent log + alert after 3 fails
**Notes:** Best for 2-person team — no noise from transient issues.

## Scraper Reliability — Anti-Bot

| Option | Description | Selected |
|--------|-------------|----------|
| Stealth mode + random delays | playwright-stealth, 2-8s delays, rotate user agents. | ✓ |
| Minimal — basic headers | Standard Playwright with realistic user-agent. | |
| You decide | Claude picks per scraper. | |

**User's choice:** Stealth mode + random delays

## Metadata Extraction — LLM Model

| Option | Description | Selected |
|--------|-------------|----------|
| GPT-4.1-mini via OpenRouter | Fast, cheap (~$0.40/1M tokens). | |
| GPT-4.1 via OpenRouter | More capable, ~8x cost. | |
| Claude Haiku via OpenRouter | Anthropic's fast model. | |

**User's choice:** GPT-5.4-mini or nano (user specified preferred model)
**Notes:** User explicitly wants GPT-5.4-mini/nano, not GPT-4.1-mini.

## Metadata Extraction — Uncertain Fields

| Option | Description | Selected |
|--------|-------------|----------|
| Null with confidence flag | Set to null, add confidence score. | ✓ |
| Best guess with low confidence | Always fill, mark low confidence. | |
| Skip entire grant | Don't ingest if critical fields missing. | |

**User's choice:** Null with confidence flag

## Backfill Strategy — Source

| Option | Description | Selected |
|--------|-------------|----------|
| API archives only | grants.ca.gov + Grants.gov historical data. | ✓ |
| APIs + scraper archives | Also scrape foundation archives. | |
| You decide | Claude determines per source. | |

**User's choice:** API archives only
**Notes:** User asked for explanation of backfill concept before answering. After understanding, agreed with API-only approach.

## Backfill Strategy — Processing

| Option | Description | Selected |
|--------|-------------|----------|
| Same pipeline as live | GPT-5.4-mini + embedding. ~$1-2 one-time. | ✓ |
| Simplified extraction | Regex/heuristics. Faster but inconsistent. | |
| You decide | Claude picks per source. | |

**User's choice:** Same pipeline as live grants

## Cost Control — Dedup Ordering

| Option | Description | Selected |
|--------|-------------|----------|
| Extract only new grants | Dedup BEFORE LLM. Only pay for new grants. | ✓ |
| Extract all, dedup after | LLM on everything, then check dupes. | |
| You decide | Claude picks ordering. | |

**User's choice:** Extract only new grants (dedup before LLM)

## Cost Control — Lambda Sizing

| Option | Description | Selected |
|--------|-------------|----------|
| 1024MB / 5min | Enough for most scrapes. ~$0.50/month. | |
| 2048MB / 10min | More headroom. ~$1/month. | ✓ |
| You decide | Claude sizes per scraper. | |

**User's choice:** 2048MB / 10min per scraper

## Scraper Registry Management

| Option | Description | Selected |
|--------|-------------|----------|
| Edit JSON + redeploy | Version-controlled, auditable. | ✓ |
| Runtime config in SSM | Toggle without redeploy. | |
| You decide | Claude picks approach. | |

**User's choice:** Edit scraper_registry.json + redeploy

## Step Functions Error Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Continue with healthy scrapers | 30% failure tolerance. Failed logged. | ✓ |
| Retry then continue | Retry 2x per scraper then continue. | |
| Both — retry then tolerate | Most resilient, longest time. | |

**User's choice:** Continue with healthy scrapers (30% tolerance)

## Grant Data Freshness

| Option | Description | Selected |
|--------|-------------|----------|
| Keep in DB, filter in evaluator | Expired stay for history. Evaluator filters. | ✓ |
| Nightly cleanup job | Delete/archive expired nightly. | |
| Soft-delete with status flag | Mark expired, keep in table. | |

**User's choice:** Keep in DB, filter in evaluator

## Testing Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Recorded responses + live smoke test | HTML fixtures for unit tests, live verify on deploy. | ✓ |
| Live tests only | Always test against real sites. | |
| You decide | Claude picks per scraper type. | |

**User's choice:** Recorded responses + live smoke test

## Claude's Discretion

- Playwright selectors per scraper site
- Step Functions state machine structure
- Scraper base class design
- Batch concurrency for backfill
- Test fixture organization

## Deferred Ideas

- Instrumentl CSV import — Phase 5 / backlog
- IRS 990-PF enrichment — Phase 5 / backlog
- Scraper auto-healing (LLM re-generates selectors) — future
- Grant detail page deep-scraping — future
