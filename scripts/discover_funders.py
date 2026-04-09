#!/usr/bin/env python3
"""Funder Discovery Script

Finds foundations funding Hanna Center's peer nonprofits by:
1. Querying ProPublica for CA youth/behavioral health nonprofits (peers)
2. Searching Grantmakers.io 990-PF grant data for foundations that gave to those peers
3. Cross-referencing against scraper_registry.json to find NEW leads

Run: python3 scripts/discover_funders.py
"""

import asyncio
import csv
import httpx
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROPUBLICA_BASE = "https://projects.propublica.org/nonprofits/api/v2"
HANNA_EIN = "941156570"

# Search queries that find relevant peer orgs (2-word queries work best with ProPublica)
PEER_SEARCHES = [
    "Seneca Family",
    "Fred Finch",
    "Sunny Hills",
    "Edgewood Children",
    "Hillsides Pasadena",
    "Victor Community",
    "Social Advocates Youth",
    "Child Parent Institute",
    "Hanna Center",          # ourselves — to see who funds us in 990-PF data
    "EMQ FamiliesFirst",
    "Sierra Forever",
    "Stars Community",
    "youth residential",
    "adolescent treatment",
    "youth counseling",
    "youth transitional",
    "children group home",
    "youth development Sonoma",
    "Buckelew Programs",
    "Community Action Sonoma",
    "North Bay Children",
    "Sunny Hills Children",
    "Boys Republic",
    "David Hoy Youth",
    "Uplift Family Services",
    "Bill Wilson Center",
    "Unity Care Group",
    "Youth Homes",
    "Aspiranet",
    "Children Home Society",
    "Five Acres",
    "Hollygrove",
    "McKinley Children",
    "New Alternatives",
    "Orangewood Foundation",
    "Tobinworld",
    "Vista Del Mar",
]

MIN_REVENUE = 2_000_000
MAX_REVENUE = 80_000_000


@dataclass
class PeerOrg:
    ein: str
    name: str
    city: str
    state: str
    ntee_code: str
    revenue: int


@dataclass
class FunderLead:
    foundation_name: str
    foundation_ein: str
    grant_to: str
    grant_amount: float | None = None
    grant_year: int | None = None
    grant_purpose: str = ""
    foundation_city: str = ""
    foundation_state: str = ""
    already_in_registry: bool = False


async def find_peer_orgs(client: httpx.AsyncClient) -> dict[str, PeerOrg]:
    """Find peer nonprofits via ProPublica search."""
    peers = {}

    for query in PEER_SEARCHES:
        try:
            resp = await client.get(
                f"{PROPUBLICA_BASE}/search.json",
                params={"q": query, "state[id]": "CA"},
            )
            if resp.status_code != 200:
                # Try without state filter
                resp = await client.get(
                    f"{PROPUBLICA_BASE}/search.json",
                    params={"q": query},
                )
                if resp.status_code != 200:
                    continue

            data = resp.json()
            orgs = data.get("organizations", [])

            for org in orgs:
                ein = str(org.get("ein", ""))
                state = org.get("state", "")
                if not ein or ein == HANNA_EIN or ein in peers:
                    continue
                if state != "CA":
                    continue

                peers[ein] = PeerOrg(
                    ein=ein,
                    name=org.get("name", "").strip(),
                    city=org.get("city", ""),
                    state=state,
                    ntee_code=org.get("ntee_code", ""),
                    revenue=0,
                )
        except Exception as e:
            logger.debug(f"Search failed for '{query}': {e}")

        await asyncio.sleep(0.3)

    # Fetch revenue for each peer
    print(f"  Found {len(peers)} CA orgs, fetching revenue details...")
    for i, (ein, peer) in enumerate(list(peers.items())):
        try:
            resp = await client.get(f"{PROPUBLICA_BASE}/organizations/{ein}.json")
            if resp.status_code == 200:
                org = resp.json().get("organization", {})
                peer.revenue = org.get("income_amount", 0) or 0
                peer.name = org.get("name", peer.name)
        except Exception:
            pass
        if (i + 1) % 25 == 0:
            print(f"    {i+1}/{len(peers)} details fetched...")
        await asyncio.sleep(0.15)

    # Filter by revenue
    before = len(peers)
    peers = {ein: p for ein, p in peers.items() if MIN_REVENUE <= p.revenue <= MAX_REVENUE}
    print(f"  Revenue filter: {before} → {len(peers)} peers (${MIN_REVENUE:,}-${MAX_REVENUE:,})")

    return peers


async def search_grantmakers(client: httpx.AsyncClient, org_name: str) -> list[dict]:
    """Search Grantmakers.io Algolia for 990-PF grants made TO an org."""
    try:
        # Grantmakers.io public search-only Algolia keys (from their open source repo)
        algolia_app_id = os.environ.get("ALGOLIA_APP_ID", "QA1231C5W9")
        algolia_key = os.environ.get("ALGOLIA_SEARCH_KEY", "96a419d65f67ff3b4c54939f8e90c220")
        resp = await client.post(
            f"https://{algolia_app_id}-dsn.algolia.net/1/indexes/grantmakers_io/query",
            headers={
                "X-Algolia-Application-Id": algolia_app_id,
                "X-Algolia-API-Key": algolia_key,
                "Content-Type": "application/json",
                "Referer": "https://www.grantmakers.io/",
            },
            json={"params": f"query={org_name}&hitsPerPage=50"},
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", [])

        # Filter to hits where the org name actually appears in grantee_name
        # (Algolia does fuzzy matching, so we need to verify relevance)
        name_words = set(org_name.lower().split())
        relevant = []
        for hit in hits:
            grantee = (hit.get("grantee_name") or "").lower()
            # At least 2 words from our search must appear in the grantee name
            # or the grantee name contains our search as a substring
            matches = sum(1 for w in name_words if w in grantee and len(w) > 2)
            if matches >= 2 or org_name.lower()[:10] in grantee:
                relevant.append(hit)

        return relevant
    except Exception as e:
        logger.debug(f"Algolia failed for '{org_name}': {e}")
        return []


def load_registry() -> set[str]:
    """Load existing scraper registry identifiers."""
    path = Path(__file__).parent.parent / "scraper_registry.json"
    try:
        with open(path) as f:
            data = json.load(f)
        names = set()
        for s in data.get("scraper_registry", []):
            names.add(s.get("name", "").lower())
            names.add(s.get("scraper_id", "").lower())
            url = s.get("url", "")
            if url:
                from urllib.parse import urlparse
                names.add(urlparse(url).netloc.replace("www.", "").lower())
        return names
    except Exception:
        return set()


def in_registry(name: str, registry: set[str]) -> bool:
    name_lower = name.lower()
    for entry in registry:
        if len(entry) > 3 and (entry in name_lower or name_lower in entry):
            return True
    return False


async def main():
    print("\n" + "=" * 70)
    print("  FUNDER DISCOVERY — Finding foundations that fund Hanna's peers")
    print("=" * 70 + "\n")

    registry = load_registry()
    print(f"Registry: {len(registry)} existing identifiers\n")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # === STEP 1: Find peers ===
        print("STEP 1: Finding peer nonprofits via ProPublica...")
        peers = await find_peer_orgs(client)

        peers_sorted = sorted(peers.values(), key=lambda p: p.revenue, reverse=True)
        print(f"\n  Peers found ({len(peers_sorted)}):")
        for i, p in enumerate(peers_sorted, 1):
            print(f"    {i:2}. {p.name} ({p.city}) — ${p.revenue:,} — {p.ntee_code}")

        # === STEP 2: Search Grantmakers.io for funders ===
        print(f"\nSTEP 2: Searching Grantmakers.io for who funds these {len(peers_sorted)} peers...\n")

        all_leads: dict[str, FunderLead] = {}
        fdn_to_peers: dict[str, set[str]] = {}
        fdn_to_grants: dict[str, list[tuple[str, float, int]]] = {}  # fdn -> [(peer, amt, year)]

        # Also search for Hanna Center directly
        search_orgs = [(p.name, p.name) for p in peers_sorted]
        search_orgs.insert(0, ("Hanna Center", "Hanna Center (self)"))

        for i, (search_name, display_name) in enumerate(search_orgs, 1):
            short_name = " ".join(search_name.split()[:3])
            logger.info(f"  [{i}/{len(search_orgs)}] {short_name}")

            hits = await search_grantmakers(client, short_name)
            if hits:
                logger.info(f"    → {len(hits)} relevant grants found")

            for hit in hits:
                fdn_name = (hit.get("organization_name") or "").strip()
                fdn_ein = str(hit.get("ein") or "")
                if not fdn_name:
                    continue

                amount = hit.get("grant_amount")
                year = hit.get("tax_year")
                purpose = hit.get("grant_purpose", "")
                grantee = hit.get("grantee_name", "")
                fdn_city = hit.get("city", "")
                fdn_state = hit.get("state", "")

                # Track foundation → peer relationships
                if fdn_name not in fdn_to_peers:
                    fdn_to_peers[fdn_name] = set()
                fdn_to_peers[fdn_name].add(display_name)

                if fdn_name not in fdn_to_grants:
                    fdn_to_grants[fdn_name] = []
                fdn_to_grants[fdn_name].append((grantee, amount or 0, year or 0))

                # Keep lead with highest grant amount
                key = fdn_ein or fdn_name.lower()
                if key not in all_leads or (amount and (all_leads[key].grant_amount or 0) < amount):
                    all_leads[key] = FunderLead(
                        foundation_name=fdn_name,
                        foundation_ein=fdn_ein,
                        grant_to=grantee,
                        grant_amount=amount,
                        grant_year=year,
                        grant_purpose=purpose,
                        foundation_city=fdn_city,
                        foundation_state=fdn_state,
                        already_in_registry=in_registry(fdn_name, registry),
                    )

            await asyncio.sleep(0.15)

        # === STEP 3: Results ===
        print(f"\n  Total unique foundations found: {len(all_leads)}\n")
        print("STEP 3: Cross-referencing...\n")

        new_leads = {k: v for k, v in all_leads.items() if not v.already_in_registry}
        existing = {k: v for k, v in all_leads.items() if v.already_in_registry}

        if existing:
            print(f"  Already in registry ({len(existing)}):")
            for v in existing.values():
                print(f"    ✓ {v.foundation_name}")

        print(f"\n  NEW leads: {len(new_leads)}\n")

        # Rank by: peer count, then total grant amount across all grants
        def rank_score(item):
            key, lead = item
            peer_count = len(fdn_to_peers.get(lead.foundation_name, set()))
            total_amount = sum(amt for _, amt, _ in fdn_to_grants.get(lead.foundation_name, []))
            return (peer_count, total_amount)

        ranked = sorted(new_leads.items(), key=rank_score, reverse=True)

        print("=" * 70)
        print("  NEW FOUNDATION LEADS")
        print("=" * 70 + "\n")

        for i, (key, lead) in enumerate(ranked[:60], 1):
            peer_count = len(fdn_to_peers.get(lead.foundation_name, set()))
            grants = fdn_to_grants.get(lead.foundation_name, [])
            total = sum(amt for _, amt, _ in grants)
            amount_str = f"${lead.grant_amount:,.0f}" if lead.grant_amount else "N/A"
            total_str = f"${total:,.0f}" if total else "N/A"
            peers_list = list(fdn_to_peers.get(lead.foundation_name, set()))
            location = f"{lead.foundation_city}, {lead.foundation_state}" if lead.foundation_city else ""

            print(f"  {i:2}. {lead.foundation_name} {f'({location})' if location else ''}")
            print(f"      Largest: {amount_str} | Total seen: {total_str} | Peers: {peer_count}")
            if lead.grant_purpose:
                print(f"      Purpose: {lead.grant_purpose[:80]}")
            print(f"      Example: → {lead.grant_to}")
            if peer_count > 1:
                print(f"      Also funds: {', '.join(peers_list[:4])}")
            print(f"      Profile: https://www.grantmakers.io/profiles/v1/{lead.foundation_ein}/")
            print()

        # === Save CSVs ===
        output_dir = Path(__file__).parent.parent / "output"
        output_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        csv_path = output_dir / f"funder_leads_{ts}.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "rank", "foundation_name", "foundation_ein", "location",
                "largest_grant", "total_grants_seen", "grant_year",
                "grant_purpose", "example_grantee", "peers_funded_count",
                "peers_funded", "profile_url", "in_registry"
            ])
            for i, (key, lead) in enumerate(ranked, 1):
                peer_count = len(fdn_to_peers.get(lead.foundation_name, set()))
                total = sum(amt for _, amt, _ in fdn_to_grants.get(lead.foundation_name, []))
                peers_str = "; ".join(fdn_to_peers.get(lead.foundation_name, set()))
                loc = f"{lead.foundation_city}, {lead.foundation_state}" if lead.foundation_city else ""
                writer.writerow([
                    i, lead.foundation_name, lead.foundation_ein, loc,
                    lead.grant_amount or "", total or "", lead.grant_year or "",
                    lead.grant_purpose, lead.grant_to, peer_count, peers_str,
                    f"https://www.grantmakers.io/profiles/v1/{lead.foundation_ein}/",
                    lead.already_in_registry,
                ])

        peers_csv = output_dir / f"peer_orgs_{ts}.csv"
        with open(peers_csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["ein", "name", "city", "state", "ntee_code", "revenue"])
            for p in peers_sorted:
                writer.writerow([p.ein, p.name, p.city, p.state, p.ntee_code, p.revenue])

        print(f"  Saved: {csv_path}")
        print(f"  Saved: {peers_csv}")
        print(f"  Total new leads: {len(ranked)}\n")


if __name__ == "__main__":
    asyncio.run(main())
