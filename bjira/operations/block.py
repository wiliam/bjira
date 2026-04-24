import sys

from jira import JIRAError

from bjira.operations import BJiraOperation
from bjira._blocker import (
    ABSENCE_LINK_TYPE,
    BLOCKER_ISSUETYPE_ID,
    BLOCKER_PROJECT,
    CF_BLOCK_END,
    CF_BLOCK_START,
    CF_BLOCKED_ISSUE_URL,
    CF_BLOCKER_TYPE,
    blocked_issue_url,
    blocker_summary,
    match_blocker_type,
)
from bjira._fields import parse_due


class Operation(BJiraOperation):

    def configure_arg_parser(self, subparsers):
        parser = subparsers.add_parser("block", help="mark an issue as blocked")
        parser.add_argument("key", nargs="?", default=None,
                            help="parent issue key (the one being blocked)")
        parser.add_argument("--type", dest="block_type", default=None,
                            help="blocker type (fuzzy match)")
        parser.add_argument("--start", default=None,
                            help="start date YYYY-MM-DD (default: omitted)")
        parser.add_argument("--end", default=None,
                            help="planned end date YYYY-MM-DD")
        parser.add_argument("--reason", default=None,
                            help="text for BLOCKER description")
        parser.add_argument("--absence", default=None,
                            help="existing absence issue key to link via Relation")
        parser.add_argument("--comment", default=None,
                            help="add a comment to the parent issue")
        parser.add_argument("--no-blocker", dest="no_blocker", action="store_true",
                            help="only set Flagged; don't create a BLOCKER ticket")
        parser.add_argument("--list-types", dest="list_types", action="store_true",
                            help="list the blocker types and exit")
        parser.set_defaults(func=self._run)

    def _run(self, args):
        jira = self.get_jira_api()

        if args.list_types:
            return self._list_types(jira)

        if not args.key:
            self._fail_args("KEY is required (or pass --list-types)")

        creating_blocker = not args.no_blocker and any([
            args.block_type, args.start, args.end, args.reason, args.absence
        ])

        try:
            parent = jira.issue(args.key, fields="summary")
        except JIRAError as exc:
            self._fail_api("block", args.key, exc)

        blocker_key = None
        if creating_blocker:
            if not args.block_type:
                self._fail_args("--type is required when creating a BLOCKER "
                                "(or pass --no-blocker / --list-types)")

            try:
                allowed = self._fetch_blocker_types(jira)
            except Exception as exc:
                self._fail_args(f"cannot fetch blocker type dictionary: {exc}")

            try:
                type_name = match_blocker_type(args.block_type, allowed)
            except ValueError as exc:
                self._fail_args(str(exc))

            start_value = None
            if args.start:
                try:
                    start_value = parse_due(args.start)
                except ValueError as exc:
                    self._fail_args(f"--start: {exc}")
            end_value = None
            if args.end:
                try:
                    end_value = parse_due(args.end)
                except ValueError as exc:
                    self._fail_args(f"--end: {exc}")

            host = self.get_config()["host"]

            create_fields = {
                "project": {"key": BLOCKER_PROJECT},
                "issuetype": {"id": BLOCKER_ISSUETYPE_ID},
                "summary": blocker_summary(type_name, parent.fields.summary or ""),
                CF_BLOCKER_TYPE: {"value": type_name},
                CF_BLOCKED_ISSUE_URL: blocked_issue_url(host, args.key),
            }
            if start_value:
                create_fields[CF_BLOCK_START] = start_value
            if end_value:
                create_fields[CF_BLOCK_END] = end_value
            if args.reason:
                create_fields["description"] = args.reason

            try:
                blocker = jira.create_issue(fields=create_fields)
                blocker_key = blocker.key
            except JIRAError as exc:
                self._fail_api("block", args.key, exc)

            try:
                jira.create_issue_link("Blocks", inwardIssue=args.key,
                                       outwardIssue=blocker_key)
            except JIRAError as exc:
                self._fail_api("block", args.key, exc)

            if args.absence:
                try:
                    jira.create_issue_link(ABSENCE_LINK_TYPE,
                                           inwardIssue=args.absence,
                                           outwardIssue=blocker_key)
                except JIRAError as exc:
                    self._fail_api("block", args.key, exc)

        try:
            jira.issue(args.key).update(
                fields={"customfield_11210": [{"value": "Impediment"}]}
            )
        except JIRAError as exc:
            self._fail_api("block", args.key, exc)

        if args.comment:
            try:
                jira.add_comment(args.key, args.comment)
            except JIRAError as exc:
                self._fail_api("block", args.key, exc)

        if blocker_key:
            msg = f"{args.key}: flagged, {blocker_key} created (Blocks)"
            if args.absence:
                msg += f", linked to {args.absence}"
        else:
            msg = f"{args.key}: flagged"
        print(msg)

    def _fetch_blocker_types(self, jira):
        url = (f"{jira._options['server']}/rest/api/2/issue/createmeta/"
               f"{BLOCKER_PROJECT}/issuetypes/{BLOCKER_ISSUETYPE_ID}")
        resp = jira._session.get(url)
        resp.raise_for_status()
        data = resp.json()
        for v in data.get("values", []):
            if v.get("fieldId") == CF_BLOCKER_TYPE:
                return v.get("allowedValues") or []
        raise RuntimeError(f"{CF_BLOCKER_TYPE} not found in createmeta response")

    def _list_types(self, jira):
        try:
            allowed = self._fetch_blocker_types(jira)
        except Exception as exc:
            print(f"ERROR: block --list-types: {exc}", file=sys.stderr)
            sys.exit(3)
        for a in allowed:
            print(a["value"])

    def _fail_args(self, msg):
        print(f"ERROR: block: {msg}", file=sys.stderr)
        sys.exit(2)

    def _fail_api(self, op, key, exc):
        print(f"ERROR: {op} {key}: {exc.status_code} {exc.text}", file=sys.stderr)
        sys.exit(3)
