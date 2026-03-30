#!/usr/bin/env python3
"""Rotation-aware PostgreSQL connection via Secrets Manager.

Module-level connection cache for Lambda warm reuse. Handles Secrets Manager
90-day rotation gracefully: catches auth errors and re-fetches credentials.
All Lambdas must import from this module -- never create psycopg2.connect() directly.
"""
import json
import time
import boto3
import psycopg2
from pgvector.psycopg2 import register_vector
from utils.config import AWS_REGION

_conn = None
_secret_fetched_at = 0
_SECRET_MAX_AGE = 12 * 3600  # Re-fetch credentials after 12 hours


def get_connection(secret_arn: str, region: str = AWS_REGION):
    global _conn, _secret_fetched_at

    # If cached connection exists and credentials are fresh, try to reuse it
    if _conn is not None and not _conn.closed:
        if (time.time() - _secret_fetched_at) < _SECRET_MAX_AGE:
            try:
                _conn.cursor().execute("SELECT 1")
                return _conn
            except psycopg2.OperationalError:
                pass  # Stale connection, fall through
        else:
            # Credentials may be rotated, close and reconnect
            try:
                _conn.close()
            except Exception:
                pass

    # Create new connection (handles rotation-aware reconnection)
    try:
        _conn = _create_connection(secret_arn, region)
        _secret_fetched_at = time.time()
        return _conn
    except psycopg2.OperationalError as e:
        if "password authentication failed" in str(e):
            # Rotation happened -- credentials in cache are stale
            # Force re-fetch from Secrets Manager
            _conn = _create_connection(secret_arn, region)
            _secret_fetched_at = time.time()
            return _conn
        raise


def _create_connection(secret_arn: str, region: str):
    sm = boto3.client("secretsmanager", region_name=region)
    secret = json.loads(sm.get_secret_value(SecretId=secret_arn)["SecretString"])
    conn = psycopg2.connect(
        host=secret["host"],
        port=secret.get("port", 5432),
        dbname=secret.get("dbname", "hanna"),
        user=secret["username"],
        password=secret["password"],
        sslmode="require",
        connect_timeout=10,
    )
    try:
        register_vector(conn)
    except psycopg2.ProgrammingError:
        pass  # pgvector extension not yet installed (init_db.py will create it)
    return conn
