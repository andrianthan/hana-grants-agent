---
phase: 01-org-profile-and-context
plan: 02
subsystem: org-context
tags: [org-profile, evaluation-criteria, scraper-registry, grant-scoring, markdown]

# Dependency graph
requires:
  - phase: none
    provides: "First plan in wave 1 — no dependencies"
provides:
  - "Extended ORG-PROFILE.md with 5 current strategic priorities for Evaluator scoring"
  - "EVAL-CRITERIA.md with 6-flag evaluation framework, eligibility pre-filters, and scoring table"
  - "scraper_registry.json with 10 grant source targets (3 APIs + 7 scrapers)"
affects: [phase-02-grant-ingestion, phase-03-evaluation-agents]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Structured markdown files as agent-readable configuration"
    - "JSON registry pattern for fan-out Lambda configuration"

key-files:
  created:
    - org-materials/EVAL-CRITERIA.md
    - scraper_registry.json
  modified:
    - org-materials/ORG-PROFILE.md

key-decisions:
  - "6-flag evaluation framework with HIGH/MEDIUM weights — 3 flags marked calibration_needed for Phase 3 tuning with Marisa"
  - "10 scraper targets covering CA state, federal, Sonoma County, and foundation sources — 3 API-based, 7 Playwright scrapers"
  - "Scoring threshold set at 6/10 for weekly digest inclusion"

patterns-established:
  - "Append-only updates to ORG-PROFILE.md — never rewrite existing content"
  - "Evaluation criteria stored in markdown (not code) so grant staff can edit directly"
  - "Scraper registry as JSON config read at Lambda runtime"

requirements-completed: [PROF-01]

# Metrics
duration: 3min
completed: 2026-03-27
---

# Phase 1 Plan 2: Org Context Files Summary

**Extended ORG-PROFILE.md with 5 strategic priorities, created 6-flag EVAL-CRITERIA.md for Evaluator agent scoring, and built scraper_registry.json with 10 grant source targets**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-27T06:00:00Z
- **Completed:** 2026-03-27T06:03:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- ORG-PROFILE.md extended (append-only) with Current Strategic Priorities section covering CSC Early Psychosis, Mental Health Hub, HEAL/Camino Nuevo, Hanna Academy CTE, and Trauma-Informed Training
- EVAL-CRITERIA.md created with 6 structured evaluation flags (strategic_priority_alignment, staff_time_cost, reporting_burden, relationship_required, timeline_fit, current_vs_new_programs), eligibility pre-filters, core eligibility themes, and 1-10 scoring table
- scraper_registry.json created with 10 targets: 3 APIs (grants.ca.gov, Grants.gov, grantmakers.io) and 7 Playwright scrapers (Sonoma County CF, CA Wellness, Blue Shield CA, Walter S. Johnson, Sonoma County Health, SAMHSA, CA DHCS)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend ORG-PROFILE.md and create EVAL-CRITERIA.md** - `f5d8ccb` (feat)
2. **Task 2: Create scraper_registry.json** - `6dfa177` (feat)

## Files Created/Modified
- `org-materials/ORG-PROFILE.md` - Extended with Current Strategic Priorities section (5 priorities)
- `org-materials/EVAL-CRITERIA.md` - New file: 6-flag evaluation framework for Evaluator agent with eligibility pre-filters and scoring guidance
- `scraper_registry.json` - New file: 10 scraper/API targets for Phase 2 fan-out Lambda

## Decisions Made
- 6-flag evaluation framework uses HIGH/MEDIUM weight system; flags 2, 3, and 5 marked `calibration_needed: true` for tuning with Marisa Binder before Phase 3
- Scoring threshold of 6/10 set as the cutoff for weekly digest inclusion
- 10 grant sources selected covering Hanna's priority channels: CA state (grants.ca.gov, DHCS), federal (Grants.gov, SAMHSA), Sonoma County (Community Foundation, County Health), and CA foundations (CA Wellness, Blue Shield, Walter S. Johnson)
- Added Core Eligibility Themes section to EVAL-CRITERIA.md sourced from Grant Eligibility Criteria document (5 Hanna Center themes + 4 Hanna Academy themes)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- ORG-PROFILE.md and EVAL-CRITERIA.md are ready for Phase 3 Evaluator agent to consume
- scraper_registry.json is ready for Phase 2 fan-out Lambda to read at runtime
- 3 flags need calibration with Marisa Binder before Phase 3: staff_time_cost, reporting_burden, timeline_fit

## Self-Check: PASSED

All files verified present, all commits verified in git log.

---
*Phase: 01-org-profile-and-context*
*Completed: 2026-03-27*
