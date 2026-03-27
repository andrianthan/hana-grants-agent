# Hanna Center — Grant Search Profiles

*This file defines department-specific search profiles for the grants agent.*
*Each profile generates its own HyDE query and applies department-specific evaluation weights.*
*When staff trigger a grant search via Custom GPT, they select the profile that matches their need.*

---

## How Profiles Work

1. **Staff selects a profile** in Custom GPT: *"Search for grants for the Mental Health Hub"*
2. **System loads the matching profile** from this file
3. **HyDE query** for that profile is retrieved from `hyde_queries` table (pre-generated)
4. **Vector search** runs using the profile's HyDE embedding
5. **Evaluator agent** applies profile-specific weights and flags during scoring
6. **Digest** is labeled with the active profile so staff know the lens used

If no profile is selected, the system runs **all profiles** and deduplicates results by grant ID, using the highest score across all profile perspectives.

---

## Profile Index

| profile_id | Department | Lead Contact | Primary Focus |
|---|---|---|---|
| `mental-health-hub` | Community Mental Health Hub | Noeli Zamora, Clinical Director | Community mental health, ACEs, bilingual therapy |
| `hanna-institute` | Hanna Institute (Training & Research) | Marissa LaBrecque, VP Training & Research | Workforce training, TIC certification, professional development |
| `residential-housing` | Residential & Transitional Housing | Scott Singer, VP Residential | Foster youth housing, independent living, TAY |
| `hanna-academy` | Hanna Academy (Education) | Courtney Jackson, Principal | Alternative education, CTE, special ed, workforce readiness |
| `recreation-enrichment` | Recreation & Community Enrichment | Meredith Standing, VP Community Supports | Youth camps, sports, arts, community access |
| `general-operations` | Organization-Wide / Capacity Building | Cameron Safarloo, CEO | General operating support, capital, infrastructure |

---

## Profile Definitions

---

### Profile: `mental-health-hub`

**Department:** Community Mental Health Hub
**Lead:** Noeli Zamora, Clinical Director (nzamora@hannacenter.org)

**Active Programs:**
- Community outpatient mental health (individual therapy, family counseling, grief/bereavement)
- CSC Early Psychosis Intervention (CYBHI-funded, launched Oct 2025)
- School-Based Mental Health (ARPA-funded, SVUSD partnership)
- HEAL Program / Camino Nuevo (Elevate Youth CA, Spanish-speaking newcomer youth)
- Suicide prevention awareness (7th, 9th, 11th graders)

**Population Served:**
- Youth ages 10–21 and families in Sonoma Valley
- 61% Latine, bilingual (Spanish/English), 60% BIPOC
- Medically Underserved Population (MUP) + Health Professional Shortage Area (HPSA)
- Youth with 4+ Adverse Childhood Experiences (ACEs)

**Key Metrics (FY24-25):**
- 392 unique clients (57% increase YoY)
- 3,976 hours of bilingual therapy (90% increase YoY)
- 87% of direct service staff are bilingual

**Target Funders:**
- SAMHSA (CCBHC, MHAT, System of Care)
- CA DHCS / CYBHI (existing relationship — follow-on opportunities)
- California Wellness Foundation
- Blue Shield of California Foundation
- HRSA (HPSA/MUP geography boost)
- Elevate Youth California / Sierra Health Foundation (existing relationship)
- Kaiser Permanente NorCal Community Benefit

**Evaluation Weight Adjustments:**
- Boost: bilingual/culturally responsive services, ACEs framework, HPSA geography, early psychosis, suicide prevention
- Flag: grants requiring SUD services (Hanna lacks SUD-specific programming in MH Hub)
- Flag: grants requiring 24/7 crisis line (not yet operational)

**HyDE Seed Prompt:**
```
Write a grant announcement for funding community-based, trauma-informed mental health services
for underserved youth and families in a medically underserved rural California community.
The funder prioritizes bilingual (Spanish/English) services, evidence-based care for
Adverse Childhood Experiences (ACEs), early psychosis intervention, and health equity for
BIPOC populations. The program serves youth ages 10–21 and their families through individual
therapy, family counseling, and community outreach. The service area is a designated Health
Professional Shortage Area (HPSA) and Medically Underserved Population (MUP) zone.
```

---

### Profile: `hanna-institute`

**Department:** Hanna Institute (Training & Research)
**Lead:** Marissa LaBrecque, VP Training & Research (mlabrecque@hannacenter.org)

**Active Programs:**
- Trauma-Informed Care (TIC) certification training
- Mental Health First Aid (MHFA) training
- Suicide Prevention Basics + Safety Planning
- De-escalation and Crisis Intervention training
- QPR (Question, Persuade, Refer) gatekeeper training
- Annual Trauma-Informed Care Summit (national reach)
- AMSR + CALM certifications (expanding)

**Population Served (Trainees):**
- Mental health clinicians and social workers
- K-12 educators and school administrators
- First responders (law enforcement, fire, EMS)
- Community health workers and case managers
- 2,419 professionals trained in FY24-25
- 6,801 participants across 339 trainings since June 2023
- 30,000+ person mailing list

**Geographic Reach:** Sonoma, Napa, Marin counties (and national for Summit)

**Target Funders:**
- HRSA (Behavioral Health Workforce Education and Training — BHWET)
- SAMHSA (Mental Health Awareness Training — MHAT grant)
- CA Office of Emergency Services (first responder training)
- J.W. Couch Foundation (trauma-responsive educator training — active relationship)
- CA Department of Education (educator workforce development)
- Local foundations supporting workforce capacity building

**Evaluation Weight Adjustments:**
- Boost: workforce development, HPSA geography, evidence-based curricula, multi-county reach, national Summit
- Boost: training first responders or educators (MHAT and BHWET both prioritize these)
- Flag: grants requiring accredited academic partner (Hanna Institute is not a degree-granting institution)

**HyDE Seed Prompt:**
```
Write a grant announcement to fund training for mental health professionals, educators,
and first responders in evidence-based trauma-informed care practices in underserved
California communities. The funder prioritizes building behavioral health workforce capacity
in Health Professional Shortage Areas (HPSAs), certification programs in Mental Health First Aid,
suicide prevention gatekeeper training (QPR), and de-escalation. The training organization
serves Sonoma, Napa, and Marin counties and conducts national conferences.
The program aims to train 2,000+ professionals annually.
```

---

### Profile: `residential-housing`

**Department:** Residential & Transitional Housing
**Lead:** Scott Singer, VP Residential Programs; Jeremiah Presinal, Sr. Director Residential

**Active Programs:**
- Transitional Housing Placement Program (THPP) — foster youth ages 16–21
- Independent Living Plan (ILP): nutrition, cooking, laundry, financial literacy, life skills
- Residential treatment for youth with IEPs/behavioral challenges (added 2024)
- Vocational education and career support for residents
- Family therapy and group therapy within residential

**Population Served:**
- Foster youth ages 16–21 aging out of care (primary)
- Transition-age youth (TAY) ages 16–24
- Youth with emotional/behavioral challenges placed via county systems
- FY24-25: 53 young people housed; every minor opting to stay in extended support

**Capacity:** Up to 36 youth

**Target Funders:**
- ACF / HHS (Transitional Living Program — TLP, CFDA 93.550) — untapped federal source
- California Department of Social Services (CDSS) — foster youth programs
- Sonoma County HHSA — foster care and housing
- Sisters of St. Joseph Healthcare Foundation (active application — $30K transitional housing)
- CA Housing Is Key / HHAP housing funds
- Foundations supporting foster youth and housing stability

**Evaluation Weight Adjustments:**
- Boost: foster youth, aging out of care, transitional housing, independent living skills, TAY
- Boost: any ACF/HHS programs (Hanna has no current federal grants — TLP would be first)
- Flag: grants requiring mental health clinic licensure for housing component (Hanna's housing is separate from MH Hub)
- Flag: grants requiring permanent supportive housing (Hanna's program is transitional, not permanent)

**HyDE Seed Prompt:**
```
Write a grant announcement to fund transitional housing and independent living services
for young people ages 16–22 who are aging out of foster care. The funder prioritizes
evidence-based life skills development (financial literacy, cooking, employment readiness),
trauma-informed case management, vocational education, and family reconnection support.
The program provides stable housing plus wraparound services to support youth in
successfully transitioning to independent adulthood. The service area is rural Northern California.
```

---

### Profile: `hanna-academy`

**Department:** Hanna Academy (Education — separate 501(c)(3): EIN 88-2156897)
**Lead:** Courtney Jackson, Principal (courtney@hannaacademy.org)
**Note:** Hanna Academy is a legally separate 501(c)(3). Some grants require applying as Hanna Education Corporation. Confirm with Marisa Binder which entity applies.

**Active Programs:**
- Non-public high school for students ages 14–18 with IEPs (WASC accredited)
- CTE Tracks: Construction Trades, Health, Technology for Industry, Culinary/Hospitality, Digital Photography/Design, 3D Modeling
- On-site Career Center (internship placement, opened 2023)
- Residential program for up to 24 Academy students (added 2024)
- Small class sizes, individualized curriculum

**Population Served:**
- ~60 students/year with IEPs for emotional/behavioral challenges
- 64% Sonoma County, 12% Marin County, remainder Northern/Central CA
- Students who couldn't succeed in traditional school settings

**Target Funders:**
- CA Department of Education (CTE and special education grants)
- Carl D. Perkins Career and Technical Education Act (federal CTE funding)
- Sonoma County Office of Education
- Kimball Foundation (CTE programs — applied Sept 2025; separate rejection Feb 2025)
- J.W. Couch Foundation "Get Outside" (after school wellness — applied Sept 2026)
- Speedway Children's Charities / Broderick Foundation (CTE — applied Aug 2025)
- Walter S. Johnson Foundation (youth development + CTE)
- Foundations supporting alternative education and special education

**Evaluation Weight Adjustments:**
- Boost: CTE, alternative education, special education, IEP students, vocational training, workforce readiness
- Boost: arts/digital media/technology grants (Digital Photography and 3D Modeling CTE are new — needs funding)
- Flag: grants requiring public school eligibility (Hanna Academy is a non-public school — some public ed grants exclude non-public)
- Flag: Kimball Foundation — two applications in 2025; check for recency fatigue before applying again

**HyDE Seed Prompt:**
```
Write a grant announcement to fund career and technical education (CTE) programs at an
alternative school serving students ages 14–18 with Individualized Education Programs (IEPs)
and emotional/behavioral challenges in rural Northern California. The funder prioritizes
hands-on vocational training tracks (construction, culinary, health sciences, technology),
pathway-to-employment programming, and small-classroom individualized instruction for
students who have not succeeded in traditional school settings. The school is WASC accredited
and California Department of Education certified.
```

---

### Profile: `recreation-enrichment`

**Department:** Recreation & Community Enrichment
**Lead:** Meredith Standing, VP Marketing, Communications & Community Supports

**Active Programs:**
- Summer camps (grew from 6 to 13 sessions FY24-25, 218 participants ages 6–13)
- Youth sports (soccer and football fields, ~1,700 participants/year)
- Arts, gardening, robotics, culinary, life-skills workshops
- Financial assistance: 21% of summer participants, 65% of school-year participants

**Population Served:**
- Youth ages 6–13 in Sonoma Valley
- Low-income families (majority receive financial assistance)
- Community members accessing recreation/support services: 2,654 in FY24-25

**Target Funders:**
- Community Foundation Sonoma County (local, rolling grants)
- City of Sonoma (active — $3,000 pending for youth scholarships)
- Olympic Club Foundation (active — $25K for youth athletics/soccer, applied Feb 2026)
- Local corporate philanthropy (Bank of Marin, wineries, Sonoma businesses)
- Foundations supporting youth sports and enrichment
- After-school enrichment and summer program funders

**Evaluation Weight Adjustments:**
- Boost: youth enrichment, summer programming, sports, arts, low-income access, Sonoma County geography
- Boost: grants with low reporting burden (small team managing this program area)
- Flag: grants requiring academic outcome metrics (recreation programs don't have test score data)
- Flag: grants under $10K — very low ROI for staff time unless part of ongoing relationship

**HyDE Seed Prompt:**
```
Write a grant announcement to fund summer camps, youth sports programs, and enrichment
activities for low-income children ages 6–13 in rural Northern California. The funder
prioritizes free or sliding-scale community recreation, arts and STEM enrichment,
outdoor programming, and scholarship support for families who cannot afford program fees.
The program provides a safe, structured summer environment for youth from underserved
families in the Sonoma Valley.
```

---

### Profile: `general-operations`

**Department:** Organization-Wide / Capacity Building
**Lead:** Cameron Safarloo, CEO; Catherine Donahue, VP Finance & Facilities

**Scope:**
- General operating support (unrestricted or lightly restricted)
- Capital projects (facilities, infrastructure)
- Staff development and retention
- Technology and data systems
- Organizational capacity building

**Current Capital/Capacity Needs:**
- Residential cottage renovations (Bothin Foundation applied Dec 2025 — $50K)
- Student engagement technology (Bothin Foundation rejected Dec 2024 — $50K; do not re-apply for tech)
- General operations (Bank of Marin $10K, Callie McGrath $20K — active applications)
- Staff capacity for growing program portfolio

**Target Funders:**
- Community Foundation Sonoma County (general operating support)
- Callie McGrath Foundation (general operations — active)
- Bank of Marin (general operations — active)
- Foundations offering capacity building or general operating grants
- Multi-year operating support from major institutional funders

**Evaluation Weight Adjustments:**
- Boost: general operating support, capacity building, multi-year awards, low reporting burden
- Boost: grants that don't require new programs (all funds apply to existing operations)
- Flag: grants requiring specific programmatic outcomes (general ops grants are hard to tie to direct service metrics)
- Flag: grants under $15K with heavy reporting — not worth it for general ops

**HyDE Seed Prompt:**
```
Write a grant announcement for general operating support or capacity-building funding
for an established nonprofit with 80+ years of service to youth, families, and communities
impacted by trauma and adversity in Northern California. The funder supports organizations
with proven track records delivering mental health services, transitional housing, education,
and trauma-informed training. Priority given to organizations serving BIPOC and low-income
populations in medically underserved communities. Unrestricted or lightly restricted
multi-year support preferred.
```

---

## How to Update This File

This file is maintained by **Marisa Binder, VP of Grants** and **Monica Argenti, Grants Manager**.

When to update a profile:
- A new program launches or an existing program ends
- A program changes its target population or geography
- Key staff contacts change
- A new funder relationship is established (add to Target Funders)
- A funder relationship ends or a rejection makes re-application premature (add to evaluation flags)

After updating this file, run `generate_hyde.py --profile-id <profile_id> --force` to regenerate the HyDE embedding for the changed profile.

*Last updated: 2026-03-26*
*Owner: Marisa Binder (VP Grants), Hanna Center*
