import pytest

from bjira._fields import (
    FIELD_SPECS,
    SET_DENY,
    build_fields_payload,
    merge_labels,
    parse_due,
    parse_set_arg,
    should_require_force,
)


def test_merge_labels_adds_new():
    assert merge_labels(existing=["a", "b"], add=["c"], clear=False) == ["a", "b", "c"]


def test_merge_labels_ignores_duplicates():
    assert merge_labels(existing=["a", "b"], add=["a", "c"], clear=False) == ["a", "b", "c"]


def test_merge_labels_clear_wipes_then_adds():
    assert merge_labels(existing=["a", "b"], add=["x"], clear=True) == ["x"]


def test_merge_labels_clear_only():
    assert merge_labels(existing=["a", "b"], add=[], clear=True) == []


def test_merge_labels_returns_none_when_no_change():
    assert merge_labels(existing=["a", "b"], add=["a"], clear=False) is None


def test_merge_labels_preserves_existing_order():
    assert merge_labels(existing=["z", "a", "m"], add=["b"], clear=False) == ["z", "a", "m", "b"]


def test_parse_due_valid_date():
    assert parse_due("2026-05-15") == "2026-05-15"


def test_parse_due_none_keyword_returns_none_string():
    assert parse_due("none") is None


def test_parse_due_rejects_invalid_format():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        parse_due("15/05/2026")


def test_parse_due_rejects_empty():
    with pytest.raises(ValueError):
        parse_due("")


def test_parse_due_rejects_bad_calendar_date():
    with pytest.raises(ValueError):
        parse_due("2026-13-40")


def test_force_required_when_description_nonempty_and_no_force():
    assert should_require_force("description", current="old body", force=False) is True


def test_force_not_required_when_description_empty():
    assert should_require_force("description", current="", force=False) is False


def test_force_not_required_when_description_whitespace_only():
    assert should_require_force("description", current="   \n\n  ", force=False) is False


def test_force_not_required_when_force_passed():
    assert should_require_force("description", current="old body", force=True) is False


def test_force_required_when_summary_nonempty_and_no_force():
    assert should_require_force("summary", current="old title", force=False) is True


def test_force_not_required_for_other_fields():
    assert should_require_force("duedate", current="2026-01-01", force=False) is False
    assert should_require_force("labels", current=["a"], force=False) is False
    assert should_require_force("assignee", current="someone", force=False) is False


def test_field_specs_has_expected_flags():
    expected = {"summary", "description", "due", "assignee", "priority",
                "version", "team", "sp"}
    assert expected.issubset(FIELD_SPECS.keys())


def test_build_fields_payload_version():
    specs = {"version": ("fixVersions", lambda v: [{"name": v}], [])}
    assert build_fields_payload(specs, {"version": "2026Q2"}) == \
        {"fixVersions": [{"name": "2026Q2"}]}


def test_build_fields_payload_clear_value():
    specs = {"version": ("fixVersions", lambda v: [{"name": v}], [])}
    assert build_fields_payload(specs, {"version": "none"}) == {"fixVersions": []}


def test_build_fields_payload_clear_value_with_none_sentinel():
    specs = {"due": ("duedate", lambda v: v, None)}
    assert build_fields_payload(specs, {"due": "none"}) == {"duedate": None}


def test_build_fields_payload_skips_unset_flags():
    specs = {
        "version": ("fixVersions", lambda v: [{"name": v}], []),
        "team":    ("customfield_34238", lambda v: [{"value": v}], []),
    }
    assert build_fields_payload(specs, {"version": "2026Q2", "team": None}) == \
        {"fixVersions": [{"name": "2026Q2"}]}


def test_parse_set_arg_simple():
    assert parse_set_arg("customfield_99=hello") == ("customfield_99", "hello")


def test_parse_set_arg_with_equals_in_value():
    assert parse_set_arg("customfield_99=a=b=c") == ("customfield_99", "a=b=c")


def test_parse_set_arg_rejects_missing_equals():
    with pytest.raises(ValueError, match="--set expects"):
        parse_set_arg("customfield_99")


def test_parse_set_arg_rejects_denied_field():
    with pytest.raises(ValueError, match="not editable via bjira"):
        parse_set_arg("status=Done")


def test_set_deny_includes_workflow_fields():
    assert {"status", "resolution", "issuetype", "project"}.issubset(SET_DENY)


def test_field_specs_includes_flagged():
    assert "flagged" in FIELD_SPECS
    jira_field, to_payload, clear = FIELD_SPECS["flagged"]
    assert jira_field == "customfield_11210"
    assert to_payload("Impediment") == [{"value": "Impediment"}]
    assert clear == []
