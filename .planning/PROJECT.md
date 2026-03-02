# HANA Center Grants AI Agent

## What This Is

An end-to-end AI-powered grants pipeline for HANA Center — a Korean-American nonprofit in the Chicago area providing social services, domestic violence support, immigration services, and mental health programs. The system automatically discovers eligible grant opportunities from the web, evaluates their fit against HANA Center's mission and programs, generates draft proposals, and tracks deadlines — all surfaced to grant staff via automated reports and notifications.

## Core Value

Grant staff can discover, evaluate, and begin applying to relevant grants in a fraction of the time, with AI handling research and first drafts while humans make final decisions.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] System automatically finds new grant opportunities via web research and public grant APIs
- [ ] System evaluates each grant's fit against HANA Center's mission, programs, and eligibility criteria
- [ ] System generates draft grant proposals based on HANA's org profile and past submissions
- [ ] System tracks application deadlines and sends reminders to grant staff
- [ ] System runs as an automated pipeline (CLI/script) with output to email or Slack
- [ ] Grant staff can review matched grants with fit scores and reasoning
- [ ] System ingests HANA Center's org profile, past grants, and program guidelines as context

### Out of Scope

- Full web application / browser UI — CLI/script pipeline is sufficient for v1
- Automatic grant submission — humans review and submit all applications
- Real-time chat interface — not needed for v1
- Mobile app — out of scope entirely

## Context

- **Organization**: HANA Center, Chicago area, Korean-American community nonprofit
  - Programs: DV support, immigration legal services, mental health, social services
  - Key grant sources: OVW Culturally Specific Services, ORR Ethnic Community Self-Help, IDHS contracts, Allstate Foundation, Chicago Community Trust, SAMHSA
- **Grant lifecycle**: Prospecting → Fit evaluation → Proposal drafting → Deadline tracking
- **Key grant terminology**: RFP (Request for Proposal), RFA (Request for Application); funders care about mission alignment, eligibility, staff capacity, reporting burden, and relationship history
- **Materials pending**: HANA Center will provide examples of past grants received and program guidelines — these will be used to build the org profile and RAG context for proposal drafting
- **Research already done**: Full tech stack and grant domain research completed in prior session (LangGraph, Claude API, Grants.gov API, pgvector, Playwright/Firecrawl)
- **Timeline**: 1-2 months to deliver; this week focused on research prep for 1:1 meeting with HANA Center

## Constraints

- **Timeline**: 1-2 months to delivery — scope must stay focused
- **Budget**: Nonprofit context — target <$50/month total infrastructure cost
- **Materials**: Org-specific context (past grants, guidelines) not yet available — system must be designed to plug them in later
- **Interface**: CLI/script for v1 — no frontend needed
- **Deployment**: TBD — design for portability (local or cloud)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| CLI/script interface (not web app) | Grant staff want automated pipeline, not a dashboard to manage | — Pending |
| LangGraph for orchestration | Stateful multi-step pipeline with HITL checkpoints; supports cycles and conditional routing | — Pending |
| Claude Sonnet 4.6 as primary LLM | Best-in-class for long-form writing, 200K context window, strong instruction following | — Pending |
| Grants.gov API + web scraping | Free federal grant data + Playwright for foundation sites | — Pending |
| pgvector / ChromaDB for vector store | Low-cost, integrates with existing stack; Supabase free tier | — Pending |
| 3-agent architecture | Prospector → Evaluator → Drafter mirrors the real-world grants workflow | — Pending |

---
*Last updated: 2026-03-02 after initialization*
