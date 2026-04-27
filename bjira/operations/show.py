"""bjira show KEY — selective read of issue fields with alias support.

Reads any field on an issue (including ones not exposed by MCP). Field labels
can be:
  - Field ids (e.g. 'customfield_11210', 'summary')
  - Human names (e.g. 'Flagged', 'Дата блокировки')
  - Fieldset aliases from ~/.bjira_config (e.g. 'blocker' -> [...])

Default fieldset (when --fields is not passed) comes from config 'fieldsets.default'
or a hardcoded minimum.
"""
import json
import sys

from jira import JIRAError

from bjira.operations import BJiraOperation
from bjira._show import (
    format_field_value,
    parse_fields_request,
    resolve_field_id,
)


HARDCODED_DEFAULT_FIELDSET = ["summary", "status", "assignee", "labels", "duedate"]


class Operation(BJiraOperation):

    def configure_arg_parser(self, subparsers):
        parser = subparsers.add_parser("show", help="show selected fields of an issue")
        parser.add_argument("key", help="issue key")
        parser.add_argument(
            "--fields", default=None,
            help="comma-separated list of field names, ids, or fieldset aliases "
                 "from ~/.bjira_config 'fieldsets'",
        )
        parser.add_argument(
            "--json", dest="as_json", action="store_true",
            help="emit JSON list instead of YAML-like text",
        )
        parser.set_defaults(func=self._run)

    def _run(self, args):
        jira = self.get_jira_api()

        labels = parse_fields_request(
            args.fields,
            self.get_fieldsets(),
            HARDCODED_DEFAULT_FIELDSET,
        )

        try:
            field_meta = self._fetch_field_metadata(jira)
        except Exception as exc:
            self._fail(f"cannot fetch field metadata: {exc}")

        name_to_id = {m["name"].lower(): m["id"] for m in field_meta}
        known_ids = {m["id"] for m in field_meta}
        meta_by_id = {m["id"]: m for m in field_meta}

        resolved = []
        unknown = []
        for label in labels:
            fid = resolve_field_id(label, name_to_id, known_ids)
            if fid is None:
                unknown.append(label)
            else:
                resolved.append((label, fid))

        if unknown:
            self._fail(
                "unknown field(s): " + ", ".join(repr(u) for u in unknown)
                + ". Pass an exact id, a known field name (case-insensitive), or a "
                  "fieldset alias from ~/.bjira_config",
            )

        try:
            issue = jira.issue(args.key, fields=",".join(fid for _, fid in resolved))
        except JIRAError as exc:
            self._fail_api(args.key, exc)

        rows = []
        for label, fid in resolved:
            raw = issue.raw["fields"].get(fid)
            schema_type = (
                meta_by_id.get(fid, {}).get("schema", {}).get("type", "string")
            )
            human_name = meta_by_id.get(fid, {}).get("name", fid)
            rows.append({
                "id": fid,
                "name": human_name,
                "label": label,  # what user typed
                "type": schema_type,
                "raw": raw,
                "value": format_field_value(raw, schema_type),
            })

        if args.as_json:
            json.dump(
                [{"id": r["id"], "name": r["name"], "type": r["type"],
                  "value": r["raw"]} for r in rows],
                sys.stdout, ensure_ascii=False, indent=2,
            )
            sys.stdout.write("\n")
            return

        self._print_yaml_like(args.key, rows)

    def _fetch_field_metadata(self, jira):
        """Fetch /rest/api/2/field — list of {id, name, schema, custom, ...}."""
        url = f"{jira._options['server']}/rest/api/2/field"
        resp = jira._session.get(url)
        resp.raise_for_status()
        return resp.json()

    def _print_yaml_like(self, key, rows):
        print(key)
        if not rows:
            return
        max_label = max(len(r["label"]) for r in rows)
        for r in rows:
            value_str = r["value"]
            label = r["label"].ljust(max_label)
            if "\n" in value_str:
                # Multi-line: print first line on the header line, rest indented.
                first, *rest = value_str.split("\n")
                print(f"  {label}: {first}")
                indent = " " * (2 + max_label + 2)  # "  " + label + ": "
                for line in rest:
                    print(f"{indent}{line}")
            else:
                print(f"  {label}: {value_str}")

    def _fail(self, msg):
        print(f"ERROR: show: {msg}", file=sys.stderr)
        sys.exit(2)

    def _fail_api(self, key, exc):
        print(f"ERROR: show {key}: {exc.status_code} {exc.text}", file=sys.stderr)
        sys.exit(3)
