"""
get_weather tool — calls Open-Meteo (free, no API key required) for
current conditions at a named location.

Two-step call: geocode the location name to lat/lon, then fetch current
weather for those coordinates. Both are public, unauthenticated JSON APIs.
"""
import httpx

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Keep this short — a slow weather provider shouldn't stall the whole
# agent loop. If it times out, the exception propagates up and the loop
# turns it into a recoverable tool-error message for the LLM.
_TIMEOUT = httpx.Timeout(10.0)

# WMO weather codes -> human-readable text (common subset; unmapped codes
# fall back to showing the raw code rather than failing).
_WEATHER_CODES = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    95: "thunderstorm",
}

SCHEMA = {
    "name": "get_weather",
    "description": (
        "Get current weather conditions for a named location. Use this "
        "whenever the user asks about weather — it's always more current "
        "than anything in your training data."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "Location name, e.g. 'Tel Aviv' or 'Paris, France'.",
            }
        },
        "required": ["location"],
    },
}


async def get_weather(location: str) -> str:
    """
    Geocodes `location`, then returns a one-line current-conditions
    summary. Raises ValueError for an unresolvable location, or an
    httpx exception on network/timeout failure — both are caught by the
    agent loop (app/agent/loop.py) and turned into a recoverable
    tool-error message rather than crashing the request.
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        geo_resp = await client.get(GEOCODING_URL, params={"name": location, "count": 1})
        geo_resp.raise_for_status()
        results = geo_resp.json().get("results")

        if not results:
            raise ValueError(f"Could not find a location matching '{location}'")

        place = results[0]
        lat, lon = place["latitude"], place["longitude"]
        display_name = ", ".join(
            part for part in (place.get("name"), place.get("admin1"), place.get("country")) if part
        )

        weather_resp = await client.get(
            FORECAST_URL,
            params={"latitude": lat, "longitude": lon, "current_weather": "true"},
        )
        weather_resp.raise_for_status()
        current = weather_resp.json()["current_weather"]

    condition = _WEATHER_CODES.get(current["weathercode"], f"weather code {current['weathercode']}")
    return (
        f"{display_name}: {current['temperature']}°C, {condition}, "
        f"wind {current['windspeed']} km/h"
    )
