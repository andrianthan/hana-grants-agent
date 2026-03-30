"""ProPublica Nonprofit Explorer API client.

Searches 990 filing data for CA nonprofits to identify funders.
"""

import logging

from scrapers.base_api_client import BaseApiClient
from scrapers.base_scraper import RawGrant

logger = logging.getLogger(__name__)

PROPUBLICA_BASE = "https://projects.propublica.org/nonprofits/api/v2"


class ProPublica(BaseApiClient):
    """ProPublica Nonprofit Explorer API client (990 filings)."""

    async def fetch_grants(self) -> list[RawGrant]:
        grants = []
        page = 0

        while True:
            data = await self._get_json(
                f"{PROPUBLICA_BASE}/search.json",
                params={
                    "q": "youth services mental health",
                    "state[id]": "CA",
                    "page": page,
                },
            )

            organizations = data.get("organizations", [])
            if not organizations:
                break

            for org in organizations:
                ein = org.get("ein", "")
                name = org.get("name", "").strip()
                city = org.get("city", "")
                state = org.get("state", "")

                grant = RawGrant(
                    title=f"{name} - 990 Filing",
                    funder=name,
                    description=f"Nonprofit in {city}, {state}. "
                    f"Total revenue: ${org.get('total_revenue', 0):,}. "
                    f"NTEE code: {org.get('ntee_code', 'N/A')}.",
                    deadline=None,
                    source_url=f"https://projects.propublica.org/nonprofits/organizations/{ein}",
                    source_id=self.scraper_id,
                )
                grants.append(grant)

            # ProPublica returns 25 per page; stop when less than full page
            if len(organizations) < 25:
                break

            page += 1
            await self._pace()

        logger.info(f"ProPublica: fetched {len(grants)} organizations")
        await self.close()
        return grants
