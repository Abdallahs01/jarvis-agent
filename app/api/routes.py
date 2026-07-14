"""
HTTP routes. Deliberately thin - all decision-making lives in app/agent/.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.agent.loop import run_agent_loop
from app.api.dependencies import require_api_key
from app.api.schemas import ChatRequest, ChatResponse, ToolCallTrace
from app.rate_limiting import limiter

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/chat",
    response_model=ChatResponse,
    dependencies=[Depends(require_api_key)],
)
@limiter.limit("10/minute")
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    """
    Runs one turn of the agent loop for `body.message`, within the
    conversation identified by `body.conversation_id` (a new id is
    generated if omitted), and returns the final answer plus a trace of
    every tool call the agent made along the way.

    Protected by a static API key (see app/api/dependencies.py) and
    rate-limited to 10 requests/minute per client IP (see
    app/rate_limiting.py) — both guard against runaway usage burning
    through the Anthropic API budget, not against sophisticated abuse.

    `request: Request` is required here (unused directly) because the
    slowapi rate-limit decorator needs it to key the limit by client IP.
    """
    try:
        result = await run_agent_loop(body.message, body.conversation_id)
    except Exception as exc:
        # Anything reaching here is NOT a tool failure - those are caught
        # inside the loop and fed back to the LLM to recover from. This is
        # something unexpected, e.g. the Anthropic API being unreachable.
        # Surface it as a 502 (upstream failure) rather than a bare 500.
        logger.exception("chat_request_failed", extra={"conversation_id": body.conversation_id})
        raise HTTPException(
            status_code=502, detail=f"Agent failed to respond: {exc}"
        ) from exc

    return ChatResponse(
        conversation_id=result.conversation_id,
        response=result.response_text,
        tool_calls=[
            ToolCallTrace(
                tool_name=tc.tool_name,
                tool_input=tc.tool_input,
                tool_output=tc.tool_output,
                is_error=tc.is_error,
            )
            for tc in result.tool_calls
        ],
    )
