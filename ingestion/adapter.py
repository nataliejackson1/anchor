"""
Adapter layer — normalizes raw event dicts into CalendarEvent objects.
Each source gets its own _from_X() function.
run_pipeline.py only ever calls normalize_events() and never touches raw shapes.
"""

import json
import logging
from datetime import datetime
from ingestion.calendar_schema import CalendarEvent

log = logging.getLogger(__name__)


def normalize_events(raw_events: list[dict]) -> list[CalendarEvent]:
    """Route each raw event to the correct adapter based on its _raw_source field."""
    normalized = []
    for raw in raw_events:
        source = raw.get("_raw_source", "unknown")
        try:
            if source == "google":
                event = _from_google(raw)
            elif source.startswith("ical"):
                event = _from_ical(raw, source)
            else:
                log.warning(f"Unknown source '{source}', skipping event: {raw}")
                continue
            normalized.append(event)
        except Exception as e:
            log.error(f"Failed to normalize event from {source}: {e} | raw={raw}")
            # Skip bad events, don't crash the whole pipeline
            continue
    return normalized


def _from_google(raw: dict) -> CalendarEvent:
    """Normalize a Google Calendar API event dict."""
    start_str = raw["start"].get("dateTime") or raw["start"].get("date")
    end_str   = raw["end"].get("dateTime")   or raw["end"].get("date")

    is_all_day = "dateTime" not in raw["start"]

    attendees = [
        a.get("displayName") or a.get("email", "Unknown")
        for a in raw.get("attendees", [])
    ]

    return CalendarEvent(
        event_id=f"google_{raw['id']}",
        source="google",
        title=raw.get("summary", "Untitled"),
        start_time=_parse_dt(start_str),
        end_time=_parse_dt(end_str),
        location=raw.get("location"),
        description=raw.get("description"),
        is_all_day=is_all_day,
        attendees=attendees,
        raw_payload=json.dumps(raw),
    )


def _from_ical(raw: dict, source: str) -> CalendarEvent:
    """Normalize a flat iCal-style event dict."""
    start_str = raw.get("DTSTART", "")
    end_str   = raw.get("DTEND", start_str)

    # All-day events in iCal have date-only strings (YYYY-MM-DD, no time)
    is_all_day = "T" not in start_str

    return CalendarEvent(
        event_id=f"{source}_{raw.get('UID', '')}",
        source=source,
        title=raw.get("SUMMARY", "Untitled"),
        start_time=_parse_dt(start_str),
        end_time=_parse_dt(end_str),
        location=raw.get("LOCATION") or None,
        description=raw.get("DESCRIPTION") or None,
        is_all_day=is_all_day,
        attendees=[],           # iCal school exports rarely include attendees
        raw_payload=json.dumps(raw),
    )


def _parse_dt(value: str) -> datetime:
    """Parse ISO datetime string, handling both full datetimes and date-only strings."""
    if not value:
        raise ValueError("Empty datetime string")
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        # Fall back: treat date-only as midnight
        return datetime.strptime(value[:10], "%Y-%m-%d")
