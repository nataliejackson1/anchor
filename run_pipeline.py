"""
run_pipeline.py — Full pipeline entry point including Phase 2 agent.

Steps:
  1. Fetch events from Google Calendar
  2. Normalize to canonical schema
  3. Write Parquet to S3
  4. Sync local DuckDB from S3
  5. Run LLM agent → generate weekly briefing
  6. Render and save briefing
"""

import logging
from config import settings
from delivery.email_sender import send_briefing_email
from ingestion.google_source import fetch_google_events
from ingestion.google_source import fetch_google_events_from_calendar
from ingestion.adapter import normalize_events
from storage.s3_writer import write_parquet_to_s3
from storage.duckdb_sync import sync_duckdb_from_s3
from agent.agent import run_agent
from agent.briefing import render_briefing

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/pipeline.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def deduplicate(events):
    """Remove duplicate events by event_id."""
    seen = set()
    unique = []
    for event in events:
        if event.event_id not in seen:
            seen.add(event.event_id)
            unique.append(event)
    return unique


def run_pipeline():
    log.info("=== Pipeline started ===")
    try:
        # ── Phase 1: Ingest ───────────────────────────────────────────────────
        raw_events = fetch_google_events_from_calendar(calendar_id=settings.calendar_id, days_ahead=21)
        raw_events = fetch_google_events(days_ahead=14)
        log.info(f"Fetched {len(raw_events)} raw events")

        events = normalize_events(raw_events)
        events = deduplicate(events)
        log.info(f"Normalized and deduped: {len(events)} events")

        s3_path = write_parquet_to_s3(events)
        log.info(f"Written to S3: {s3_path}")

        row_count = sync_duckdb_from_s3()
        log.info(f"DuckDB synced — {row_count} total rows")

        # ── Phase 2: Agent ────────────────────────────────────────────────────
        log.info("Running agent...")
        briefing_text = run_agent(days_ahead=7)

        briefing = render_briefing(briefing_text)
        print("\n" + briefing)

        success = send_briefing_email(briefing_text)
        if success:
            log.info(f"Email delivered to {settings.email_recipient}")
        else:
            log.warning("Email delivery failed — check logs above for details")

        log.info("=== Pipeline complete ===")

    except Exception as e:
        log.error(f"Pipeline failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    run_pipeline()
