"""bjira unblock — fire the parent's status self-transition.

In hh.jira, every status has a self-loop transition (e.g. Backlog→Backlog, id 1421;
Problem Discovery: In progress self-loop, id 1441; etc.). These self-transitions
carry a post-function that clears Flagged + is_blocked on the parent and
transitions every active 'blocked by' BLOCKER-* to 'Блокировка снята'.

One gesture == full unblock. For targeted control (close one specific blocker but
keep flag), use --blocker / --keep-flag which fall back to manual transitions.
"""
import sys

from jira import JIRAError

from bjira.operations import BJiraOperation
from bjira._blocker import TRANSITION_REMOVE_BLOCK_ID, active_blockers


class Operation(BJiraOperation):

    def configure_arg_parser(self, subparsers):
        parser = subparsers.add_parser("unblock", help="clear blockage on an issue")
        parser.add_argument("key", help="parent issue key")
        parser.add_argument("--blocker", default=None,
                            help="close only this specific BLOCKER (manual path; "
                                 "flag stays untouched unless you omit this)")
        parser.add_argument("--comment", default=None,
                            help="add a comment to the parent after unblocking")
        parser.add_argument("--keep-flag", dest="keep_flag", action="store_true",
                            help="don't clear Flagged; only transition BLOCKER(s) "
                                 "via manual path")
        parser.set_defaults(func=self._run)

    def _run(self, args):
        jira = self.get_jira_api()

        # Manual path: targeted / keep-flag
        if args.blocker or args.keep_flag:
            return self._manual(jira, args)

        # Default: fire the self-transition of the current status (one gesture).
        try:
            issue = jira.issue(args.key, fields="status,issuelinks")
        except JIRAError as exc:
            self._fail_api(args.key, exc)

        current = issue.fields.status.name
        try:
            transitions = jira.transitions(args.key)
        except JIRAError as exc:
            self._fail_api(args.key, exc)

        # 1) Named "Снять блок" (appears only when the issue is currently blocked).
        # 2) Fallback: self-loop whose transition name equals the status name —
        #    this is the canonical self-loop with an unblock post-function.
        # 3) Explicitly EXCLUDE transition 1341 ("Блокер") which creates a blocker.
        candidates = [t for t in transitions
                      if t["to"]["name"] == current and t["id"] != "1341"]
        chosen = (
            next((t for t in candidates if t["name"].lower().startswith("снять")), None)
            or next((t for t in candidates if t["name"].lower() == current.lower()), None)
        )
        if not chosen:
            self._fail_args(
                f"no unblock-style transition available from status {current!r} "
                "(expected one named 'Снять блок' or a self-loop named like the "
                "status); try --blocker BLOCKER-XX for manual close"
            )

        try:
            jira.transition_issue(args.key, chosen["id"])
        except JIRAError as exc:
            self._fail_api(args.key, exc)

        if args.comment:
            try:
                jira.add_comment(args.key, args.comment)
            except JIRAError as exc:
                self._fail_api(args.key, exc)

        print(f"{args.key}: unblocked via self-transition [{chosen['id']}] "
              f"{chosen['name']} (flag + is_blocked cleared, active BLOCKERs resolved)")

    def _manual(self, jira, args):
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

        if args.comment:
            try:
                jira.add_comment(args.key, args.comment)
            except JIRAError as exc:
                self._fail_api(args.key, exc)

        flag_part = "flag kept" if args.keep_flag else "flag unchanged (manual path)"
        blockers_part = ", ".join(transitioned) if transitioned else "no blockers closed"
        print(f"{args.key}: {blockers_part}; {flag_part}")

    def _fail_args(self, msg):
        print(f"ERROR: unblock: {msg}", file=sys.stderr)
        sys.exit(2)

    def _fail_api(self, key, exc):
        print(f"ERROR: unblock {key}: {exc.status_code} {exc.text}", file=sys.stderr)
        sys.exit(3)
