"""SHA-256 dedup check against grants table (D-08: dedup before LLM calls)."""


def is_duplicate(conn, content_hash: str) -> bool:
    """Check if grant already exists by SHA-256 content hash."""
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM grants WHERE content_hash = %s", (content_hash,))
    return cur.fetchone() is not None


def check_duplicates_batch(conn, grants: list) -> list:
    """Filter out grants whose content_hash already exists. Returns only new grants."""
    if not grants:
        return []
    hashes = [g.content_hash for g in grants]
    cur = conn.cursor()
    cur.execute("SELECT content_hash FROM grants WHERE content_hash = ANY(%s)", (hashes,))
    existing = {row[0] for row in cur.fetchall()}
    return [g for g in grants if g.content_hash not in existing]
