"""
Thin wrapper around the Anthropic SDK. Isolating this here means:
  - the agent loop doesn't import `anthropic` directly (easy to mock in tests
    by patching app.agent.llm_client.call_llm)
  - swapping model providers later touches one file, not the loop logic
"""
from functools import lru_cache

from anthropic import AsyncAnthropic
from anthropic.types import Message

from app.config import get_settings

DEFAULT_SYSTEM_PROMPT = (
    "You are Jarvis, a helpful assistant with access to tools for checking "
    "current weather and saving/retrieving notes. Use a tool whenever it "
    "would give a more accurate or current answer than you could give from "
    "memory alone. If a tool call fails, explain the failure plainly and, "
    "if there's a sensible alternate approach, try it instead of giving up "
    "silently."
)


@lru_cache
def _get_client() -> AsyncAnthropic:
    """Cached so the process reuses one HTTP connection pool instead of
    opening a new client per request — matters for latency under repeated
    use."""
    settings = get_settings()
    return AsyncAnthropic(api_key=settings.anthropic_api_key)


async def call_llm(messages: list[dict], tools: list[dict]) -> Message:
    """
    Single call to Claude with the current conversation + tool schemas.

    Returns the raw SDK Message so the agent loop can inspect
    `stop_reason` and content blocks directly — deliberately not wrapped
    further, to keep one less abstraction to maintain.
    """
    settings = get_settings()
    client = _get_client()
    return await client.messages.create(
        model=settings.llm_model,
        max_tokens=1024,
        system=DEFAULT_SYSTEM_PROMPT,
        messages=messages,
        tools=tools,
    )
