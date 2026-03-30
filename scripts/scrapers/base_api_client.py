"""Base API client with httpx for API-based grant scrapers."""

import asyncio
import logging

import httpx

from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class BaseApiClient(BaseScraper):
    """Base class for API-based grant sources with httpx helpers."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None
        self._page_delay: float = 1.0  # seconds between paginated requests

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient()
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _get_json(self, url: str, params: dict | None = None, timeout: int = 30) -> dict:
        """GET request returning parsed JSON."""
        client = await self._get_client()
        resp = await client.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    async def _post_json(self, url: str, json_data: dict | None = None, timeout: int = 30) -> dict:
        """POST request returning parsed JSON."""
        client = await self._get_client()
        resp = await client.post(url, json=json_data, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    async def _pace(self):
        """Rate limiting delay between paginated requests."""
        await asyncio.sleep(self._page_delay)
