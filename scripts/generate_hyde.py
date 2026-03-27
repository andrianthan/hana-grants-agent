#!/usr/bin/env python3
"""Generate per-profile HyDE (Hypothetical Document Embedding) queries.

Reads SEARCH-PROFILES.md, extracts each department profile's HyDE seed prompt,
sends it to GPT-5.4 to generate a realistic hypothetical grant announcement,
embeds the result via Bedrock Titan V2, and stores in the hyde_queries table.

A SHA-256 hash of each profile section enables automatic regeneration when
the profile definition changes in SEARCH-PROFILES.md.

Usage:
    python generate_hyde.py --secret-arn arn:aws:secretsmanager:us-west-2:ACCOUNT:secret:NAME
    python generate_hyde.py --secret-arn ARN --profile-id mental-health-hub
    python generate_hyde.py --secret-arn ARN --force
"""
import argparse
import hashlib
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from openai import OpenAI
from utils.config import EMBEDDING_DIMS, HYDE_MODEL, AWS_REGION
from utils.db import get_connection
from utils.embeddings import get_embedding

# Path to SEARCH-PROFILES.md relative to project root
SEARCH_PROFILES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "org-materials",
    "SEARCH-PROFILES.md",
)

# System prompt for HyDE generation
HYDE_SYSTEM_PROMPT = """You are a grant announcement writer. Given a description of an ideal grant opportunity,
write a realistic hypothetical grant announcement (500-800 words) that a funder would publish.

Include:
- A realistic funder name and program title
- Eligibility criteria matching the described organization type
- Funding amount range
- Application deadline (use a realistic future date)
- Program goals and priorities that match the description
- Required components (narrative, budget, LOI, etc.)
- Geographic focus area
- Population served

Write as if this is a real Request for Applications (RFA) posted on a government or foundation website.
Do NOT include any meta-commentary -- just write the announcement itself."""

# Number of retry attempts for API calls
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1


def parse_profiles(filepath: str) -> dict:
    """Parse SEARCH-PROFILES.md and extract profile sections with HyDE seed prompts.

    Returns dict mapping profile_id -> {section_text, seed_prompt}.
    """
    with open(filepath, "r") as f:
        content = f.read()

    profiles = {}
    # Split on profile headers: ### Profile: `profile_id`
    profile_pattern = re.compile(r"^### Profile: `([^`]+)`", re.MULTILINE)
    matches = list(profile_pattern.finditer(content))

    for i, match in enumerate(matches):
        profile_id = match.group(1)
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        section_text = content[start:end].strip()

        # Extract HyDE Seed Prompt from code block
        seed_match = re.search(
            r"\*\*HyDE Seed Prompt:\*\*\s*```\s*\n(.*?)```",
            section_text,
            re.DOTALL,
        )
        if seed_match:
            seed_prompt = seed_match.group(1).strip()
        else:
            print(f"  WARNING: No HyDE Seed Prompt found for {profile_id}, skipping")
            continue

        profiles[profile_id] = {
            "section_text": section_text,
            "seed_prompt": seed_prompt,
        }

    return profiles


def compute_profile_hash(section_text: str) -> str:
    """Compute SHA-256 hash of a profile section for change detection."""
    return hashlib.sha256(section_text.encode("utf-8")).hexdigest()


def get_existing_hashes(conn, profile_ids: list) -> dict:
    """Fetch existing profile hashes from hyde_queries table.

    Returns dict mapping profile_id -> profile_hash.
    """
    cur = conn.cursor()
    placeholders = ",".join(["%s"] * len(profile_ids))
    cur.execute(
        f"SELECT profile_id, profile_hash FROM hyde_queries WHERE profile_id IN ({placeholders})",
        profile_ids,
    )
    result = {row[0]: row[1] for row in cur.fetchall()}
    cur.close()
    return result


def generate_hyde_text(client: OpenAI, seed_prompt: str) -> str:
    """Call GPT-5.4 to generate a hypothetical grant announcement from the seed prompt.

    Retries with exponential backoff on transient failures.
    """
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=HYDE_MODEL,
                messages=[
                    {"role": "system", "content": HYDE_SYSTEM_PROMPT},
                    {"role": "user", "content": seed_prompt},
                ],
                temperature=0.7,
                max_tokens=1200,
            )
            return response.choices[0].message.content
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
                print(f"    OpenAI API error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                print(f"    Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise RuntimeError(f"OpenAI API failed after {MAX_RETRIES} attempts: {e}")


def embed_with_retry(text: str) -> list:
    """Embed text via Bedrock Titan with retry/backoff.

    Returns embedding vector of EMBEDDING_DIMS dimensions.
    """
    for attempt in range(MAX_RETRIES):
        try:
            embedding = get_embedding(text)
            assert len(embedding) == EMBEDDING_DIMS, (
                f"Embedding dimension mismatch: got {len(embedding)}, expected {EMBEDDING_DIMS}"
            )
            return embedding
        except AssertionError:
            raise
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
                print(f"    Bedrock API error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                print(f"    Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise RuntimeError(f"Bedrock API failed after {MAX_RETRIES} attempts: {e}")


def upsert_hyde_query(conn, profile_id: str, query_text: str, embedding: list, profile_hash: str):
    """Insert or update a HyDE query in the hyde_queries table."""
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO hyde_queries (profile_id, query_text, embedding, profile_hash, updated_at)
        VALUES (%s, %s, %s::vector, %s, NOW())
        ON CONFLICT (profile_id) DO UPDATE SET
            query_text = EXCLUDED.query_text,
            embedding = EXCLUDED.embedding,
            profile_hash = EXCLUDED.profile_hash,
            updated_at = NOW()
        """,
        (profile_id, query_text, str(embedding), profile_hash),
    )
    conn.commit()
    cur.close()


def main():
    parser = argparse.ArgumentParser(
        description="Generate per-profile HyDE queries for Hanna Grants Agent"
    )
    parser.add_argument(
        "--secret-arn",
        required=True,
        help="AWS Secrets Manager ARN for RDS credentials",
    )
    parser.add_argument(
        "--profile-id",
        default=None,
        help="Regenerate a single profile (default: all profiles)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate all profiles regardless of hash match",
    )
    parser.add_argument(
        "--region",
        default=AWS_REGION,
        help=f"AWS region (default: {AWS_REGION})",
    )
    args = parser.parse_args()

    # Parse profiles from SEARCH-PROFILES.md
    profiles_path = os.path.normpath(SEARCH_PROFILES_PATH)
    print(f"Reading profiles from {profiles_path}")
    profiles = parse_profiles(profiles_path)
    print(f"Found {len(profiles)} profiles: {', '.join(profiles.keys())}")

    if not profiles:
        print("ERROR: No profiles found in SEARCH-PROFILES.md")
        sys.exit(1)

    # Filter to single profile if requested
    if args.profile_id:
        if args.profile_id not in profiles:
            print(f"ERROR: Profile '{args.profile_id}' not found. Available: {', '.join(profiles.keys())}")
            sys.exit(1)
        profiles = {args.profile_id: profiles[args.profile_id]}
        print(f"Targeting single profile: {args.profile_id}")

    # Connect to DB
    print("Connecting to RDS via Secrets Manager...")
    conn = get_connection(args.secret_arn, args.region)

    # Get existing hashes for skip logic
    existing_hashes = get_existing_hashes(conn, list(profiles.keys()))

    # Initialize OpenAI client
    client = OpenAI()

    # Process each profile
    generated = 0
    skipped = 0
    failed = 0

    for profile_id, profile_data in profiles.items():
        print(f"\n--- Profile: {profile_id} ---")
        section_text = profile_data["section_text"]
        seed_prompt = profile_data["seed_prompt"]
        current_hash = compute_profile_hash(section_text)

        # Check if regeneration needed
        if not args.force and profile_id in existing_hashes:
            if existing_hashes[profile_id] == current_hash:
                print(f"  Hash unchanged, skipping (use --force to override)")
                skipped += 1
                continue
            else:
                print(f"  Hash changed -- regenerating")

        try:
            # Step 1: Generate hypothetical grant via GPT-5.4
            print(f"  Generating HyDE text via {HYDE_MODEL}...")
            hyde_text = generate_hyde_text(client, seed_prompt)
            print(f"  Generated {len(hyde_text)} chars")

            # Step 2: Embed via Bedrock Titan
            print(f"  Embedding via Bedrock Titan ({EMBEDDING_DIMS} dims)...")
            embedding = embed_with_retry(hyde_text)
            print(f"  Embedding complete ({len(embedding)} dims)")

            # Step 3: Upsert into hyde_queries
            print(f"  Storing in hyde_queries table...")
            upsert_hyde_query(conn, profile_id, hyde_text, embedding, current_hash)
            print(f"  Stored successfully")
            generated += 1

        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1

    # Summary
    print(f"\n{'=' * 50}")
    print(f"HyDE Generation Summary")
    print(f"{'=' * 50}")
    print(f"  Profiles processed: {len(profiles)}")
    print(f"  Generated (new/updated): {generated}")
    print(f"  Skipped (hash unchanged): {skipped}")
    print(f"  Failed: {failed}")

    # Verify final state
    cur = conn.cursor()
    cur.execute("SELECT profile_id, LENGTH(query_text), updated_at FROM hyde_queries ORDER BY profile_id")
    rows = cur.fetchall()
    print(f"\n  hyde_queries table ({len(rows)} rows):")
    for pid, text_len, updated in rows:
        print(f"    {pid}: {text_len} chars, updated {updated}")
    cur.close()

    conn.close()

    if failed > 0:
        print(f"\nWARNING: {failed} profile(s) failed -- re-run with --force to retry")
        sys.exit(1)
    else:
        print(f"\nDone.")


if __name__ == "__main__":
    main()
