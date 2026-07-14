# Jarvis

A tool-calling AI agent backend built with FastAPI and the Claude API. Given a natural-language request, the agent decides which tool(s) to call, executes them, and returns a coherent final answer — the standard "ReAct-style" agent loop, implemented from scratch (no LangChain/agent framework) to make the control flow explicit.

This is Phase 1: a single `/chat` endpoint, two real tools, in-memory conversation state. Later phases add persistence, more tools, and eventually a frontend.

## Setup

```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY

uvicorn app.main:app --reload
```

Test it:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What'\''s the weather in Tel Aviv?"}'
```

Run tests:

```bash
pytest
```

## Architecture

```
Request → /chat → agent loop → [LLM decides: answer, or call a tool?]
                                        │
                                        ▼
                              tool registry executes it
                                        │
                                        ▼
                          result fed back into message history
                                        │
                                        ▼
                              LLM sees result → repeat or finish
```

**API layer** (`app/api/`) is intentionally dumb: it validates the HTTP request, calls into the agent, and shapes the response. No decision-making happens here.

**Agent loop** (`app/agent/loop.py`) is the core: it sends the conversation + tool schemas to Claude, and if Claude requests a tool call, executes it via the tool registry and appends the result back into history, repeating until Claude returns a final text answer or a hard iteration cap (default 5, via `MAX_TOOL_ITERATIONS`) is hit. `llm_client.py` isolates the actual Anthropic SDK call so the loop logic can be unit-tested without hitting a real API.

**Tools** (`app/tools/`) are self-contained: each module exports a JSON schema (Anthropic's `tools` format) and a plain function. `base.py` builds a registry from them. Adding a tool means writing a module and registering it — the loop never changes.

**Conversation state** (`app/agent/conversation_store.py`) is a plain in-memory dict keyed by `conversation_id`. This is a deliberate Phase 1 simplification: history is lost on restart and isn't shared across worker processes. Fine for a single-process local demo; Phase 3 swaps in persistent storage behind the same interface.

**Persistence** for the `save_note`/`get_notes` tool uses SQLite directly via `aiosqlite` (no ORM — one table doesn't justify one).

## Design decisions & tradeoffs

- **Model**: defaults to `claude-haiku-4-5-20251001` for low latency on simple tool-routing decisions; swappable via `.env` if a task needs stronger reasoning.
- **Hand-written tool schemas** rather than auto-derived from Python type hints — more boilerplate, but explicit and easy to reason about/explain, with no hidden magic.
- **Async throughout**: the weather call uses `httpx.AsyncClient`, SQLite access goes through `aiosqlite`/a thread pool, so a slow tool call never blocks the event loop.
- **Tool errors are recoverable, not fatal**: a failing tool call produces an `is_error` tool result fed back to the LLM (it can retry, use another tool, or explain the failure to the user) rather than crashing the request.

## Out of scope for Phase 1

Calendar integration, web search, vector/long-term memory, voice I/O, auth, rate limiting, deployment config, frontend UI. See project notes for the full phased roadmap.
