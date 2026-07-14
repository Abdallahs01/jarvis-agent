"""
Integration test for the agent loop: mocks the Anthropic call
(app.agent.loop.call_llm) so no real API key or network access is
needed, and verifies the loop correctly dispatches a tool call, feeds
the result back, and returns the LLM's final answer plus an accurate
trace.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import app.tools.base as tool_base
from app.agent import conversation_store
from app.agent.loop import run_agent_loop


def _text_block(text: str) -> SimpleNamespace:
    block = SimpleNamespace(type="text", text=text)
    block.model_dump = lambda: {"type": "text", "text": text}
    return block


def _tool_use_block(tool_id: str, name: str, tool_input: dict) -> SimpleNamespace:
    block = SimpleNamespace(type="tool_use", id=tool_id, name=name, input=tool_input)
    block.model_dump = lambda: {
        "type": "tool_use",
        "id": tool_id,
        "name": name,
        "input": tool_input,
    }
    return block


async def test_agent_loop_executes_tool_and_returns_final_answer(monkeypatch):
    tool_call = _tool_use_block("tu_1", "get_weather", {"location": "Tel Aviv"})
    resp_tool_use = SimpleNamespace(stop_reason="tool_use", content=[tool_call])
    resp_final = SimpleNamespace(stop_reason="end_turn", content=[_text_block("It's sunny.")])

    async def fake_weather(location):
        return f"Sunny in {location}"

    monkeypatch.setitem(tool_base.TOOL_FUNCTIONS, "get_weather", fake_weather)
    monkeypatch.setattr(
        "app.agent.loop.call_llm",
        AsyncMock(side_effect=[resp_tool_use, resp_final]),
    )

    result = await run_agent_loop("What's the weather in Tel Aviv?")
    conversation_store.reset(result.conversation_id)

    assert result.response_text == "It's sunny."
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "get_weather"
    assert result.tool_calls[0].tool_input == {"location": "Tel Aviv"}
    assert result.tool_calls[0].is_error is False


async def test_agent_loop_recovers_from_tool_error(monkeypatch):
    tool_call = _tool_use_block("tu_1", "broken_tool", {})
    resp_tool_use = SimpleNamespace(stop_reason="tool_use", content=[tool_call])
    resp_final = SimpleNamespace(
        stop_reason="end_turn", content=[_text_block("Sorry, that failed.")]
    )

    async def broken():
        raise TimeoutError("upstream timed out")

    monkeypatch.setitem(tool_base.TOOL_FUNCTIONS, "broken_tool", broken)
    monkeypatch.setattr(
        "app.agent.loop.call_llm",
        AsyncMock(side_effect=[resp_tool_use, resp_final]),
    )

    result = await run_agent_loop("do the broken thing")
    conversation_store.reset(result.conversation_id)

    assert result.tool_calls[0].is_error is True
    assert "failed" in result.tool_calls[0].tool_output
    # Crucially: a tool failure doesn't crash the loop — it recovers and
    # still returns the LLM's follow-up answer.
    assert result.response_text == "Sorry, that failed."


async def test_agent_loop_stops_at_iteration_cap(monkeypatch):
    tool_call = _tool_use_block("tu_1", "get_weather", {"location": "X"})
    resp_tool_use = SimpleNamespace(stop_reason="tool_use", content=[tool_call])

    async def fake_weather(location):
        return "still going"

    monkeypatch.setitem(tool_base.TOOL_FUNCTIONS, "get_weather", fake_weather)
    monkeypatch.setattr(
        "app.agent.loop.call_llm",
        AsyncMock(return_value=resp_tool_use),
    )

    result = await run_agent_loop("keep looping forever")
    conversation_store.reset(result.conversation_id)

    # Default MAX_TOOL_ITERATIONS is 5 — the loop must not run past it
    # even though the (fake) LLM keeps requesting more tool calls.
    assert len(result.tool_calls) == 5
    assert "allotted" in result.response_text


async def test_agent_loop_reuses_history_across_turns(monkeypatch):
    resp = SimpleNamespace(stop_reason="end_turn", content=[_text_block("ok")])
    monkeypatch.setattr("app.agent.loop.call_llm", AsyncMock(return_value=resp))

    first = await run_agent_loop("hello")
    await run_agent_loop("follow-up", conversation_id=first.conversation_id)

    history = conversation_store.get_history(first.conversation_id)
    conversation_store.reset(first.conversation_id)

    # 2 user turns + 2 assistant turns = 4 messages accumulated.
    assert len(history) == 4
    assert history[0]["content"] == "hello"
    assert history[2]["content"] == "follow-up"
