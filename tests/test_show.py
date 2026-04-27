from bjira._show import (
    format_field_value,
    parse_fields_request,
    resolve_field_id,
)


# --- parse_fields_request ---

def test_parse_fields_default_when_empty():
    assert parse_fields_request(None, {}, ["a", "b"]) == ["a", "b"]


def test_parse_fields_uses_default_alias_from_config():
    fieldsets = {"default": ["x", "y"]}
    assert parse_fields_request(None, fieldsets, ["fallback"]) == ["x", "y"]


def test_parse_fields_expands_alias():
    fieldsets = {"blocker": ["Flagged", "is_blocked"]}
    assert parse_fields_request("blocker", fieldsets, []) == ["Flagged", "is_blocked"]


def test_parse_fields_mixes_alias_and_literal():
    fieldsets = {"blocker": ["Flagged", "is_blocked"]}
    assert parse_fields_request("blocker,summary", fieldsets, []) == [
        "Flagged", "is_blocked", "summary",
    ]


def test_parse_fields_dedups_preserve_order():
    fieldsets = {"a": ["x", "y"], "b": ["y", "z"]}
    assert parse_fields_request("a,b,x", fieldsets, []) == ["x", "y", "z"]


def test_parse_fields_trims_whitespace():
    assert parse_fields_request("  x ,  y  ", {}, []) == ["x", "y"]


# --- resolve_field_id ---

def test_resolve_field_id_known_id_passthrough():
    assert resolve_field_id(
        "customfield_11210", {}, {"customfield_11210"}
    ) == "customfield_11210"


def test_resolve_field_id_case_insensitive_name_lookup():
    nm = {"flagged": "customfield_11210"}
    assert resolve_field_id("Flagged", nm, set()) == "customfield_11210"


def test_resolve_field_id_unknown_returns_none():
    assert resolve_field_id("notarealthing", {}, set()) is None


# --- format_field_value ---

def test_format_field_value_option():
    assert format_field_value({"value": "Impediment"}, "option") == "Impediment"


def test_format_field_value_array_of_options():
    val = [{"value": "A"}, {"value": "B"}]
    assert format_field_value(val, "array") == "A, B"


def test_format_field_value_user():
    assert format_field_value({"displayName": "Молтянинов И."}, "user") == "Молтянинов И."


def test_format_field_value_string_passthrough():
    assert format_field_value("hello", "string") == "hello"
