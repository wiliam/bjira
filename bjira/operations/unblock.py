import sys

from jira import JIRAError

from bjira.operations import BJiraOperation
from bjira._blocker import TRANSITION_REMOVE_BLOCK_ID, active_blockers


class Operation(BJiraOperation):

    def configure_arg_parser(self, subparsers):
        parser = subparsers.add_parser("unblock", help="clear blockage on an issue")
        parser.add_argument("key", help="parent issue key")
        parser.add_argument("--blocker", default=None,
                            help="remove only this specific BLOCKER (otherwise all active)")
        parser.add_argument("--comment", default=None,
                            help="add a comment to the parent")
        parser.add_argument("--keep-flag", dest="keep_flag", action="store_true",
                            help="do not clear Flagged; only transition BLOCKERs")
        parser.set_defaults(func=self._run)

    def _run(self, args):
        jira = self.get_jira_api()

        try:
            parent = jira.issue(args.key, fields="issuelinks")
        except JIRAError as exc:
            self._fail_api(args.key, exc)

        links = parent.raw["fields"].get("issuelinks") or []
        if args.blocker:
            targets = [args.blocker]
        else:
            targets = active_blockers(links)

        transitioned = []
        for b in targets:
            try:
                jira.transition_issue(b, TRANSITION_REMOVE_BLOCK_ID)
                transitioned.append(b)
            except JIRAError as exc:
                print(f"WARN: unblock {args.key}: could not transition {b}: "
                      f"{exc.status_code} {exc.text}", file=sys.stderr)

        if not args.keep_flag:
            try:
                jira.issue(args.key).update(fields={"customfield_11210": []})
            except JIRAError as exc:
                self._fail_api(args.key, exc)

        if args.comment:
            try:
                jira.add_comment(args.key, args.comment)
            except JIRAError as exc:
                self._fail_api(args.key, exc)

        flag_part = "flag kept" if args.keep_flag else "flag cleared"
        blockers_part = ", ".join(transitioned) if transitioned else "no active blockers"
        print(f"{args.key}: {blockers_part}; {flag_part}")

    def _fail_api(self, key, exc):
        print(f"ERROR: unblock {key}: {exc.status_code} {exc.text}", file=sys.stderr)
        sys.exit(3)
