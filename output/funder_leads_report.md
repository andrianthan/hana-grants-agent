# Funder Discovery Report for Hanna Center Development Team

**Generated:** April 7, 2026
**Method:** 990-PF Schedule I analysis via Grantmakers.io
**Total leads discovered:** 356 foundations
**Data source:** output/funder_leads_20260407_191657.csv

---

## How Leads Were Found

1. **Identified 25 peer nonprofits** — CA organizations similar to Hanna Center (youth services, behavioral health, residential care, $2M-$50M revenue) via ProPublica Nonprofit Explorer API
2. **Searched 990-PF grant data** — For each peer, queried Grantmakers.io's database of 3.3M+ grants from private foundation tax filings (Schedule I) to find which foundations gave them money
3. **Cross-referenced** against Hanna's existing 17 scraper sources to isolate NEW leads
4. **Ranked** by number of peer orgs funded and total grant amounts

## Peer Organizations Used

| Name | City | Revenue | NTEE |
|------|------|---------|------|
| Five Acres (Boys & Girls Aid Society) | Pasadena | $53.3M | — |
| Fred Finch Youth Center | Oakland | $49.5M | F33Z |
| McKinley Children's Center | San Dimas | $49.2M | F33Z |
| Vista Del Mar Child & Family Services | Los Angeles | $48.3M | P400 |
| Boys Republic | Chino Hills | $37.8M | P300 |
| Edgewood Center for Children & Families | San Francisco | $33.4M | F33Z |
| Bill Wilson Center | Santa Clara | $32.6M | P460 |
| Social Advocates for Youth (San Diego) | San Diego | $28.5M | P300 |
| Orangewood Foundation | Santa Ana | $21.6M | I72J |
| Buckelew Programs | Novato | $21.2M | F30Z |
| David & Margaret Home | La Verne | $17.4M | P73Z |
| Community Action Partnership of Sonoma | Santa Rosa | $17.3M | S200 |
| North Bay Children's Center | Novato | $15.4M | P33Z |
| Helpline Youth Counseling | Whittier | $13.7M | I21 |
| The Unity Care Group | San Jose | $9.6M | P730 |

---

## Foundations Already Funding Hanna

These foundations appeared in 990-PF data as having made grants to "Hanna Boys Center":

| Foundation | Location | Amount | Purpose |
|-----------|----------|--------|---------|
| **KHR McNeely Family Foundation** | Sonoma, CA | $190,000 | Community Mental Health Hub at Hanna Center |
| **Callie McGrath Charitable Trust** | Dallas, TX | $20,000 | Unrestricted General |
| **Heck Foundation** | Guerneville, CA | $1,000 | Teen Care |
| **Cigna Foundation** | Philadelphia, PA | $500 | General Operating Purpose |

These confirm existing funder relationships. KHR McNeely is a major local funder ($12.7M total giving across 73 grants).

---

## Top 15 NEW Foundation Leads

Ranked by number of Hanna peer orgs they fund:

| # | Foundation | Location | Largest Grant | Total Seen | Peers | Application Status |
|---|-----------|----------|---------------|------------|:-----:|-------------------|
| 1 | **Sobrato Family Foundation** | Mountain View, CA | $169,500 | $602,720 | 5 | Email inquiry (grants@sobrato.org) |
| 2 | **Samueli Foundation** | Corona Del Mar, CA | $1,000,000 | $1,611,667 | 3 | Open apps (March annually) — OC focus |
| 3 | **Price Philanthropies** | La Jolla, CA | $88,000 | $138,000 | 3 | Not accepting unsolicited — SD focus |
| 4 | **Gordon & Betty Moore Foundation** | Palo Alto, CA | $50,000 | $100,000 | 3 | Invitation only — science/environment focus |
| 5 | **Heffernan Foundation** | Walnut Creek, CA | $10,000 | $30,000 | 3 | Invite-only annual (Sept 15 deadline) |
| 6 | **Sun Family Foundation** | Fountain Valley, CA | $500,000 | $600,000 | 2 | No unsolicited proposals — OC only |
| 7 | **Atlas Kardia Foundation** | Wilmington, DE | $125,000 | $263,508 | 2 | No public process |
| 8 | **Gilead Sciences Foundation** | Foster City, CA | $50,000 | $100,000 | 2 | Corporate foundation — relationship needed |
| 9 | **Wells Fargo Foundation** | Minneapolis, MN | $50,000 | $65,000 | 2 | Corporate giving — local branch relationship |
| 10 | **Weingart Foundation** | Los Angeles, CA | $175,000 | $175,470 | 1 | Invitation only — SoCal 5-county |
| 11 | **Carrie Estelle Doheny Foundation** | Los Angeles, CA | $250,500 | $250,500 | 1 | **ACCEPTS APPLICATIONS** — CA 501(c)(3) |
| 12 | **Winifred Johnson Clive Foundation** | San Francisco, CA | $25,000 | $40,000 | 2 | Invitation only — children welfare |
| 13 | **Atkinson Foundation** | San Francisco, CA | $15,000 | $25,000 | 2 | **Open quarterly apps** — San Mateo County only |
| 14 | **William H. Donner Foundation** | Tarrytown, NY | $25,000 | $45,000 | 2 | Invitation only |
| 15 | **Lindskog Foundation** | San Francisco, CA | $100,000 | $200,000 | 1 | No public process — group therapy focus |

---

## Recommended Actions

### Immediate (scrapers added to pipeline)
- **Carrie Estelle Doheny Foundation** — Full Playwright scraper added. Accepts applications from CA 501(c)(3) nonprofits. Youth welfare, counseling, social welfare. Awards $1K-$350K. Multiple cycles per year.
- **Sobrato Philanthropies** — Page-change monitor added. When their page updates, Hanna's team should email grants@sobrato.org.
- **Weingart Foundation** — Page-change monitor added. Invitation-only but public grants database shows giving patterns.
- **Heffernan Foundation** — Page-change monitor added. Bay Area, annual cycle, education/shelter focus.

### Relationship Building (no scraper, requires outreach)
- **Gilead Sciences Foundation** (Foster City, CA) — Gave $50K to Fred Finch for Racial Equity Initiative. Hanna's mental health programs could align. Contact via corporate giving portal.
- **Wells Fargo Foundation** — Gave $50K for Financial Empowerment. Approach via local Sonoma branch relationship.
- **KHR McNeely Family Foundation** (Sonoma) — Already gave $190K for Mental Health Hub. Relationship deepening opportunity — family is active in Sonoma community.
- **Winifred Johnson Clive Foundation** (SF) — Funds children welfare. Board-invited only, but Hanna's profile aligns well.

### Monitor But Lower Priority
- **Samueli Foundation** — Large grants but Orange County focused
- **Price Philanthropies** — San Diego focused, not accepting
- **Sun Family Foundation** — OC only, no unsolicited
- **Gordon & Betty Moore** — Science/environment focus, not youth services

---

## Full Data

Complete CSV with all 356 leads: `output/funder_leads_20260407_191657.csv`
Peer organizations list: `output/peer_orgs_20260407_191657.csv`
Discovery script: `scripts/discover_funders.py`
