"""
The core tool-calling loop.

Standard flow:
  1. send conversation history + tool schemas to Claude
  2. if Claude's stop_reason is "tool_use", execute each requested tool
     and feed the result(s) back as a "tool_result" message
  3. repeat until Claude returns a plain text answer, or a hard iteration
     cap is hit (guards against runaway tool-call cycles)
"""
import logging
import time
from dataclasses import dataclass, field

from app.agent import conversation_store
from app.agent.llm_client import call_llm
from app.config import get_settings
from app.tools.base import TOOL_FUNCTIONS, TOOL_SCHEMAS

logger = logging.getLogger(__name__)


@dataclass
class ToolCallRecord:
    """One tool invocation, for the trace returned to the caller."""
    tool_name: str
    tool_input: dict
    tool_output: str
    is_error: bool = False


@dataclass
class AgentResult:
    conversation_id: str
    response_text: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


async def run_agent_loop(message: str, conversation_id: str | None = None) -> AgentResult:
    settings = get_settings()

    if conversation_id is None:
        conversation_id = conversation_store.new_conversation_id()

    logger.info(
        "agent_turn_started",
        extra={"conversation_id": conversation_id, "message_length": len(message)},
    )

    history = conversation_store.get_history(conversation_id)
    history.append({"role": "user", "content": message})

    trace: list[ToolCallRecord] = []

    for iteration in range(settings.max_tool_iterations):
        response = await call_llm(messages=history, tools=TOOL_SCHEMAS)

        # Store the assistant's turn as plain dicts (not SDK model
        # instances) so history stays a clean, JSON-serializable list —
        # important once Phase 3 persists it to disk.
        history.append({
            "role": "assistant",
            "content": [block.model_dump() for block in response.content],
        })

        if response.stop_reason != "tool_use":
            logger.info(
                "agent_turn_finished",
                extra={
                    "conversation_id": conversation_id,
                    "iterations_used": iteration + 1,
                    "tool_call_count": len(trace),
                },
            )
            return AgentResult(conversation_id, _extract_text(response.content), trace)

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            output, is_error = await _execute_tool(block.name, block.input)
            trace.append(ToolCallRecord(block.name, block.input, output, is_error))
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": output,
                "is_error": is_error,
            })

        history.append({"role": "user", "content": tool_results})

    # Iteration cap hit — return what we have instead of looping forever.
    logger.warning(
        "agent_turn_hit_iteration_cap",
        extra={
            "conversation_id": conversation_id,
            "max_tool_iterations": settings.max_tool_iterations,
            "tool_call_count": len(trace),
        },
    )
    return AgentResult(
        conversation_id,
        "I wasn't able to finish within the allotted number of tool-call "
        "steps. Here's what I found so far — try rephrasing or breaking "
        "the request into smaller parts.",
        trace,
    )


async def _execute_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Runs a single tool call, catching any exception so a bad tool
    invocation (bad input, network timeout, ...) becomes a recoverable
    message fed back to the LLM rather than an unhandled crash."""
    func = TOOL_FUNCTIONS.get(name)
    start = time.perf_counter()

    if func is None:
        logger.warning("tool_call_unknown", extra={"tool_name": name})
        return f"Unknown tool: {name}", True

    try:
        result = await func(**tool_input)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.info(
            "tool_call_succeeded",
            extra={"tool_name": name, "duration_ms": duration_ms},
        )
        return str(result), False
    except Exception as exc:  # noqa: BLE001 — intentionally broad: any
        # failure inside a tool must degrade to a message the LLM can
        # react to, never bubble up and crash the request.
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.warning(
            "tool_call_failed",
            extra={"tool_name": name, "duration_ms": duration_ms, "error": str(exc)},
        )
        return f"Tool '{name}' failed: {exc}", True


def _extract_text(content_blocks) -> str:
    """Concatenates the text blocks of a Claude response. A tool-use-only
    response (no text block) falls back to an empty string rather than
    raising, though this shouldn't occur once stop_reason != 'tool_use'."""
    return "".join(block.text for block in content_blocks if block.type == "text")
