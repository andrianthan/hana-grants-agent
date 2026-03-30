"""Grants.gov REST API client.

Uses the search2 endpoint with nonprofit eligibility filter.
Pagination via startRecordNum (Pitfall 3).
"""

import logging

from scrapers.base_api_client import BaseApiClient
from scrapers.base_scraper import RawGrant

logger = logging.getLogger(__name__)

GRANTS_GOV_URL = "https://api.grants.gov/v1/api/search2"


class GrantsGov(BaseApiClient):
    """Grants.gov search2 API client with nonprofit filter."""

    async def fetch_grants(self) -> list[RawGrant]:
        grants = []
        rows = 250
        start = 0

        while True:
            data = await self._post_json(
                GRANTS_GOV_URL,
                json_data={
                    "oppStatuses": "posted",
                    "rows": rows,
                    "startRecordNum": start,
                    "eligibilities": "25",  # 25 = nonprofits
                },
            )

            hit_count = data.get("data", {}).get("hitCount", 0)
            opp_hits = data.get("data", {}).get("oppHits", [])

            for opp in opp_hits:
                grant = RawGrant(
                    title=opp.get("oppTitle", "").strip(),
                    funder=opp.get("agencyName", "").strip(),
                    description=opp.get("description", "").strip(),
                    deadline=opp.get("closeDate"),
                    source_url=f"https://www.grants.gov/view-opportunity/{opp.get('id', '')}",
                    source_id=self.scraper_id,
                )
                grants.append(grant)

            start += rows
            if start >= hit_count:
                break

            await self._pace()

        logger.info(f"Grants.gov: fetched {len(grants)} grants")
        await self.close()
        return grants
