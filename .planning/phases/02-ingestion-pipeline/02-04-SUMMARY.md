---
phase: 02-ingestion-pipeline
plan: 04
status: completed
completed_at: 2026-03-30
---

# Plan 02-04 Summary: Step Functions Pipeline + EventBridge + Backfill

## What was built

Full pipeline orchestration wiring Plans 01-03 together, plus one-time historical backfill.

### CDK Stack Updates (`infrastructure/stacks/hanna_stack.py`)

1. **Scraper Docker Lambda** (`HannaScraperFn`) — `DockerImageFunction` with 2048MB memory, 10-min timeout, X86_64 architecture for Playwright. Builds from `infrastructure/docker/scraper/Dockerfile`. Environment includes `DB_SECRET_ARN`, `S3_BUCKET`, `OPENAI_BASE_URL` (OpenRouter), `EXTRACTION_MODEL`.

2. **Processing Lambda** (`HannaProcessingFn`) — Zip-packaged `lambda_.Function` with Python 3.13, handler `processing_handler.handler`, 512MB memory, 5-min timeout. Same env vars as scraper.

3. **Step Functions Standard Pipeline** (`HannaIngestionPipeline`) — 30-min timeout state machine:
   - `DistributedMap` (`ScrapeAllSources`) with `max_concurrency=5` and `tolerated_failure_percentage=30` — healthy scrapers still process when some fail (D-11).
   - Per-source chain: `ScrapeSingle` (LambdaInvoke with retry: 2 attempts, 5s backoff, catch errors) → `ProcessBatch` (dedup → extract → embed → health).
   - Final `LogPipelineRun` step aggregates results into pipeline_runs table.

4. **EventBridge Daily Rule** (`HannaDailyIngestion`) — **NOW ENABLED** at 13:00 UTC (6am PT). Targets Step Functions with all 17 source configs loaded from `scraper_registry.json` at CDK synth time.

5. **CloudWatch Alarm** (`ScraperHealthAlarm`) — Fires SNS to billing topic when `ScraperConsecutiveZeros` metric ≥ 3 (24h period).

6. **New CfnOutputs**: `ScraperFnArn`, `ProcessingFnArn`, `IngestionPipelineArn`.

### Backfill Script (`scripts/scrapers/backfill.py`)

One-time historical grant loader for grants.ca.gov and Grants.gov (D-05):
- Batches of 50 with 5s pause between batches (D-07)
- Resume from failure via `backfill_progress.json` checkpoint file
- Same extraction pipeline as live grants: dedup → extract → embed (D-06)
- Pipeline run logged via `start_run` / `complete_run` / `fail_run`
- Usage: `python backfill.py --secret-arn <ARN> [--batch-size 50] [--resume]`

### Tests (`scripts/tests/test_backfill.py`)

8 tests covering:
- `load_progress` defaults when no file exists
- `load_progress` reads existing checkpoint
- `save_progress` creates JSON file
- `_process_batch` calls dedup before extract (ordering guarantee)
- `_process_batch` logs extraction failures
- `backfill_grants_ca_gov` stops on empty records
- `backfill_grants_ca_gov` processes single batch correctly
- `backfill_grants_gov` stops on empty hits

## Verification

- CDK stack imports: PASS
- CDK synth: PASS (full CloudFormation template generated)
- All tests: 74 passed (66 existing + 8 new)
- `DockerImageFunction` with memory_size=2048, timeout 10min: PRESENT
- `DistributedMap` (not sfn.Map) with tolerated_failure_percentage=30: PRESENT
- `json.load` reading scraper_registry at synth time: PRESENT
- EventBridge `enabled=True` targeting Step Functions with source_configs: PRESENT
- `ScraperHealthAlarm` with threshold 3: PRESENT

## Requirements Coverage

| Requirement | Status |
|-------------|--------|
| INGEST-06: Fan-out orchestration with failure tolerance | Covered by DistributedMap + tolerated_failure_percentage=30 |
| INGEST-08: Historical backfill 500+ grants | Covered by backfill.py with batch processing + resume |
| PIPE-01: Daily automated pipeline | Covered by EventBridge → Step Functions at 13:00 UTC |
| PIPE-03: Pipeline audit trail | Covered by LogPipelineRun step + pipeline_logger |

## Existing Infrastructure Preserved

All Phase 1 constructs unchanged: VPC, RDS, S3, API Gateway, Lambda role, SNS billing topic, CloudWatch log group, weekly evaluation rule (still disabled for Phase 3).
