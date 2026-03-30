"""grants.ca.gov CKAN API client.

Fetches California state grants from the data.ca.gov CKAN datastore.
All fields are text type — dates and amounts require safe parsing.
"""

import logging
import re
from typing import Optional

from dateutil import parser as dateutil_parser

from scrapers.base_api_client import BaseApiClient
from scrapers.base_scraper import RawGrant

logger = logging.getLogger(__name__)

CKAN_API_URL = "https://data.ca.gov/api/3/action/datastore_search"
RESOURCE_ID = "111c8c88-21f6-453c-ae2c-b4785a0624f5"


def _parse_date(value: Optional[str]) -> Optional[str]:
    """Parse a text-typed date field to ISO format. Returns None on failure."""
    if not value or not value.strip():
        return None
    try:
        return dateutil_parser.parse(value.strip()).date().isoformat()
    except (ValueError, OverflowError):
        return None


def _parse_amount(value: Optional[str]) -> Optional[int]:
    """Extract first dollar figure from text. Returns None on failure."""
    if not value or not value.strip():
        return None
    match = re.search(r"\$?\s*([\d,]+)", value)
    if match:
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


class GrantsCaGov(BaseApiClient):
    """grants.ca.gov CKAN API client (Pitfall 1: all fields are text)."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._page_delay = 1.0  # Conservative pacing per research

    async def fetch_grants(self) -> list[RawGrant]:
        grants = []
        offset = 0
        limit = 100

        while True:
            data = await self._get_json(
                CKAN_API_URL,
                params={
                    "resource_id": RESOURCE_ID,
                    "limit": limit,
                    "offset": offset,
                },
            )

            records = data.get("result", {}).get("records", [])
            if not records:
                break

            for rec in records:
                grant = RawGrant(
                    title=rec.get("Title", "").strip(),
                    funder=rec.get("AgencyDept", "").strip(),
                    description=rec.get("Description", "").strip(),
                    deadline=_parse_date(rec.get("ApplicationDeadline")),
                    source_url=rec.get("GrantURL", self.url),
                    source_id=self.scraper_id,
                )
                grants.append(grant)

            total = data.get("result", {}).get("total", 0)
            offset += limit
            if offset >= total:
                break

            await self._pace()

        logger.info(f"grants.ca.gov: fetched {len(grants)} grants")
        await self.close()
        return grants
