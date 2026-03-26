"""
agent/tools.py — Tool functions the LLM agent can call.

Each function here maps directly to a tool definition in agent.py.
Keep these pure and testable — no LLM logic in here, just API calls
that return clean structured data.
"""

import logging
import os
import requests
from datetime import datetime
from config import settings

log = logging.getLogger(__name__)


# ── Weather ───────────────────────────────────────────────────────────────────

def get_weather(date: str, location: str) -> dict:
    """
    Get weather forecast for a given date and location.

    Args:
        date:     ISO date string e.g. "2026-03-15"
        location: City name or address e.g. "Riverview, FL"

    Returns:
        dict with temp_f, condition, precipitation_chance, wind_mph, summary
    """
    log.info(f"Fetching weather for {location} on {date}")

    try:
        # Step 1: Geocode location → lat/lon
        geo_query = location
        if ", US" not in geo_query and ", USA" not in geo_query:
            geo_query += ", US"
        geo_url = "http://api.openweathermap.org/geo/1.0/direct"
        geo_resp = requests.get(geo_url, params={
            "q": geo_query,
            "limit": 1,
            "appid": settings.openweather_api_key,
        }, timeout=10)
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()

        if not geo_data:
            return _weather_error(f"Could not geocode location: {location}")

        lat = geo_data[0]["lat"]
        lon = geo_data[0]["lon"]

        # Step 2: Fetch 5-day forecast (free tier — no hourly history)
        forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
        forecast_resp = requests.get(forecast_url, params={
            "lat": lat,
            "lon": lon,
            "appid": settings.openweather_api_key,
            "units": "imperial",    # Fahrenheit
            "cnt": 40,              # max forecast entries (5 days x 8 per day)
        }, timeout=10)
        forecast_resp.raise_for_status()
        forecast_data = forecast_resp.json()

        # Step 3: Find the forecast entry closest to the requested date
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
        best_entry = _find_closest_forecast(forecast_data["list"], target_date)

        if not best_entry:
            return _weather_error(f"No forecast available for {date} (only 5 days out)")

        # Step 4: Extract and return clean fields
        temp_f = best_entry["main"]["temp"]
        feels_like_f = best_entry["main"]["feels_like"]
        condition = best_entry["weather"][0]["description"].capitalize()
        precipitation_chance = int(best_entry.get("pop", 0) * 100)  # pop = probability of precipitation
        wind_mph = best_entry["wind"]["speed"]
        humidity = best_entry["main"]["humidity"]

        summary = _build_weather_summary(temp_f, condition, precipitation_chance, wind_mph)

        return {
            "location": location,
            "date": date,
            "temp_f": round(temp_f),
            "feels_like_f": round(feels_like_f),
            "condition": condition,
            "precipitation_chance": precipitation_chance,
            "wind_mph": round(wind_mph, 1),
            "humidity_pct": humidity,
            "summary": summary,
            "error": None,
        }

    except requests.RequestException as e:
        log.error(f"Weather API request failed: {e}")
        return _weather_error(str(e))
    except Exception as e:
        log.error(f"Unexpected error fetching weather: {e}")
        return _weather_error(str(e))


def _find_closest_forecast(entries: list, target_date) -> dict | None:
    """Find the forecast entry closest to noon on the target date."""
    target_noon = datetime.combine(target_date, datetime.min.time().replace(hour=12))
    best = None
    best_diff = float("inf")

    for entry in entries:
        entry_dt = datetime.fromtimestamp(entry["dt"])
        diff = abs((entry_dt - target_noon).total_seconds())
        if diff < best_diff:
            best_diff = diff
            best = entry

    return best


def _build_weather_summary(temp_f: float, condition: str, precip_pct: int, wind_mph: float) -> str:
    """Build a human-readable weather summary for the agent to reason about."""
    parts = [f"{round(temp_f)}°F, {condition}"]

    if precip_pct >= 50:
        parts.append(f"high chance of rain ({precip_pct}%)")
    elif precip_pct >= 25:
        parts.append(f"possible rain ({precip_pct}%)")

    if wind_mph >= 20:
        parts.append(f"windy ({round(wind_mph)} mph)")

    if temp_f <= 40:
        parts.append("dress warmly")
    elif temp_f >= 90:
        parts.append("very hot, bring water")

    return ". ".join(parts) + "."


def _weather_error(message: str) -> dict:
    return {
        "location": None, "date": None, "temp_f": None, "feels_like_f": None,
        "condition": None, "precipitation_chance": None, "wind_mph": None,
        "humidity_pct": None, "summary": f"Weather unavailable: {message}",
        "error": message,
    }


# ── Drive Time ────────────────────────────────────────────────────────────────

def get_drive_time(origin: str, destination: str, arrival_time: str) -> dict:
    """
    Get drive time estimate between two locations.

    Args:
        origin:       Starting address e.g. "Riverview, FL"
        destination:  Destination address e.g. "Riverview Sports Complex, FL"
        arrival_time: Optional ISO datetime string e.g. "2026-03-15T16:00:00"
                      If provided, Google Maps factors in expected traffic at that time.

    Returns:
        dict with duration_minutes, distance_miles, summary, leave_by
    """
    log.info(f"Fetching drive time from '{origin}' to '{destination}'")

    try:
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"

        params = {
            "origins": origin,
            "destinations": destination,
            "units": "imperial",
            "key": settings.google_maps_api_key,
        }

        if arrival_time:
            arrival_dt = datetime.fromisoformat(arrival_time)
            from datetime import timedelta
            estimated_departure = arrival_dt - timedelta(minutes=45)
            params["departure_time"] = int(estimated_departure.timestamp())
            params["traffic_model"] = "best_guess"

        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # Parse response
        if data["status"] != "OK":
            return _drive_time_error(f"API status: {data['status']}")

        element = data["rows"][0]["elements"][0]
        if element["status"] != "OK":
            return _drive_time_error(f"Route status: {element['status']} — check addresses")

        # Prefer duration_in_traffic if available (requires departure_time)
        duration_key = "duration_in_traffic" if "duration_in_traffic" in element else "duration"
        duration_seconds = element[duration_key]["value"]
        duration_minutes = round(duration_seconds / 60)

        distance_text = element["distance"]["text"]          # e.g. "8.3 mi"
        distance_miles = float(distance_text.replace(" mi", "").replace(",", ""))

        # Calculate leave_by time if arrival_time was given
        leave_by = None
        if arrival_time:
            arrival_dt = datetime.fromisoformat(arrival_time)
            from datetime import timedelta
            leave_dt = arrival_dt - timedelta(minutes=duration_minutes + 10)  # +10 min buffer
            leave_by = leave_dt.strftime("%-I:%M %p")   # e.g. "3:35 PM"

        summary = _build_drive_summary(origin, destination, duration_minutes, distance_miles, leave_by)

        return {
            "origin": origin,
            "destination": destination,
            "duration_minutes": duration_minutes,
            "distance_miles": distance_miles,
            "leave_by": leave_by,
            "traffic_aware": "duration_in_traffic" in element,
            "summary": summary,
            "error": None,
        }

    except requests.RequestException as e:
        log.error(f"Drive time API request failed: {e}")
        return _drive_time_error(str(e))
    except Exception as e:
        log.error(f"Unexpected error fetching drive time: {e}")
        return _drive_time_error(str(e))


def _build_drive_summary(origin, destination, duration_minutes, distance_miles, leave_by) -> str:
    """Build a human-readable drive time summary for the agent."""
    summary = f"{duration_minutes} min drive ({distance_miles} miles) from {origin} to {destination}"
    if leave_by:
        summary += f". Leave by {leave_by} to arrive on time."
    return summary


def _drive_time_error(message: str) -> dict:
    return {
        "origin": None, "destination": None, "duration_minutes": None,
        "distance_miles": None, "leave_by": None, "traffic_aware": False,
        "summary": f"Drive time unavailable: {message}", "error": message,
    }
