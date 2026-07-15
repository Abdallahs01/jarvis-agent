"""
web_search tool -- uses the Tavily Search API (free tier, no card
required; https://tavily.com), a search API purpose-built for feeding
LLM agents clean, pre-summarized results instead of raw HTML.

Design note: unlike weather.py, this uses Tavily's official async SDK
rather than a hand-rolled httpx call. Open-Meteo is a simple,
unauthenticated public GET API whose shape is easy to hand-write and
trust; Tavily's authenticated request/response contract is more
involved (auth, ranking/scoring options, response format), and the SDK
(itself built on httpx, so still fully async and non-blocking) avoids
re-implementing and maintaining that contract by hand for little
benefit.
"""
from tavily import AsyncTavilyClient

from app.config import get_settings

SCHEMA = {
    "name": "web_search",
    "description": (
        "Search the web for current information not in your training "
        "data -- news, recent events, prices, docs, or anything that may "
        "have changed. Returns a handful of summarized results with "
        "source URLs."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            }
        },
        "required": ["query"],
    },
}


async def web_search(query: str) -> str:
    """
    Runs a Tavily search and returns a compact text summary (title,
    snippet, source URL per result) for the LLM to read and cite.

    Raises on network failure or a missing/invalid API key -- caught by
    the agent loop (app/agent/loop.py) and turned into a recoverable
    tool-error message rather than crashing the request.
    """
    settings = get_settings()
    client = AsyncTavilyClient(api_key=settings.tavily_api_key)

    response = await client.search(query, max_results=4)
    results = response.get("results", [])

    if not results:
        return f"No web results found for '{query}'."

    lines = [f"- {r['title']}: {r['content']} (source: {r['url']})" for r in results]
    return "\n".join(lines)
