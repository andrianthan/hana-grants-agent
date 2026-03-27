# Feature Landscape: Hanna Center Grants AI Agent

**Domain:** AI-powered grant discovery and evaluation for a mid-size nonprofit
**Researched:** 2026-03-26
**Confidence:** HIGH (features derived from PROJECT.md decisions + competitive landscape analysis)

## Market Context

The grant management tool market splits into three tiers:

1. **Discovery-only** (GrantStation, OpenGrants): curated databases with keyword/filter search. $29-99/month per user. No evaluation intelligence.
2. **Full-lifecycle platforms** (Instrumentl, Fluxx): discovery + tracking + collaboration + reporting. $3,000-10,000+/year. Designed for teams of 5+.
3. **AI writing tools** (Grantable, GrantBoost, FundRobin): proposal drafting with LLMs. $20-100/month. No discovery or evaluation.

Hanna currently pays ~$3,000/year for Instrumentl (tier 2). The Hanna agent replaces Instrumentl's discovery + evaluation functions with a system tuned specifically to Hanna's programs, at <$50/month infrastructure cost. It does NOT need to replicate Instrumentl's full lifecycle management -- Hanna's 2-person grants team does not need Fluxx-style collaboration features.

**Key insight from market research:** No existing tool combines (a) custom source scraping, (b) org-specific AI scoring with multi-dimensional flags, and (c) conversational grant interaction. Tools either discover OR evaluate OR draft. The Hanna agent integrates all three stages (with drafting deferred to v2).

---

## Table Stakes

Features the grants team expects. Missing any of these = the tool cannot replace manual process + Instrumentl.

| # | Feature | Why Expected | Complexity | Phase | Notes |
|---|---------|-------------|------------|-------|-------|
| T1 | **Automated grant discovery from CA state + federal sources** | Replaces daily Google searching. This is the core value proposition -- without it, Hanna keeps Instrumentl. | High | 2 | 5 APIs + 12 scrapers. Step Functions fan-out architecture already designed. |
| T2 | **Content-hash deduplication** | Same grants appear across sources. Without dedup, digest is 40% duplicates and staff lose trust. | Low | 2 | SHA-256 hash of title + funder + deadline. Already in schema. |
| T3 | **Hard metadata filtering** | Geography (CA/Sonoma), deadline (not expired), eligibility (nonprofits), program area. Without this, irrelevant grants flood the digest. | Medium | 3 | Prospector node applies filters before scoring. Depends on clean metadata extraction (T1). |
| T4 | **AI fit scoring (1-10) with written reasoning** | Staff need to understand WHY a grant scored high/low, not just a number. Instrumentl shows match % but no reasoning. This is the minimum intelligence layer. | High | 3 | GPT-5.4 Evaluator with Pydantic-validated output. 7 scoring dimensions. |
| T5 | **7 evaluation flags** | Hanna's real evaluation framework (from discovery call): strategic priority alignment, program fit, staff time cost, reporting burden, relationship required, timeline fit, current vs new programs. Without these flags, scoring is a black box. | High | 3 | Each flag derived from Hanna's actual evaluation criteria. Needs calibration call with Marisa (pending decision). |
| T6 | **Weekly email digest** | Passive delivery -- grants arrive in inbox Monday 8am. If staff must proactively open a tool, adoption drops. Average nonprofit grant writer tenure is 16 months; the tool must survive staff turnover via simplicity. | Medium | 4 | SES HTML email. Sorted by deadline urgency. Approve/skip one-click links. |
| T7 | **HITL approve/skip workflow** | Confirmed as a hard workflow requirement in discovery call. Staff explicitly want a checkpoint before any action is taken on a grant. | Medium | 4 | Email one-click links + Custom GPT both write to same RDS approval_status column. |
| T8 | **Org profile ingestion** | System must "know" Hanna: mission, programs, geography, population, NTEE codes, strategic priorities. Without this, scoring is generic and useless. | Medium | 1 | ORG-PROFILE.md + SEARCH-PROFILES.md. Already designed. 6 department profiles. |
| T9 | **Deadline visibility + urgency sorting** | Grants with deadlines < 30 days need to be flagged. Missing a deadline because it was buried in the list is a critical failure. | Low | 4 | Digest sorted by (deadline - today) ascending. Flag icon for < 30 days. |
| T10 | **Skip reason capture** | Staff select why they skip (too_small, wrong_geography, already_applied, wrong_program, relationship_required, other). After 3-6 months, patterns inform prompt tuning. | Low | 4 | Enum on skip endpoint. Feeds future calibration. |

---

## Differentiators

Features that set the Hanna agent apart from Instrumentl and manual process. Not expected by default, but deliver outsized value.

| # | Feature | Value Proposition | Complexity | Phase | Notes |
|---|---------|-------------------|------------|-------|-------|
| D1 | **Multi-profile HyDE search (6 department profiles)** | Instrumentl uses keyword search. HyDE generates a hypothetical "ideal grant" for each Hanna department and uses that as the search vector. Mental Health Hub grants and CTE education grants occupy different embedding space -- a single query misses one or the other. This is the single biggest technical differentiator. | High | 1 + 3 | HyDE generation in Phase 1. Profile-specific search in Phase 3. Already fully designed. |
| D2 | **Profile-specific evaluation weights** | Each department has different scoring priorities. Mental Health Hub boosts HPSA/MUP geography matches; Hanna Academy boosts CTE program fit. Instrumentl applies the same generic match logic to all searches. | Medium | 3 | Weight overrides defined in SEARCH-PROFILES.md per profile. |
| D3 | **Known funder relationship boost** | Cross-references FUNDER-DIRECTORY.md against incoming grants. If Walter S. Johnson Foundation posts a new grant, it gets flagged and boosted because Hanna has a prior relationship. No competing tool does this with Hanna-specific funder data. | Medium | 3 | Depends on funder directory being populated (Phase 1 org materials). |
| D4 | **Custom GPT conversational layer** | Staff ask natural language questions about grants: "Tell me more about the BHS grant", "Compare this week's mental health grants", "Which should I prioritize?" Zero learning curve -- Hanna already uses ChatGPT Enterprise daily. No competing tool offers this. | Medium | 4 | Custom GPT + Actions connecting to API Gateway. |
| D5 | **Google Sheets pipeline tracker** | Cumulative grant history across weeks. Filterable by profile, funder, score. After 6 months, this is a full historical pipeline -- no manual data entry. Hanna uses Google Workspace for Nonprofits (free). | Medium | 4 | Sheets API Lambda appends rows after each weekly run. Read-only in v1. |
| D6 | **CSV export endpoint** | `GET /grants/export.csv` -- staff can open in Excel, Numbers, or Sheets. Accessible via bookmarked URL or Custom GPT. Useful for board reports, grant committee meetings. | Low | 4 | Simple endpoint with query params for profile, week, status. |
| D7 | **ROI estimate per grant** | Award range vs. estimated staff hours to apply + report. A $10K grant requiring 80 hours is worse than a $50K grant requiring 40 hours. No discovery tool surfaces this. | Medium | 3 | Requires Hanna's loaded labor rate and typical application hours (pending calibration call). |
| D8 | **Source-level scraper health monitoring** | If a scraper breaks silently (site redesign), CloudWatch alarm fires after 3 consecutive zero-grant days. Instrumentl's human curation team handles this; the Hanna agent needs automated detection. | Low | 2 | scraper_health table + CloudWatch metric + SNS alert. |
| D9 | **Versioned prompts as files** | Prompts stored as .txt/.md in repo. Marisa can tune evaluation criteria without developer involvement. Reduces long-term maintenance burden. | Low | 3 | Standard file-based prompt management. |
| D10 | **Operational runbook** | RUNBOOK.md for non-technical staff: pipeline health checks, restart procedures, adding sources, updating org profile, cost monitoring. Designed for a 2-person grants team with no AWS knowledge. | Low | 4 | Documentation deliverable. Critical for handoff sustainability. |

---

## Anti-Features

Features to deliberately NOT build. Each has a clear reason and an alternative approach.

| # | Anti-Feature | Why Avoid | What to Do Instead |
|---|-------------|-----------|-------------------|
| A1 | **Browser-based web UI** | 2-person grants team does not need a dashboard. Custom GPT + email + Google Sheets covers all interaction surfaces. Building a web UI would consume 3-4 weeks of the 10-week timeline for zero additional value. | Custom GPT as conversational interface; SES email for passive delivery; Google Sheets for tabular view. |
| A2 | **Automatic grant submission** | Too risky. Funders reject poorly formatted submissions. Hanna's grants team treats each application as a relationship-building exercise. Automation here destroys trust. | HITL checkpoint is a hard requirement. System recommends; humans decide and submit. |
| A3 | **Proposal drafting (v1)** | High complexity, requires extensive RAG corpus (past proposals, program data, budget templates). Drafter node is designed but deferred to v2. V1 validates discovery + evaluation first. | Defer to Phase 5/v2. Staff continue using their existing Grant Writing GPT for drafting. |
| A4 | **Google Calendar integration (v1)** | Nice-to-have but not blocking. Deadline visibility is handled by the digest's urgency sort + 30-day flag. Calendar integration adds a Google API dependency and OAuth flow. | Defer to v2. Deadlines visible in email digest and Google Sheets. |
| A5 | **Slack notifications (v1)** | Hanna's grants team uses email as primary communication. Adding Slack means maintaining two notification channels. | Defer to v2. SES email is sufficient for 2-3 staff members. |
| A6 | **Multi-organization support** | V1 is Hanna-specific by design. Multi-org would require tenant isolation, org-switching UI, and generic scoring -- all of which dilute the Hanna-specific tuning that makes the system valuable. | Single-org. Hanna's org profile is hard-coded into prompts and search profiles. |
| A7 | **Grant budget builder** | Requires Hanna's chart of accounts, indirect cost rates, fringe benefit calculations. This is accounting software, not grant discovery. | Staff build budgets in Excel/Sheets as they do today. |
| A8 | **Funder CRM / relationship tracking (v1)** | Full relationship management (contact logs, meeting notes, cultivation stages) is a separate product category (Fluxx, Salesforce NPSP). The Hanna agent surfaces relationship flags, not manages relationships. | FUNDER-DIRECTORY.md provides known-funder flags. Full CRM deferred to Phase 5 (Funder Match Pipeline). |
| A9 | **Real-time grant alerts (push notifications)** | Daily scraping + weekly digest is sufficient cadence. Real-time alerts for every new grant would create notification fatigue for a 2-person team processing 30-80 grants/week. | Weekly batch digest. Staff can do on-demand search via Custom GPT between digests. |
| A10 | **Compliance / post-award reporting tracker** | Post-award management (reporting deadlines, compliance checklists, expenditure tracking) is a different product. Hanna's grants team manages this in spreadsheets today and it works. | Out of scope entirely. Not even v2. |
| A11 | **Mobile app** | 2-person grants team works from desktop. Email digest is already mobile-readable. Custom GPT has a mobile app. No additional mobile surface needed. | Email + ChatGPT mobile app cover mobile access. |

---

## Feature Dependencies

```
Phase 1 (Infrastructure):
  T8 (org profile) ──────────────────────────┐
  D1 (HyDE generation) ─────────────────────┤
                                              │
Phase 2 (Ingestion):                          │
  T1 (grant discovery) ──→ T2 (dedup) ──────┤
  D8 (scraper health) ──────────────────────┤
                                              │
Phase 3 (AI Pipeline):                        ▼
  T3 (metadata filtering) ←── T1 (needs clean metadata)
  T4 (fit scoring) ←── T8 (needs org profile)
  T5 (7 flags) ←── T4 (scoring infrastructure)
  D1 (HyDE search) ←── T8 (needs profile definitions)
  D2 (profile weights) ←── D1 (needs profile system)
  D3 (funder boost) ←── T8 (needs FUNDER-DIRECTORY.md)
  D7 (ROI estimate) ←── T5 (part of flag system)
  D9 (versioned prompts) ←── T4 (prompt infrastructure)

Phase 4 (Interface):
  T6 (email digest) ←── T4 (needs scored grants)
  T7 (HITL approve/skip) ←── T6 (email links call approve endpoint)
  T9 (deadline urgency) ←── T6 (sort order in digest)
  T10 (skip reasons) ←── T7 (part of skip flow)
  D4 (Custom GPT) ←── T7 (shares same API endpoints)
  D5 (Google Sheets) ←── T4 (needs scored grant data)
  D6 (CSV export) ←── T4 (needs scored grant data)
  D10 (runbook) ←── all (documents everything)
```

**Critical path:** T8 (org profile) -> T1 (discovery) -> T4 (scoring) -> T6 (digest) -> T7 (HITL)

Everything else hangs off this spine. The most complex dependency cluster is Phase 3 where scoring, flags, HyDE search, and profile weights all interlock.

---

## MVP Recommendation

The v1 scope is already well-defined in PROJECT.md. This analysis confirms the split is correct:

### v1 (10 weeks, Phases 1-4) -- Prioritize:

1. **T1 + T2**: Automated discovery + dedup (the core pipeline that replaces Instrumentl)
2. **T4 + T5**: AI scoring with 7 flags (the intelligence layer that beats keyword search)
3. **D1**: Multi-profile HyDE search (the biggest technical differentiator)
4. **T6 + T7**: Email digest + HITL (the delivery mechanism staff actually use)
5. **D4**: Custom GPT conversational layer (zero-learning-curve interface)
6. **D5 + D6**: Google Sheets tracker + CSV export (reporting surfaces)

### Defer to v2:

| Feature | Reason for Deferral | When |
|---------|-------------------|------|
| A3: Proposal drafting | Requires extensive RAG corpus not yet available; validate discovery + eval first | Phase 5+ (post-v1) |
| A4: Google Calendar | Deadline visibility handled by digest urgency sort | Phase 5+ |
| A5: Slack notifications | Email sufficient for 2-3 staff | Phase 5+ |
| A8: Full funder CRM | Phase 5 Funder Match Pipeline addresses this | Phase 5 |
| D5 write-back: Sheets approval | Apps Script webhook for sheet -> RDS. Nice-to-have, not blocking. | v1.5 |

### Features at risk in 10-week timeline:

- **D3 (known funder boost)**: Depends on FUNDER-DIRECTORY.md being populated with relationship data. If Hanna doesn't provide funder history before Phase 3, this degrades to a simple name-match without relationship context. Mitigation: can ship with name-match only and add relationship data later.
- **D7 (ROI estimate)**: Requires Hanna's loaded labor rate and typical application hours. Pending calibration call with Marisa. If call doesn't happen before Phase 3 prompt design, ROI flag ships with generic estimates and is calibrated post-launch.
- **T5 flag calibration**: Three flags need Hanna-specific inputs (ROI, reporting burden thresholds, timeline fit mechanism). All gated on a 30-minute call with Marisa before Week 7.

---

## Competitive Positioning vs. Instrumentl

| Capability | Instrumentl ($3K/yr) | Hanna Agent (<$50/mo) | Winner |
|-----------|---------------------|----------------------|--------|
| Grant database size | 20,000+ curated nationwide | 17 CA/Sonoma-focused sources | Instrumentl (breadth) |
| CA state grant coverage | Included but not prioritized | Primary focus (grants.ca.gov API) | Hanna Agent (depth) |
| Match quality | Keyword match % | HyDE + 7-flag evaluation + written reasoning | Hanna Agent |
| Funder intelligence | 990 visualizations, peer prospecting | Known-funder boost from Hanna's own history | Hanna Agent (specificity) |
| Scoring transparency | Match % (no reasoning) | 1-10 score + reasoning + 7 flags | Hanna Agent |
| Multi-department search | Single org profile | 6 department-specific HyDE profiles | Hanna Agent |
| Interface | Web dashboard | Email + Custom GPT + Google Sheets | Tie (different approaches) |
| Proposal drafting | AI Apply module (2025) | Deferred to v2 | Instrumentl (v1 only) |
| Deadline tracking | Calendar + reminders | Digest urgency sort + 30-day flag | Instrumentl |
| Cost | $3,000/year | ~$16-19/month (~$200/year) | Hanna Agent (15x cheaper) |

**Takeaway:** The Hanna agent wins on match quality, scoring transparency, and cost. Instrumentl wins on breadth and full lifecycle features. For a 2-person grants team focused on CA/Sonoma, the Hanna agent provides better signal at a fraction of the cost.

---

## Sources

- [Instrumentl features and pricing](https://www.instrumentl.com/solutions/nonprofits) -- MEDIUM confidence (marketing page)
- [OpenGrants grant management comparison](https://opengrants.io/best-grant-management-software-for-nonprofits/) -- MEDIUM confidence
- [Idealist Consulting: Must-have grant management features](https://idealistconsulting.com/blog/top-10-must-have-features-successful-grant-management-solution) -- MEDIUM confidence
- [FundRobin AI grant matching](https://fundrobin.com/grant-finder/) -- LOW confidence (marketing claims)
- [Benevity 2026 AI grant features](https://www.bnnbloomberg.ca/press-releases/2026/03/16/benevity-unveils-new-ai-and-management-features-designed-to-streamline-global-grantmaking/) -- HIGH confidence (press release with specific features)
- [NetSuite: Grant management best practices](https://www.netsuite.com/portal/resource/articles/crm/grant-management-best-practices.shtml) -- MEDIUM confidence
- PROJECT.md and ARCHITECTURE.md -- HIGH confidence (primary project documentation)
