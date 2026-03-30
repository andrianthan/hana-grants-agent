"""Sonoma County Health Services scraper.

Scrapes https://sonomacounty.ca.gov/health-and-human-services/health-services
for county health department grants and RFPs.
"""

import logging

from playwright.async_api import Page

from scrapers.base_scraper import RawGrant
from scrapers.playwright.base_playwright import BasePlaywrightScraper

logger = logging.getLogger(__name__)


class SonomaCountyHealth(BasePlaywrightScraper):
    """Sonoma County Health Services scraper."""

    async def _scrape_page(self, page: Page) -> list[RawGrant]:
        await page.goto(self.url, wait_until="domcontentloaded")
        await self._random_delay()
        await page.wait_for_load_state("networkidle")

        page_html = await page.content()
        grants: list[RawGrant] = []

        # Sonoma County gov sites use a consistent CMS structure
        items = await page.query_selector_all(
            "article, .views-row, .content-item, .list-item, "
            ".field-content, .card"
        )
        for item in items:
            title_el = await item.query_selector("h2 a, h3 a, h2, h3, .title")
            if not title_el:
                continue
            title = (await title_el.inner_text()).strip()
            if not title or len(title) < 5:
                continue

            desc_el = await item.query_selector("p, .summary, .description, .body")
            desc = (await desc_el.inner_text()).strip() if desc_el else title

            deadline_el = await item.query_selector(".date, time, .deadline")
            deadline = (await deadline_el.inner_text()).strip() if deadline_el else None

            link_el = await item.query_selector("a[href]")
            href = await link_el.get_attribute("href") if link_el else self.url

            grants.append(RawGrant(
                title=title,
                funder="Sonoma County Health Services",
                description=desc,
                deadline=deadline,
                source_url=href if href and href.startswith("http") else self.url,
                source_id=self.scraper_id,
                raw_html=page_html,
            ))

        # Fallback: extract from main content area
        if not grants:
            main = await page.query_selector("main, [role='main'], #main-content")
            if main:
                links = await main.query_selector_all("a[href]")
                for link in links:
                    title = (await link.inner_text()).strip()
                    href = await link.get_attribute("href") or ""
                    if title and len(title) >= 10 and (
                        "grant" in title.lower() or "rfp" in title.lower()
                        or "funding" in title.lower() or "opportunity" in title.lower()
                    ):
                        grants.append(RawGrant(
                            title=title,
                            funder="Sonoma County Health Services",
                            description=title,
                            deadline=None,
                            source_url=href if href.startswith("http") else self.url,
                            source_id=self.scraper_id,
                            raw_html=page_html,
                        ))

        logger.info(f"sonoma_county_health: found {len(grants)} opportunities")
        return grants
