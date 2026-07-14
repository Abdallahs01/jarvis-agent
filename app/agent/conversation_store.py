"""
In-memory, per-process conversation history.

Phase 1 tradeoff (flagged explicitly, see README): a plain dict keyed by
conversation_id means history is lost on restart and isn't shared across
multiple worker processes. Acceptable for a single-process local demo;
Phase 3 swaps this for persistent storage behind the same three functions
below, so nothing above this layer needs to change.
"""
import uuid

# conversation_id -> list of Anthropic-format message dicts:
# {"role": "user" | "assistant", "content": str | list[dict]}
_conversations: dict[str, list[dict]] = {}


def new_conversation_id() -> str:
    return str(uuid.uuid4())


def get_history(conversation_id: str) -> list[dict]:
    """Returns the message list for this conversation, creating it if new.
    Returns the live list (not a copy) — callers append to it in place.
    Fine for Phase 1: single process, one writer per conversation_id at a
    time (no concurrent requests against the same conversation)."""
    return _conversations.setdefault(conversation_id, [])


def reset(conversation_id: str) -> None:
    """Drops a conversation's history. Used by tests to isolate cases."""
    _conversations.pop(conversation_id, None)
