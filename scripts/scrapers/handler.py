"""Lambda entry point for scraper dispatch.

Reads scraper_registry.json at runtime and dispatches to the correct
parser class based on the scraper_id in the event payload.
"""

import asyncio
import json
import logging
import os
import traceback

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Lazy imports to avoid circular dependencies at module level
_registry = None


def _load_registry() -> list[dict]:
    global _registry
    if _registry is None:
        registry_path = os.path.join(os.path.dirname(__file__), "..", "scraper_registry.json")
        if not os.path.exists(registry_path):
            # Fallback for Docker image layout where registry is at FUNCTION_DIR root
            registry_path = os.path.join(os.path.dirname(__file__), "..", "..", "scraper_registry.json")
        with open(registry_path) as f:
            data = json.load(f)
        _registry = data["scraper_registry"]
    return _registry


def _get_scraper_classes() -> dict:
    """Build mapping of scraper_id -> class. Imported lazily."""
    # API scrapers (6)
    from scrapers.api.grants_ca_gov import GrantsCaGov
    from scrapers.api.grants_gov import GrantsGov
    from scrapers.api.propublica import ProPublica
    from scrapers.api.usaspending import USASpending
    from scrapers.api.grantmakers_io import GrantmakersIo
    from scrapers.api.simpler_grants_gov import SimplerGrantsGov

    # Playwright scrapers (12)
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

    return {
        # API scrapers
        "grants-ca-gov": GrantsCaGov,
        "grants-gov": GrantsGov,
        "propublica-990": ProPublica,
        "usaspending-gov": USASpending,
        "grantmakers-io": GrantmakersIo,
        "simpler-grants-gov": SimplerGrantsGov,
        # Playwright scrapers
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


SCRAPER_CLASSES = None


def handler(event, context):
    """Lambda handler: dispatch to the correct scraper based on scraper_id.

    Event payload: {"scraper_id": "grants-ca-gov"}
    Returns: {"scraper_id": str, "grants_found": int, "grants": [dict]}
    """
    global SCRAPER_CLASSES
    if SCRAPER_CLASSES is None:
        SCRAPER_CLASSES = _get_scraper_classes()

    scraper_id = event.get("scraper_id")
    if not scraper_id:
        return {"error": "Missing scraper_id in event payload"}

    # Look up config from registry
    registry = _load_registry()
    config = next((s for s in registry if s["scraper_id"] == scraper_id), None)
    if config is None:
        return {"error": f"Unknown scraper_id: {scraper_id}"}

    # Look up scraper class
    scraper_cls = SCRAPER_CLASSES.get(scraper_id)
    if scraper_cls is None:
        return {"error": f"No scraper class registered for: {scraper_id}"}

    try:
        scraper = scraper_cls(config)
        grants = asyncio.run(scraper.fetch_grants())
        grants = scraper.validate(grants)

        return {
            "scraper_id": scraper_id,
            "grants_found": len(grants),
            "grants": [
                {
                    "title": g.title,
                    "funder": g.funder,
                    "description": g.description,
                    "deadline": g.deadline,
                    "source_url": g.source_url,
                    "source_id": g.source_id,
                    "content_hash": g.content_hash,
                }
                for g in grants
            ],
        }
    except Exception as e:
        logger.error(f"Scraper {scraper_id} failed: {e}\n{traceback.format_exc()}")
        return {
            "scraper_id": scraper_id,
            "error": str(e),
            "grants_found": 0,
            "grants": [],
        }
