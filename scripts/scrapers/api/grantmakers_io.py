"""Grantmakers.io Playwright scraper.

Grantmakers.io has no documented REST API (Pitfall 7). Implemented as a
Playwright scraper with stealth mode per D-02.
"""

import asyncio
import logging
import random

from scrapers.base_scraper import BaseScraper, RawGrant

logger = logging.getLogger(__name__)

GRANTMAKERS_URL = "https://www.grantmakers.io/"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0",
]


class GrantmakersIo(BaseScraper):
    """Grantmakers.io Playwright scraper (no true API — Pitfall 7)."""

    async def fetch_grants(self) -> list[RawGrant]:
        grants = []

        try:
            from playwright.async_api import async_playwright
            from playwright_stealth import Stealth
        except ImportError:
            logger.warning("Playwright not installed — skipping Grantmakers.io")
            return grants

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--disable-gpu", "--single-process", "--no-sandbox"],
                )
                context = await browser.new_context(
                    user_agent=random.choice(USER_AGENTS),
                    viewport={"width": 1920, "height": 1080},
                )
                page = await context.new_page()
                stealth = Stealth()
                await stealth.apply_stealth_async(page)

                # Navigate to Grantmakers.io search
                await page.goto(GRANTMAKERS_URL, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(random.uniform(2.0, 5.0))

                # Search for CA foundations funding youth/mental health
                search_input = page.locator('input[type="search"], input[placeholder*="Search"]').first
                if await search_input.is_visible():
                    await search_input.fill("California youth mental health")
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(random.uniform(3.0, 8.0))

                # Extract foundation cards/results
                results = await page.query_selector_all(
                    '[class*="result"], [class*="card"], [class*="grant"], tr[data-id]'
                )

                for result in results:
                    try:
                        title_el = await result.query_selector(
                            'h2, h3, h4, [class*="title"], [class*="name"], td:first-child'
                        )
                        title = await title_el.inner_text() if title_el else ""

                        desc_el = await result.query_selector(
                            'p, [class*="description"], [class*="summary"], td:nth-child(2)'
                        )
                        desc = await desc_el.inner_text() if desc_el else ""

                        link_el = await result.query_selector("a[href]")
                        link = await link_el.get_attribute("href") if link_el else GRANTMAKERS_URL

                        if title.strip():
                            grants.append(
                                RawGrant(
                                    title=title.strip(),
                                    funder=title.strip(),
                                    description=desc.strip() or f"Foundation from Grantmakers.io: {title.strip()}",
                                    deadline=None,
                                    source_url=link if link.startswith("http") else f"{GRANTMAKERS_URL}{link}",
                                    source_id=self.scraper_id,
                                )
                            )

                        # Random delay between extractions (D-02)
                        await asyncio.sleep(random.uniform(0.5, 1.5))

                    except Exception as e:
                        logger.debug(f"Failed to parse result: {e}")
                        continue

                await browser.close()

        except Exception as e:
            logger.warning(f"Grantmakers.io scraper failed (graceful fallback): {e}")
            return []

        logger.info(f"Grantmakers.io: fetched {len(grants)} foundations")
        return grants
