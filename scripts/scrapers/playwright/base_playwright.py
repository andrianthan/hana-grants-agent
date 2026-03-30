"""Base class for Playwright-based grant scrapers.

Provides stealth mode, random delays, user agent rotation, and safe
error handling. Subclasses implement _scrape_page() only.
"""

import asyncio
import logging
import random
from abc import abstractmethod

from playwright.async_api import async_playwright, Page
from playwright_stealth import Stealth

from scrapers.base_scraper import BaseScraper, RawGrant

logger = logging.getLogger(__name__)

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]


class BasePlaywrightScraper(BaseScraper):
    """Abstract Playwright scraper with stealth, delays, and UA rotation."""

    @staticmethod
    def _random_user_agent() -> str:
        """Return a random Chrome user agent string."""
        return random.choice(_USER_AGENTS)

    @staticmethod
    async def _random_delay(min_s: float = 2.0, max_s: float = 8.0) -> None:
        """Sleep for a random duration between min_s and max_s seconds."""
        await asyncio.sleep(random.uniform(min_s, max_s))

    async def fetch_grants(self) -> list[RawGrant]:
        """Launch browser, scrape page, return validated grants.

        Never raises — returns empty list on any error.
        """
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=["--disable-gpu", "--single-process", "--no-sandbox"],
                )
                context = await browser.new_context(
                    user_agent=self._random_user_agent(),
                    viewport={"width": 1920, "height": 1080},
                )
                page = await context.new_page()
                stealth = Stealth()
                await stealth.apply_stealth_async(page)

                try:
                    grants = await self._scrape_page(page)
                finally:
                    await browser.close()

            return self.validate(grants)
        except Exception:
            logger.exception(f"Scraper {self.scraper_id} failed")
            return []

    @abstractmethod
    async def _scrape_page(self, page: Page) -> list[RawGrant]:
        """Scrape grants from the page. Subclasses implement this."""
        ...
