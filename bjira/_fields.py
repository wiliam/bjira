import datetime


def merge_labels(existing, add, clear):
    """Return the final label list after merge, or None if no API change needed.

    - clear=True  → wipe existing first, then add
    - clear=False → union of existing + add, preserving existing order
    - If result equals existing, return None to signal no-op.
    """
    if clear:
        result = []
        for label in add:
            if label not in result:
                result.append(label)
        return result if result != existing else None

    result = list(existing)
    for label in add:
        if label not in result:
            result.append(label)
    return result if result != existing else None


def parse_due(value):
    """Return ISO date string, or None to clear. Raise ValueError on invalid input."""
    if value == "none":
        return None
    if not value:
        raise ValueError("due must be YYYY-MM-DD or 'none'")
    try:
        datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"due must be YYYY-MM-DD or 'none', got {value!r}") from exc
    return value


_FORCE_GATED_FIELDS = {"summary", "description"}


def should_require_force(field, current, force):
    """Return True if this edit needs --force but force was not passed.

    Only 'summary' and 'description' are gated: they are free-form, potentially long,
    and a typo'd overwrite is painful. Whitespace-only existing values count as empty.
    """
    if force:
        return False
    if field not in _FORCE_GATED_FIELDS:
        return False
    if not current or not current.strip():
        return False
    return True


# --- map-driven editing ---

# flag_name -> (jira_field_id, to_payload, clear_payload)
# to_payload: raw CLI string value -> Jira payload for that field
# clear_payload: what to send when user passes "none" ([] for arrays, None for strings)
FIELD_SPECS = {
    "summary":     ("summary",            lambda v: v,                   None),
    "description": ("description",        lambda v: v,                   None),
    "due":         ("duedate",            parse_due,                     None),
    "assignee":    ("assignee",           lambda v: {"name": v},         None),
    "priority":    ("priority",           lambda v: {"name": v},         None),
    "version":     ("fixVersions",        lambda v: [{"name": v}],       []),
    "team":        ("customfield_34238",  lambda v: [{"value": v}],      []),
    "sp":          ("customfield_11212",  float,                         None),
    "flagged":     ("customfield_11210",  lambda v: [{"value": v}],      []),
}

SET_DENY = {
    "status", "resolution",
    "issuetype", "project",
    "created", "updated", "creator", "reporter",
    "issuelinks", "subtasks",
}


def build_fields_payload(specs, values):
    """Build the Jira `fields` dict from a FIELD_SPECS-shaped map and CLI values.

    `values` is {flag_name: raw_string_or_None}. Skipped when None.
    Value "none" triggers clear_payload.
    """
    payload = {}
    for flag, (jira_field, to_payload, clear) in specs.items():
        v = values.get(flag)
        if v is None:
            continue
        payload[jira_field] = clear if v == "none" else to_payload(v)
    return payload


def parse_set_arg(s):
    """Parse a `--set key=value` argument. Returns (jira_field_id, raw_value_string)."""
    if "=" not in s:
        raise ValueError(f"--set expects key=value, got {s!r}")
    key, value = s.split("=", 1)
    key = key.strip()
    if key in SET_DENY:
        raise ValueError(
            f"--set: field {key!r} is not editable via bjira "
            f"(status/resolution → use 'bjira status'; others are managed by Jira)"
        )
    return key, value
