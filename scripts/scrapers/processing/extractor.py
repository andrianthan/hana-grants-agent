"""LLM metadata extraction via OpenRouter (D-03, D-04, D-14).

Model configurable via EXTRACTION_MODEL env var (default openai/gpt-5.4-mini).
Sets uncertain fields to null -- no hallucinated values.
"""
import os
from typing import Optional

from openai import OpenAI
from pydantic import BaseModel, Field


class GrantMetadata(BaseModel):
    """Structured grant metadata extracted by LLM."""

    title: str
    funder: str
    deadline: Optional[str] = Field(None, description="ISO date string or null if uncertain")
    funding_min: Optional[int] = None
    funding_max: Optional[int] = None
    geography: Optional[str] = None
    eligibility: Optional[str] = None
    program_area: Optional[str] = None
    population_served: Optional[str] = None
    relationship_required: Optional[bool] = None
    extraction_confidence: float = Field(ge=0.0, le=1.0)


EXTRACTION_MODEL = os.environ.get("EXTRACTION_MODEL", "openai/gpt-5.4-mini")


def get_openrouter_client() -> OpenAI:
    """Create OpenAI client configured for OpenRouter."""
    return OpenAI(
        base_url=os.environ.get("OPENAI_BASE_URL", "https://openrouter.ai/api/v1"),
        api_key=os.environ["OPENROUTER_API_KEY"],
        default_headers={"HTTP-Referer": "https://hannacenter.org"},
    )


def extract_metadata(raw_text: str, client: OpenAI = None) -> GrantMetadata:
    """Extract structured grant metadata via LLM on OpenRouter.

    Model configurable via EXTRACTION_MODEL env var (default openai/gpt-5.4-mini per D-03).
    Sets fields to null when uncertain -- no hallucinated values per D-04.
    """
    if client is None:
        client = get_openrouter_client()
    response = client.beta.chat.completions.parse(
        model=EXTRACTION_MODEL,
        messages=[
            {"role": "system", "content": (
                "Extract grant metadata from the text. "
                "Set any field to null when you cannot confidently extract it. "
                "Set extraction_confidence between 0.0 and 1.0 reflecting overall certainty."
            )},
            {"role": "user", "content": raw_text},
        ],
        response_format=GrantMetadata,
    )
    return response.choices[0].message.parsed


def log_extraction_failure(conn, scraper_id: str, error: str, raw_s3_key: str = None):
    """Log extraction failure to extraction_failures table."""
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO extraction_failures (scraper_id, raw_s3_key, error) VALUES (%s, %s, %s)",
        (scraper_id, raw_s3_key, str(error)[:2000]),
    )
    conn.commit()
