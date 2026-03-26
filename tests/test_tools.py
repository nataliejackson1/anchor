"""
tests/test_tools.py — Tests for weather and drive time tools.

These tests use mocking so they don't make real API calls.
Run with: pytest tests/test_tools.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
from agent.tools import get_weather, get_drive_time


# ── Weather tests ─────────────────────────────────────────────────────────────

@patch("agent.tools.requests.get")
def test_get_weather_success(mock_get):
    """Weather tool returns clean structured data on success."""

    # Mock geocoding response
    geo_response = MagicMock()
    geo_response.json.return_value = [{"lat": 27.87, "lon": -82.33}]
    geo_response.raise_for_status = MagicMock()

    # Mock forecast response
    forecast_response = MagicMock()
    forecast_response.json.return_value = {
        "list": [
            {
                "dt": 1742054400,  # some unix timestamp
                "main": {
                    "temp": 78.5,
                    "feels_like": 80.0,
                    "humidity": 65,
                },
                "weather": [{"description": "partly cloudy"}],
                "pop": 0.2,
                "wind": {"speed": 8.5},
            }
        ]
    }
    forecast_response.raise_for_status = MagicMock()

    mock_get.side_effect = [geo_response, forecast_response]

    result = get_weather(date="2026-03-15", location="Riverview, FL")

    assert result["error"] is None
    assert result["temp_f"] == 78         # rounded
    assert result["condition"] == "Partly cloudy"
    assert result["precipitation_chance"] == 20
    assert result["wind_mph"] == 8.5
    assert "summary" in result
    assert result["location"] == "Riverview, FL"


@patch("agent.tools.requests.get")
def test_get_weather_unknown_location(mock_get):
    """Weather tool returns error dict when location can't be geocoded."""
    geo_response = MagicMock()
    geo_response.json.return_value = []   # empty = location not found
    geo_response.raise_for_status = MagicMock()

    mock_get.return_value = geo_response

    result = get_weather(date="2026-03-15", location="Nowhere Land")

    assert result["error"] is not None
    assert "geocode" in result["error"].lower()
    assert result["temp_f"] is None


@patch("agent.tools.requests.get")
def test_get_weather_api_failure(mock_get):
    """Weather tool handles network errors gracefully."""
    import requests
    mock_get.side_effect = requests.RequestException("Connection timeout")

    result = get_weather(date="2026-03-15", location="Riverview, FL")

    assert result["error"] is not None
    assert result["temp_f"] is None
    assert "unavailable" in result["summary"].lower()


# ── Drive time tests ──────────────────────────────────────────────────────────

@patch("agent.tools.requests.get")
def test_get_drive_time_success(mock_get):
    """Drive time tool returns clean structured data on success."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "status": "OK",
        "rows": [{
            "elements": [{
                "status": "OK",
                "duration": {"value": 1500, "text": "25 mins"},    # 25 minutes
                "distance": {"value": 12800, "text": "8.3 mi"},
            }]
        }]
    }
    mock_get.return_value = mock_response

    result = get_drive_time(
        origin="Riverview, FL",
        destination="Riverview Sports Complex, FL",
        arrival_time="2026-03-18T10:00:00",
    )

    assert result["error"] is None
    assert result["duration_minutes"] == 25
    assert result["distance_miles"] == 8.3
    assert result["origin"] == "Riverview, FL"
    assert "summary" in result


@patch("agent.tools.requests.get")
def test_get_drive_time_with_arrival_time(mock_get):
    """Drive time with arrival_time returns a leave_by time."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "status": "OK",
        "rows": [{
            "elements": [{
                "status": "OK",
                "duration": {"value": 1200, "text": "20 mins"},    # 20 min drive
                "duration_in_traffic": {"value": 1500, "text": "25 mins"},  # 25 with traffic
                "distance": {"value": 10000, "text": "6.2 mi"},
            }]
        }]
    }
    mock_get.return_value = mock_response

    result = get_drive_time(
        origin="Riverview, FL",
        destination="St. Joseph Pediatrics, FL",
        arrival_time="2026-03-18T10:00:00",
    )

    assert result["error"] is None
    assert result["duration_minutes"] == 25   # uses traffic-aware duration
    assert result["traffic_aware"] is True
    assert result["leave_by"] is not None     # should have a leave_by time
    assert "PM" in result["leave_by"] or "AM" in result["leave_by"]


@patch("agent.tools.requests.get")
def test_get_drive_time_bad_destination(mock_get):
    """Drive time tool handles unresolvable destinations gracefully."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "status": "OK",
        "rows": [{
            "elements": [{
                "status": "NOT_FOUND",
            }]
        }]
    }
    mock_get.return_value = mock_response

    result = get_drive_time(
        origin="500 Channelside Drive, Tampa, FL 33602",
        destination="Nonexistent Place XYZ 99999",
        arrival_time="2026-03-18T10:00:00",
    )

    assert result["error"] is not None
    assert result["duration_minutes"] is None
