---
phase: 05-expand-data-sources-simpler-grants-gov-api-scraper
plan: 01
subsystem: ingestion
tags: [simpler-grants-gov, httpx, scraper, federal-grants, api, cdk, step-functions]

# Dependency graph
requires:
  - phase: 02-data-ingestion
    provides: BaseApiClient, RawGrant, scraper_registry.json, handler.py pattern, CDK scraper Lambda

provides:
  - SimplerGrantsGov API client class in scripts/scrapers/api/simpler_grants_gov.py
  - 4 unit tests with fixture data in scripts/tests/test_simpler_grants_gov.py
  - Fixture JSON in scripts/tests/fixtures/simpler_grants_gov_response.json
  - scraper_registry.json entry for simpler-grants-gov (18 total scrapers)
  - handler.py dispatch mapping for simpler-grants-gov
  - CDK SimplerGrantsApiKey CfnParameter and SIMPLER_GRANTS_API_KEY Lambda env var

affects: [phase-05, cdk-deploy, step-functions-fan-out, federal-grant-coverage]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Custom headers via raw client.post: when X-API-Key header needed, use await self._get_client() + client.post(url, headers=headers) instead of _post_json"
    - "Pagination via page_offset/total_pages from pagination_info response object"

key-files:
  created:
    - scripts/scrapers/api/simpler_grants_gov.py
    - scripts/tests/test_simpler_grants_gov.py
    - scripts/tests/fixtures/simpler_grants_gov_response.json
  modified:
    - scraper_registry.json
    - scripts/scrapers/handler.py
    - infrastructure/stacks/hanna_stack.py

key-decisions:
  - "Simpler.Grants.gov supplements (does not replace) grants-gov legacy scraper — SHA-256 dedup collapses any duplicates automatically"
  - "Raw client.post required for X-API-Key header — _post_json has no custom header support, confirmed in base_api_client.py"

patterns-established:
  - "Custom auth headers pattern: _get_headers() method + raw client.post for scrapers requiring API key in header"

requirements-completed: [EXPAND-01, EXPAND-02]

# Metrics
duration: 2min
completed: 2026-04-07
---

# Phase 5 Plan 01: Simpler.Grants.gov API Scraper Summary

**SimplerGrantsGov(BaseApiClient) class added: X-API-Key header auth, 501(c)(3) nonprofit filter, pagination, registered in handler + registry + CDK**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-08T04:22:44Z
- **Completed:** 2026-04-08T04:24:47Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- SimplerGrantsGov class parses Simpler.Grants.gov REST API responses into RawGrant objects with correct field mapping
- 4 unit tests pass offline against recorded fixture data (parse response, pagination stops, content hash, source_id)
- Scraper registered in all 3 integration points: scraper_registry.json (18 entries), handler.py dispatch, hanna_stack.py CDK parameter

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for SimplerGrantsGov** - `ba0c13f` (test)
2. **Task 1 GREEN: SimplerGrantsGov implementation** - `f102319` (feat)
3. **Task 2: Register in handler, registry, CDK** - `5a67e92` (feat)

_Note: TDD task had RED + GREEN commits as required._

## Files Created/Modified

- `scripts/scrapers/api/simpler_grants_gov.py` - SimplerGrantsGov class: X-API-Key header, nonprofit filter, pagination
- `scripts/tests/test_simpler_grants_gov.py` - 4 unit tests using httpx.MockTransport
- `scripts/tests/fixtures/simpler_grants_gov_response.json` - Recorded API response with 2 sample opportunities
- `scraper_registry.json` - Added simpler-grants-gov entry (17 -> 18 total scrapers)
- `scripts/scrapers/handler.py` - Import + dispatch mapping for SimplerGrantsGov
- `infrastructure/stacks/hanna_stack.py` - SimplerGrantsApiKey CfnParameter + SIMPLER_GRANTS_API_KEY env var

## Decisions Made

- Used raw `client.post()` with explicit headers instead of `_post_json()` — base class does not support custom headers; this pattern is documented in plan and confirmed in base_api_client.py
- Scraper supplements grants-gov (not replaces) — both scrapers run in parallel, dedup by SHA-256 content hash handles any overlapping opportunities during Grants.gov migration period

## Deviations from Plan

None - plan executed exactly as written.

## User Setup Required

**External services require manual configuration.**

To use this scraper in production, a Simpler.Grants.gov API key is needed:

1. Sign in at `simpler.grants.gov/developer` using Login.gov credentials
2. Generate an API key in the developer dashboard
3. At CDK deploy time, pass: `--parameters SimplerGrantsApiKey=<your-key>`

Without the key, the scraper will send requests with an empty `X-API-Key` header, which the API will reject with 401. The Lambda will log the error and return 0 grants (consistent with existing error-handling behavior in other scrapers).

## Next Phase Readiness

- Simpler.Grants.gov is fully wired into the Step Functions fan-out — next `cdk deploy` will include it automatically
- API key setup needed before production use (see User Setup above)
- No blockers for other work

---
*Phase: 05-expand-data-sources-simpler-grants-gov-api-scraper*
*Completed: 2026-04-07*
