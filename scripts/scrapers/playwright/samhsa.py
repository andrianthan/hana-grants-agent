"""SAMHSA Grant Announcements scraper.

Scrapes https://www.samhsa.gov/grants/grant-announcements for federal
mental health and substance use grant opportunities.
"""

import logging

from playwright.async_api import Page

from scrapers.base_scraper import RawGrant
from scrapers.playwright.base_playwright import BasePlaywrightScraper

logger = logging.getLogger(__name__)


class Samhsa(BasePlaywrightScraper):
    """SAMHSA grant announcements scraper."""

    async def _scrape_page(self, page: Page) -> list[RawGrant]:
        await page.goto(self.url, wait_until="domcontentloaded")
        await self._random_delay()
        await page.wait_for_load_state("networkidle")

        page_html = await page.content()
        grants: list[RawGrant] = []

        # SAMHSA lists grants in a structured list/table with titles and dates
        items = await page.query_selector_all("article, .views-row, .grant-announcement")
        if items:
            for item in items:
                title_el = await item.query_selector("h2 a, h3 a, .views-field-title a, a")
                if not title_el:
                    continue
                title = (await title_el.inner_text()).strip()
                if not title:
                    continue

                desc_el = await item.query_selector(".views-field-body, .field-content, p")
                desc = (await desc_el.inner_text()).strip() if desc_el else title

                deadline_el = await item.query_selector(
                    ".views-field-field-application-deadline, .date-display-single, time"
                )
                deadline = (await deadline_el.inner_text()).strip() if deadline_el else None

                grants.append(RawGrant(
                    title=title,
                    funder="SAMHSA",
                    description=desc,
                    deadline=deadline,
                    source_url=self.url,
                    source_id=self.scraper_id,
                    raw_html=page_html,
                ))
            return grants

        # Fallback: extract structured links from main content
        main = await page.query_selector("main, #main-content, [role='main']")
        if not main:
            main = page
        links = await main.query_selector_all("a[href*='grant']")
        for link in links:
            title = (await link.inner_text()).strip()
            if not title or len(title) < 10:
                continue
            grants.append(RawGrant(
                title=title,
                funder="SAMHSA",
                description=title,
                deadline=None,
                source_url=self.url,
                source_id=self.scraper_id,
                raw_html=page_html,
            ))

        logger.info(f"samhsa: found {len(grants)} grant announcements")
        return grants
