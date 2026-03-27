# Hanna Center — Grant Evaluation Criteria

*This file is read directly by the Evaluator agent (Phase 3) to score grant opportunities.*
*Marisa Binder (VP Grants) updates this file when priorities or thresholds shift.*

***

## How to Use This File

The Evaluator agent reads each flag below and scores incoming grants against them. Each flag produces a rating and reasoning that appears in the weekly digest. Staff should update thresholds and weights here — not in ORG-PROFILE.md or in code.

***

## Evaluation Flags

### Flag 1: Strategic Priority Alignment
- **Question:** Does this grant fund one of Hanna's current strategic priorities?
- **id:** `strategic_priority_alignment`
- **weight:** HIGH
- **scoring:**
  - Strong match: Grant explicitly funds an active strategic priority (see ORG-PROFILE.md > Current Strategic Priorities)
  - Partial match: Grant aligns with Hanna's mission but not a current priority
  - Weak match: Grant is tangentially related or requires new program development
- **source:** Cross-reference with `org-materials/ORG-PROFILE.md ## Current Strategic Priorities`

### Flag 2: Staff Time Cost
- **Question:** What is the true staff time cost (application + reporting + compliance)?
- **id:** `staff_time_cost`
- **weight:** HIGH
- **scoring:**
  - Low burden: < 20 hours total (application + first year reporting)
  - Medium burden: 20-60 hours total
  - High burden: > 60 hours total
- **context:** Hanna has a 2-person grants team (VP Grants + Grants Manager). High-burden grants must have proportionally high award amounts to justify.
- **calibration_needed:** true — confirm loaded labor rate with Marisa before Phase 3

### Flag 3: Reporting Burden
- **Question:** How heavy is the ongoing reporting requirement?
- **id:** `reporting_burden`
- **weight:** MEDIUM
- **scoring:**
  - Light: Annual narrative report only
  - Medium: Quarterly reports with basic metrics
  - Heavy: Monthly reporting, site visits, external evaluation required
- **context:** For a 2-person team, heavy reporting on a $25K grant is not viable. Threshold: grants under $50K should not carry heavy reporting.
- **calibration_needed:** true — calibrate light/medium/heavy with Marisa before Phase 3

### Flag 4: Relationship Required
- **Question:** Is a prior funder relationship required or advantageous?
- **id:** `relationship_required`
- **weight:** MEDIUM
- **scoring:**
  - No relationship needed: Open competition, first-time applicants welcome
  - Relationship helpful: Prior grantees given preference but not required
  - Relationship required: Invitation-only or requires letter of intent from known grantee
- **source:** Cross-reference with `org-materials/FUNDER-DIRECTORY.md` for known funder relationships

### Flag 5: Timeline Fit
- **Question:** Does the deadline fit Hanna's current capacity and grant load?
- **id:** `timeline_fit`
- **weight:** MEDIUM
- **scoring:**
  - Good fit: Deadline > 4 weeks out, no competing deadlines in same window
  - Tight fit: Deadline 2-4 weeks out, manageable with prioritization
  - Poor fit: Deadline < 2 weeks or overlaps with multiple active applications
- **context:** Staff capacity fluctuates — this flag is most useful when combined with the active grant load visible in the system.
- **calibration_needed:** true — need mechanism to capture current staff capacity (changes weekly)

### Flag 6: Current Programs vs. New Programs
- **Question:** Does this fund existing programs or require building something new?
- **id:** `current_vs_new_programs`
- **weight:** HIGH
- **scoring:**
  - Current programs: Grant funds services Hanna already delivers (strong — can show track record)
  - Program expansion: Grant funds extending existing programs to new populations or geographies (moderate)
  - New program: Grant requires building a program Hanna does not currently operate (weak — high startup cost, no track record to cite)
- **source:** Cross-reference with `org-materials/ORG-PROFILE.md` program descriptions

***

## Overall Scoring

The Evaluator agent produces a composite fit score (1-10) by weighing all 6 flags. Grants scoring below 6/10 are filtered out of the weekly digest.

| Score Range | Interpretation |
|-------------|----------------|
| 8-10 | Strong match — prioritize application |
| 6-7 | Worth reviewing — flag for staff decision |
| 4-5 | Marginal — likely skip unless strategic reason |
| 1-3 | Poor fit — auto-filtered |

***

## Eligibility Pre-Filters (Hard Stops)

Before flag scoring, the Evaluator checks these hard eligibility criteria. If ANY fails, the grant is rejected without scoring:

1. **Organization type:** Must accept 501(c)(3) nonprofit applicants
2. **Geography:** Must be open to California, specifically Sonoma County organizations (or national/statewide)
3. **Population served:** Must align with youth, families, or communities impacted by trauma/adversity
4. **Deadline:** Must be in the future (not expired)

***

## Core Eligibility Themes (from Grant Eligibility Criteria document)

The following themes represent areas where Hanna Center and Hanna Academy consistently qualify for funding. The Evaluator agent uses these as positive signals when scoring alignment:

### Hanna Center Themes
1. **Trauma-Informed Youth Services & Behavioral Health** — Licensed provider, evidence-based models, high-risk youth
2. **Foster Youth, TAY, and Systems-Involved Youth** — Housing, wraparound supports, county coordination
3. **Career Technical Education & Workforce Pathways** — CTE tracks, specialized education, workforce readiness
4. **Arts, Recreation, and Enrichment** — After-school/summer programs, social-emotional development
5. **General Operating & Institutional Trust** — 80+ year history, strong governance, community impact

### Hanna Academy Themes
- Alternative/nontraditional education for youth with IEPs
- Workforce and postsecondary transition support
- Equity in education access
- Small cohort learning environments

***

*Last updated: 2026-03-23*
*Owner: Marisa Binder (VP Grants), Hanna Center*
