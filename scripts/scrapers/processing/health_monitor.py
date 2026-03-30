"""Scraper health monitoring -- tracks consecutive zero-grant runs (INGEST-07, D-01)."""


def update_health(conn, scraper_id: str, grant_count: int, error: str = None):
    """Update scraper_health table. Increment consecutive_zeros when 0 grants, reset on >0."""
    cur = conn.cursor()
    if grant_count > 0:
        cur.execute("""
            INSERT INTO scraper_health (scraper_id, last_success_at, last_grant_count, consecutive_zeros, updated_at)
            VALUES (%s, NOW(), %s, 0, NOW())
            ON CONFLICT (scraper_id) DO UPDATE SET
                last_success_at = NOW(),
                last_grant_count = EXCLUDED.last_grant_count,
                consecutive_zeros = 0,
                last_error = NULL,
                updated_at = NOW()
        """, (scraper_id, grant_count))
    else:
        cur.execute("""
            INSERT INTO scraper_health (scraper_id, last_grant_count, consecutive_zeros, last_error, updated_at)
            VALUES (%s, 0, 1, %s, NOW())
            ON CONFLICT (scraper_id) DO UPDATE SET
                last_grant_count = 0,
                consecutive_zeros = scraper_health.consecutive_zeros + 1,
                last_error = EXCLUDED.last_error,
                updated_at = NOW()
        """, (scraper_id, error))
    conn.commit()


def get_unhealthy_scrapers(conn, threshold: int = 3) -> list[dict]:
    """Return scrapers with consecutive_zeros >= threshold for alerting."""
    cur = conn.cursor()
    cur.execute(
        "SELECT scraper_id, consecutive_zeros, last_error FROM scraper_health WHERE consecutive_zeros >= %s",
        (threshold,),
    )
    return [{"scraper_id": r[0], "consecutive_zeros": r[1], "last_error": r[2]} for r in cur.fetchall()]
