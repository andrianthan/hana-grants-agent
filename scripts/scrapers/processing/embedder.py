"""Bedrock Titan V2 embedding + grants table insert (INGEST-04, D-12, D-16)."""
import re
from utils.embeddings import get_embedding


def _safe_date(value):
    """Return value only if it looks like a valid ISO date (YYYY-MM-DD), else None."""
    if not value:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value).strip()):
        return str(value).strip()
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
            source, content_hash
        ) VALUES (
            %s, %s, %s, %s::date, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s, %s
        )
        ON CONFLICT (content_hash) DO NOTHING
    """, (
        grant_id, metadata.title, metadata.funder,
        _safe_date(metadata.deadline), metadata.funding_min, metadata.funding_max,
        metadata.geography, metadata.eligibility, raw_grant.description,
        metadata.program_area, metadata.population_served,
        metadata.relationship_required, embedding,
        raw_grant.source_id, raw_grant.content_hash,
    ))
    conn.commit()
    return cur.rowcount > 0
