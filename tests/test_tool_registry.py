"""
Sanity check on the tool registry itself (app/tools/base.py): every
schema's declared name must have a matching registered function, and
vice versa. Cheap to run, catches a typo'd registration before it ships
(e.g. forgetting to add a new tool to TOOL_FUNCTIONS after adding its
SCHEMA, or a name mismatch between the two).
"""
from app.tools.base import TOOL_FUNCTIONS, TOOL_SCHEMAS


def test_every_schema_has_a_registered_function():
    schema_names = {schema["name"] for schema in TOOL_SCHEMAS}
    function_names = set(TOOL_FUNCTIONS.keys())

    assert schema_names == function_names


def test_expected_phase_1_and_2_tools_are_registered():
    expected = {
        "get_weather",
        "save_note",
        "get_notes",
        "update_note",
        "delete_note",
        "web_search",
    }

    assert expected == set(TOOL_FUNCTIONS.keys())
