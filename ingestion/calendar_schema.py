"""
Canonical CalendarEvent schema.
ALL sources normalize into this shape before touching storage (S3 - parquet).
"""

from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional
import uuid


class CalendarEvent(BaseModel):
    event_id: str                       # "{source}_{original_id}"
    source: str                         # "google", "ical_school", "dummy", etc.
    title: str
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    description: Optional[str] = None
    is_all_day: bool = False
    attendees: list[str] = []           # flat list of names or emails
    tags: list[str] = []                # populated later by classifier
    raw_payload: Optional[str] = None   # original JSON string, for debugging

    @field_validator("event_id", mode="before")
    @classmethod
    def ensure_event_id(cls, v):
        """Fall back to a UUID if no ID provided."""
        return v or str(uuid.uuid4())

    @field_validator("title", mode="before")
    @classmethod
    def ensure_title(cls, v):
        return v or "Untitled"
