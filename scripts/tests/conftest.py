"""Shared pytest fixtures for scraper tests."""

import os
import sys

import pytest

# Add scripts/ to sys.path so scrapers/utils imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scrapers.base_scraper import RawGrant


@pytest.fixture
def sample_raw_grant():
    """A sample RawGrant for testing."""
    return RawGrant(
        title="Test Grant",
        funder="Test Funder",
        description="A test grant description",
        deadline="2026-06-01",
        source_url="http://example.com/grant",
        source_id="test-source",
    )


@pytest.fixture
def sample_registry_config():
    """Factory fixture returning registry config for a given scraper_id."""

    def _config(scraper_id: str) -> dict:
        configs = {
            "grants-ca-gov": {
                "scraper_id": "grants-ca-gov",
                "name": "California State Grants",
                "url": "https://www.grants.ca.gov/grants/",
                "type": "api",
                "priority": "high",
                "frequency": "daily",
            },
            "grants-gov": {
                "scraper_id": "grants-gov",
                "name": "Federal Grants",
                "url": "https://www.grants.gov/",
                "type": "api",
                "priority": "high",
                "frequency": "daily",
            },
            "propublica-990": {
                "scraper_id": "propublica-990",
                "name": "ProPublica Nonprofit Explorer",
                "url": "https://projects.propublica.org/nonprofits/api",
                "type": "api",
                "priority": "medium",
                "frequency": "weekly",
            },
            "usaspending-gov": {
                "scraper_id": "usaspending-gov",
                "name": "USASpending.gov",
                "url": "https://api.usaspending.gov/",
                "type": "api",
                "priority": "medium",
                "frequency": "weekly",
            },
            "grantmakers-io": {
                "scraper_id": "grantmakers-io",
                "name": "Grantmakers.io",
                "url": "https://www.grantmakers.io/",
                "type": "api",
                "priority": "medium",
                "frequency": "weekly",
            },
        }
        return configs[scraper_id]

    return _config


@pytest.fixture
def mock_ckan_response():
    """Sample grants.ca.gov CKAN API response."""
    return {
        "success": True,
        "result": {
            "total": 2,
            "records": [
                {
                    "Title": "Youth Mental Health Grant",
                    "AgencyDept": "California DHCS",
                    "Description": "Funding for youth mental health services in California.",
                    "ApplicationDeadline": "06/30/2026",
                    "EstAmounts": "$500,000",
                    "Geography": "California",
                    "GrantURL": "https://www.grants.ca.gov/grants/youth-mh/",
                },
                {
                    "Title": "Community Wellness Program",
                    "AgencyDept": "CA Health & Human Services",
                    "Description": "Support for community wellness programs.",
                    "ApplicationDeadline": "",
                    "EstAmounts": "Up to $1,000,000",
                    "Geography": "Statewide",
                    "GrantURL": "https://www.grants.ca.gov/grants/wellness/",
                },
            ],
        },
    }


@pytest.fixture
def mock_grants_gov_response():
    """Sample Grants.gov search2 API response."""
    return {
        "data": {
            "hitCount": 2,
            "oppHits": [
                {
                    "id": "350001",
                    "oppTitle": "SAMHSA Youth Mental Health",
                    "agencyName": "SAMHSA",
                    "description": "Federal mental health grant for youth services.",
                    "closeDate": "2026-08-15",
                    "awardCeiling": 500000,
                    "awardFloor": 100000,
                },
                {
                    "id": "350002",
                    "oppTitle": "HHS Community Health",
                    "agencyName": "HHS",
                    "description": "Community health services funding.",
                    "closeDate": "2026-09-01",
                    "awardCeiling": 250000,
                    "awardFloor": 50000,
                },
            ],
        }
    }


@pytest.fixture
def mock_propublica_response():
    """Sample ProPublica search response."""
    return {
        "organizations": [
            {
                "ein": "941234567",
                "name": "Hanna Center",
                "city": "Sonoma",
                "state": "CA",
                "total_revenue": 17500000,
                "ntee_code": "P20",
            },
        ]
    }


@pytest.fixture
def mock_usaspending_response():
    """Sample USASpending.gov response."""
    return {
        "results": [
            {
                "Award ID": "GRANT-2026-001",
                "Recipient Name": "Hanna Boys Center",
                "Description": "Youth residential treatment services",
                "Award Amount": 750000,
                "Awarding Agency": "HHS",
                "Start Date": "2026-01-01",
                "End Date": "2026-12-31",
            },
        ]
    }
