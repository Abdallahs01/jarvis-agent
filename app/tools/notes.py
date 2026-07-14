"""
save_note / get_notes tools — simple SQLite-backed memory so the agent
can persist and recall short notes within and across conversations.

Uses short-lived aiosqlite connections per call rather than one shared
connection — simpler to reason about for a single-process app, and
opening a SQLite connection is cheap.
"""
import aiosqlite

from app.config import get_settings

SCHEMA_SAVE = {
    "name": "save_note",
    "description": "Save a short note to persistent memory for later recall.",
    "input_schema": {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "The note text to save."}
        },
        "required": ["content"],
    },
}

SCHEMA_GET = {
    "name": "get_notes",
    "description": "Retrieve all previously saved notes, most recent first.",
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}


async def save_note(content: str) -> str:
    if not content.strip():
        raise ValueError("Note content cannot be empty.")

    settings = get_settings()
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute("INSERT INTO notes (content) VALUES (?)", (content,))
        await db.commit()

    return f"Saved note: {content!r}"


async def get_notes() -> str:
    settings = get_settings()
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT content, created_at FROM notes ORDER BY id DESC"
        )
        rows = await cursor.fetchall()

    if not rows:
        return "No notes saved yet."

    return "\n".join(f"- [{row['created_at']}] {row['content']}" for row in rows)
