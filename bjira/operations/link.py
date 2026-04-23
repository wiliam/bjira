import sys

from jira import JIRAError

from bjira.operations import BJiraOperation
from bjira._match import resolve_link_type, NoMatch


class Operation(BJiraOperation):

    def configure_arg_parser(self, subparsers):
        parser = subparsers.add_parser("link", help="link two existing issues")
        parser.add_argument("from_key", nargs="?", default=None, help="source issue key")
        parser.add_argument("link_type", nargs="?", default=None, help="link type name, e.g. Blocks")
        parser.add_argument("to_key", nargs="?", default=None, help="target issue key")
        parser.add_argument("--list", dest="list_types", action="store_true",
                            help="list available link types and exit")
        parser.set_defaults(func=self._run)

    def _run(self, args):
        jira = self.get_jira_api()
        try:
            link_types = [
                {"name": lt.name, "inward": lt.inward, "outward": lt.outward}
                for lt in jira.issue_link_types()
            ]
        except JIRAError as exc:
            print(f"ERROR: link: {exc.status_code} {exc.text}", file=sys.stderr)
            sys.exit(3)

        if args.list_types:
            max_name = max(len(lt["name"]) for lt in link_types)
            for lt in link_types:
                print(f"{lt['name']:<{max_name}}  ({lt['inward']} / {lt['outward']})")
            return

        if not (args.from_key and args.link_type and args.to_key):
            print("ERROR: link: FROM, TYPE, and TO are required (or pass --list)",
                  file=sys.stderr)
            sys.exit(2)

        try:
            canonical = resolve_link_type(args.link_type, link_types)
        except NoMatch as exc:
            print(f"ERROR: link: {exc}", file=sys.stderr)
            sys.exit(3)

        outward_verb = next(lt["outward"] for lt in link_types if lt["name"] == canonical)

        try:
            jira.create_issue_link(canonical, inwardIssue=args.to_key, outwardIssue=args.from_key)
        except JIRAError as exc:
            print(f"ERROR: link: {exc.status_code} {exc.text}", file=sys.stderr)
            sys.exit(3)

        print(f"{args.from_key} {outward_verb} {args.to_key}")
