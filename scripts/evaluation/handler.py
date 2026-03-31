#!/usr/bin/env python3
"""Lambda handler for the evaluation pipeline.

Invoked by Step Functions or EventBridge. Wraps pipeline.run_pipeline()
with Lambda-specific event parsing, logging, and error handling.

Environment Variables:
    DB_SECRET_ARN: AWS Secrets Manager ARN for RDS credentials
    OPENROUTER_API_KEY: API key for OpenRouter (GPT-4.1 / GPT-4.1-mini)
    AWS_REGION: AWS region (default: us-west-2)

Event Format (from Step Functions):
    {
        "profile_id": "mental-health-hub",  // optional — omit for all profiles
        "dry_run": false                     // optional — default false
    }

EventBridge scheduled event (no profile_id → runs all profiles).
"""
import json
import logging
import os
import sys

# Add evaluation package and scripts to path for Lambda
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """Lambda entry point for the evaluation pipeline.

    Args:
        event: Step Functions / EventBridge event dict.
        context: Lambda context object.

    Returns:
        Pipeline results dict (serializable).
    """
    # Late import to allow Lambda cold start optimization
    from pipeline import run_pipeline

    # Parse event
    # EventBridge scheduled events have a 'detail-type' key
    if "detail-type" in event:
        # EventBridge — run all profiles
        profile_id = None
        dry_run = False
        logger.info("Invoked by EventBridge (scheduled run, all profiles)")
    else:
        # Step Functions or direct invocation
        profile_id = event.get("profile_id")
        dry_run = event.get("dry_run", False)
        logger.info("Invoked with profile_id=%s, dry_run=%s", profile_id, dry_run)

    # Get config from environment
    secret_arn = os.environ.get("DB_SECRET_ARN")
    if not secret_arn:
        raise RuntimeError("DB_SECRET_ARN environment variable is required")

    region = os.environ.get("AWS_REGION", "us-west-2")

    # Validate OPENROUTER_API_KEY is set
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise RuntimeError("OPENROUTER_API_KEY environment variable is required")

    try:
        result = run_pipeline(
            secret_arn=secret_arn,
            profile_id=profile_id,
            dry_run=dry_run,
            region=region,
        )

        logger.info("Pipeline completed: %s", json.dumps(result, default=str))
        return result

    except Exception as e:
        logger.error("Pipeline failed: %s", e, exc_info=True)
        raise
