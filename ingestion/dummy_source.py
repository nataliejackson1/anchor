"""
AI generated garbage data for testing and development until OAuth established.
"""

from datetime import datetime, timedelta
import random


def fetch_dummy_events() -> list[dict]:
    """
    Returns a list of raw event dicts in two different shapes:
      - "google" shape: nested dateTime, summary, attendees as objects
      - "ical" shape: flat DTSTART/SUMMARY strings (like a school .ics export)

    This is the mess your adapter will clean up.
    """
    base = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    google_events = [
        {
            "_raw_source": "google",
            "id": "g001",
            "summary": "Soccer Practice — Mia",
            "start": {"dateTime": (base + timedelta(days=1, hours=16)).isoformat()},
            "end":   {"dateTime": (base + timedelta(days=1, hours=17, minutes=30)).isoformat()},
            "location": "Riverview Sports Complex",
            "description": "Bring shin guards and water bottle",
            "attendees": [
                {"displayName": "Mia", "email": "mia@family.com"},
                {"displayName": "Coach Sarah", "email": "sarah@club.com"},
            ],
        },
        {
            "_raw_source": "google",
            "id": "g002",
            "summary": "Pediatrician — Theo 18mo checkup",
            "start": {"dateTime": (base + timedelta(days=3, hours=10)).isoformat()},
            "end":   {"dateTime": (base + timedelta(days=3, hours=11)).isoformat()},
            "location": "St. Joseph Pediatrics",
            "description": "Bring insurance card. Shots likely.",
            "attendees": [],
        },
        {
            "_raw_source": "google",
            "id": "g003",
            "summary": "Team Standup",
            "start": {"dateTime": (base + timedelta(days=2, hours=9)).isoformat()},
            "end":   {"dateTime": (base + timedelta(days=2, hours=9, minutes=30)).isoformat()},
            "location": None,
            "description": "Zoom link in calendar",
            "attendees": [
                {"displayName": "Manager Bob"},
                {"displayName": "Priya"},
            ],
        },
    ]

    # iCal shape — flat strings, different field names
    ical_events = [
        {
            "_raw_source": "ical_school",
            "UID": "ical-school-001@district.edu",
            "SUMMARY": "Kindergarten Spring Concert",
            "DTSTART": (base + timedelta(days=5, hours=18)).isoformat(),
            "DTEND":   (base + timedelta(days=5, hours=19)).isoformat(),
            "LOCATION": "Jefferson Elementary Auditorium",
            "DESCRIPTION": "Please arrive 15 minutes early for seating.",
        },
        {
            "_raw_source": "ical_school",
            "UID": "ical-school-002@district.edu",
            "SUMMARY": "No School — Teacher Planning Day",
            "DTSTART": (base + timedelta(days=7)).strftime("%Y-%m-%d"),  # all-day: date only
            "DTEND":   (base + timedelta(days=7)).strftime("%Y-%m-%d"),
            "LOCATION": "",
            "DESCRIPTION": "",
        },
    ]

    return google_events + ical_events
