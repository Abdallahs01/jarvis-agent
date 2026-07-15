# Jarvis

A tool-calling AI agent backend built with FastAPI and the Claude API. Given a natural-language request, the agent decides which tool(s) to call, executes them, and returns a coherent final answer - the standard "ReAct-style" agent loop, implemented from scratch (no LangChain/agent framework) to make the control flow explicit.

**Live demo:** https://jarvis-agent-z2ox.onrender.com (see "Trying the live demo" below - needs an API key, and the free instance sleeps after 15 min idle, so the first request can take up to a minute to wake it up).

## Project phases

- **Phase 1 (done):** core agent loop, two tools (`get_weather`, `save_note`/`get_notes`), in-memory conversation history, tests.
- **Phase 4 (done):** production hardening - structured logging, API key auth, rate limiting, Docker, live deployment. Built before Phases 2-3 because a hardened live demo is more valuable for job applications than a longer tool list.
- **Phase 2 (done):** more tools - `web_search` (via Tavily) and `update_note`/`delete_note`, closing the "read and write but never edit" gap from Phase 1.
- **Phase 3 (planned):** conversation history persisted across restarts (currently in-memory only - see tradeoffs below).
- **Phase 5 (stretch):** long-term/semantic memory, a minimal frontend.

## Tools

- `get_weather(location)` - current conditions via Open-Meteo (free, no key).
- `save_note(content)` / `get_notes()` - SQLite-backed memory; `get_notes()` lists each note with a numeric id.
- `update_note(note_id, content)` / `delete_note(note_id)` - edit or remove a note by the id shown in `get_notes()`.
- `web_search(query)` - current web information via Tavily (free tier, no card), returning a handful of summarized, cited results.

## Setup (local)

```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

cp .env.example .env
# edit .env and set:
#   ANTHROPIC_API_KEY - from console.anthropic.com
#   API_KEY           - any random string you choose (protects your own
#                        /chat endpoint, unrelated to the Anthropic key;
#                        generate one with:
#                        python -c "import secrets; print(secrets.token_urlsafe(32))")
#   TAVILY_API_KEY    - from tavily.com (free tier, no card, used by web_search)

uvicorn app.main:app --reload
```

Test it (PowerShell):

```powershell
$body = '{"message": "What is the weather in Tel Aviv?"}'
Invoke-RestMethod -Uri http://localhost:8000/chat -Method Post -ContentType "application/json" -Headers @{"X-API-Key"="your-api-key-from-env"} -Body $body
```

Test it (curl / bash):

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-from-env" \
  -d '{"message": "What'\''s the weather in Tel Aviv?"}'
```

Run tests (no real API keys needed - the LLM call and the Tavily client are both mocked):

```bash
pytest
```

## Trying the live demo

```powershell
$body = '{"message": "What is the weather in Tel Aviv?"}'
Invoke-RestMethod -Uri https://jarvis-agent-z2ox.onrender.com/chat -Method Post -ContentType "application/json" -Headers @{"X-API-Key"="<ask for a demo key>"} -Body $body
```

`/health` is unauthenticated and cheap to poll if you just want to confirm the instance is awake:

```powershell
Invoke-RestMethod -Uri https://jarvis-agent-z2ox.onrender.com/health
```

## Running with Docker

```bash
docker build -t jarvis .
docker run -p 8000:8000 --env-file .env jarvis
```

## Architecture

```
Request -> API key check -> rate limit check -> agent loop -> [LLM decides: answer, or call a tool?]
                                                                    |
                                                                    v
                                                          tool registry executes it
                                                                    |
                                                                    v
                                                      result fed back into message history
                                                                    |
                                                                    v
                                                          LLM sees result -> repeat or finish
```

**API layer** (`app/api/`) is intentionally dumb: it validates the HTTP request, checks auth, calls into the agent, and shapes the response. No agent decision-making happens here.

**Agent loop** (`app/agent/loop.py`) is the core: it sends the conversation + tool schemas to Claude, and if Claude requests a tool call, executes it via the tool registry and appends the result back into history, repeating until Claude returns a final text answer or a hard iteration cap (default 5, via `MAX_TOOL_ITERATIONS`) is hit. `llm_client.py` isolates the actual Anthropic SDK call so the loop logic can be unit-tested without hitting a real API. Every tool call and turn outcome is logged as structured JSON (see `app/logging_config.py`) through the single `_execute_tool()` choke point.

**Tools** (`app/tools/`) are self-contained: each module exports a JSON schema (Anthropic's `tools` format) and a plain function. `base.py` builds a registry from them. Adding a tool means writing a module and registering it - the loop never changes, and it's automatically covered by the existing auth/rate-limit/logging since those all wrap the single `/chat` route, not individual tools. `tests/test_tool_registry.py` guards against a schema/function registration mismatch.

**Conversation state** (`app/agent/conversation_store.py`) is a plain in-memory dict keyed by `conversation_id`. Deliberate simplification: history is lost on restart (and on Render's free tier, on every sleep/wake cycle) and isn't shared across worker processes. Fine for a demo; Phase 3 swaps in persistent storage behind the same interface.

**Persistence** for the notes tools uses SQLite directly via `aiosqlite` (no ORM - one table doesn't justify one). `get_notes()` exposes each row's id specifically so the LLM can reference it in a later `update_note`/`delete_note` call. On Render's free tier this resets on redeploy since there's no attached persistent volume.

**Auth** (`app/api/dependencies.py`) is a single static API key checked via the `X-API-Key` header on `/chat`. `/health` is deliberately left open for hosting-platform health probes.

**Rate limiting** (`app/rate_limiting.py`) uses `slowapi` with an in-memory backend, capped at 10 requests/minute per client IP on `/chat`.

## Design decisions & tradeoffs

- **Model**: defaults to `claude-haiku-4-5-20251001` for low latency on simple tool-routing decisions; swappable via `.env` if a task needs stronger reasoning.
- **Hand-written tool schemas** rather than auto-derived from Python type hints - more boilerplate, but explicit and easy to reason about/explain, with no hidden magic.
- **Async throughout**: the weather and search calls use async HTTP clients, SQLite access goes through `aiosqlite`, so a slow tool call never blocks the event loop.
- **Tool errors are recoverable, not fatal**: a failing tool call produces an `is_error` tool result fed back to the LLM (it can retry, use another tool, or explain the failure to the user) rather than crashing the request.
- **`web_search` uses Tavily's official SDK, not a hand-rolled HTTP call** (unlike the weather tool). Open-Meteo is a simple, unauthenticated public API whose shape is trivial to hand-write; Tavily's authenticated request/response contract is more involved, and its SDK is itself async (built on `httpx`), so using it doesn't cost us the "async throughout" property - it just avoids re-implementing and maintaining an auth contract by hand for no real benefit.
- **Auth is a single static key, not a user-account system.** Appropriate for a single-operator demo (stops randoms from burning your Anthropic credit); a real multi-user product would swap this dependency for OAuth2/JWT without touching any other code.
- **Rate limiting is in-memory and per-IP**, not per-tenant or Redis-backed. Resets on restart and doesn't coordinate across multiple instances - a non-issue on a single free-tier Render instance, and the same tradeoff already accepted for conversation state. Redis-backed storage is `slowapi`'s documented upgrade path if this ever runs multi-instance.
- **Structured (JSON) logging** over freeform text, so logs are immediately parseable by log aggregators (or just `jq` on Render's log viewer) without a heavier dependency like `structlog`.
- **SQLite with no persistent volume on Render's free tier** - notes and conversation history reset on redeploy/sleep. Acceptable for a demo; a real deployment would attach a Render Disk or move to managed Postgres.

## Out of scope (planned for later phases)

Calendar integration, persistent conversation history across restarts, vector/long-term memory, voice I/O, frontend UI, multi-user auth.
