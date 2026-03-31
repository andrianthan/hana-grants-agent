#!/usr/bin/env python3
"""Evaluation Pipeline: orchestrates Prospector + Evaluator for all profiles.

Main entry point for running the grant evaluation pipeline.
Can be run locally or invoked via Lambda handler.

Usage:
    python pipeline.py --secret-arn arn:aws:secretsmanager:us-west-2:ACCOUNT:secret:NAME
    python pipeline.py --secret-arn ARN --profile mental-health-hub
    python pipeline.py --secret-arn ARN --profile mental-health-hub --dry-run
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

# Add parent dir to path for utils imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"))
except ImportError:
    pass  # python-dotenv not needed in Lambda (env vars set by CDK)

from openai import OpenAI
from utils.db import get_connection

from prospector import run_prospector, _parse_profile_sections
from evaluator import run_evaluator, _load_org_profile

# All 6 search profiles
ALL_PROFILES = [
    "mental-health-hub",
    "hanna-institute",
    "residential-housing",
    "hanna-academy",
    "recreation-enrichment",
    "general-operations",
]

logger = logging.getLogger(__name__)


def create_openrouter_client() -> OpenAI:
    """Create an OpenAI-compatible client pointing to OpenRouter."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY environment variable is required. "
            "Set it in .env or export it before running."
        )
    base_url = os.environ.get("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
    )


def log_pipeline_run_start(conn, profile_id: str | None) -> int:
    """Create a pipeline_runs entry and return its id."""
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO pipeline_runs (run_type, profile_id, started_at, status)
        VALUES ('evaluation', %s, NOW(), 'running')
        RETURNING id
        """,
        (profile_id,),
    )
    run_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    return run_id


def log_pipeline_run_end(conn, run_id: int, grants_scored: int, errors: dict | None, status: str):
    """Update a pipeline_runs entry with completion info."""
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE pipeline_runs SET
            completed_at = NOW(),
            grants_scored = %s,
            errors = %s,
            status = %s
        WHERE id = %s
        """,
        (grants_scored, json.dumps(errors) if errors else None, status, run_id),
    )
    conn.commit()
    cur.close()


def deduplicate_candidates(all_candidates: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Deduplicate grants across profiles.

    If the same grant appears in multiple profiles, it stays in all of them
    (each profile scores independently). This function just logs overlap stats.
    """
    seen_grants = {}
    for profile_id, candidates in all_candidates.items():
        for g in candidates:
            gid = g["grant_id"]
            if gid not in seen_grants:
                seen_grants[gid] = []
            seen_grants[gid].append(profile_id)

    multi_profile = {gid: profiles for gid, profiles in seen_grants.items() if len(profiles) > 1}
    if multi_profile:
        logger.info(
            "Cross-profile overlap: %d grants appear in multiple profiles",
            len(multi_profile),
        )
        for gid, profiles in multi_profile.items():
            logger.debug("  %s: %s", gid, ", ".join(profiles))

    return all_candidates


def run_pipeline(
    secret_arn: str,
    profile_id: str | None = None,
    dry_run: bool = False,
    region: str = "us-west-2",
) -> dict:
    """Run the full evaluation pipeline.

    Args:
        secret_arn: AWS Secrets Manager ARN for RDS credentials.
        profile_id: Optional single profile to run (default: all profiles).
        dry_run: If True, run prospector only (no evaluator scoring).
        region: AWS region.

    Returns:
        Summary dict with per-profile stats.
    """
    start_time = time.time()

    # Connect to DB
    logger.info("Connecting to RDS via Secrets Manager...")
    conn = get_connection(secret_arn, region)

    # Create OpenRouter client
    logger.info("Initializing OpenRouter client...")
    client = create_openrouter_client()

    # Determine which profiles to run
    profiles_to_run = [profile_id] if profile_id else ALL_PROFILES
    logger.info("Running evaluation for profiles: %s", ", ".join(profiles_to_run))

    # Log pipeline run
    run_id = log_pipeline_run_start(conn, profile_id)
    logger.info("Pipeline run ID: %d", run_id)

    # Load shared context once
    _eval_dir = os.path.dirname(os.path.abspath(__file__))
    _org_materials_dir = os.environ.get("ORG_MATERIALS_DIR") or (
        os.path.join(_eval_dir, "..", "org-materials")
        if os.path.isdir(os.path.join(_eval_dir, "..", "org-materials"))
        else os.path.join(_eval_dir, "..", "..", "org-materials")
    )
    profile_sections = _parse_profile_sections(
        os.path.join(_org_materials_dir, "SEARCH-PROFILES.md")
    )
    org_profile = _load_org_profile()

    # Phase 1: Prospector — find candidates for each profile
    all_candidates = {}
    total_errors = {}

    for pid in profiles_to_run:
        if pid not in profile_sections:
            logger.error("Profile '%s' not found in SEARCH-PROFILES.md. Available: %s",
                         pid, ", ".join(profile_sections.keys()))
            total_errors[pid] = "Profile not found"
            continue

        try:
            candidates = run_prospector(
                conn=conn,
                client=client,
                profile_id=pid,
                profile_sections=profile_sections,
            )
            all_candidates[pid] = candidates
            logger.info("Profile '%s': %d candidates from Prospector", pid, len(candidates))
        except Exception as e:
            logger.error("Prospector failed for profile '%s': %s", pid, e, exc_info=True)
            total_errors[pid] = f"Prospector error: {e}"
            all_candidates[pid] = []

    # Log cross-profile overlap
    all_candidates = deduplicate_candidates(all_candidates)

    total_candidates = sum(len(c) for c in all_candidates.values())
    logger.info("Total candidates across all profiles: %d", total_candidates)

    if dry_run:
        logger.info("DRY RUN — skipping evaluator scoring")
        log_pipeline_run_end(conn, run_id, 0, total_errors or None, "completed-dry-run")
        elapsed = time.time() - start_time
        return {
            "run_id": run_id,
            "profiles": {pid: {"candidates": len(c)} for pid, c in all_candidates.items()},
            "total_candidates": total_candidates,
            "dry_run": True,
            "duration_seconds": round(elapsed, 1),
            "errors": total_errors or None,
        }

    # Phase 2: Evaluator — score each profile's candidates
    summary = {}
    total_scored = 0

    for pid in profiles_to_run:
        candidates = all_candidates.get(pid, [])
        if not candidates:
            summary[pid] = {"candidates": 0, "scored": 0, "above_threshold": 0, "below_threshold": 0, "errors": 0}
            continue

        try:
            stats = run_evaluator(
                conn=conn,
                client=client,
                candidates=candidates,
                profile_id=pid,
                org_profile=org_profile,
                profile_sections=profile_sections,
            )
            summary[pid] = {
                "candidates": len(candidates),
                **stats,
            }
            total_scored += stats["scored"]
        except Exception as e:
            logger.error("Evaluator failed for profile '%s': %s", pid, e, exc_info=True)
            total_errors[pid] = f"Evaluator error: {e}"
            summary[pid] = {"candidates": len(candidates), "scored": 0, "above_threshold": 0,
                            "below_threshold": 0, "errors": len(candidates)}

    # Finalize pipeline run
    status = "completed" if not total_errors else "completed-with-errors"
    log_pipeline_run_end(conn, run_id, total_scored, total_errors or None, status)

    elapsed = time.time() - start_time
    logger.info("Pipeline complete in %.1fs — %d grants scored across %d profiles",
                elapsed, total_scored, len(profiles_to_run))

    conn.close()

    return {
        "run_id": run_id,
        "profiles": summary,
        "total_scored": total_scored,
        "duration_seconds": round(elapsed, 1),
        "errors": total_errors or None,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run the Hanna Grants evaluation pipeline (Prospector + Evaluator)"
    )
    parser.add_argument(
        "--secret-arn",
        required=True,
        help="AWS Secrets Manager ARN for RDS credentials",
    )
    parser.add_argument(
        "--profile",
        default=None,
        choices=ALL_PROFILES,
        help="Run a single profile (default: all profiles)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run prospector only — no evaluator scoring or DB writes",
    )
    parser.add_argument(
        "--region",
        default="us-west-2",
        help="AWS region (default: us-west-2)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    result = run_pipeline(
        secret_arn=args.secret_arn,
        profile_id=args.profile,
        dry_run=args.dry_run,
        region=args.region,
    )

    print("\n" + "=" * 60)
    print("EVALUATION PIPELINE RESULTS")
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
