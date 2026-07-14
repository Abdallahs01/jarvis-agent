"""
Unit tests for the get_weather tool, in isolation from the agent loop.
Open-Meteo's HTTP calls are faked so tests don't depend on network access
or the real API's current data.
"""
import httpx
import pytest

from app.tools import weather

GEO_RESPONSE = {
    "results": [
        {
            "name": "Tel Aviv",
            "admin1": "Tel Aviv District",
            "country": "Israel",
            "latitude": 32.08,
            "longitude": 34.78,
        }
    ]
}
FORECAST_RESPONSE = {
    "current_weather": {
        "temperature": 29.4,
        "windspeed": 12.3,
        "weathercode": 1,
        "time": "2026-07-08T12:00",
    }
}


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


async def test_get_weather_returns_readable_summary(monkeypatch):
    async def fake_get(self, url, params=None):
        if "geocoding" in url:
            return _FakeResponse(GEO_RESPONSE)
        return _FakeResponse(FORECAST_RESPONSE)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    result = await weather.get_weather("Tel Aviv")

    assert "Tel Aviv" in result
    assert "29.4" in result
    assert "mainly clear" in result


async def test_get_weather_unmapped_code_falls_back_to_raw_code(monkeypatch):
    forecast = {"current_weather": {**FORECAST_RESPONSE["current_weather"], "weathercode": 999}}

    async def fake_get(self, url, params=None):
        if "geocoding" in url:
            return _FakeResponse(GEO_RESPONSE)
        return _FakeResponse(forecast)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    result = await weather.get_weather("Tel Aviv")

    assert "weather code 999" in result


async def test_get_weather_unknown_location_raises_value_error(monkeypatch):
    async def fake_get(self, url, params=None):
        return _FakeResponse({"results": []})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    with pytest.raises(ValueError, match="Could not find a location"):
        await weather.get_weather("Nowheresville")


async def test_get_weather_propagates_http_errors(monkeypatch):
    async def fake_get(self, url, params=None):
        request = httpx.Request("GET", url)
        raise httpx.TimeoutException("connect timed out", request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    with pytest.raises(httpx.TimeoutException):
        await weather.get_weather("Tel Aviv")
