"""
Family Chaos Orchestrator — Pipeline Entry Point
Run this to execute a full ingest cycle:
  1. Generate/fetch events (dummy data for now, real API later)
  2. Normalize to canonical schema
  3. Write Parquet to S3
  4. Sync local DuckDB from S3
"""

import logging
from ingestion.dummy_source import fetch_dummy_events
from ingestion.adapter import normalize_events
from storage.s3_writer import write_parquet_to_s3
from storage.duckdb_sync import sync_duckdb_from_s3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("pipeline.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def run_pipeline():
    log.info("=== Pipeline started ===")
    try:
        # Step 1: Fetch raw events (swap dummy_source for google_source later)
        raw_events = fetch_dummy_events()
        log.info(f"Fetched {len(raw_events)} raw events")

        # Step 2: Normalize to canonical CalendarEvent schema
        events = normalize_events(raw_events)
        log.info(f"Normalized {len(events)} events")

        # Step 3: Write to S3 as Parquet
        s3_path = write_parquet_to_s3(events)
        log.info(f"Written to S3: {s3_path}")

        # Step 4: Sync local DuckDB from S3
        row_count = sync_duckdb_from_s3()
        log.info(f"DuckDB synced — {row_count} total rows")

        log.info("=== Pipeline complete ===")

    except Exception as e:
        log.error(f"Pipeline failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    run_pipeline()
