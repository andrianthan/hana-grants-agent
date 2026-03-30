#!/usr/bin/env python3
"""Ingest extracted text + supplementary markdown into pgvector documents table.

Reads extracted PDF text files from org-materials/.extracted-text/ and
supplementary markdown files from org-materials/. Chunks via multi-strategy
chunking, embeds via Bedrock Titan V2, and inserts into the documents table
with ON CONFLICT (source_file, chunk_index) DO UPDATE for idempotent upserts.

Usage:
    python ingest_documents.py --secret-arn arn:aws:secretsmanager:...
    python ingest_documents.py --secret-arn arn:... --fresh  # truncate first
"""

import os
import re
import sys
import time
import argparse
from datetime import datetime

# Add parent directory to path so utils imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.config import EMBEDDING_DIMS
from utils.db import get_connection
from utils.embeddings import get_embedding
from utils.chunking import chunk_by_section


# Retry configuration for Bedrock API calls
MAX_RETRIES = 3
INITIAL_BACKOFF_SECS = 1.0

# Document type inference patterns
DOC_TYPE_PATTERNS = {
    "application": [
        "grant-applications",
        "proposal",
        "application",
    ],
    "progress-report": [
        "progress-reports",
        "report",
    ],
    "work-plan": [
        "work-plans",
        "work_plan",
        "workplan",
        "scope_of_work",
    ],
}

# Supplementary markdown files and their doc_type mappings
SUPPLEMENTARY_MARKDOWN = {
    "FUNDER-DIRECTORY.md": "reference",
    "METRICS-AND-OUTCOMES.md": "reference",
    "PARTNER-NETWORK.md": "reference",
    "WRITING-STYLE-GUIDE.md": "reference",
    "ORG-PROFILE.md": "org_profile",
    "SEARCH-PROFILES.md": "reference",
}


def infer_doc_type(filename: str) -> str:
    """Infer document type from filename patterns."""
    lower = filename.lower()
    for doc_type, patterns in DOC_TYPE_PATTERNS.items():
        for pattern in patterns:
            if pattern.lower() in lower:
                return doc_type
    return "reference"


def derive_funder_year(filename: str) -> tuple[str, str]:
    """Derive funder and year from filename conventions.

    Patterns:
        SAMHSA_2023_Application.txt -> funder=SAMHSA, year=2023
        FYC_CSS_Proposal.txt -> funder=FYC, year=<current_year>
        Bank_of_Marin_Charitable_... -> funder=Bank, year=<from_filename>

    Fallback: funder="unknown", year=str(current_year)
    """
    current_year = str(datetime.now().year)

    # Strip extension
    name = os.path.splitext(filename)[0]

    # Extract year: look for 4-digit pattern matching 20XX
    year_match = re.search(r"(20\d{2})", name)
    year = year_match.group(1) if year_match else current_year

    # Extract funder: first underscore-delimited token
    tokens = name.split("_")
    if tokens:
        funder = tokens[0].strip()
        if funder:
            return funder, year

    return "unknown", year


def get_embedding_with_retry(text: str) -> list[float]:
    """Wrap get_embedding with retry/exponential backoff for transient failures."""
    backoff = INITIAL_BACKOFF_SECS
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return get_embedding(text)
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                print(f"    Embedding retry {attempt}/{MAX_RETRIES} after error: {e}")
                time.sleep(backoff)
                backoff *= 2
            else:
                raise last_error


def ingest_file(
    conn,
    text: str,
    source_file: str,
    doc_type: str,
    funder: str,
    year: str,
) -> int:
    """Chunk, embed, and insert a single file into the documents table.

    Returns the number of chunks inserted/updated.
    """
    chunks = chunk_by_section(text, source_file, doc_type, funder, year)

    if not chunks:
        print(f"    WARNING: No chunks produced for {source_file}")
        return 0

    cur = conn.cursor()
    count = 0

    for chunk in chunks:
        embedding = get_embedding_with_retry(chunk["content"])

        # Verify embedding dimensions match config
        assert len(embedding) == EMBEDDING_DIMS, (
            f"Embedding dimension mismatch: got {len(embedding)}, "
            f"expected {EMBEDDING_DIMS}"
        )

        cur.execute(
            """
            INSERT INTO documents (
                source_file, chunk_index, content, section_title,
                doc_type, funder, year, embedding
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
            ON CONFLICT (source_file, chunk_index) DO UPDATE SET
                content = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                section_title = EXCLUDED.section_title,
                doc_type = EXCLUDED.doc_type,
                funder = EXCLUDED.funder,
                year = EXCLUDED.year
            """,
            (
                chunk["source_file"],
                chunk["chunk_index"],
                chunk["content"],
                chunk["section_title"],
                chunk["doc_type"],
                chunk["funder"],
                chunk["year"],
                str(embedding),
            ),
        )
        count += 1

    conn.commit()
    return count


def _reconnect_if_needed(conn, secret_arn: str):
    """Reconnect to the database if the connection is closed or broken."""
    if conn is None or conn.closed:
        print("    Reconnecting to database...")
        import utils.db as db_mod
        db_mod._conn = None  # Clear cached connection
        return get_connection(secret_arn)
    try:
        conn.rollback()  # Clear any failed transaction state
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        return conn
    except Exception:
        print("    Reconnecting to database...")
        import utils.db as db_mod
        db_mod._conn = None
        return get_connection(secret_arn)


def ingest_extracted_pdfs(conn, org_dir: str, secret_arn: str) -> tuple:
    """Phase 1: Ingest extracted PDF text files. Returns (conn, stats)."""
    extracted_dir = os.path.join(org_dir, ".extracted-text")
    stats = {"files": 0, "chunks": 0, "errors": []}

    if not os.path.isdir(extracted_dir):
        print(f"  WARNING: Extracted text directory not found: {extracted_dir}")
        return conn, stats

    txt_files = sorted(
        f for f in os.listdir(extracted_dir) if f.endswith(".txt")
    )

    print(f"\n--- Phase 1: Ingesting {len(txt_files)} extracted PDF text files ---\n")

    for filename in txt_files:
        filepath = os.path.join(extracted_dir, filename)
        text = open(filepath, "r", encoding="utf-8").read()

        if not text.strip():
            print(f"  SKIP (empty): {filename}")
            continue

        doc_type = infer_doc_type(filename)
        funder, year = derive_funder_year(filename)

        print(f"  Ingesting: {filename} (type={doc_type}, funder={funder}, year={year})")

        try:
            conn = _reconnect_if_needed(conn, secret_arn)
            chunk_count = ingest_file(conn, text, filename, doc_type, funder, year)
            stats["files"] += 1
            stats["chunks"] += chunk_count
            print(f"    -> {chunk_count} chunks")
        except Exception as e:
            print(f"    ERROR: {e}")
            stats["errors"].append({"file": filename, "error": str(e)})

    return conn, stats


def ingest_supplementary_markdown(conn, org_dir: str, secret_arn: str) -> tuple:
    """Phase 2: Ingest supplementary markdown files. Returns (conn, stats)."""
    current_year = str(datetime.now().year)
    stats = {"files": 0, "chunks": 0, "errors": []}

    print(f"\n--- Phase 2: Ingesting supplementary markdown files ---\n")

    for filename, doc_type in SUPPLEMENTARY_MARKDOWN.items():
        filepath = os.path.join(org_dir, filename)

        if not os.path.isfile(filepath):
            print(f"  SKIP (not found): {filename}")
            continue

        text = open(filepath, "r", encoding="utf-8").read()

        if not text.strip():
            print(f"  SKIP (empty): {filename}")
            continue

        funder = "internal"
        year = current_year

        print(f"  Ingesting: {filename} (type={doc_type}, funder={funder}, year={year})")

        try:
            conn = _reconnect_if_needed(conn, secret_arn)
            chunk_count = ingest_file(conn, text, filename, doc_type, funder, year)
            stats["files"] += 1
            stats["chunks"] += chunk_count
            print(f"    -> {chunk_count} chunks")
        except Exception as e:
            print(f"    ERROR: {e}")
            stats["errors"].append({"file": filename, "error": str(e)})

    return conn, stats


def main():
    parser = argparse.ArgumentParser(
        description="Ingest documents into pgvector for RAG"
    )
    parser.add_argument(
        "--secret-arn",
        required=True,
        help="AWS Secrets Manager ARN for RDS credentials",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Truncate documents table before ingesting",
    )
    parser.add_argument(
        "--org-materials",
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "org-materials",
        ),
        help="Path to org-materials/ directory",
    )
    args = parser.parse_args()

    print(f"Connecting to database...")
    conn = get_connection(args.secret_arn)

    if args.fresh:
        print("  --fresh flag set: truncating documents table")
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE documents")
        conn.commit()

    # Phase 1: Extracted PDF text files
    conn, pdf_stats = ingest_extracted_pdfs(conn, args.org_materials, args.secret_arn)

    # Phase 2: Supplementary markdown files
    conn, md_stats = ingest_supplementary_markdown(conn, args.org_materials, args.secret_arn)

    # Final verification: count total rows
    conn = _reconnect_if_needed(conn, args.secret_arn)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM documents")
    total_rows = cur.fetchone()[0]

    # Summary
    total_files = pdf_stats["files"] + md_stats["files"]
    total_chunks = pdf_stats["chunks"] + md_stats["chunks"]
    total_errors = pdf_stats["errors"] + md_stats["errors"]
    avg_chunks = total_chunks / total_files if total_files > 0 else 0

    print()
    print("=" * 50)
    print("Ingestion Summary")
    print("=" * 50)
    print(f"  Files processed:       {total_files}")
    print(f"    PDF text files:      {pdf_stats['files']}")
    print(f"    Markdown files:      {md_stats['files']}")
    print(f"  Total chunks:          {total_chunks}")
    print(f"  Avg chunks/file:       {avg_chunks:.1f}")
    print(f"  Errors:                {len(total_errors)}")
    if total_errors:
        for err in total_errors:
            print(f"    - {err['file']}: {err['error']}")
    print(f"  Total rows in DB:      {total_rows}")
    print("=" * 50)

    conn.close()


if __name__ == "__main__":
    main()
