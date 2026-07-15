"""
Unit tests for save_note / get_notes / update_note / delete_note, in
isolation from the agent loop. Each test gets its own SQLite file via
the autouse _test_settings fixture in conftest.py.
"""
import re

import pytest

from app.db.database import init_db
from app.tools import notes


async def _first_note_id() -> int:
    """Saves happen via save_note(), which doesn't return the new row's
    id directly -- pull it out of get_notes()'s formatted output instead,
    exactly as the LLM itself would have to."""
    listed = await notes.get_notes()
    match = re.search(r"id=(\d+)", listed)
    assert match, f"no note id found in: {listed!r}"
    return int(match.group(1))


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


async def test_get_notes_exposes_id_for_update_delete():
    await init_db()
    await notes.save_note("has an id")

    listed = await notes.get_notes()

    assert re.search(r"id=\d+", listed)


async def test_save_note_rejects_empty_content():
    await init_db()

    with pytest.raises(ValueError):
        await notes.save_note("   ")


async def test_update_note_changes_content():
    await init_db()
    await notes.save_note("original content")
    note_id = await _first_note_id()

    result = await notes.update_note(note_id, "updated content")
    assert f"Updated note {note_id}" in result

    listed = await notes.get_notes()
    assert "updated content" in listed
    assert "original content" not in listed


async def test_update_note_rejects_empty_content():
    await init_db()
    await notes.save_note("original content")
    note_id = await _first_note_id()

    with pytest.raises(ValueError):
        await notes.update_note(note_id, "   ")


async def test_update_note_missing_id_raises():
    await init_db()

    with pytest.raises(ValueError, match="No note found"):
        await notes.update_note(999, "new content")


async def test_delete_note_removes_it():
    await init_db()
    await notes.save_note("to be deleted")
    note_id = await _first_note_id()

    result = await notes.delete_note(note_id)
    assert f"Deleted note {note_id}" in result

    listed = await notes.get_notes()
    assert listed == "No notes saved yet."


async def test_delete_note_missing_id_raises():
    await init_db()

    with pytest.raises(ValueError, match="No note found"):
        await notes.delete_note(999)
