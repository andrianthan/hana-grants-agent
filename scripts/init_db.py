#!/usr/bin/env python3
"""Initialize RDS PostgreSQL schema with pgvector extension and all 6 tables.

Creates: grants, documents, hyde_queries, scraper_health, extraction_failures, pipeline_runs
Plus HNSW indexes on vector columns and B-tree indexes on frequently queried columns.

Usage:
    python init_db.py --secret-arn arn:aws:secretsmanager:us-west-2:ACCOUNT:secret:NAME
"""
import argparse
import sys

sys.path.insert(0, ".")
from utils.config import EMBEDDING_DIMS
from utils.db import get_connection

DDL = f"""
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- Table 1: grants (primary data store)
-- ============================================================
CREATE TABLE IF NOT EXISTS grants (
    id                  SERIAL PRIMARY KEY,
    grant_id            TEXT UNIQUE NOT NULL,
    title               TEXT,
    funder              TEXT,
    deadline            DATE,
    funding_min         INTEGER,
    funding_max         INTEGER,
    geography           TEXT,
    eligibility         TEXT,
    description         TEXT,
    program_area        TEXT,
    population_served   TEXT,
    relationship_req    BOOLEAN DEFAULT FALSE,
    embedding           vector({EMBEDDING_DIMS}),
    source              TEXT,
    raw_s3_key          TEXT,
    content_hash        TEXT NOT NULL,
    approval_status     TEXT DEFAULT 'pending',
    approved_profile_id TEXT,
    skip_reason         TEXT,
    score               FLOAT,
    score_reasoning     TEXT,
    score_flags         JSONB,
    scored_by_profiles  TEXT[],
    ingested_at         TIMESTAMPTZ DEFAULT NOW(),
    scored_at           TIMESTAMPTZ,
    alerted_at          TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(content_hash)
);

-- Add alerted_at column if missing (migration for existing deployments)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'grants' AND column_name = 'alerted_at'
    ) THEN
        ALTER TABLE grants ADD COLUMN alerted_at TIMESTAMPTZ;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_grants_deadline ON grants (deadline);
CREATE INDEX IF NOT EXISTS idx_grants_approval_status ON grants (approval_status);
CREATE INDEX IF NOT EXISTS idx_grants_source ON grants (source);
CREATE INDEX IF NOT EXISTS idx_grants_funder ON grants (funder);
CREATE INDEX IF NOT EXISTS idx_grants_content_hash ON grants (content_hash);

-- HNSW index on grants.embedding
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes WHERE indexname = 'idx_grants_embedding_hnsw'
    ) THEN
        CREATE INDEX idx_grants_embedding_hnsw ON grants
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
    END IF;
END
$$;

-- ============================================================
-- Table 2: documents (Hanna org RAG corpus)
-- ============================================================
CREATE TABLE IF NOT EXISTS documents (
    id          SERIAL PRIMARY KEY,
    source_file   TEXT NOT NULL,
    doc_type      TEXT NOT NULL,
    title         TEXT,
    section_title TEXT,
    funder        TEXT,
    year          TEXT,
    content       TEXT NOT NULL,
    chunk_index   INTEGER DEFAULT 0,
    embedding     vector({EMBEDDING_DIMS}) NOT NULL,
    metadata      JSONB,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_file, chunk_index)
);

-- HNSW index on documents.embedding
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes WHERE indexname = 'idx_documents_embedding_hnsw'
    ) THEN
        CREATE INDEX idx_documents_embedding_hnsw ON documents
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_documents_source_file ON documents (source_file);

-- ============================================================
-- Table 3: hyde_queries (one per search profile)
-- ============================================================
CREATE TABLE IF NOT EXISTS hyde_queries (
    id              SERIAL PRIMARY KEY,
    profile_id      TEXT NOT NULL,
    query_text      TEXT NOT NULL,
    embedding       vector({EMBEDDING_DIMS}) NOT NULL,
    profile_hash    TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(profile_id)
);

-- HNSW index on hyde_queries.embedding
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes WHERE indexname = 'idx_hyde_queries_embedding_hnsw'
    ) THEN
        CREATE INDEX idx_hyde_queries_embedding_hnsw ON hyde_queries
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_hyde_queries_profile_id ON hyde_queries (profile_id);

-- ============================================================
-- Table 4: scraper_health (one row per source, upserted daily)
-- ============================================================
CREATE TABLE IF NOT EXISTS scraper_health (
    scraper_id        TEXT PRIMARY KEY,
    last_success_at   TIMESTAMPTZ,
    last_grant_count  INTEGER DEFAULT 0,
    last_error        TEXT,
    consecutive_zeros INTEGER DEFAULT 0,
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Table 5: extraction_failures (dead letter logging)
-- ============================================================
CREATE TABLE IF NOT EXISTS extraction_failures (
    id         SERIAL PRIMARY KEY,
    scraper_id TEXT,
    raw_s3_key TEXT,
    error      TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Table 6: pipeline_runs (audit trail)
-- ============================================================
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              SERIAL PRIMARY KEY,
    run_type        TEXT NOT NULL,
    profile_id      TEXT,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    grants_ingested INTEGER DEFAULT 0,
    grants_scored   INTEGER DEFAULT 0,
    grants_new      INTEGER DEFAULT 0,
    errors          JSONB,
    status          TEXT DEFAULT 'running'
);
"""


def main():
    parser = argparse.ArgumentParser(description="Initialize Hanna Grants Agent database schema")
    parser.add_argument("--secret-arn", required=True, help="AWS Secrets Manager ARN for RDS credentials")
    parser.add_argument("--region", default="us-west-2", help="AWS region (default: us-west-2)")
    args = parser.parse_args()

    print(f"Connecting to RDS via Secrets Manager...")
    conn = get_connection(args.secret_arn, args.region)
    conn.rollback()  # Clear any open transaction from connection setup
    conn.autocommit = True

    print(f"Creating schema (EMBEDDING_DIMS={EMBEDDING_DIMS})...")
    cur = conn.cursor()
    cur.execute(DDL)

    # Post-init verification
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
    tables = [r[0] for r in cur.fetchall()]
    expected = ["grants", "documents", "hyde_queries", "scraper_health", "extraction_failures", "pipeline_runs"]
    for t in expected:
        assert t in tables, f"Missing table: {t}"
    print(f"Verified: all {len(expected)} tables created successfully")

    # Verify uniqueness constraints
    cur.execute("""
        SELECT tc.table_name, tc.constraint_name, tc.constraint_type
        FROM information_schema.table_constraints tc
        WHERE tc.constraint_type = 'UNIQUE' AND tc.table_schema = 'public'
        ORDER BY tc.table_name
    """)
    unique_constraints = cur.fetchall()
    print(f"Uniqueness constraints: {len(unique_constraints)}")
    for table, name, ctype in unique_constraints:
        print(f"  {table}: {name}")

    # Verify HNSW indexes
    cur.execute("SELECT indexname FROM pg_indexes WHERE indexdef LIKE '%hnsw%'")
    hnsw_indexes = [r[0] for r in cur.fetchall()]
    print(f"HNSW indexes: {len(hnsw_indexes)}")
    for idx in hnsw_indexes:
        print(f"  {idx}")

    cur.close()
    conn.close()
    print("Schema initialization complete.")


if __name__ == "__main__":
    main()
