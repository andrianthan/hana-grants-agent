"""Tests for Playwright-based scrapers: base class behavior and registration."""

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add scripts/ to path for imports
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scrapers.base_scraper import RawGrant
from scrapers.playwright.base_playwright import BasePlaywrightScraper, _USER_AGENTS
from scrapers.playwright.ca_dhcs import CaDhcs
from scrapers.playwright.samhsa import Samhsa
from scrapers.playwright.bscc import Bscc
from scrapers.playwright.sonoma_community_foundation import SonomaCommunityFoundation
from scrapers.playwright.california_wellness import CaliforniaWellness
from scrapers.playwright.blue_shield_ca import BlueShieldCa
from scrapers.playwright.walter_s_johnson import WalterSJohnson
from scrapers.playwright.sonoma_county_health import SonomaCountyHealth
from scrapers.playwright.sonoma_county_probation import SonomaCountyProbation
from scrapers.playwright.sonoma_county_oes import SonomaCountyOes
from scrapers.playwright.sonoma_county_css import SonomaCountyCss
from scrapers.playwright.sonoma_county_bhs import SonomaCountyBhs


def _load_registry():
    registry_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "scraper_registry.json"
    )
    with open(registry_path) as f:
        return json.load(f)["scraper_registry"]


def _make_config(scraper_id: str) -> dict:
    """Build a config dict from registry for a given scraper_id."""
    registry = _load_registry()
    config = next(s for s in registry if s["scraper_id"] == scraper_id)
    return config


# --- Base class tests ---


def test_random_user_agent_returns_chrome_ua():
    """_random_user_agent returns a valid Chrome UA string."""
    ua = BasePlaywrightScraper._random_user_agent()
    assert "Chrome" in ua
    assert "Mozilla/5.0" in ua
    assert ua in _USER_AGENTS


def test_random_user_agent_has_at_least_3_options():
    """At least 3 user agent strings are available for rotation."""
    assert len(_USER_AGENTS) >= 3


@pytest.mark.asyncio
async def test_random_delay_calls_sleep_in_range():
    """_random_delay sleeps for a duration between min_s and max_s."""
    with patch("scrapers.playwright.base_playwright.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await BasePlaywrightScraper._random_delay(2.0, 8.0)
        mock_sleep.assert_called_once()
        delay = mock_sleep.call_args[0][0]
        assert 2.0 <= delay <= 8.0


@pytest.mark.asyncio
async def test_fetch_grants_returns_empty_on_error():
    """fetch_grants returns empty list on exception (never raises)."""
    config = _make_config("california-dhcs")
    scraper = CaDhcs(config)

    # Patch async_playwright to raise an error
    with patch(
        "scrapers.playwright.base_playwright.async_playwright",
        side_effect=RuntimeError("browser launch failed"),
    ):
        result = await scraper.fetch_grants()
        assert result == []


@pytest.mark.asyncio
async def test_fetch_grants_calls_stealth_async():
    """fetch_grants applies stealth_async to the page."""
    config = _make_config("california-dhcs")
    scraper = CaDhcs(config)

    mock_page = AsyncMock()
    mock_page.content.return_value = "<html></html>"
    mock_page.query_selector_all.return_value = []
    mock_page.query_selector.return_value = None

    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = AsyncMock()
    mock_browser.new_context.return_value = mock_context
    mock_browser.close = AsyncMock()

    mock_pw = AsyncMock()
    mock_pw.chromium.launch.return_value = mock_browser

    mock_pw_ctx = AsyncMock()
    mock_pw_ctx.__aenter__ = AsyncMock(return_value=mock_pw)
    mock_pw_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_stealth_instance = MagicMock()
    mock_stealth_instance.apply_stealth_async = AsyncMock()

    with patch(
        "scrapers.playwright.base_playwright.async_playwright",
        return_value=mock_pw_ctx,
    ), patch(
        "scrapers.playwright.base_playwright.Stealth",
        return_value=mock_stealth_instance,
    ):
        await scraper.fetch_grants()
        mock_stealth_instance.apply_stealth_async.assert_called_once_with(mock_page)


# --- Scraper instantiation tests ---

PLAYWRIGHT_SCRAPER_IDS = [
    "california-dhcs",
    "samhsa-grants",
    "bscc-ca-gov",
    "sonoma-county-community-foundation",
    "california-wellness-foundation",
    "blue-shield-ca-foundation",
    "walter-s-johnson-foundation",
    "sonoma-county-health",
    "sonoma-county-probation",
    "sonoma-county-oes",
    "sonoma-county-css",
    "sonoma-county-bhs",
]

SCRAPER_CLASSES_MAP = {
    "california-dhcs": CaDhcs,
    "samhsa-grants": Samhsa,
    "bscc-ca-gov": Bscc,
    "sonoma-county-community-foundation": SonomaCommunityFoundation,
    "california-wellness-foundation": CaliforniaWellness,
    "blue-shield-ca-foundation": BlueShieldCa,
    "walter-s-johnson-foundation": WalterSJohnson,
    "sonoma-county-health": SonomaCountyHealth,
    "sonoma-county-probation": SonomaCountyProbation,
    "sonoma-county-oes": SonomaCountyOes,
    "sonoma-county-css": SonomaCountyCss,
    "sonoma-county-bhs": SonomaCountyBhs,
}


@pytest.mark.parametrize("scraper_id", PLAYWRIGHT_SCRAPER_IDS)
def test_scraper_instantiates_with_registry_config(scraper_id):
    """Each Playwright scraper can be instantiated with its registry config."""
    config = _make_config(scraper_id)
    cls = SCRAPER_CLASSES_MAP[scraper_id]
    scraper = cls(config)
    assert scraper.scraper_id == scraper_id
    assert scraper.url == config["url"]
    assert isinstance(scraper, BasePlaywrightScraper)


def test_all_playwright_scrapers_inherit_from_base():
    """All 12 Playwright scraper classes inherit from BasePlaywrightScraper."""
    for scraper_id, cls in SCRAPER_CLASSES_MAP.items():
        assert issubclass(cls, BasePlaywrightScraper), (
            f"{cls.__name__} does not inherit from BasePlaywrightScraper"
        )


# --- Handler registration tests ---


def test_handler_scraper_classes_has_17_entries():
    """handler.SCRAPER_CLASSES has exactly 17 entries (5 API + 12 Playwright)."""
    from scrapers.handler import _get_scraper_classes

    classes = _get_scraper_classes()
    assert len(classes) == 17, f"Expected 17, got {len(classes)}: {list(classes.keys())}"


def test_handler_covers_all_registry_ids():
    """Every scraper_id in scraper_registry.json has a handler entry."""
    from scrapers.handler import _get_scraper_classes

    classes = _get_scraper_classes()
    registry = _load_registry()
    registry_ids = {s["scraper_id"] for s in registry}
    handler_ids = set(classes.keys())

    missing = registry_ids - handler_ids
    assert not missing, f"Registry IDs missing from handler: {missing}"

    extra = handler_ids - registry_ids
    assert not extra, f"Handler has IDs not in registry: {extra}"
