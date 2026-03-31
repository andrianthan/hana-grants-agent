#!/usr/bin/env python3
"""One-time historical grant backfill from API archives.
Per D-05: Only grants.ca.gov and Grants.gov (no fragile archive scraping).
Per D-06: Uses same extraction pipeline as live grants.
Per D-07: Batches of 50, resume from last successful batch.

Usage:
    python backfill.py --secret-arn <ARN> [--batch-size 50] [--resume]
"""
import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.api.grants_ca_gov import GrantsCaGov
from scrapers.api.grants_gov import GrantsGov
from scrapers.processing.dedup import check_duplicates_batch
from scrapers.processing.extractor import extract_metadata, log_extraction_failure
from scrapers.processing.embedder import embed_and_store
from scrapers.processing.pipeline_logger import start_run, complete_run, fail_run
from utils.db import get_connection

PROGRESS_FILE = "backfill_progress.json"


def load_progress() -> dict:
    """Load resume checkpoint from progress file."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"grants_ca_gov_offset": 0, "grants_gov_offset": 0, "total_processed": 0, "total_new": 0}


def save_progress(progress: dict):
    """Save progress checkpoint for resume capability."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def _process_batch(conn, grants, scraper_id, progress):
    """Dedup -> extract -> embed a batch of grants. Returns count of new grants stored."""
    new_grants = check_duplicates_batch(conn, grants)

    for grant in new_grants:
        try:
            metadata = extract_metadata(grant.description)
            embed_and_store(conn, grant, metadata)
            progress["total_new"] += 1
        except Exception as e:
            conn.rollback()
            log_extraction_failure(conn, scraper_id, str(e))

    return len(new_grants)


async def backfill_grants_ca_gov(conn, batch_size: int, progress: dict):
    """Backfill all grants.ca.gov historical records (~1871 total)."""
    config = {"scraper_id": "grants-ca-gov", "url": "https://data.ca.gov/api/3/action/datastore_search", "type": "api"}
    scraper = GrantsCaGov(config)
    offset = progress.get("grants_ca_gov_offset", 0)

    print(f"grants.ca.gov: starting from offset {offset}")

    while True:
        data = await scraper._get_json(
            "https://data.ca.gov/api/3/action/datastore_search",
            params={"resource_id": "111c8c88-21f6-453c-ae2c-b4785a0624f5", "limit": batch_size, "offset": offset},
        )

        records = data.get("result", {}).get("records", [])
        if not records:
            break

        from scrapers.base_scraper import RawGrant
        from scrapers.api.grants_ca_gov import _parse_date

        grants = []
        for rec in records:
            grants.append(RawGrant(
                title=rec.get("Title", "").strip(),
                funder=rec.get("AgencyDept", "").strip(),
                description=rec.get("Description", "").strip(),
                deadline=_parse_date(rec.get("ApplicationDeadline")),
                source_url=rec.get("GrantURL", config["url"]),
                source_id="grants-ca-gov",
            ))

        new_count = _process_batch(conn, grants, "grants-ca-gov", progress)
        print(f"  grants.ca.gov batch offset={offset}: {len(grants)} fetched, {new_count} new")

        progress["total_processed"] += len(grants)
        progress["grants_ca_gov_offset"] = offset + batch_size
        save_progress(progress)

        total = data.get("result", {}).get("total", 0)
        offset += batch_size
        if offset >= total:
            break

        time.sleep(5)  # Pause between batches per D-07

    await scraper.close()


async def backfill_grants_gov(conn, batch_size: int, progress: dict):
    """Backfill Grants.gov historical records for nonprofits."""
    config = {"scraper_id": "grants-gov", "url": "https://api.grants.gov/v1/api/search2", "type": "api"}
    scraper = GrantsGov(config)
    offset = progress.get("grants_gov_offset", 0)

    print(f"Grants.gov: starting from offset {offset}")

    while True:
        data = await scraper._post_json(
            "https://api.grants.gov/v1/api/search2",
            json_data={
                "oppStatuses": "posted",
                "rows": batch_size,
                "startRecordNum": offset,
                "eligibilities": "25",
            },
        )

        opp_hits = data.get("data", {}).get("oppHits", [])
        if not opp_hits:
            break

        from scrapers.base_scraper import RawGrant

        grants = []
        for opp in opp_hits:
            grants.append(RawGrant(
                title=opp.get("oppTitle", "").strip(),
                funder=opp.get("agencyName", "").strip(),
                description=opp.get("description", "").strip(),
                deadline=opp.get("closeDate"),
                source_url=f"https://www.grants.gov/view-opportunity/{opp.get('id', '')}",
                source_id="grants-gov",
            ))

        new_count = _process_batch(conn, grants, "grants-gov", progress)
        print(f"  Grants.gov batch offset={offset}: {len(grants)} fetched, {new_count} new")

        progress["total_processed"] += len(grants)
        progress["grants_gov_offset"] = offset + batch_size
        save_progress(progress)

        hit_count = data.get("data", {}).get("hitCount", 0)
        offset += batch_size
        if offset >= hit_count:
            break

        time.sleep(5)

    await scraper.close()


def main():
    parser = argparse.ArgumentParser(description="Backfill historical grants from API archives")
    parser.add_argument("--secret-arn", required=True)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--resume", action="store_true", help="Resume from last progress checkpoint")
    args = parser.parse_args()

    conn = get_connection(args.secret_arn)
    progress = load_progress() if args.resume else {
        "grants_ca_gov_offset": 0, "grants_gov_offset": 0,
        "total_processed": 0, "total_new": 0,
    }

    run_id = start_run(conn, "backfill")
    try:
        asyncio.run(backfill_grants_ca_gov(conn, args.batch_size, progress))
        asyncio.run(backfill_grants_gov(conn, args.batch_size, progress))
        complete_run(conn, run_id, grants_found=progress["total_processed"], grants_new=progress["total_new"])
        print(f"Backfill complete: {progress['total_processed']} processed, {progress['total_new']} new")
    except Exception as e:
        conn.rollback()
        fail_run(conn, run_id, {"error": str(e)})
        save_progress(progress)
        print(f"Backfill failed at progress: {progress}. Use --resume to continue.")
        raise


if __name__ == "__main__":
    main()
