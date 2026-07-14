"""
Integration test for the HTTP layer itself: POST /chat end-to-end
through FastAPI's TestClient, with the LLM call mocked. Checks that the
route correctly shapes the agent's result into the ChatResponse contract
(conversation_id, response text, tool call trace), and that the Phase 4
protections (API key auth, rate limiting) actually work.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

import app.tools.base as tool_base
from app.main import app
from tests.conftest import TEST_API_KEY

AUTH_HEADERS = {"X-API-Key": TEST_API_KEY}


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


def test_chat_endpoint_returns_answer_and_tool_trace(monkeypatch):
    tool_call = _tool_use_block("tu_1", "get_weather", {"location": "Tel Aviv"})
    resp_tool_use = SimpleNamespace(stop_reason="tool_use", content=[tool_call])
    resp_final = SimpleNamespace(
        stop_reason="end_turn", content=[_text_block("It is sunny in Tel Aviv.")]
    )

    async def fake_weather(location):
        return f"Sunny in {location}, 27C"

    monkeypatch.setitem(tool_base.TOOL_FUNCTIONS, "get_weather", fake_weather)
    monkeypatch.setattr(
        "app.agent.loop.call_llm",
        AsyncMock(side_effect=[resp_tool_use, resp_final]),
    )

    client = TestClient(app)
    response = client.post("/chat", json={"message": "weather in Tel Aviv?"}, headers=AUTH_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["response"] == "It is sunny in Tel Aviv."
    assert body["conversation_id"]
    assert body["tool_calls"] == [
        {
            "tool_name": "get_weather",
            "tool_input": {"location": "Tel Aviv"},
            "tool_output": "Sunny in Tel Aviv, 27C",
            "is_error": False,
        }
    ]


def test_chat_endpoint_rejects_empty_message():
    client = TestClient(app)
    response = client.post("/chat", json={"message": ""}, headers=AUTH_HEADERS)

    assert response.status_code == 422  # Pydantic min_length validation


def test_chat_endpoint_requires_api_key_header():
    """No X-API-Key header at all -> FastAPI's own request validation
    rejects it before our code even runs (422, not 401)."""
    client = TestClient(app)
    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 422


def test_chat_endpoint_rejects_wrong_api_key():
    """Header present but wrong -> our dependency explicitly rejects it
    with 401."""
    client = TestClient(app)
    response = client.post(
        "/chat", json={"message": "hello"}, headers={"X-API-Key": "not-the-real-key"}
    )

    assert response.status_code == 401


def test_chat_endpoint_rate_limits_after_threshold(monkeypatch):
    """The 11th request within a minute from the same client should be
    rejected with 429 -- proves the rate limiter is actually wired up,
    not just configured and unused."""
    resp = SimpleNamespace(stop_reason="end_turn", content=[_text_block("ok")])
    monkeypatch.setattr("app.agent.loop.call_llm", AsyncMock(return_value=resp))

    client = TestClient(app)
    statuses = [
        client.post("/chat", json={"message": f"hi {i}"}, headers=AUTH_HEADERS).status_code
        for i in range(11)
    ]

    assert statuses[:10] == [200] * 10
    assert statuses[10] == 429


def test_health_check():
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
