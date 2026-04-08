"""Simpler.Grants.gov REST API client.

Queries the newer Simpler.Grants.gov API (successor to legacy Grants.gov),
filtering for 501(c)(3) nonprofits with grant/cooperative_agreement instruments
and posted/forecasted status. Supplements — does not replace — the existing
grants-gov scraper. SHA-256 dedup layer collapses any duplicates automatically.

API rate limit: 60 req/min. page_delay=1.0s enforces this.
Requires SIMPLER_GRANTS_API_KEY env var (obtain from simpler.grants.gov/developer
via Login.gov sign-in).
"""

import logging
import os
from typing import Optional

from scrapers.base_api_client import BaseApiClient
from scrapers.base_scraper import RawGrant

logger = logging.getLogger(__name__)

SIMPLER_GRANTS_SEARCH_URL = "https://api.simpler.grants.gov/v1/opportunities/search"


class SimplerGrantsGov(BaseApiClient):
    """Simpler.Grants.gov REST API client with nonprofit filter and pagination."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._page_delay = 1.0  # 60 req/min rate limit

    async def _get_headers(self) -> dict:
        """Build request headers including X-API-Key from environment."""
        api_key = os.environ.get("SIMPLER_GRANTS_API_KEY", "")
        return {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        }

    async def fetch_grants(self) -> list[RawGrant]:
        """Fetch all posted/forecasted federal grant opportunities for 501(c)(3) nonprofits."""
        grants: list[RawGrant] = []
        page_offset = 1
        page_size = 25
        total_pages: Optional[int] = None

        headers = await self._get_headers()
        # Use raw client.post — _post_json does not support custom headers
        client = await self._get_client()

        while True:
            payload = {
                "pagination": {
                    "page_offset": page_offset,
                    "page_size": page_size,
                    "sort_order": [
                        {"order_by": "post_date", "sort_direction": "descending"}
                    ],
                },
                "filters": {
                    "funding_instrument": {
                        "one_of": ["grant", "cooperative_agreement"]
                    },
                    "applicant_type": {
                        "one_of": ["nonprofits_non_higher_education_with_501c3"]
                    },
                    "opportunity_status": {
                        "one_of": ["posted", "forecasted"]
                    },
                },
            }

            resp = await client.post(
                SIMPLER_GRANTS_SEARCH_URL,
                json=payload,
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            pagination_info = data.get("pagination_info", {})
            if total_pages is None:
                total_pages = pagination_info.get("total_pages", 1)

            for opp in data.get("data", []):
                opportunity_id = opp.get("opportunity_id", "")
                grant = RawGrant(
                    title=opp.get("opportunity_title", "").strip(),
                    funder=opp.get("agency_name", "").strip(),
                    description=opp.get("summary", "").strip(),
                    deadline=opp.get("close_date"),
                    source_url=f"https://simpler.grants.gov/opportunity/{opportunity_id}",
                    source_id=self.scraper_id,
                )
                grants.append(grant)

            if page_offset >= total_pages:
                break

            page_offset += 1
            await self._pace()

        logger.info(f"Simpler.Grants.gov: fetched {len(grants)} grants")
        await self.close()
        return grants
