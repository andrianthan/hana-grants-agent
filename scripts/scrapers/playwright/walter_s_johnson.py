"""Walter S. Johnson Foundation scraper.

Scrapes https://www.wsjf.org/how-we-work/ for youth development
and education equity grant opportunities in Northern California.
"""

import logging

from playwright.async_api import Page

from scrapers.base_scraper import RawGrant
from scrapers.playwright.base_playwright import BasePlaywrightScraper

logger = logging.getLogger(__name__)


class WalterSJohnson(BasePlaywrightScraper):
    """Walter S. Johnson Foundation grants scraper."""

    async def _scrape_page(self, page: Page) -> list[RawGrant]:
        await page.goto(self.url, wait_until="domcontentloaded")
        await self._random_delay()
        await page.wait_for_load_state("networkidle")

        page_html = await page.content()
        grants: list[RawGrant] = []

        # WSJF is invitation-based but posts RFPs — look for grant/RFP sections
        items = await page.query_selector_all(
            "article, .wp-block-group, .entry-content > section, "
            ".grant-opportunity, .rfp-listing"
        )
        for item in items:
            title_el = await item.query_selector("h2, h3, h4")
            if not title_el:
                continue
            title = (await title_el.inner_text()).strip()
            if not title or len(title) < 5:
                continue

            desc_el = await item.query_selector("p, .description")
            desc = (await desc_el.inner_text()).strip() if desc_el else title

            deadline_el = await item.query_selector(".deadline, time, .date")
            deadline = (await deadline_el.inner_text()).strip() if deadline_el else None

            link_el = await item.query_selector("a[href]")
            href = await link_el.get_attribute("href") if link_el else self.url

            grants.append(RawGrant(
                title=title,
                funder="Walter S. Johnson Foundation",
                description=desc,
                deadline=deadline,
                source_url=href if href and href.startswith("http") else self.url,
                source_id=self.scraper_id,
                raw_html=page_html,
            ))

        # Fallback: extract headings from main content
        if not grants:
            main = await page.query_selector("main, [role='main'], .entry-content")
            if main:
                headings = await main.query_selector_all("h2, h3")
                for h in headings:
                    title = (await h.inner_text()).strip()
                    if title and len(title) >= 10:
                        grants.append(RawGrant(
                            title=title,
                            funder="Walter S. Johnson Foundation",
                            description=title,
                            deadline=None,
                            source_url=self.url,
                            source_id=self.scraper_id,
                            raw_html=page_html,
                        ))

        logger.info(f"walter_s_johnson: found {len(grants)} opportunities")
        return grants
