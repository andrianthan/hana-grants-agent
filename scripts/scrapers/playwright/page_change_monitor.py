"""Generic page-change monitor for invitation-only foundations.

Does not parse page structure. Simply detects when page content changes
(new RFP posted, priorities updated, fund opened) via SHA-256 hash comparison.
Returns a single RawGrant when a change is detected.
"""

import hashlib
import logging

from playwright.async_api import Page

from scrapers.base_scraper import RawGrant
from scrapers.playwright.base_playwright import BasePlaywrightScraper

logger = logging.getLogger(__name__)


class PageChangeMonitor(BasePlaywrightScraper):
    """Detects page changes for invitation-only foundations."""

    async def _scrape_page(self, page: Page) -> list[RawGrant]:
        await page.goto(self.url, wait_until="domcontentloaded")
        await self._random_delay()
        await page.wait_for_load_state("networkidle")

        # Extract visible text content (ignore HTML/CSS changes)
        body = await page.query_selector("main, [role='main'], .entry-content, body")
        if not body:
            logger.warning(f"page_change_monitor: no body found at {self.url}")
            return []

        text = await body.inner_text()
        text_clean = " ".join(text.split())  # Normalize whitespace
        content_hash = hashlib.sha256(text_clean.encode()).hexdigest()

        # The hash comparison happens downstream in the processing pipeline.
        # We always return the current state — dedup logic handles whether
        # this is "new" vs "already seen".
        funder_name = self.config.get("name", "Unknown Foundation")
        grants = [
            RawGrant(
                title=f"{funder_name} — Grant Page Update Check",
                funder=funder_name,
                description=f"Page content snapshot from {self.url}. "
                f"Content hash: {content_hash[:16]}... "
                f"Review this page for new grant opportunities, "
                f"updated priorities, or open application windows.",
                deadline=None,
                source_url=self.url,
                source_id=self.scraper_id,
                raw_html=text_clean[:5000],  # Store truncated text for diff
            ),
        ]

        logger.info(
            f"page_change_monitor ({self.scraper_id}): "
            f"hash={content_hash[:12]}"
        )
        return grants
