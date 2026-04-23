from bjira._fields import merge_labels


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
