"""Carrie Estelle Doheny Foundation scraper.

Scrapes https://www.dohenyfoundation.org/grants/ for youth welfare,
health/wellness, and social welfare grant opportunities.
Accepts applications from CA 501(c)(3) nonprofits.
Awards: $1,000 - $350,000. Multiple cycles per year.
"""

import logging

from playwright.async_api import Page

from scrapers.base_scraper import RawGrant
from scrapers.playwright.base_playwright import BasePlaywrightScraper

logger = logging.getLogger(__name__)


class DohenyFoundation(BasePlaywrightScraper):
    """Carrie Estelle Doheny Foundation grants scraper."""

    async def _scrape_page(self, page: Page) -> list[RawGrant]:
        await page.goto(self.url, wait_until="domcontentloaded")
        await self._random_delay()
        await page.wait_for_load_state("networkidle")

        page_html = await page.content()
        grants: list[RawGrant] = []

        # Doheny uses WordPress (Astra theme). Grant categories are in
        # .entry-content with headings, lists, and wp-block-button links.
        # Main grants page lists categories: Education, Medical/Health,
        # Social Welfare (youth programs, camperships, restorative justice)
        items = await page.query_selector_all(
            ".entry-content h2, .entry-content h3, "
            "article, .grant-item, .wp-block-group, "
            ".elementor-widget-container"
        )

        current_category = ""
        for item in items:
            tag = await item.evaluate("el => el.tagName")
            if tag in ("H2", "H3"):
                current_category = (await item.inner_text()).strip()
                continue

            # Look for grant opportunity blocks
            title_el = await item.query_selector(
                "h2 a, h3 a, h2, h3, .wp-block-heading, strong"
            )
            if not title_el:
                continue
            title = (await title_el.inner_text()).strip()
            if not title or len(title) < 5:
                continue

            desc_el = await item.query_selector("p, .entry-content p")
            desc = (await desc_el.inner_text()).strip() if desc_el else ""
            if current_category:
                desc = f"Category: {current_category}. {desc}"

            deadline_el = await item.query_selector(
                ".deadline, time, [class*='date']"
            )
            deadline = (await deadline_el.inner_text()).strip() if deadline_el else None

            link_el = await item.query_selector("a[href]")
            href = await link_el.get_attribute("href") if link_el else self.url

            grants.append(RawGrant(
                title=title,
                funder="Carrie Estelle Doheny Foundation",
                description=desc or f"Doheny Foundation grant: {title}",
                deadline=deadline,
                source_url=href if href and href.startswith("http") else self.url,
                source_id=self.scraper_id,
                raw_html=page_html,
            ))

        # Fallback: scan for grant/application links in main content
        if not grants:
            main = await page.query_selector(
                "main, [role='main'], .entry-content"
            )
            if main:
                links = await main.query_selector_all("a[href]")
                for link in links:
                    text = (await link.inner_text()).strip()
                    if text and len(text) >= 8 and any(
                        kw in text.lower()
                        for kw in ("grant", "apply", "rfp", "fund", "application")
                    ):
                        href = await link.get_attribute("href") or self.url
                        grants.append(RawGrant(
                            title=text,
                            funder="Carrie Estelle Doheny Foundation",
                            description=f"Doheny Foundation: {text}",
                            deadline=None,
                            source_url=href if href.startswith("http") else f"https://www.dohenyfoundation.org{href}",
                            source_id=self.scraper_id,
                            raw_html=page_html,
                        ))

        logger.info(f"doheny_foundation: found {len(grants)} opportunities")
        return grants
