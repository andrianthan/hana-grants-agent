# Evaluation Criteria

*This file is read by the Evaluator agent (Phase 3). Marisa Binder updates this file when priorities or thresholds shift.*
*Format: Each flag is a structured block. Do not change the field names (id, weight, etc.) -- only change the values.*
*Last updated: 2026-03-27*

## Eligibility Pre-Filters (Hard Stops)

The Evaluator rejects grants that fail ANY of these before scoring:

- org_type: 501(c)(3) nonprofit
- geography: California OR Sonoma County OR national (with CA eligibility)
- population: youth, families, trauma-impacted, mental health, residential, community resilience
- deadline: > today (not expired)

## Evaluation Flags

### Flag 1: Strategic Priority Alignment

id: strategic_priority_alignment
weight: HIGH
status: confirmed
calibration_needed: false
description: Does this grant align with Hanna's current strategic priorities listed in ORG-PROFILE.md?
scoring_rubric:
  9-10: Directly funds an active strategic priority (CSC, Mental Health Hub, HEAL, CTE, Trauma Training)
  7-8: Strong overlap with one or more strategic priorities
  5-6: Tangential connection to strategic priorities
  3-4: Weak connection; would require repurposing existing programs
  1-2: No connection to current strategic priorities

### Flag 2: Staff Time Cost

id: staff_time_cost
weight: HIGH
status: confirmed
calibration_needed: true
description: Estimated staff hours for application + reporting + compliance relative to award size.
scoring_rubric:
  9-10: Minimal application effort, streamlined reporting (e.g., foundation letter of inquiry)
  7-8: Moderate application, standard quarterly reporting
  5-6: Significant application (20+ hours), detailed reporting requirements
  3-4: Major application effort (40+ hours), intensive compliance monitoring
  1-2: Extreme effort relative to award size; ROI negative for a 2-person grants team
notes: Calibrate labor rate and hour thresholds with Marisa before Phase 3 prompt design.

### Flag 3: Reporting Burden

id: reporting_burden
weight: MEDIUM
status: confirmed
calibration_needed: true
description: Weight of ongoing reporting requirements relative to a 2-person grants team.
scoring_rubric:
  9-10: Light -- annual narrative report only
  7-8: Light-Medium -- semi-annual reports, basic data collection
  5-6: Medium -- quarterly reports, outcome tracking, site visits
  3-4: Medium-Heavy -- monthly reports, federal compliance, audits
  1-2: Heavy -- continuous reporting, complex federal requirements, multiple agency oversight
notes: Calibrate burden thresholds with Marisa before Phase 3 prompt design.

### Flag 4: Relationship Required

id: relationship_required
weight: MEDIUM
status: confirmed
calibration_needed: false
description: Does the funder require or strongly prefer an existing relationship with the applicant?
scoring_rubric:
  9-10: No relationship required; open competitive process
  7-8: Relationship helpful but not required; Hanna has prior contact
  5-6: Relationship preferred; Hanna has no prior contact but could establish one
  3-4: Strong relationship required; Hanna has no prior contact
  1-2: Invitation-only or requires multi-year established relationship

### Flag 5: Timeline Fit

id: timeline_fit
weight: MEDIUM
status: confirmed
calibration_needed: true
description: Does the grant deadline fit Hanna's current staff capacity and active grant load?
scoring_rubric:
  9-10: 60+ days to deadline; no competing deadlines
  7-8: 30-60 days; manageable with current load
  5-6: 14-30 days; tight but possible if prioritized
  3-4: 7-14 days; would require dropping other work
  1-2: < 7 days; effectively impossible for a 2-person team
notes: Calibrate capacity mechanism with Marisa before Phase 3 prompt design.

### Flag 6: Current vs New Programs

id: current_vs_new_programs
weight: HIGH
status: confirmed
calibration_needed: false
description: Does this grant fund services Hanna already delivers, or would it require building something new?
scoring_rubric:
  9-10: Directly funds an existing, operational Hanna program
  7-8: Funds existing program with minor expansion or adaptation
  5-6: Requires moderate program development or new partnerships
  3-4: Requires significant new program development
  1-2: Would require entirely new infrastructure, staff, or capabilities

### Flag 7: Program Fit (PROPOSED -- Pending Confirmation)

id: program_fit
weight: MEDIUM
status: proposed
calibration_needed: true
description: How well does the grant's program requirements match Hanna's specific department capabilities? This flag was proposed by the planner as distinct from strategic_priority_alignment (which measures alignment with org-wide priorities). Program fit measures whether a specific department has the operational capacity and expertise to execute. Needs Marisa's confirmation before Phase 3 implementation.
scoring_rubric:
  9-10: Perfect match -- department already runs this exact type of program
  7-8: Strong match -- department has relevant expertise and infrastructure
  5-6: Partial match -- department could adapt existing programs
  3-4: Weak match -- would require significant department capacity building
  1-2: No match -- wrong department entirely
notes: This is a PROPOSED 7th flag. It will not be used in Phase 3 scoring unless Marisa confirms it in the pre-Phase-3 calibration call. If confirmed, it distinguishes department-level fit from org-level strategic alignment.

## Scoring Guide

scale: 1-10 (integer)
threshold: 6 (grants scoring below 6 are filtered from digest)
method: Weighted average across all confirmed flags (6 flags in v1; 7 if program_fit is confirmed)
output: Overall score (1-10), per-flag scores, 2-sentence reasoning, flags as JSON object
