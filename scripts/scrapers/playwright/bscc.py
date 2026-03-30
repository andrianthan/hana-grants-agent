"""BSCC (Board of State and Community Corrections) scraper.

Scrapes https://www.bscc.ca.gov/s_correctionsplanninggrants/ for
juvenile justice and corrections planning grants.
"""

import logging

from playwright.async_api import Page

from scrapers.base_scraper import RawGrant
from scrapers.playwright.base_playwright import BasePlaywrightScraper

logger = logging.getLogger(__name__)


class Bscc(BasePlaywrightScraper):
    """BSCC corrections planning grants scraper."""

    async def _scrape_page(self, page: Page) -> list[RawGrant]:
        await page.goto(self.url, wait_until="domcontentloaded")
        await self._random_delay()
        await page.wait_for_load_state("networkidle")

        page_html = await page.content()
        grants: list[RawGrant] = []

        # BSCC uses WordPress-style content with headings and paragraphs
        sections = await page.query_selector_all(
            ".entry-content h2, .entry-content h3, article h2, article h3"
        )
        for heading in sections:
            title = (await heading.inner_text()).strip()
            if not title or len(title) < 5:
                continue

            # Get description from following sibling paragraphs
            desc_parts = []
            sibling = await heading.evaluate_handle(
                "el => el.nextElementSibling"
            )
            for _ in range(3):
                if await sibling.json_value() is None:
                    break
                tag = await sibling.evaluate("el => el.tagName")
                if tag in ("H2", "H3"):
                    break
                text = await sibling.evaluate("el => el.textContent || ''")
                text = text.strip()
                if text:
                    desc_parts.append(text)
                sibling = await sibling.evaluate_handle(
                    "el => el.nextElementSibling"
                )

            desc = " ".join(desc_parts) if desc_parts else title
            grants.append(RawGrant(
                title=title,
                funder="BSCC",
                description=desc,
                deadline=None,
                source_url=self.url,
                source_id=self.scraper_id,
                raw_html=page_html,
            ))

        # Fallback: look for grant-related links
        if not grants:
            links = await page.query_selector_all(
                ".entry-content a[href], article a[href]"
            )
            for link in links:
                title = (await link.inner_text()).strip()
                if not title or len(title) < 10:
                    continue
                href = await link.get_attribute("href") or ""
                if "grant" in title.lower() or "rfp" in title.lower() or "bscc" in href:
                    grants.append(RawGrant(
                        title=title,
                        funder="BSCC",
                        description=title,
                        deadline=None,
                        source_url=href if href.startswith("http") else self.url,
                        source_id=self.scraper_id,
                        raw_html=page_html,
                    ))

        logger.info(f"bscc: found {len(grants)} grants")
        return grants
