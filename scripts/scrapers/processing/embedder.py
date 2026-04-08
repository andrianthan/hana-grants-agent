"""Bedrock Titan V2 embedding + grants table insert (INGEST-04, D-12, D-16)."""
import re
from datetime import datetime
from utils.embeddings import get_embedding


def _safe_date(value):
    """Parse various date formats into YYYY-MM-DD, or return None."""
    if not value:
        return None
    s = str(value).strip()
    # Already ISO format
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    # Try common date formats
    for fmt in (
        "%m/%d/%Y", "%m-%d-%Y",         # 03/15/2026, 03-15-2026
        "%B %d, %Y", "%b %d, %Y",       # March 15, 2026 / Mar 15, 2026
        "%Y-%m-%dT%H:%M:%S",            # ISO datetime
        "%Y-%m-%dT%H:%M:%SZ",           # ISO datetime UTC
        "%m/%d/%y",                      # 03/15/26
    ):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def embed_and_store(conn, raw_grant, metadata, secret_arn: str = None):
    """Embed grant text via Bedrock Titan V2 and insert into grants table.

    Uses ON CONFLICT (content_hash) DO NOTHING for idempotent inserts per D-12.
    """
    embed_text = f"{metadata.title}: {raw_grant.description}"
    embedding = get_embedding(embed_text)

    grant_id = f"{metadata.funder or 'unknown'}-{raw_grant.content_hash[:12]}"

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO grants (
            grant_id, title, funder, deadline, funding_min, funding_max,
            geography, eligibility, description, program_area,
            population_served, relationship_req, embedding,
            source, source_url, content_hash
        ) VALUES (
            %s, %s, %s, %s::date, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s, %s, %s
        )
        ON CONFLICT (content_hash) DO UPDATE SET
            source_url = COALESCE(EXCLUDED.source_url, grants.source_url),
            deadline = COALESCE(EXCLUDED.deadline, grants.deadline),
            updated_at = NOW()
    """, (
        grant_id, metadata.title, metadata.funder,
        _safe_date(metadata.deadline), metadata.funding_min, metadata.funding_max,
        metadata.geography, metadata.eligibility, raw_grant.description,
        metadata.program_area, metadata.population_served,
        metadata.relationship_required, embedding,
        raw_grant.source_id, raw_grant.source_url, raw_grant.content_hash,
    ))
    conn.commit()
    return cur.rowcount > 0
