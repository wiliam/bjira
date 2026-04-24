"""Constants and pure helpers for the bjira block/unblock flow."""

BLOCKER_PROJECT = "BLOCKER"
BLOCKER_ISSUETYPE_ID = "22108"                   # "Блокер"

CF_BLOCKER_TYPE = "customfield_31724"            # Тип блокировки (option)
CF_BLOCK_START = "customfield_37313"             # Дата блокировки (date)
CF_BLOCK_END = "customfield_35718"               # Дата разблокировки (date)
CF_BLOCKED_ISSUE_URL = "customfield_31723"       # Заблокированная задача (URL string)

TRANSITION_REMOVE_BLOCK_ID = "11"                # "Снять блокировку" -> "Блокировка снята"

ABSENCE_LINK_TYPE = "Relation"                   # jira.hh.ru uses "Relation", not "Relates"

RESOLVED_STATUS = "Блокировка снята"


def blocker_summary(type_name, parent_summary):
    return f"{type_name} для {parent_summary}"


def blocked_issue_url(host, key):
    return f"{host.rstrip('/')}/browse/{key}"


def match_blocker_type(query, allowed_values):
    """Resolve user input to a canonical blocker-type name.

    `allowed_values` is the editmeta/createmeta `allowedValues` list for
    customfield_31724: [{"value": "...", ...}, ...].
    Match order: case-insensitive exact -> unique case-insensitive substring.
    """
    q = query.lower()
    names = [a["value"] for a in allowed_values]

    exact = [n for n in names if n.lower() == q]
    if len(exact) == 1:
        return exact[0]

    substr = [n for n in names if q in n.lower()]
    if len(substr) == 1:
        return substr[0]
    if len(substr) > 1:
        raise ValueError(
            f"ambiguous blocker type {query!r}; matches: {', '.join(substr)}"
        )
    raise ValueError(f"no blocker type matches {query!r}")


def active_blockers(issuelinks):
    """Return keys of active BLOCKER tickets linked to this parent.

    Active = link type 'Blocks' + inward (parent is on the blocked side) +
    blocker status is not 'Блокировка снята'.
    """
    out = []
    for lnk in issuelinks:
        if (lnk.get("type") or {}).get("name") != "Blocks":
            continue
        inner = lnk.get("inwardIssue")
        if not inner:
            continue
        status = (inner.get("fields") or {}).get("status", {}).get("name")
        if status == RESOLVED_STATUS:
            continue
        out.append(inner["key"])
    return out
