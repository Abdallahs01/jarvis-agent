"""
Unit tests for the web_search tool, in isolation from the agent loop.
Tavily's client method is monkeypatched so tests don't depend on
network access or a real Tavily account.
"""
import pytest
from tavily import AsyncTavilyClient

from app.tools import web_search


async def test_web_search_returns_formatted_summary(monkeypatch):
    async def fake_search(self, query, max_results=None, **kwargs):
        return {
            "results": [
                {
                    "title": "Tel Aviv weather today",
                    "content": "Sunny, 29C",
                    "url": "https://example.com/weather",
                },
                {
                    "title": "Tel Aviv forecast",
                    "content": "Clear skies expected all week",
                    "url": "https://example.com/forecast",
                },
            ]
        }

    monkeypatch.setattr(AsyncTavilyClient, "search", fake_search)

    result = await web_search.web_search("weather in Tel Aviv")

    assert "Tel Aviv weather today" in result
    assert "Sunny, 29C" in result
    assert "https://example.com/weather" in result
    # Both results should appear, not just the first.
    assert "Tel Aviv forecast" in result


async def test_web_search_no_results(monkeypatch):
    async def fake_search(self, query, max_results=None, **kwargs):
        return {"results": []}

    monkeypatch.setattr(AsyncTavilyClient, "search", fake_search)

    result = await web_search.web_search("something obscure with no hits")

    assert "No web results found" in result


async def test_web_search_propagates_errors(monkeypatch):
    async def fake_search(self, query, max_results=None, **kwargs):
        raise RuntimeError("Tavily API unavailable")

    monkeypatch.setattr(AsyncTavilyClient, "search", fake_search)

    with pytest.raises(RuntimeError):
        await web_search.web_search("anything")
