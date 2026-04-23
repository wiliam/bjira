import json
import sys

from jira import JIRAError

from bjira.operations import BJiraOperation
from bjira._fields import (
    FIELD_SPECS,
    build_fields_payload,
    merge_labels,
    parse_set_arg,
    should_require_force,
)
from bjira._text import resolve_body_source


class Operation(BJiraOperation):

    def configure_arg_parser(self, subparsers):
        parser = subparsers.add_parser("edit", help="edit fields on an issue")
        parser.add_argument("key", help="issue key")

        for flag in FIELD_SPECS:
            parser.add_argument(f"--{flag}", default=None,
                                help=f"set '{flag}' (value or 'none' to clear)")

        parser.add_argument("--description-file", dest="description_file", default=None)
        parser.add_argument("--label", dest="labels", action="append", default=[],
                            help="repeatable; merged with existing")
        parser.add_argument("--labels-clear", dest="labels_clear", action="store_true")
        parser.add_argument("--set", dest="set_pairs", action="append", default=[],
                            metavar="KEY=VALUE",
                            help="escape hatch for fields not in the map; repeatable")
        parser.add_argument("--force", action="store_true",
                            help="allow overwriting non-empty summary/description")
        parser.add_argument("--list-fields", dest="list_fields", action="store_true",
                            help="list editable fields for this issue and exit")
        parser.add_argument("--json", dest="as_json", action="store_true",
                            help="with --list-fields, emit JSON instead of a table")
        parser.set_defaults(func=self._run)

    def _run(self, args):
        if args.list_fields:
            return self._list_fields(args.key, args.as_json)

        if args.description is not None and args.description_file is not None:
            self._fail_args("--description and --description-file are mutually exclusive")

        map_values = {flag: getattr(args, flag, None) for flag in FIELD_SPECS}

        if args.description_file is not None:
            try:
                map_values["description"] = resolve_body_source(None, args.description_file)
            except ValueError as exc:
                self._fail_args(str(exc))

        set_pairs = []
        for raw in args.set_pairs:
            try:
                set_pairs.append(parse_set_arg(raw))
            except ValueError as exc:
                self._fail_args(str(exc))

        wants_any = (
            any(v is not None for v in map_values.values())
            or args.labels
            or args.labels_clear
            or set_pairs
        )
        if not wants_any:
            self._fail_args(
                "nothing to update; pass at least one of "
                + ", ".join(f"--{f}" for f in FIELD_SPECS)
                + ", --description-file, --label, --labels-clear, --set KEY=VALUE"
            )

        jira = self.get_jira_api()
        try:
            issue = jira.issue(args.key, fields="summary,description,labels")
        except JIRAError as exc:
            self._fail_api(args.key, exc)

        if map_values.get("summary") is not None \
                and map_values["summary"] != (issue.fields.summary or "") \
                and should_require_force("summary", issue.fields.summary or "", args.force):
            self._fail_args(
                f"existing summary is not empty ({len(issue.fields.summary)} chars); "
                "pass --force to overwrite"
            )
        if map_values.get("description") is not None \
                and map_values["description"] != (issue.fields.description or "") \
                and should_require_force("description", issue.fields.description or "", args.force):
            self._fail_args(
                f"existing description is not empty ({len(issue.fields.description)} chars); "
                "pass --force to overwrite"
            )

        try:
            fields = build_fields_payload(FIELD_SPECS, map_values)
        except ValueError as exc:
            self._fail_args(str(exc))

        if fields.get("summary") == (issue.fields.summary or ""):
            fields.pop("summary", None)
        if fields.get("description") == (issue.fields.description or ""):
            fields.pop("description", None)

        if args.labels or args.labels_clear:
            merged = merge_labels(list(issue.fields.labels or []), args.labels, args.labels_clear)
            if merged is not None:
                fields["labels"] = merged

        for key, value in set_pairs:
            fields[key] = value

        if not fields:
            print(f"{args.key}: no changes")
            return

        try:
            issue.update(fields=fields)
        except JIRAError as exc:
            self._fail_api(args.key, exc)

        parts = []
        for k, v in fields.items():
            if k == "description":
                parts.append(f"description=<{len(v)} chars>" if v else "description=cleared")
            else:
                parts.append(f"{k}={v}")
        print(f"OK: {args.key} {', '.join(parts)}")

    def _list_fields(self, key, as_json):
        jira = self.get_jira_api()
        try:
            meta = jira.editmeta(key)
        except JIRAError as exc:
            self._fail_api(key, exc)

        rows = []
        for fid, spec in (meta.get("fields") or {}).items():
            name = spec.get("name", fid)
            schema = spec.get("schema") or {}
            ftype = schema.get("type", "?")
            ops = ",".join(spec.get("operations") or [])
            allowed = spec.get("allowedValues") or []
            allowed_display = ", ".join(
                (av.get("name") or av.get("value") or av.get("key") or str(av))
                for av in allowed[:10]
            )
            if len(allowed) > 10:
                allowed_display += f", ... ({len(allowed)} total)"
            rows.append({"field": name, "id": fid, "type": ftype,
                         "ops": ops, "allowed": allowed_display})

        if as_json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
            return

        if not rows:
            print(f"{key}: no editable fields (check permissions?)")
            return

        widths = {col: max(len(col), max(len(str(r[col])) for r in rows))
                  for col in ("field", "id", "type", "ops")}
        header = (f"{'field':<{widths['field']}}  {'id':<{widths['id']}}  "
                  f"{'type':<{widths['type']}}  {'ops':<{widths['ops']}}  allowed")
        print(header)
        print("-" * len(header))
        for r in rows:
            print(f"{r['field']:<{widths['field']}}  {r['id']:<{widths['id']}}  "
                  f"{r['type']:<{widths['type']}}  {r['ops']:<{widths['ops']}}  {r['allowed']}")

    def _fail_args(self, msg):
        print(f"ERROR: edit: {msg}", file=sys.stderr)
        sys.exit(2)

    def _fail_api(self, key, exc):
        print(f"ERROR: edit {key}: {exc.status_code} {exc.text}", file=sys.stderr)
        sys.exit(3)
