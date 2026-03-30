"""USASpending.gov API client.

Searches federal award data for CA grants to identify funding patterns.
"""

import logging

from scrapers.base_api_client import BaseApiClient
from scrapers.base_scraper import RawGrant

logger = logging.getLogger(__name__)

USASPENDING_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"


class USASpending(BaseApiClient):
    """USASpending.gov awards search API client."""

    async def fetch_grants(self) -> list[RawGrant]:
        grants = []
        page = 1

        while True:
            data = await self._post_json(
                USASPENDING_URL,
                json_data={
                    "filters": {
                        "award_type_codes": ["02", "03", "04", "05"],  # Grant types
                        "place_of_performance_locations": [
                            {"country": "USA", "state": "CA"}
                        ],
                    },
                    "fields": [
                        "Award ID",
                        "Recipient Name",
                        "Description",
                        "Award Amount",
                        "Awarding Agency",
                        "Start Date",
                        "End Date",
                    ],
                    "page": page,
                    "limit": 100,
                    "sort": "Award Amount",
                    "order": "desc",
                },
            )

            results = data.get("results", [])
            if not results:
                break

            for award in results:
                amount = award.get("Award Amount", 0) or 0
                grant = RawGrant(
                    title=f"{award.get('Awarding Agency', 'Federal')} - {award.get('Award ID', '')}",
                    funder=award.get("Awarding Agency", "").strip(),
                    description=f"Recipient: {award.get('Recipient Name', '')}. "
                    f"{award.get('Description', '')}. "
                    f"Amount: ${amount:,.0f}.",
                    deadline=award.get("End Date"),
                    source_url=f"https://www.usaspending.gov/award/{award.get('Award ID', '')}",
                    source_id=self.scraper_id,
                )
                grants.append(grant)

            # Stop if fewer results than limit
            if len(results) < 100:
                break

            page += 1
            await self._pace()

        logger.info(f"USASpending: fetched {len(grants)} awards")
        await self.close()
        return grants
