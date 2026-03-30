"""Base scraper classes and RawGrant data model for the Hanna Grants Agent."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import hashlib


@dataclass
class RawGrant:
    """Raw grant data before LLM extraction."""

    title: str
    funder: str
    description: str
    deadline: Optional[str]  # ISO date string or None
    source_url: str
    source_id: str  # scraper_id from registry
    raw_html: Optional[str] = None  # For S3 archival

    @property
    def content_hash(self) -> str:
        """SHA-256 of title + funder + deadline + description for dedup (D-08)."""
        content = f"{self.title}|{self.funder}|{self.deadline or ''}|{self.description}"
        return hashlib.sha256(content.encode()).hexdigest()


class BaseScraper(ABC):
    """Abstract base class for all grant scrapers."""

    def __init__(self, config: dict):
        self.scraper_id = config["scraper_id"]
        self.url = config["url"]
        self.source_type = config["type"]

    @abstractmethod
    async def fetch_grants(self) -> list[RawGrant]:
        """Fetch all current grants from this source."""
        ...

    def validate(self, grants: list[RawGrant]) -> list[RawGrant]:
        """Filter out grants with missing required fields."""
        return [g for g in grants if g.title and g.description]
