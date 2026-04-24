"""bjira block — fire the parent's 'Блокер' transition (id 1341).

The transition has post-functions that create a BLOCKER-* ticket with the right
type/dates, link it as 'Blocks', and set Flagged+is_blocked on the parent.
This reproduces the UI 'Блокер' form in one gesture.
"""
import sys

from jira import JIRAError

from bjira.operations import BJiraOperation
from bjira._blocker import (
    ABSENCE_LINK_TYPE,
    CF_BLOCK_END,
    CF_BLOCK_START,
    CF_BLOCKER_TYPE,
    match_blocker_type,
)
from bjira._fields import parse_due


BLOCK_TRANSITION_ID = "1341"     # "Блокер" on PORTFOLIO parents


class Operation(BJiraOperation):

    def configure_arg_parser(self, subparsers):
        parser = subparsers.add_parser("block", help="mark an issue as blocked")
        parser.add_argument("key", nargs="?", default=None,
                            help="parent issue key (the one being blocked)")
        parser.add_argument("--type", dest="block_type", default=None,
                            help="blocker type (fuzzy match)")
        parser.add_argument("--start", default=None,
                            help="start date YYYY-MM-DD")
        parser.add_argument("--end", default=None,
                            help="planned end date YYYY-MM-DD")
        parser.add_argument("--reason", default=None,
                            help="text — set as description of the created BLOCKER")
        parser.add_argument("--absence", default=None,
                            help="existing absence issue key to link via Relation")
        parser.add_argument("--comment", default=None,
                            help="add a comment to the parent issue")
        parser.add_argument("--list-types", dest="list_types", action="store_true",
                            help="list the blocker types available for this flow")
        parser.set_defaults(func=self._run)

    def _run(self, args):
        jira = self.get_jira_api()

        if args.list_types:
            if not args.key:
                self._fail_args("--list-types requires a KEY (types are per-issue "
                                "transition screen)")
            try:
                allowed = self._fetch_block_transition_types(jira, args.key)
            except Exception as exc:
                self._fail_args(f"cannot fetch blocker type dictionary: {exc}")
            for a in allowed:
                print(a["value"])
            return

        if not args.key:
            self._fail_args("KEY is required (or pass KEY --list-types)")
        if not args.block_type:
            self._fail_args("--type is required (see 'bjira block KEY --list-types')")

        # Resolve type against the 'Блокер' transition screen's allowedValues.
        try:
            allowed = self._fetch_block_transition_types(jira, args.key)
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

        # Snapshot current BLOCKER links to detect the newly created one.
        try:
            before = jira.issue(args.key, fields="issuelinks")
        except JIRAError as exc:
            self._fail_api(args.key, exc)
        before_keys = _blocked_by_keys(before.raw["fields"].get("issuelinks") or [])

        fields = {CF_BLOCKER_TYPE: {"value": type_name}}
        if start_value:
            fields[CF_BLOCK_START] = start_value
        if end_value:
            fields[CF_BLOCK_END] = end_value

        try:
            jira.transition_issue(args.key, BLOCK_TRANSITION_ID, fields=fields)
        except JIRAError as exc:
            self._fail_api(args.key, exc)

        # Identify newly created BLOCKER by diffing issuelinks.
        try:
            after = jira.issue(args.key, fields="issuelinks")
        except JIRAError as exc:
            self._fail_api(args.key, exc)
        after_keys = _blocked_by_keys(after.raw["fields"].get("issuelinks") or [])
        new_keys = [k for k in after_keys if k not in before_keys]
        blocker_key = new_keys[0] if new_keys else None

        # Set reason on the new BLOCKER.
        if args.reason and blocker_key:
            try:
                jira.issue(blocker_key).update(fields={"description": args.reason})
            except JIRAError as exc:
                print(f"WARN: block {args.key}: could not set description on "
                      f"{blocker_key}: {exc.status_code} {exc.text}", file=sys.stderr)

        # Link existing absence ticket.
        if args.absence and blocker_key:
            try:
                jira.create_issue_link(ABSENCE_LINK_TYPE,
                                       inwardIssue=args.absence,
                                       outwardIssue=blocker_key)
            except JIRAError as exc:
                print(f"WARN: block {args.key}: could not link absence "
                      f"{args.absence}: {exc.status_code} {exc.text}", file=sys.stderr)

        # Optional parent comment.
        if args.comment:
            try:
                jira.add_comment(args.key, args.comment)
            except JIRAError as exc:
                self._fail_api(args.key, exc)

        if blocker_key:
            msg = f"{args.key}: blocked via {blocker_key} ({type_name})"
            if args.absence:
                msg += f", linked to {args.absence}"
        else:
            msg = f"{args.key}: transition 1341 fired but no new BLOCKER detected"
        print(msg)

    def _fetch_block_transition_types(self, jira, key):
        url = (f"{jira._options['server']}/rest/api/2/issue/{key}/"
               f"transitions?transitionId={BLOCK_TRANSITION_ID}"
               f"&expand=transitions.fields")
        resp = jira._session.get(url)
        resp.raise_for_status()
        data = resp.json()
        for t in data.get("transitions", []):
            if t.get("id") == BLOCK_TRANSITION_ID:
                spec = (t.get("fields") or {}).get(CF_BLOCKER_TYPE)
                if spec is None:
                    raise RuntimeError(
                        f"{CF_BLOCKER_TYPE} not on 'Блокер' transition screen")
                return spec.get("allowedValues") or []
        raise RuntimeError(f"transition {BLOCK_TRANSITION_ID} not available for {key}")

    def _fail_args(self, msg):
        print(f"ERROR: block: {msg}", file=sys.stderr)
        sys.exit(2)

    def _fail_api(self, key, exc):
        print(f"ERROR: block {key}: {exc.status_code} {exc.text}", file=sys.stderr)
        sys.exit(3)


def _blocked_by_keys(issuelinks):
    out = []
    for lnk in issuelinks:
        if (lnk.get("type") or {}).get("name") != "Blocks":
            continue
        inner = lnk.get("inwardIssue")
        if not inner:
            continue
        out.append(inner["key"])
    return out
