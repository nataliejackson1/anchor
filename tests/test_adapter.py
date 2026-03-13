"""
Tests for the adapter layer.
Run with: pytest tests/test_adapter.py -v
"""

import pytest
from datetime import datetime
from ingestion.dummy_source import fetch_dummy_events
from ingestion.adapter import normalize_events, _from_google, _from_ical


def test_normalize_all_dummy_events():
    """All dummy events should normalize without errors."""
    raw = fetch_dummy_events()
    events = normalize_events(raw)
    assert len(events) == len(raw)


def test_google_event_normalized_correctly():
    """Google event fields map to canonical schema correctly."""
    raw = {
        "_raw_source": "google",
        "id": "test123",
        "summary": "Soccer Practice",
        "start": {"dateTime": "2026-03-15T16:00:00"},
        "end":   {"dateTime": "2026-03-15T17:30:00"},
        "location": "Sports Complex",
        "description": "Bring shin guards",
        "attendees": [
            {"displayName": "Mia"},
            {"email": "coach@club.com"},
        ],
    }
    event = _from_google(raw)
    assert event.event_id == "google_test123"
    assert event.source == "google"
    assert event.title == "Soccer Practice"
    assert event.location == "Sports Complex"
    assert event.is_all_day is False
    assert "Mia" in event.attendees
    assert "coach@club.com" in event.attendees
    assert event.raw_payload is not None


def test_ical_event_normalized_correctly():
    """iCal event fields map to canonical schema correctly."""
    raw = {
        "_raw_source": "ical_school",
        "UID": "abc123@school.edu",
        "SUMMARY": "Spring Concert",
        "DTSTART": "2026-03-20T18:00:00",
        "DTEND":   "2026-03-20T19:00:00",
        "LOCATION": "Auditorium",
        "DESCRIPTION": "Arrive early",
    }
    event = _from_ical(raw, "ical_school")
    assert event.event_id == "ical_school_abc123@school.edu"
    assert event.source == "ical_school"
    assert event.title == "Spring Concert"
    assert event.is_all_day is False


def test_ical_all_day_event():
    """iCal all-day events (date-only DTSTART) are detected correctly."""
    raw = {
        "_raw_source": "ical_school",
        "UID": "allday@school.edu",
        "SUMMARY": "No School",
        "DTSTART": "2026-03-25",   # date only — no time component
        "DTEND":   "2026-03-25",
        "LOCATION": "",
        "DESCRIPTION": "",
    }
    event = _from_ical(raw, "ical_school")
    assert event.is_all_day is True
    assert event.start_time == datetime(2026, 3, 25, 0, 0, 0)


def test_bad_event_is_skipped_not_crashed():
    """A malformed event should be skipped, not crash the whole pipeline."""
    raw_events = [
        {"_raw_source": "google", "id": "bad"},  # missing required fields
        {
            "_raw_source": "google",
            "id": "good001",
            "summary": "Good Event",
            "start": {"dateTime": "2026-03-15T10:00:00"},
            "end":   {"dateTime": "2026-03-15T11:00:00"},
            "attendees": [],
        },
    ]
    events = normalize_events(raw_events)
    # Bad event skipped, good event kept
    assert len(events) == 1
    assert events[0].event_id == "google_good001"


def test_unknown_source_is_skipped():
    """Events with unknown source tags should be skipped gracefully."""
    raw_events = [{"_raw_source": "mystery_app", "id": "x1"}]
    events = normalize_events(raw_events)
    assert len(events) == 0
