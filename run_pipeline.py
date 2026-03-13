"""
Family Chaos Orchestrator — Pipeline Entry Point
Run this to execute a full ingest cycle:
  1. Generate/fetch events (dummy data for now, real API later)
  2. Normalize to canonical schema
  3. Write Parquet to S3
  4. Sync local DuckDB from S3
"""

import logging
# from ingestion.dummy_source import fetch_dummy_events
from ingestion.calendar_schema import CalendarEvent
from ingestion.google_source import fetch_google_events
from ingestion.google_source import fetch_google_events_from_calendar
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

        # Step 1: Fetch raw events
        raw_events = fetch_google_events_from_calendar(calendar_id="hjg67thptksgup0b3219brfs44@group.calendar.google.com", days_ahead=21)
        # raw_events = fetch_dummy_events()
        log.info(f"Fetched {len(raw_events)} raw events")

        # Step 2: Normalize to canonical CalendarEvent schema
        events = normalize_events(raw_events)
        log.info(f"Normalized {len(events)} events")

        events = deduplicate(events)

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

def deduplicate(events: list[CalendarEvent]) -> list[CalendarEvent]:
    """Remove duplicate events based on source + original event ID."""
    seen = set()
    unique = []
    for event in events:
        if event.event_id not in seen:
            seen.add(event.event_id)
            unique.append(event)
    return unique

if __name__ == "__main__":
    run_pipeline()
