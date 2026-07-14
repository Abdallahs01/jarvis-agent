"""
Pydantic request/response models for the HTTP layer.

Kept separate from the agent's internal message representation
(app/agent/loop.py) on purpose: the API contract and the LLM message
format are different concerns and will likely diverge as the project
grows (e.g. adding streaming, richer trace metadata).
"""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User's natural-language input")
    conversation_id: str | None = Field(
        default=None,
        description="Groups turns into one conversation. If omitted, a new one is created.",
    )


class ToolCallTrace(BaseModel):
    """One entry per tool invocation the agent made while answering."""
    tool_name: str
    tool_input: dict
    tool_output: str
    is_error: bool = False


class ChatResponse(BaseModel):
    conversation_id: str
    response: str
    tool_calls: list[ToolCallTrace] = Field(default_factory=list)
