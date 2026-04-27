"""Pure helpers for `bjira show`: parse --fields, resolve names→ids, render values."""

# Built-in system field ids that should pass through resolve_field_id without
# requiring a name→id lookup. Case-sensitive — Jira uses these exact tokens.
_SYSTEM_FIELD_IDS = {
    "summary", "description", "status", "assignee", "reporter", "creator",
    "issuetype", "project", "priority", "resolution", "labels",
    "duedate", "created", "updated", "resolutiondate", "lastViewed",
    "issuelinks", "subtasks", "components", "fixVersions", "versions",
    "attachment", "comment", "worklog", "watches", "votes", "security",
    "progress", "aggregateprogress", "workratio", "timetracking",
}


def parse_fields_request(spec, fieldsets, default_fieldset):
    """Resolve user --fields spec into a flat ordered list of field labels.

    Args:
        spec: Comma-separated string from CLI, or None.
        fieldsets: Mapping {alias: [labels]} from config; alias 'default' is
                   used when spec is None.
        default_fieldset: Fallback list when spec is None and 'default' alias
                          is absent in fieldsets.

    Behaviour:
      - spec=None → fieldsets['default'] if present else default_fieldset
      - Each comma-separated entry expands if it's a fieldset key, else stays literal
      - Whitespace trimmed; empty entries dropped
      - Dedup preserving first-occurrence order
    """
    if spec is None or spec == "":
        if "default" in fieldsets:
            return list(fieldsets["default"])
        return list(default_fieldset)

    raw_entries = [s.strip() for s in spec.split(",")]
    raw_entries = [s for s in raw_entries if s]

    expanded = []
    for entry in raw_entries:
        if entry in fieldsets:
            expanded.extend(fieldsets[entry])
        else:
            expanded.append(entry)

    seen = set()
    out = []
    for label in expanded:
        if label not in seen:
            seen.add(label)
            out.append(label)
    return out


def resolve_field_id(label, name_to_id, known_ids):
    """Resolve a user-typed label to a Jira field id, or None if unknown.

    Args:
        label: User-supplied string — can be a field id (e.g. 'customfield_11210',
               'summary') or a human field name (e.g. 'Flagged', 'Дата блокировки').
        name_to_id: Case-insensitive map {lowercased name: field_id} from
                    Jira's /rest/api/2/field response.
        known_ids: Set of customfield ids known on the instance (e.g.
                   {'customfield_11210', 'customfield_31724', ...}).

    Returns:
        Resolved field id, or None if the label can't be matched.
    """
    if label in _SYSTEM_FIELD_IDS:
        return label
    if label in known_ids:
        return label
    return name_to_id.get(label.lower())


def format_field_value(raw, schema_type):
    """Render a Jira field's raw JSON value as a human string.

    Covers the common shapes returned by /rest/api/2/issue:
      - option:                  {"value": "X"}                 -> "X"
      - user:                    {"displayName": "Name"}        -> "Name"
      - array of options/users:  list of those                  -> "X, Y, Z"
      - array of strings:        ["a", "b"]                     -> "a, b"
      - string/number/bool/None: passthrough via str()          -> as-is

    `schema_type` is the field's `schema.type` from /rest/api/2/field
    (e.g. "string", "option", "user", "array", "date", "number"). It
    influences how arrays are unpacked.
    """
    if raw is None:
        return ""

    if isinstance(raw, list):
        return ", ".join(_render_scalar(item) for item in raw)

    if isinstance(raw, dict):
        return _render_scalar(raw)

    return str(raw)


def _render_scalar(value):
    """Render a single non-list value (string, dict for option/user, etc)."""
    if isinstance(value, dict):
        for key in ("value", "displayName", "name", "key"):
            if key in value and value[key] is not None:
                return str(value[key])
        return str(value)
    if value is None:
        return ""
    return str(value)
