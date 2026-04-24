"""Live smoke test against jira.hh.ru. Run manually after substantial changes.

Usage: ~/.local/pipx/venvs/bjira/bin/python tests/smoke.py
"""
import json
import subprocess
from pathlib import Path

import keyring
from jira import JIRA

CONFIG = json.loads((Path.home() / ".bjira_config").read_text())
USER = CONFIG["user"]
HOST = CONFIG["host"]
ISSUE = "PORTFOLIO-53307"

jira = JIRA(server=HOST, basic_auth=(USER, keyring.get_password("bjira", USER)))


def run(cmd):
    print(f"$ {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print(f"  stderr: {r.stderr}")
    return r


def main():
    print("=== 1. comments (read) ===")
    r = run(["bjira", "comments", ISSUE, "-n", "1"])
    assert r.returncode == 0, "comments read failed"

    print("\n=== 2. comment add → delete ===")
    r = run(["bjira", "comment", ISSUE, "[SMOKE] test — auto-delete"])
    assert r.returncode == 0, "comment add failed"
    cid = r.stdout.split("id=")[1].split()[0]
    jira.comment(ISSUE, cid).delete()
    print(f"  deleted comment {cid}")

    print("\n=== 3. edit --summary <same> (no-op) ===")
    current = jira.issue(ISSUE, fields="summary").fields.summary
    r = run(["bjira", "edit", ISSUE, "--summary", current])
    assert r.returncode == 0, "no-op summary failed"
    assert "no changes" in r.stdout, f"expected 'no changes' in output, got: {r.stdout!r}"

    print("\n=== 4. status — unknown transition check ===")
    r = run(["bjira", "status", ISSUE, "nonexistent"])
    assert r.returncode == 3, f"expected exit 3, got {r.returncode}"
    print("  correctly returned exit 3 for unknown transition")

    print("\n=== 5. link — unknown type check ===")
    r = run(["bjira", "link", ISSUE, "NotARealType", ISSUE])
    assert r.returncode == 3, f"expected exit 3, got {r.returncode}"
    print("  correctly returned exit 3 for unknown link type")

    print("\n=== 6. edit --list-fields (metadata read) ===")
    r = run(["bjira", "edit", ISSUE, "--list-fields"])
    assert r.returncode == 0, "list-fields failed"
    assert "field" in r.stdout, "expected header in list-fields output"
    assert "fixVersions" in r.stdout or "customfield" in r.stdout, \
        "expected fixVersions or a customfield row"

    print("\n=== 7. link --list ===")
    r = run(["bjira", "link", "--list"])
    assert r.returncode == 0, "link --list failed"
    assert "Relation" in r.stdout, "expected Relation in link types"

    print("\n=== 8. block / unblock round-trip ===")
    r = run(["bjira", "block", ISSUE,
             "--type", "Ожидание выпуска фичи",
             "--reason", "[SMOKE] block/unblock round-trip",
             "--start", "2026-04-24",
             "--end", "2026-04-30"])
    assert r.returncode == 0, "block failed"
    import re
    m = re.search(r"(BLOCKER-\d+)", r.stdout)
    assert m, f"no BLOCKER key in block output: {r.stdout!r}"
    blocker_key = m.group(1)
    print(f"  created {blocker_key}")

    r = run(["bjira", "unblock", ISSUE])
    assert r.returncode == 0, "unblock failed"

    b = jira.issue(blocker_key, fields="status")
    assert b.fields.status.name == "Блокировка снята", \
        f"expected BLOCKER resolved, got {b.fields.status.name}"
    print(f"  {blocker_key} resolved")

    print("\n=== 9. block --list-types ===")
    r = run(["bjira", "block", ISSUE, "--list-types"])
    assert r.returncode == 0, "list-types failed"
    assert "Ожидание выпуска фичи" in r.stdout

    print("\n=== all smoke checks passed ===")


if __name__ == "__main__":
    main()
