"""Unit tests for SimplerGrantsGov API scraper.

Uses httpx.MockTransport for deterministic, offline responses against
the recorded fixture in fixtures/simpler_grants_gov_response.json.
"""

import json
import os

import httpx
import pytest

from scrapers.base_scraper import RawGrant
from scrapers.api.simpler_grants_gov import SimplerGrantsGov

# --- Fixture path ---

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "simpler_grants_gov_response.json")

with open(FIXTURE_PATH) as _f:
    _FIXTURE_DATA = json.load(_f)

# --- Helper: inject mock httpx client ---


def _inject_mock_client(scraper: SimplerGrantsGov, responses: list[dict]) -> None:
    """Replace scraper's httpx client with a mock returning given responses in order."""
    call_count = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        idx = min(call_count, len(responses) - 1)
        call_count += 1
        return httpx.Response(200, json=responses[idx])

    transport = httpx.MockTransport(mock_handler)
    scraper._client = httpx.AsyncClient(transport=transport)


# --- Config helper ---

def _make_config() -> dict:
    return {
        "scraper_id": "simpler-grants-gov",
        "url": "https://simpler.grants.gov/",
        "type": "api",
    }


# --- Tests ---


class TestSimplerGrantsGov:
    @pytest.mark.asyncio
    async def test_fetch_grants_parses_response(self):
        """fetch_grants() correctly maps API fields to RawGrant objects."""
        scraper = SimplerGrantsGov(_make_config())
        _inject_mock_client(scraper, [_FIXTURE_DATA])

        grants = await scraper.fetch_grants()

        assert len(grants) == 2
        assert all(isinstance(g, RawGrant) for g in grants)

        first = grants[0]
        assert first.title == "Community Mental Health Services Block Grant"
        assert first.funder == "Department of Health and Human Services"
        assert "community-based mental health services" in first.description
        assert first.deadline == "2026-06-15"
        assert first.source_url == "https://simpler.grants.gov/opportunity/a1b2c3d4-e5f6-7890-abcd-ef1234567890"

        second = grants[1]
        assert second.title == "Youth Resilience and Recovery Program"
        assert second.funder == "Substance Abuse and Mental Health Services Administration"
        assert second.deadline == "2026-07-30"
        assert second.source_url == "https://simpler.grants.gov/opportunity/f9e8d7c6-b5a4-3210-fedc-ba9876543210"

    @pytest.mark.asyncio
    async def test_fetch_grants_pagination_stops(self):
        """When total_pages=1, fetch_grants() makes exactly one API call."""
        call_count = 0

        def counting_handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json=_FIXTURE_DATA)

        scraper = SimplerGrantsGov(_make_config())
        scraper._client = httpx.AsyncClient(transport=httpx.MockTransport(counting_handler))

        grants = await scraper.fetch_grants()

        assert call_count == 1
        assert len(grants) == 2

    @pytest.mark.asyncio
    async def test_raw_grant_content_hash(self):
        """Each returned RawGrant has a non-empty SHA-256 content_hash (64 hex chars)."""
        scraper = SimplerGrantsGov(_make_config())
        _inject_mock_client(scraper, [_FIXTURE_DATA])

        grants = await scraper.fetch_grants()

        assert len(grants) > 0
        for g in grants:
            assert isinstance(g.content_hash, str)
            assert len(g.content_hash) == 64
            # Ensure it's a valid hex string
            int(g.content_hash, 16)

    @pytest.mark.asyncio
    async def test_source_id_matches_scraper_id(self):
        """Each returned RawGrant.source_id equals 'simpler-grants-gov'."""
        scraper = SimplerGrantsGov(_make_config())
        _inject_mock_client(scraper, [_FIXTURE_DATA])

        grants = await scraper.fetch_grants()

        assert len(grants) > 0
        assert all(g.source_id == "simpler-grants-gov" for g in grants)
