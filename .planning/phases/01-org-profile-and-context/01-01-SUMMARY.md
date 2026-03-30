---
phase: 01-org-profile-and-context
plan: 01
subsystem: infra
tags: [cdk, aws, rds, postgresql, pgvector, lambda, api-gateway, s3, eventbridge, sns, iam]

# Dependency graph
requires: []
provides:
  - CDK stack with all Phase 1 AWS resources (RDS, Lambda, API GW, S3, CloudWatch, EventBridge, SNS)
  - Lambda execution role with least-privilege IAM
  - API Gateway scaffold with API key and usage plan
affects: [01-03, 01-04, 02-ingestion, 03-evaluation]

# Tech tracking
tech-stack:
  added: [aws-cdk-lib 2.245.0, constructs 10.6.0]
  patterns: [single CDK stack, CfnParameter for deploy-time overrides, least-privilege IAM with scoped ARNs]

key-files:
  created:
    - infrastructure/app.py
    - infrastructure/cdk.json
    - infrastructure/requirements.txt
    - infrastructure/stacks/__init__.py
    - infrastructure/stacks/hanna_stack.py
  modified: []

key-decisions:
  - "us-west-1 region (closest to Hanna Center in Sonoma County)"
  - "Bedrock Titan V2 ARN scoped to us-west-1"
  - "Weekly evaluation cron at 14:00 UTC (7am PT Monday)"
  - "Secrets Manager rotation deferred to Phase 2 with documented TODO"

patterns-established:
  - "CfnParameter pattern: deploy-time overrides for AllowedIps and AlertEmail"
  - "Least-privilege IAM: scoped to specific resource ARNs, no wildcards"
  - "Billing alarms documented as manual us-east-1 steps (cross-region limitation)"

requirements-completed: [INFRA-01, OPS-02]

# Metrics
duration: 3min
completed: 2026-03-30
---

# Phase 01 Plan 01: CDK Infrastructure Stack Summary

**Deployable CDK stack with RDS PostgreSQL t4g.micro (pgvector-ready), least-privilege Lambda role, API Gateway with key+usage plan, S3 with lifecycle rules, EventBridge scaffolds, and SNS billing alerts in us-west-1**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-30T03:08:24Z
- **Completed:** 2026-03-30T03:11:51Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- CDK stack synthesizes a valid CloudFormation template with all Phase 1 resources
- RDS PostgreSQL 16.4 t4g.micro with SSL enforcement, public access, and Secrets Manager password
- Lambda execution role scoped to specific Bedrock model ARN, S3 bucket, and Secrets Manager secret
- API Gateway with API key + usage plan (10 req/sec, 500/day quota)
- SNS billing alerts with documented manual us-east-1 alarm creation ($40 warning, $50 critical)
- Dual EventBridge scaffolds (daily ingestion 13:00 UTC, weekly eval Monday 14:00 UTC) both disabled

## Task Commits

Each task was committed atomically:

1. **Task 1: Create CDK project scaffold** - `e30cfb9` (feat)
2. **Task 2: Implement HannaStack CDK stack** - `b6d90bb` (feat)

## Files Created/Modified
- `infrastructure/app.py` - CDK app entry point with us-west-1 region
- `infrastructure/cdk.json` - CDK project configuration
- `infrastructure/requirements.txt` - CDK Python dependencies (aws-cdk-lib>=2.244.0)
- `infrastructure/stacks/__init__.py` - Package marker
- `infrastructure/stacks/hanna_stack.py` - Full CDK stack: VPC, RDS, Lambda, API GW, S3, CloudWatch, EventBridge, SNS, IAM

## Decisions Made
- Used us-west-1 (N. California) instead of us-west-2 per user override -- closest region to Hanna Center in Sonoma County
- Scoped Bedrock ARN to us-west-1 for Titan Embed Text V2
- Weekly evaluation cron set to 14:00 UTC (7am PT) per plan specification
- Secrets Manager rotation explicitly deferred with detailed Phase 2 TODO comment

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed weekly evaluation cron hour**
- **Found during:** Task 2 (HannaStack implementation)
- **Issue:** Existing code had hour="15" (8am PT) but plan specifies hour="14" (7am PT)
- **Fix:** Changed EventBridge weekly rule to hour="14"
- **Files modified:** infrastructure/stacks/hanna_stack.py
- **Verification:** cdk synth passes, EventBridge rule has correct schedule
- **Committed in:** b6d90bb (Task 2 commit)

**2. [Rule 2 - Missing Critical] Added detailed billing alarm documentation**
- **Found during:** Task 2 (HannaStack implementation)
- **Issue:** Existing billing comment lacked the two-tier alarm structure ($40 warning + $50 critical) specified in plan
- **Fix:** Replaced single-alarm comment with full two-tier documentation matching plan specification
- **Files modified:** infrastructure/stacks/hanna_stack.py
- **Verification:** Comment block contains both threshold levels with complete CLI examples
- **Committed in:** b6d90bb (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical)
**Impact on plan:** Both fixes align implementation with plan specification. No scope creep.

## Issues Encountered
- pip3 install blocked by PEP 668 (externally managed environment) -- resolved by creating venv at infrastructure/.venv
- Node v25.6.1 triggers JSII warning (untested version) -- warnings only, does not affect synthesis

## Known Stubs
None -- this is infrastructure-only (CDK stack). The Lambda placeholder function is intentionally minimal and will be replaced in Phase 2.

## User Setup Required
None - no external service configuration required at this stage. Billing alarms require manual us-east-1 creation after `cdk deploy` (documented in stack comments).

## Next Phase Readiness
- CDK stack ready for `cdk deploy` when AWS credentials are configured
- Lambda role, API Gateway, and S3 bucket are scaffolded for Phase 1 plans 03-05
- RDS endpoint will be available after deploy for database schema initialization (Plan 01-03)

## Self-Check: PASSED

All 5 files verified present. Both task commits (e30cfb9, b6d90bb) verified in git log.

---
*Phase: 01-org-profile-and-context*
*Completed: 2026-03-30*
