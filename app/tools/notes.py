"""
save_note / get_notes / update_note / delete_note tools — simple
SQLite-backed memory so the agent can persist, recall, edit, and remove
short notes within and across conversations.

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
    "description": (
        "Retrieve all previously saved notes, most recent first. Each "
        "note is shown with its numeric id, which you'll need to pass to "
        "update_note or delete_note."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}

SCHEMA_UPDATE = {
    "name": "update_note",
    "description": (
        "Replace the content of an existing note, identified by its id. "
        "Call get_notes first if you don't already know the id."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "note_id": {
                "type": "integer",
                "description": "The id of the note to update (from get_notes).",
            },
            "content": {
                "type": "string",
                "description": "The new text to replace the note's content with.",
            },
        },
        "required": ["note_id", "content"],
    },
}

SCHEMA_DELETE = {
    "name": "delete_note",
    "description": (
        "Permanently delete a note, identified by its id. Call get_notes "
        "first if you don't already know the id."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "note_id": {
                "type": "integer",
                "description": "The id of the note to delete (from get_notes).",
            },
        },
        "required": ["note_id"],
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
            "SELECT id, content, created_at FROM notes ORDER BY id DESC"
        )
        rows = await cursor.fetchall()

    if not rows:
        return "No notes saved yet."

    return "\n".join(
        f"- [id={row['id']}, {row['created_at']}] {row['content']}" for row in rows
    )


async def update_note(note_id: int, content: str) -> str:
    if not content.strip():
        raise ValueError("Note content cannot be empty.")

    settings = get_settings()
    async with aiosqlite.connect(settings.database_path) as db:
        cursor = await db.execute(
            "UPDATE notes SET content = ? WHERE id = ?", (content, note_id)
        )
        await db.commit()

    if cursor.rowcount == 0:
        raise ValueError(f"No note found with id {note_id}.")

    return f"Updated note {note_id}."


async def delete_note(note_id: int) -> str:
    settings = get_settings()
    async with aiosqlite.connect(settings.database_path) as db:
        cursor = await db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        await db.commit()

    if cursor.rowcount == 0:
        raise ValueError(f"No note found with id {note_id}.")

    return f"Deleted note {note_id}."
