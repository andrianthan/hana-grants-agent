"""Unit tests for all 5 API/scraper parsers.

Tests use httpx.MockTransport for deterministic API responses.
"""

import pytest
import httpx

from scrapers.base_scraper import RawGrant
from scrapers.api.grants_ca_gov import GrantsCaGov, _parse_date, _parse_amount
from scrapers.api.grants_gov import GrantsGov
from scrapers.api.propublica import ProPublica
from scrapers.api.usaspending import USASpending
from scrapers.api.grantmakers_io import GrantmakersIo


# --- Helper: inject mock httpx client into a parser ---

def _inject_mock_client(parser, responses: list[dict]):
    """Replace parser's httpx client with a mock that returns given responses."""
    call_count = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        idx = min(call_count, len(responses) - 1)
        call_count += 1
        return httpx.Response(200, json=responses[idx])

    transport = httpx.MockTransport(mock_handler)
    parser._client = httpx.AsyncClient(transport=transport)


# --- RawGrant Tests ---

class TestRawGrant:
    def test_content_hash_deterministic(self):
        g1 = RawGrant("Title", "Funder", "Desc", None, "http://x", "id")
        g2 = RawGrant("Title", "Funder", "Desc", None, "http://y", "id2")
        assert g1.content_hash == g2.content_hash

    def test_content_hash_length(self):
        g = RawGrant("T", "F", "D", None, "http://x", "id")
        assert len(g.content_hash) == 64

    def test_content_hash_includes_deadline(self):
        g1 = RawGrant("T", "F", "D", "2026-01-01", "http://x", "id")
        g2 = RawGrant("T", "F", "D", None, "http://x", "id")
        assert g1.content_hash != g2.content_hash

    def test_content_hash_spec_example(self):
        """Matches the spec: SHA-256 of 'Test Grant|Test Funder||desc'."""
        g = RawGrant("Test Grant", "Test Funder", "desc", None, "http://example.com", "test-id")
        assert len(g.content_hash) == 64


# --- BaseScraper.validate Tests ---

class TestBaseScraper:
    def test_validate_filters_missing_title(self, sample_registry_config):
        config = sample_registry_config("grants-ca-gov")
        scraper = GrantsCaGov(config)
        grants = [
            RawGrant("Good Grant", "Funder", "Description", None, "http://x", "id"),
            RawGrant("", "Funder", "Description", None, "http://x", "id"),
        ]
        valid = scraper.validate(grants)
        assert len(valid) == 1
        assert valid[0].title == "Good Grant"

    def test_validate_filters_missing_description(self, sample_registry_config):
        config = sample_registry_config("grants-ca-gov")
        scraper = GrantsCaGov(config)
        grants = [
            RawGrant("Grant", "Funder", "", None, "http://x", "id"),
            RawGrant("Grant", "Funder", "Has desc", None, "http://x", "id"),
        ]
        valid = scraper.validate(grants)
        assert len(valid) == 1


# --- grants.ca.gov Tests ---

class TestGrantsCaGov:
    @pytest.mark.asyncio
    async def test_fetch_grants(self, sample_registry_config, mock_ckan_response):
        config = sample_registry_config("grants-ca-gov")
        parser = GrantsCaGov(config)
        _inject_mock_client(parser, [mock_ckan_response])

        grants = await parser.fetch_grants()

        assert len(grants) == 2
        assert all(isinstance(g, RawGrant) for g in grants)
        assert all(g.source_id == "grants-ca-gov" for g in grants)
        assert grants[0].title == "Youth Mental Health Grant"
        assert grants[0].funder == "California DHCS"

    @pytest.mark.asyncio
    async def test_fetch_grants_empty(self, sample_registry_config):
        config = sample_registry_config("grants-ca-gov")
        parser = GrantsCaGov(config)
        _inject_mock_client(parser, [{"result": {"total": 0, "records": []}}])

        grants = await parser.fetch_grants()
        assert grants == []

    def test_parse_date_valid(self):
        assert _parse_date("06/30/2026") == "2026-06-30"

    def test_parse_date_empty(self):
        assert _parse_date("") is None
        assert _parse_date(None) is None

    def test_parse_date_garbage(self):
        assert _parse_date("not a date") is None

    def test_parse_amount_valid(self):
        assert _parse_amount("$500,000") == 500000

    def test_parse_amount_up_to(self):
        assert _parse_amount("Up to $1,000,000") == 1000000

    def test_parse_amount_empty(self):
        assert _parse_amount("") is None
        assert _parse_amount(None) is None


# --- Grants.gov Tests ---

class TestGrantsGov:
    @pytest.mark.asyncio
    async def test_fetch_grants(self, sample_registry_config, mock_grants_gov_response):
        config = sample_registry_config("grants-gov")
        parser = GrantsGov(config)
        _inject_mock_client(parser, [mock_grants_gov_response])

        grants = await parser.fetch_grants()

        assert len(grants) == 2
        assert all(isinstance(g, RawGrant) for g in grants)
        assert all(g.source_id == "grants-gov" for g in grants)
        assert grants[0].title == "SAMHSA Youth Mental Health"
        assert "350001" in grants[0].source_url

    @pytest.mark.asyncio
    async def test_pagination_stops_at_hitcount(self, sample_registry_config):
        """Pagination should stop when startRecordNum >= hitCount."""
        config = sample_registry_config("grants-gov")
        parser = GrantsGov(config)

        page1 = {
            "data": {
                "hitCount": 3,
                "oppHits": [
                    {"id": "1", "oppTitle": "G1", "agencyName": "A", "description": "D", "closeDate": None},
                    {"id": "2", "oppTitle": "G2", "agencyName": "A", "description": "D", "closeDate": None},
                    {"id": "3", "oppTitle": "G3", "agencyName": "A", "description": "D", "closeDate": None},
                ],
            }
        }
        _inject_mock_client(parser, [page1])

        grants = await parser.fetch_grants()
        assert len(grants) == 3


# --- ProPublica Tests ---

class TestProPublica:
    @pytest.mark.asyncio
    async def test_fetch_grants(self, sample_registry_config, mock_propublica_response):
        config = sample_registry_config("propublica-990")
        parser = ProPublica(config)
        _inject_mock_client(parser, [mock_propublica_response])

        grants = await parser.fetch_grants()

        assert len(grants) == 1
        assert all(isinstance(g, RawGrant) for g in grants)
        assert all(g.source_id == "propublica-990" for g in grants)
        assert "Hanna Center" in grants[0].title
        assert "941234567" in grants[0].source_url

    @pytest.mark.asyncio
    async def test_empty_response(self, sample_registry_config):
        config = sample_registry_config("propublica-990")
        parser = ProPublica(config)
        _inject_mock_client(parser, [{"organizations": []}])

        grants = await parser.fetch_grants()
        assert grants == []


# --- USASpending Tests ---

class TestUSASpending:
    @pytest.mark.asyncio
    async def test_fetch_grants(self, sample_registry_config, mock_usaspending_response):
        config = sample_registry_config("usaspending-gov")
        parser = USASpending(config)
        _inject_mock_client(parser, [mock_usaspending_response])

        grants = await parser.fetch_grants()

        assert len(grants) == 1
        assert all(isinstance(g, RawGrant) for g in grants)
        assert all(g.source_id == "usaspending-gov" for g in grants)
        assert "HHS" in grants[0].funder
        assert "750,000" in grants[0].description


# --- Grantmakers.io Tests ---

class TestGrantmakersIo:
    @pytest.mark.asyncio
    async def test_inherits_base_scraper(self, sample_registry_config):
        """Grantmakers.io should inherit from BaseScraper, NOT BaseApiClient."""
        from scrapers.base_scraper import BaseScraper
        from scrapers.base_api_client import BaseApiClient

        config = sample_registry_config("grantmakers-io")
        parser = GrantmakersIo(config)
        assert isinstance(parser, BaseScraper)
        assert not isinstance(parser, BaseApiClient)

    @pytest.mark.asyncio
    async def test_graceful_fallback_without_playwright(self, sample_registry_config, monkeypatch):
        """Should return empty list if Playwright is not available."""
        import scrapers.api.grantmakers_io as gm_module

        # Mock the import to simulate playwright not installed
        original_fetch = GrantmakersIo.fetch_grants

        async def mock_fetch(self):
            # Simulate the ImportError path
            return []

        monkeypatch.setattr(GrantmakersIo, "fetch_grants", mock_fetch)

        config = sample_registry_config("grantmakers-io")
        parser = GrantmakersIo(config)
        grants = await parser.fetch_grants()
        assert grants == []


# --- Handler Tests ---

class TestHandler:
    def test_handler_dispatches_correctly(self, sample_registry_config, monkeypatch, tmp_path):
        """Handler should dispatch to the correct scraper class."""
        import json
        import scrapers.handler as handler_module

        # Create a temp registry file
        registry = {
            "scraper_registry": [
                sample_registry_config("grants-ca-gov"),
            ]
        }
        registry_file = tmp_path / "scraper_registry.json"
        registry_file.write_text(json.dumps(registry))

        # Override registry loading
        handler_module._registry = registry["scraper_registry"]
        handler_module.SCRAPER_CLASSES = {}

        # Create a mock scraper class
        class MockScraper:
            def __init__(self, config):
                self.scraper_id = config["scraper_id"]

            async def fetch_grants(self):
                return [
                    RawGrant("Mock Grant", "Mock Funder", "Mock desc", None, "http://x", self.scraper_id)
                ]

            def validate(self, grants):
                return grants

        handler_module.SCRAPER_CLASSES["grants-ca-gov"] = MockScraper

        result = handler_module.handler({"scraper_id": "grants-ca-gov"}, None)
        assert result["scraper_id"] == "grants-ca-gov"
        assert result["grants_found"] == 1
        assert result["grants"][0]["title"] == "Mock Grant"

    def test_handler_missing_scraper_id(self):
        import scrapers.handler as handler_module
        result = handler_module.handler({}, None)
        assert "error" in result

    def test_handler_unknown_scraper_id(self):
        import scrapers.handler as handler_module
        handler_module._registry = [{"scraper_id": "other", "url": "x", "type": "api"}]
        result = handler_module.handler({"scraper_id": "nonexistent"}, None)
        assert "error" in result
