"""
Unit tests for save_note / get_notes, in isolation from the agent loop.
Each test gets its own SQLite file via the autouse _test_settings fixture
in conftest.py.
"""
import pytest

from app.db.database import init_db
from app.tools import notes


async def test_get_notes_empty_by_default():
    await init_db()

    result = await notes.get_notes()

    assert result == "No notes saved yet."


async def test_save_and_get_notes_roundtrip():
    await init_db()

    save_result = await notes.save_note("Buy milk")
    assert "Buy milk" in save_result

    listed = await notes.get_notes()
    assert "Buy milk" in listed


async def test_get_notes_orders_most_recent_first():
    await init_db()

    await notes.save_note("first note")
    await notes.save_note("second note")

    listed = await notes.get_notes()
    assert listed.index("second note") < listed.index("first note")


async def test_save_note_rejects_empty_content():
    await init_db()

    with pytest.raises(ValueError):
        await notes.save_note("   ")
