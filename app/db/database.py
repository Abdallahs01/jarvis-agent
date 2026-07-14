"""
SQLite setup for the notes tool.

Deliberately using the stdlib sqlite3 module (via aiosqlite for the async
wrapper) rather than an ORM — one table doesn't justify SQLAlchemy, and it
keeps the dependency list small for a portfolio project.
"""
import aiosqlite

from app.config import get_settings

_CREATE_NOTES_TABLE = """
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


async def init_db() -> None:
    """Create the notes table if it doesn't exist yet. Called once on
    FastAPI startup (see app/main.py lifespan)."""
    settings = get_settings()
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(_CREATE_NOTES_TABLE)
        await db.commit()


# NOTE (Task #4): tools/notes.py will open its own short-lived connections
# per call rather than sharing one long-lived connection — simpler to
# reason about for a single-process app, and aiosqlite connections are
# cheap to open.
