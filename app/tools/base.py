"""
Tool registry: maps a tool name to its callable and JSON schema.

Each tool module (weather.py, notes.py, ...) exports a SCHEMA dict (or
several) matching Anthropic's `tools` parameter format, plus a matching
async function. This module collects them into one place the agent loop
can query, rather than the loop importing each tool module directly —
adding a new tool later means writing the module and registering it
here, not touching loop.py.
"""
from app.tools import notes, weather, web_search

TOOL_SCHEMAS: list[dict] = [
    weather.SCHEMA,
    notes.SCHEMA_SAVE,
    notes.SCHEMA_GET,
    notes.SCHEMA_UPDATE,
    notes.SCHEMA_DELETE,
    web_search.SCHEMA,
]

TOOL_FUNCTIONS: dict = {
    "get_weather": weather.get_weather,
    "save_note": notes.save_note,
    "get_notes": notes.get_notes,
    "update_note": notes.update_note,
    "delete_note": notes.delete_note,
    "web_search": web_search.web_search,
}
