"""California DHCS Funding Opportunities scraper.

Scrapes https://www.dhcs.ca.gov/provgovpart/Pages/FundingOpportunities.aspx
for state Medi-Cal and behavioral health funding opportunities.
"""

import logging

from playwright.async_api import Page

from scrapers.base_scraper import RawGrant
from scrapers.playwright.base_playwright import BasePlaywrightScraper

logger = logging.getLogger(__name__)


class CaDhcs(BasePlaywrightScraper):
    """California DHCS funding opportunities scraper."""

    async def _scrape_page(self, page: Page) -> list[RawGrant]:
        await page.goto(self.url, wait_until="domcontentloaded")
        await self._random_delay()
        await page.wait_for_load_state("networkidle")

        page_html = await page.content()
        grants: list[RawGrant] = []

        # DHCS lists funding opportunities as links/sections on the page
        # Try table rows first, then fall back to list items and links
        rows = await page.query_selector_all("table.ms-rteTable-default tr")
        if rows:
            for row in rows:
                cells = await row.query_selector_all("td")
                if len(cells) >= 2:
                    title_el = await cells[0].query_selector("a")
                    title = await title_el.inner_text() if title_el else await cells[0].inner_text()
                    title = title.strip()
                    if not title:
                        continue
                    desc = await cells[1].inner_text() if len(cells) > 1 else ""
                    deadline = await cells[2].inner_text() if len(cells) > 2 else None
                    grants.append(RawGrant(
                        title=title,
                        funder="California DHCS",
                        description=desc.strip(),
                        deadline=deadline.strip() if deadline else None,
                        source_url=self.url,
                        source_id=self.scraper_id,
                        raw_html=page_html,
                    ))
            return grants

        # Fallback: extract from links in the content area
        content_area = await page.query_selector("#ctl00_PlaceHolderMain_ctl01__ControlWrapper_RichHtmlField")
        if not content_area:
            content_area = await page.query_selector("[role='main']")
        if not content_area:
            content_area = page

        links = await content_area.query_selector_all("a[href]")
        for link in links:
            title = (await link.inner_text()).strip()
            if not title or len(title) < 10:
                continue
            href = await link.get_attribute("href") or ""
            if "dhcs.ca.gov" not in href and not href.startswith("/"):
                continue
            grants.append(RawGrant(
                title=title,
                funder="California DHCS",
                description=title,
                deadline=None,
                source_url=href if href.startswith("http") else self.url,
                source_id=self.scraper_id,
                raw_html=page_html,
            ))

        logger.info(f"ca_dhcs: found {len(grants)} funding opportunities")
        return grants
