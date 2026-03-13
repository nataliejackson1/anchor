"""
DuckDB Sync — reads all Parquet files from S3 into a local DuckDB database.

DuckDB can query S3 Parquet files directly via the httpfs extension.
We materialize the results into a local table so queries are fast offline.

Local DB file: ./data/calendar.db
Table: events
"""

import logging
import os
import duckdb
from config import settings

log = logging.getLogger(__name__)

# Local DuckDB file path — committed to .gitignore, never to git
LOCAL_DB_PATH = "data/calendar.db"


def get_connection() -> duckdb.DuckDBPyConnection:
    os.makedirs("data", exist_ok=True)
    return duckdb.connect(LOCAL_DB_PATH)


def sync_duckdb_from_s3() -> int:
    """
    Pull all Parquet files from S3 into the local DuckDB `events` table.
    Uses REPLACE so re-running the pipeline is always safe (idempotent).
    Returns total row count after sync.
    """
    conn = get_connection()

    # Install and load the S3/HTTP extension (cached after first run)
    conn.execute("INSTALL httpfs; LOAD httpfs;")

    conn.execute(f"""
        SET s3_region     = '{settings.aws_region}';
        SET s3_access_key_id     = '{settings.aws_access_key_id}';
        SET s3_secret_access_key = '{settings.aws_secret_access_key}';
    """)

    # S3 glob pattern — reads ALL run-date partitions at once
    s3_glob = f"s3://{settings.s3_bucket}/calendar/events/**/*.parquet"

    # CREATE OR REPLACE materializes the full result locally
    # Next time you query `events`, it reads from local disk — fast and offline-friendly
    conn.execute(f"""
        CREATE OR REPLACE TABLE events AS
        SELECT * FROM read_parquet('{s3_glob}', hive_partitioning = true)
    """)

    row_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    conn.close()
    return row_count


def query_events(sql: str) -> list[dict]:
    """
    Run an arbitrary SQL query against the local events table.
    Useful for the agent layer to fetch upcoming events.

    Example:
        query_events("SELECT * FROM events WHERE start_time > now() ORDER BY start_time")
    """
    conn = get_connection()
    result = conn.execute(sql).fetchdf()
    conn.close()
    return result.to_dict(orient="records")
