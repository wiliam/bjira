import pytest

from bjira._blocker import (
    ABSENCE_LINK_TYPE,
    BLOCKER_ISSUETYPE_ID,
    BLOCKER_PROJECT,
    CF_BLOCK_END,
    CF_BLOCK_START,
    CF_BLOCKED_ISSUE_URL,
    CF_BLOCKER_TYPE,
    TRANSITION_REMOVE_BLOCK_ID,
    active_blockers,
    blocked_issue_url,
    blocker_summary,
    match_blocker_type,
)


def test_constants_are_sane():
    assert BLOCKER_PROJECT == "BLOCKER"
    assert BLOCKER_ISSUETYPE_ID == "22108"
    assert CF_BLOCKER_TYPE == "customfield_31724"
    assert CF_BLOCK_START == "customfield_37313"
    assert CF_BLOCK_END == "customfield_35718"
    assert CF_BLOCKED_ISSUE_URL == "customfield_31723"
    assert TRANSITION_REMOVE_BLOCK_ID == "11"
    assert ABSENCE_LINK_TYPE == "Relation"


def test_blocker_summary_format():
    assert blocker_summary(
        type_name="Переключение на приоритет",
        parent_summary="[svc] Do X",
    ) == "Переключение на приоритет для [svc] Do X"


def test_blocked_issue_url():
    assert blocked_issue_url(host="https://jira.hh.ru", key="PORTFOLIO-42") \
        == "https://jira.hh.ru/browse/PORTFOLIO-42"


def test_blocked_issue_url_trims_trailing_slash():
    assert blocked_issue_url(host="https://jira.hh.ru/", key="PORTFOLIO-42") \
        == "https://jira.hh.ru/browse/PORTFOLIO-42"


BLOCKER_TYPES = [
    {"value": "Внеплановое отсутствие (больничный, day-off)"},
    {"value": "Запланированное отсутствие (отпуск, конференция, тренинг)"},
    {"value": "Переключение на более срочный/важный портфель"},
    {"value": "Ожидание выпуска фичи"},
    {"value": "Ждёт старта АБ-теста"},
]


def test_match_blocker_type_exact():
    assert match_blocker_type("Ожидание выпуска фичи", BLOCKER_TYPES) \
        == "Ожидание выпуска фичи"


def test_match_blocker_type_case_insensitive_substring():
    assert match_blocker_type("переключение", BLOCKER_TYPES) \
        == "Переключение на более срочный/важный портфель"


def test_match_blocker_type_ambiguous():
    with pytest.raises(ValueError, match="ambiguous"):
        match_blocker_type("отсутствие", BLOCKER_TYPES)


def test_match_blocker_type_unknown():
    with pytest.raises(ValueError, match="no blocker type"):
        match_blocker_type("totallynotreal", BLOCKER_TYPES)


def _link(key, link_type_name, status_name, direction="inward"):
    inner = {"key": key, "fields": {"status": {"name": status_name}}}
    return {
        "type": {"name": link_type_name},
        "inwardIssue" if direction == "inward" else "outwardIssue": inner,
    }


def test_active_blockers_returns_only_inward_blocks_not_resolved():
    links = [
        _link("BLOCKER-1", "Blocks", "Заблокировано"),
        _link("BLOCKER-2", "Blocks", "Блокировка снята"),
        _link("BLOCKER-3", "Blocks", "Заблокировано"),
        _link("AN-4", "Relation", "Backlog"),
        _link("BLOCKER-5", "Blocks", "Заблокировано", direction="outward"),
    ]
    assert active_blockers(links) == ["BLOCKER-1", "BLOCKER-3"]


def test_active_blockers_empty():
    assert active_blockers([]) == []
