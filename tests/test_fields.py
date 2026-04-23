import pytest

from bjira._fields import merge_labels, parse_due


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
