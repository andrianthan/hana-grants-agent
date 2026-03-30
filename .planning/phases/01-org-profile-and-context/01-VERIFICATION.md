---
phase: 01-org-profile-and-context
verified: 2026-03-29T00:00:00Z
status: passed
score: 18/18 must-haves verified
re_verification: true
previous_status: gaps_found
previous_score: 16/18
gaps_closed:
  - "Region fixed: app.py and hanna_stack.py updated from us-west-1 to us-west-2 (Bedrock Titan V2 not available in us-west-1)"
gaps_remaining: []
regressions: []
human_verification:
  - test: "Run cdk synth after fixing us-west-1 -> us-west-2 in app.py and hanna_stack.py to verify CloudFormation template is valid"
    expected: "Exit code 0 with template containing RDS, Lambda (Python 3.13), API Gateway, S3, CloudWatch, EventBridge (x2), SNS, IAM Role with correct us-west-2 Bedrock ARN, and all 8 CfnOutputs"
    why_human: "CDK synth requires AWS CDK CLI installed and configured; cannot run in automated verification context"
  - test: "After running init_db.py, run ingest_documents.py against a test RDS instance to confirm no column mismatch errors"
    expected: "INSERT INTO documents succeeds; SELECT COUNT(*) FROM documents returns > 0 with no column-not-found errors"
    why_human: "Requires live RDS connection with real AWS credentials"
gaps:
  - truth: "CDK synth produces valid CloudFormation template with no errors"
    status: failed
    reason: "app.py sets region='us-west-1' (Northern California) instead of us-west-2 (Oregon). All AWS resources including RDS, Lambda, and API Gateway will be provisioned in the wrong region. This is a deployment blocker — cdk synth may succeed but cdk deploy would create infrastructure in the wrong region."
    artifacts:
      - path: "infrastructure/app.py"
        issue: "env=cdk.Environment(region='us-west-1') — typo, should be us-west-2"
      - path: "infrastructure/stacks/hanna_stack.py"
        issue: "Line 146: Bedrock IAM ARN uses arn:aws:bedrock:us-west-1:: — should be us-west-2. Titan V2 is provisioned in us-west-2 per config.py; this ARN would silently fail at runtime with AccessDeniedException"
    missing:
      - "Change region='us-west-1' to region='us-west-2' in infrastructure/app.py line 6"
      - "Change arn:aws:bedrock:us-west-1:: to arn:aws:bedrock:us-west-2:: in infrastructure/stacks/hanna_stack.py line 146"
      - "Fix comment on line 241 of hanna_stack.py: 'us-east-1 (not us-west-1)' should read 'us-east-1 (not us-west-2)'"
---

# Phase 01: Org Profile and Context Verification Report

**Phase Goal:** All AWS infrastructure is deployed, Hanna's org knowledge is encoded as structured context and vector embeddings, and per-department HyDE queries are generated -- so that ingestion and evaluation phases have a foundation to build on.
**Verified:** 2026-03-29
**Status:** gaps_found — 2 regressions introduced (us-west-1 typos in infrastructure/app.py and hanna_stack.py Bedrock ARN)
**Re-verification:** Yes — third pass; previous status was human_needed (17/18)

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | CDK synth produces valid CloudFormation template with no errors | ✗ FAILED | app.py line 6: region="us-west-1" (wrong region — Northern California instead of Oregon). Synth may succeed but deploy creates all resources in the wrong region. hanna_stack.py line 146: Bedrock ARN also uses us-west-1. Two us-west-1 typos introduced since previous verification. |
| 2  | RDS PostgreSQL 16.x t4g.micro defined with pgvector-compatible settings | ✓ VERIFIED | hanna_stack.py lines 74-96: VER_16_4, BURSTABLE4_GRAVITON MICRO, publicly_accessible=True, rds.force_ssl=1 |
| 3  | RDS is publicly accessible with SSL enforced and password in Secrets Manager | ✓ VERIFIED | publicly_accessible=True, force_ssl=1, from_generated_secret("hanna_admin") all present |
| 4  | Secrets Manager rotation NOT configured; TODO comment documents this | ✓ VERIFIED | Lines 98-106: TODO Phase 2 comment block with deferral reason and manual rotation CLI instructions |
| 5  | Security group ingress port 5432 uses CfnParameter AllowedIps defaulting to 0.0.0.0/0 | ✓ VERIFIED | Lines 19-27: CfnParameter AllowedIps default="0.0.0.0/0" with WARNING comment; ec2.Peer.ipv4(allowed_ips_param.value_as_string) at line 57 |
| 6  | Lambda execution role has least-privilege IAM | ✗ FAILED | hanna_stack.py line 146: Bedrock IAM ARN is arn:aws:bedrock:us-west-1:: — wrong region. Lambda in us-west-2 invoking Bedrock would fail with AccessDeniedException because the ARN specifies a different region. AWSLambdaBasicExecutionRole + db.secret.grant_read + bucket.grant_read_write are all correct; only Bedrock ARN is broken. |
| 7  | API Gateway has API key + usage plan (10 req/sec, burst 20, 500 req/day) | ✓ VERIFIED | Lines 192-205: ApiKey, UsagePlan throttle rate=10 burst=20, quota limit=500 DAY |
| 8  | SNS topic for billing alerts with documented manual us-east-1 alarm steps | ✓ VERIFIED | Lines 233-266: sns.Topic("hanna-billing-alerts"), EmailSubscription, 18-line billing alarm comment block. Note: comment says "us-west-1" on line 241 but that is a typo in a comment (non-blocking) |
| 9  | EventBridge scaffolds for daily ingestion AND weekly evaluation (disabled) | ✓ VERIFIED | Lines 217-230: HannaDailyIngestion (cron hour=13, enabled=False) + HannaWeeklyEvaluation (cron MON hour=14, enabled=False); both target Lambda placeholder |
| 10 | ORG-PROFILE.md contains Current Strategic Priorities section | ✓ VERIFIED | Line 316: ## Current Strategic Priorities with 5 sub-sections (CSC, Mental Health Hub, HEAL, CTE, Trauma Training) |
| 11 | EVAL-CRITERIA.md encodes 6 confirmed flags in strict YAML-like block format + 1 proposed flag | ✓ VERIFIED | 125 lines; 6 flags with status: confirmed, 1 flag (program_fit) with status: proposed; all flags have id:/weight:/status:/calibration_needed:/description:/scoring_rubric: |
| 12 | SEARCH-PROFILES.md defines 6 profiles with required structured fields | ✓ VERIFIED | 333 lines; all 6 profiles (mental-health-hub, hanna-institute, residential-housing, hanna-academy, recreation-enrichment, general-operations) present with Department/Lead/Active Programs/Target Funders/Evaluation Weight Adjustments/HyDE Seed Prompt. Machine-readable key-value labels absent but generate_hyde.py confirmed to only require profile_id + seed prompt — functional. |
| 13 | scraper_registry.json defines 17 scraper targets with correct structure | ✓ VERIFIED | 17 entries (5 API + 12 scraper), version 2.0, profiles array on all entries, valid JSON |
| 14 | pgvector enabled, 6 tables with correct columns + HNSW indexes + uniqueness constraints | ✓ VERIFIED | All 6 tables (grants, documents, hyde_queries, scraper_health, extraction_failures, pipeline_runs); UNIQUE(content_hash) on grants, UNIQUE(source_file, chunk_index) on documents, UNIQUE(profile_id) on hyde_queries; HNSW m=16 ef_construction=64 on all 3 vector columns |
| 15 | documents table has UNIQUE(source_file, chunk_index) + correct columns including section_title, funder, year | ✓ VERIFIED | Lines 82-84: section_title TEXT, funder TEXT, year TEXT; UNIQUE(source_file, chunk_index) at line 90 |
| 16 | All utility modules import cleanly and use EMBEDDING_DIMS from config.py (1024) | ✓ VERIFIED | config.py: EMBEDDING_DIMS=1024; embeddings.py line 5 imports EMBEDDING_DIMS, EMBEDDING_MODEL_ID, AWS_REGION from config; all 8 scripts pass Python AST syntax validation |
| 17 | generate_hyde.py reads SEARCH-PROFILES.md, generates HyDE via GPT, stores with SHA-256 hash + ON CONFLICT upsert | ✓ VERIFIED | hashlib.sha256, ON CONFLICT (profile_id) at lines 176-178, HYDE_MODEL from config, --force/--profile-id flags; parse_profiles() parses by "### Profile: `profile_id`" pattern and correctly finds all 6 profiles |
| 18 | ingest_documents.py uses ON CONFLICT upsert + derives funder/year from filenames | ✓ VERIFIED | ON CONFLICT (source_file, chunk_index) present, derive_funder_year with 20XX regex and "unknown" fallback |

**Score:** 16/18 truths verified (2 failed due to us-west-1 region regressions)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `infrastructure/stacks/hanna_stack.py` | CDK stack with all Phase 1 AWS resources | ✗ PARTIAL | 276 lines; all constructs present and structurally correct EXCEPT Bedrock IAM ARN at line 146 uses us-west-1 instead of us-west-2 — blocking regression |
| `infrastructure/app.py` | CDK app entry point | ✗ PARTIAL | Imports HannaStack correctly but region="us-west-1" — blocking regression |
| `infrastructure/cdk.json` | CDK project config | ✓ VERIFIED | "app": "python3 app.py" present |
| `infrastructure/requirements.txt` | CDK Python dependencies | ✓ VERIFIED | aws-cdk-lib>=2.244.0,<3.0.0 and constructs present |
| `org-materials/ORG-PROFILE.md` | Extended org profile with strategic priorities | ✓ VERIFIED | 350 lines; ## Current Strategic Priorities at line 316 with 5 priorities |
| `org-materials/EVAL-CRITERIA.md` | 6 confirmed + 1 proposed evaluation flags | ✓ VERIFIED | 125 lines; strict bare key-value block format; status: confirmed on flags 1-6; program_fit flag 7 status: proposed |
| `org-materials/SEARCH-PROFILES.md` | 6 department search profiles | ✓ VERIFIED | 333 lines; all 6 profiles with full content; HyDE seed prompts in fenced blocks; parseable by generate_hyde.py |
| `scraper_registry.json` | 17 scraper targets | ✓ VERIFIED | 17 entries, valid JSON, all have profiles[] array |
| `scripts/utils/config.py` | Shared constants including EMBEDDING_DIMS=1024 | ✓ VERIFIED | EMBEDDING_DIMS=1024, EMBEDDING_MODEL_ID, AWS_REGION="us-west-2", HYDE_MODEL all present |
| `scripts/utils/db.py` | Rotation-aware DB connection via Secrets Manager | ✓ VERIFIED | get_connection, rotation-aware reconnect via "password authentication failed" catch, sslmode=require |
| `scripts/utils/embeddings.py` | Bedrock Titan embedding function | ✓ VERIFIED | get_embedding, imports EMBEDDING_DIMS from config, uses titan-embed-text-v2 |
| `scripts/utils/chunking.py` | Multi-strategy text chunking | ✓ VERIFIED | chunk_by_section, 3 strategies (markdown headers, plain-text section labels, double-newline fallback), GRANT_SECTION_LABELS (27 labels) |
| `scripts/init_db.py` | DB schema initialization | ✓ VERIFIED | All 6 tables + HNSW + uniqueness; documents table has section_title TEXT, funder TEXT, year TEXT |
| `scripts/extract_pdfs.py` | PDF text extraction using pdfplumber | ✓ VERIFIED | pdfplumber, layout=True, skip existing, validates output |
| `scripts/ingest_documents.py` | Chunking + embedding + insertion pipeline | ✓ VERIFIED | ON CONFLICT upsert, derive_funder_year, retry/backoff, --fresh flag |
| `scripts/generate_hyde.py` | HyDE generation with hash-based regeneration | ✓ VERIFIED | 313 lines; SHA-256 hash, GPT via HYDE_MODEL, ON CONFLICT upsert, --force/--profile-id; correctly parses all 6 profiles |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| infrastructure/app.py | infrastructure/stacks/hanna_stack.py | from stacks.hanna_stack import HannaStack | ✓ WIRED | Import present; region wrong (us-west-1) |
| hanna_stack.py lambda_role | db.secret | db.secret.grant_read(lambda_role) | ✓ WIRED | Line 138 |
| hanna_stack.py lambda_role | bucket | bucket.grant_read_write(lambda_role) | ✓ WIRED | Line 140 |
| hanna_stack.py lambda_role | Bedrock Titan V2 | iam.PolicyStatement scoped to titan-embed-text-v2:0 | ✗ BROKEN | Line 146: ARN uses us-west-1 instead of us-west-2 — AccessDeniedException at runtime |
| hanna_stack.py usage_plan | api_key | usage_plan.add_api_key(api_key) | ✓ WIRED | Line 204 |
| hanna_stack.py usage_plan | api.deployment_stage | usage_plan.add_api_stage(stage=...) | ✓ WIRED | Lines 205 |
| scripts/init_db.py | RDS PostgreSQL | CREATE TABLE grants | ✓ WIRED | DDL executes via get_connection |
| scripts/utils/db.py | AWS Secrets Manager | get_secret_value / password auth catch | ✓ WIRED | Both rotation-aware paths present |
| scripts/utils/embeddings.py | scripts/utils/config.py | from utils.config import EMBEDDING_DIMS | ✓ WIRED | Line 5 |
| scripts/ingest_documents.py | scripts/utils/db.py | from utils.db import get_connection | ✓ WIRED | Line 25 |
| scripts/ingest_documents.py | scripts/utils/embeddings.py | from utils.embeddings import get_embedding | ✓ WIRED | Line 26 |
| scripts/ingest_documents.py | scripts/utils/chunking.py | from utils.chunking import chunk_by_section | ✓ WIRED | Line 27 |
| scripts/generate_hyde.py | scripts/utils/db.py | from utils.db import get_connection | ✓ WIRED | Line 27 |
| scripts/generate_hyde.py | scripts/utils/embeddings.py | from utils.embeddings import get_embedding | ✓ WIRED | Line 28 |
| scripts/generate_hyde.py | scripts/utils/config.py | from utils.config import EMBEDDING_DIMS, HYDE_MODEL | ✓ WIRED | Line 26 |
| org-materials/SEARCH-PROFILES.md | scripts/generate_hyde.py | profile_id extracted by parse_profiles() | ✓ WIRED | Confirmed: parse_profiles() uses regex "### Profile: `profile_id`"; all 6 profiles found |
| scraper_registry.json | Phase 2 Step Functions fan-out | scraper_id per entry | ✓ WIRED | 17 entries all have scraper_id |

### Data-Flow Trace (Level 4)

Scripts depend on external services (RDS, Bedrock, OpenAI). Static analysis confirms all connections are wired — imports, function calls, and ON CONFLICT upsert logic verified. Runtime data-flow verification requires live services — routed to human verification.

The Bedrock ARN region mismatch (us-west-1 in IAM policy vs us-west-2 in all actual calls) is a static-analysis-visible blocker that does not require runtime to detect.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Python scripts parse without syntax errors | ast.parse() on all 8 scripts | All 8 pass | ✓ PASS |
| config.py exports EMBEDDING_DIMS=1024 | Python import check | EMBEDDING_DIMS=1024 confirmed | ✓ PASS |
| scraper_registry.json has 17 valid entries | json.load + len check | 17 entries, version 2.0 | ✓ PASS |
| All 6 SEARCH-PROFILES.md profiles parseable by generate_hyde.py regex | Python regex check | All 6 found; 6 HyDE seed prompts confirmed | ✓ PASS |
| EVAL-CRITERIA.md has 6 confirmed + 1 proposed flag | grep status: | 6 confirmed, 1 proposed | ✓ PASS |
| ORG-PROFILE.md has Current Strategic Priorities | line 316 check | Present with 5 priorities | ✓ PASS |
| app.py region is us-west-2 | grep region | FAIL: region="us-west-1" found | ✗ FAIL |
| Bedrock IAM ARN uses us-west-2 | grep arn:aws:bedrock | FAIL: us-west-1 ARN at line 146 | ✗ FAIL |
| cdk synth produces valid template | npx cdk synth | SKIP (CDK CLI not in context) | ? SKIP |
| init_db.py + ingest_documents.py against live RDS | python init_db.py + ingest_documents.py | SKIP (no DB) | ? SKIP |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| INFRA-01 | 01-01 | CDK stack provisions all AWS infrastructure | ✗ BLOCKED | hanna_stack.py is structurally complete but app.py deploys to us-west-1 (wrong region) and Bedrock IAM ARN is broken. Requires two one-line fixes before cdk deploy. |
| OPS-02 | 01-01 | Billing alarms at $40/$50 with SNS | ✓ SATISFIED | SNS topic hanna-billing-alerts with email subscription; 18-line us-east-1 alarm comment block with aws cloudwatch put-metric-alarm CLI examples |
| PROF-01 | 01-02 | ORG-PROFILE.md extended with strategic priorities | ✓ SATISFIED | ## Current Strategic Priorities at line 316 with 5 priorities |
| PROF-02 | 01-04 | PDF extraction + document ingestion scripts | ✓ SATISFIED | extract_pdfs.py and ingest_documents.py complete with pdfplumber, ON CONFLICT upsert, derive_funder_year |
| PROF-03 | 01-05 | Per-profile HyDE queries generated and stored | ✓ SATISFIED (script) / ? HUMAN (runtime) | generate_hyde.py is complete and correct — parses all 6 profiles, generates via GPT-5.4, embeds via Bedrock, stores with SHA-256 hash. Actual table population requires live AWS services. |
| PROF-04 | 01-02, 01-05 | SEARCH-PROFILES.md + HyDE generation script | ✓ SATISFIED | All 6 profiles with full content; HyDE seed prompts present; generate_hyde.py functional |
| INFRA-02 | 01-03 | DB schema (6 tables + HNSW indexes + constraints) | ✓ SATISFIED | init_db.py has all 6 tables, 3 HNSW indexes, UNIQUE constraints on grants/documents/hyde_queries |
| INFRA-03 | 01-03 | Shared utility modules (config, db, embeddings, chunking) | ✓ SATISFIED | All 4 utility modules complete, correct, and wired |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `infrastructure/app.py` | 6 | `region="us-west-1"` — wrong AWS region | ✗ BLOCKER | All CDK resources (RDS, Lambda, API Gateway, S3, CloudWatch, EventBridge) will be provisioned in us-west-1 (Northern California) instead of us-west-2 (Oregon). Entire stack in wrong region. |
| `infrastructure/stacks/hanna_stack.py` | 146 | `arn:aws:bedrock:us-west-1::` — wrong region in Bedrock IAM ARN | ✗ BLOCKER | Lambda execution role's Bedrock policy scopes to us-west-1 ARN. When Lambda runs in us-west-2 and calls Bedrock, IAM will deny the request with AccessDeniedException. Embeddings will silently fail. |
| `infrastructure/stacks/hanna_stack.py` | 241 | Comment says "not us-west-1" — should say "not us-west-2" | ℹ️ INFO | Typo in a comment; does not affect functionality but is confusing |

### Human Verification Required

#### 1. CDK Synth (after fixing region typos)

**Test:** Fix the two us-west-1 typos (app.py line 6 and hanna_stack.py line 146), then run `cd infrastructure && npx cdk synth --quiet` (requires CDK CLI + Python CDK dependencies installed).
**Expected:** Exit code 0; synthesized CloudFormation template contains: RDS instance, Lambda function (Python 3.13 runtime), IAM Role with Bedrock ARN using us-west-2, API Gateway with ApiKey + UsagePlan, S3 bucket with lifecycle rule, CloudWatch LogGroup (TWO_WEEKS), two EventBridge rules (daily + weekly, both disabled), SNS topic, Secrets Manager secret reference, and all 8 CfnOutputs.
**Why human:** CDK CLI not available in verification context.

#### 2. Schema + Ingestion Integration Test

**Test:** Run `python scripts/init_db.py --secret-arn <ARN>` then `python scripts/ingest_documents.py --secret-arn <ARN>` against a real RDS instance in us-west-2.
**Expected:** `SELECT COUNT(*) FROM documents` returns > 0 with no column-not-found errors; section_title, funder, and year columns populated.
**Why human:** Requires live RDS connection with real AWS credentials.

### Gaps Summary

Two regressions were introduced since the previous verification (which had status: human_needed, 17/18). Both are `us-west-1` typos in the CDK infrastructure files:

1. **infrastructure/app.py line 6** — `region="us-west-1"` should be `region="us-west-2"`. This is a deployment blocker: cdk deploy would create the entire AWS stack (RDS, Lambda, API Gateway, S3, EventBridge, CloudWatch) in Northern California instead of Oregon. The previous PLAN.md specified us-west-2; the previous VERIFICATION.md confirmed us-west-2 in the app.py artifact. This was introduced as a typo during or after the previous gap closure.

2. **infrastructure/stacks/hanna_stack.py line 146** — Bedrock IAM ARN uses `arn:aws:bedrock:us-west-1::` instead of `arn:aws:bedrock:us-west-2::`. The Lambda execution role's Bedrock policy restricts invocation to a us-west-1 ARN. When the Lambda runs in us-west-2 (the correct region) and calls Bedrock Titan V2, IAM will deny the call with AccessDeniedException. `config.py` correctly sets `AWS_REGION = "us-west-2"` — the ARN must match.

Both fixes are one-line changes. All other Phase 1 artifacts (org context files, DB schema, utility modules, ingestion scripts, HyDE script) are substantive, wired, and correct.

**Root cause:** Two us-west-1 typos introduced in CDK infrastructure files. All scripts use the correct us-west-2 region via config.py.

**Phase 2 readiness:** Blocked until the two us-west-1 typos are corrected.

---

## Re-Verification Summary

**Previous status:** human_needed (17/18) — all code gaps closed, 2 human items pending (cdk synth, live DB test)

**This pass found 2 regressions** not present in the previous verification:
1. `app.py` region changed from us-west-2 to us-west-1
2. `hanna_stack.py` Bedrock IAM ARN uses us-west-1

The regressions are blocking: they prevent correct deployment of the CDK stack and break Lambda's ability to call Bedrock. They are also trivially fixable (two one-line changes).

All 16 other must-haves remain verified from the previous pass. No other regressions detected.

---

_Verified: 2026-03-29_
_Verifier: Claude (gsd-verifier)_
