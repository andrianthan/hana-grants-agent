"""Pipeline run audit trail logging (INGEST-09, PIPE-03)."""
import json


def start_run(conn, run_type: str = "ingestion", profile_id: str = None) -> int:
    """Insert pipeline_runs row, return run_id."""
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO pipeline_runs (run_type, profile_id) VALUES (%s, %s) RETURNING id",
        (run_type, profile_id),
    )
    run_id = cur.fetchone()[0]
    conn.commit()
    return run_id


def complete_run(conn, run_id: int, grants_found: int = 0, grants_new: int = 0, errors: dict = None):
    """Mark run as completed with stats."""
    cur = conn.cursor()
    cur.execute("""
        UPDATE pipeline_runs SET
            completed_at = NOW(), grants_ingested = %s, grants_new = %s,
            errors = %s::jsonb, status = 'completed'
        WHERE id = %s
    """, (grants_found, grants_new, json.dumps(errors) if errors else None, run_id))
    conn.commit()


def fail_run(conn, run_id: int, errors: dict = None):
    """Mark run as failed."""
    cur = conn.cursor()
    cur.execute("""
        UPDATE pipeline_runs SET completed_at = NOW(), errors = %s::jsonb, status = 'failed'
        WHERE id = %s
    """, (json.dumps(errors) if errors else None, run_id))
    conn.commit()
