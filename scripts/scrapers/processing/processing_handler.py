"""Processing Lambda handler -- orchestrates dedup -> extract -> embed -> health -> log.

Invoked by Step Functions after each scraper Lambda returns its batch of RawGrant dicts.
"""
import json
import os
import sys

# When bundled from scripts/, the Lambda root is scripts/
# Add it to path so scrapers.* and utils.* imports work
_lambda_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, _lambda_root)

from scrapers.processing.dedup import check_duplicates_batch
from scrapers.processing.extractor import extract_metadata, log_extraction_failure
from scrapers.processing.embedder import embed_and_store
from scrapers.processing.health_monitor import update_health
from scrapers.processing.pipeline_logger import start_run, complete_run, fail_run
from scrapers.base_scraper import RawGrant
from utils.db import get_connection


def handler(event, context):
    """Process a batch of scraped grants from Step Functions.

    Event payload (from scraper Lambda result):
    {
        "scraper_id": "grants-ca-gov",
        "grants_found": 15,
        "grants": [{"title": ..., "funder": ..., ...}]
    }

    OR for pipeline logging action:
    {
        "action": "log_pipeline_run",
        "results": [...]
    }
    """
    if event.get("action") == "log_pipeline_run":
        return _log_pipeline_run(event)

    secret_arn = os.environ["DB_SECRET_ARN"]
    conn = get_connection(secret_arn)
    scraper_id = event.get("scraper_id", "unknown")
    grant_dicts = event.get("grants", [])

    try:
        raw_grants = []
        for g in grant_dicts:
            raw_grants.append(RawGrant(
                title=g["title"],
                funder=g["funder"],
                description=g["description"],
                deadline=g.get("deadline"),
                source_url=g["source_url"],
                source_id=g["source_id"],
                raw_html=g.get("raw_html"),
            ))

        # 1a. Backfill source_url and deadline for existing grants
        _backfill_missing_fields(conn, raw_grants)

        # 1b. Dedup -- skip grants already in DB (per D-08)
        new_grants = check_duplicates_batch(conn, raw_grants)

        # 2. Extract + Embed each new grant
        grants_stored = 0
        for grant in new_grants:
            try:
                metadata = extract_metadata(grant.description)
                stored = embed_and_store(conn, grant, metadata)
                if stored:
                    grants_stored += 1
            except Exception as e:
                log_extraction_failure(conn, scraper_id, str(e))

        # 3. Update health monitor
        update_health(conn, scraper_id, len(raw_grants))

        return {
            "scraper_id": scraper_id,
            "grants_received": len(raw_grants),
            "grants_new": len(new_grants),
            "grants_stored": grants_stored,
            "status": "success",
        }

    except Exception as e:
        try:
            update_health(conn, scraper_id, 0, error=str(e))
        except Exception:
            pass
        return {
            "scraper_id": scraper_id,
            "status": "error",
            "error": str(e)[:2000],
        }


def _backfill_missing_fields(conn, raw_grants):
    """Update source_url and deadline for existing grants that are missing them."""
    from scrapers.processing.embedder import _safe_date
    cur = conn.cursor()
    for g in raw_grants:
        cur.execute("""
            UPDATE grants
            SET source_url = COALESCE(%s, source_url),
                deadline = COALESCE(%s::date, deadline),
                updated_at = NOW()
            WHERE content_hash = %s
              AND (source_url IS NULL OR deadline IS NULL)
        """, (g.source_url, _safe_date(g.deadline), g.content_hash))
    conn.commit()
    cur.close()


def _log_pipeline_run(event):
    """Aggregate results from all scrapers and log to pipeline_runs table."""
    secret_arn = os.environ["DB_SECRET_ARN"]
    conn = get_connection(secret_arn)
    results = event.get("results", [])

    run_id = start_run(conn, "ingestion")
    total_received = sum(r.get("grants_received", 0) for r in results if isinstance(r, dict))
    total_new = sum(r.get("grants_stored", 0) for r in results if isinstance(r, dict))
    errors = {r.get("scraper_id", "unknown"): r.get("error") for r in results if isinstance(r, dict) and r.get("status") == "error"}

    if errors:
        complete_run(conn, run_id, grants_found=total_received, grants_new=total_new, errors=errors)
    else:
        complete_run(conn, run_id, grants_found=total_received, grants_new=total_new)

    return {"run_id": run_id, "total_received": total_received, "total_new": total_new, "errors_count": len(errors)}
