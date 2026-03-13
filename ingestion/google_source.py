import os
import logging
from datetime import datetime, timedelta, timezone
from google.auth.transport.requests import Request # type: ignore
from google.oauth2.credentials import Credentials # pyright: ignore[reportMissingImports]
from google_auth_oauthlib.flow import InstalledAppFlow # type: ignore
from googleapiclient.discovery import build # type: ignore
from googleapiclient.errors import HttpError # type: ignore

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CREDENTIALS_FILE = "credentials.json"   
TOKEN_FILE = "token.json"         


def _get_credentials() -> Credentials:
    """
    Load stored credentials or run the OAuth flow to get new ones.
    On first run: opens a browser window for you to approve access.
    On subsequent runs: silently loads token.json (no browser needed).
    """
    creds = None

    # Load existing token if it exists
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If no valid credentials, run the auth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Silently refresh expired token
            log.info("Refreshing expired Google credentials...")
            creds.refresh(Request())
        else:
            # First-time auth — opens browser
            log.info("No credentials found — opening browser for Google auth...")
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Missing {CREDENTIALS_FILE}. "
                    "Download it from Google Cloud Console → APIs & Services → Credentials."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save for next run
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        log.info(f"Credentials saved to {TOKEN_FILE}")

    return creds

# python -c "from ingestion.google_source import list_all_calendars; list_all_calendars()"

def fetch_google_events(days_ahead: int = 14) -> list[dict]:
    """
    Fetch events from Google Calendar for the next `days_ahead` days.
    Returns raw API response dicts with _raw_source injected.

    Args:
        days_ahead: How many days forward to fetch. Default 14 (two weeks).
    """
    try:
        creds = _get_credentials()
        service = build("calendar", "v3", credentials=creds)

        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        time_max = (now + timedelta(days=days_ahead)).isoformat()

        log.info(f"Fetching Google Calendar events for next {days_ahead} days...")
        result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,          # expand recurring events
                orderBy="startTime",        # sorted chronologically
                maxResults=250,             # safety cap
            )
            .execute()
        )

        raw_events = result.get("items", [])
        log.info(f"Fetched {len(raw_events)} events from Google Calendar")

        for event in raw_events:
            event["_raw_source"] = "google"

        return raw_events

    except HttpError as e:
        log.error(f"Google Calendar API error: {e}")
        raise
    except Exception as e:
        log.error(f"Failed to fetch Google Calendar events: {e}")
        raise


def fetch_google_events_from_calendar(calendar_id: str, days_ahead: int = 14) -> list[dict]:
    """
    Fetch events from a specific calendar (not just primary).
    Useful for fetching a shared family calendar or a kids' school calendar
    if it's been added to your Google Calendar.

    Args:
        calendar_id: The calendar ID under each calendar → Integrate calendar → Calendar ID.
                     Ex: abc123@group.calendar.google.com
        days_ahead: How many days forward to fetch.
    """
    try:
        creds = _get_credentials()
        service = build("calendar", "v3", credentials=creds)

        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        time_max = (now + timedelta(days=days_ahead)).isoformat()

        log.info(f"Fetching events from calendar: {calendar_id}")

        result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                maxResults=250,
            )
            .execute()
        )

        raw_events = result.get("items", [])
        log.info(f"Fetched {len(raw_events)} events from {calendar_id}")

        for event in raw_events:
            event["_raw_source"] = "google"

        return raw_events

    except HttpError as e:
        log.error(f"Google Calendar API error for calendar {calendar_id}: {e}")
        raise


def list_all_calendars() -> list[dict]:
    """
    Utility function — lists all calendars on your account.
    Run this once to find the calendar IDs for your family/school calendars.

    Usage:
        python -c "from ingestion.google_source import list_all_calendars; list_all_calendars()"
    """
    creds = _get_credentials()
    service = build("calendar", "v3", credentials=creds)

    calendar_list = service.calendarList().list().execute()
    calendars = calendar_list.get("items", [])

    print(f"\nFound {len(calendars)} calendars on your account:\n")
    for cal in calendars:
        print(f"  Name: {cal.get('summary')}")
        print(f"  ID:   {cal.get('id')}")
        print(f"  {'PRIMARY' if cal.get('primary') else ''}")
        print()

    return calendars


if __name__ == "__main__":
    # Run this file directly to trigger first-time browser auth and token.json will be generated
    #   python ingestion/google_source.py
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    events = fetch_google_events(days_ahead=7)
    print(f"\nFetched {len(events)} events:\n")
    for e in events:
        start = e.get("start", {}).get("dateTime") or e.get("start", {}).get("date")
        print(f"  {start}  —  {e.get('summary', 'Untitled')}")