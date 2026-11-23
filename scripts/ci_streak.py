"""The CI green streak under D-034, with run IDs.

    python scripts/ci_streak.py [--repo OWNER/NAME] [--branch v1] [--json]

D-034: the streak counts push runs of the `tests` workflow on distinct commits of
the branch, plus scheduled runs of the `nightly` workflow. Manual re-runs of the
same commit do not count: each run is judged by its FIRST attempt. Runs still in
progress are listed but neither count nor break the streak. Read-only (gh api).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class Run:
    id: int
    sha: str
    event: str
    created: str
    status: str
    first: str          # the first attempt's conclusion ("" while running)


def _gh(path: str) -> object:
    out = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def _first_attempt(repo: str, run: dict[str, object]) -> str:
    if run["status"] != "completed":
        return ""
    if run.get("run_attempt", 1) == 1:
        return str(run["conclusion"])
    att = _gh(f"repos/{repo}/actions/runs/{run['id']}/attempts/1")
    return str(att["conclusion"])  # type: ignore[index]


def runs(repo: str, branch: str) -> list[Run]:
    out: list[Run] = []
    for wf, event in (("tests.yml", "push"), ("nightly.yml", "schedule")):
        try:
            data = _gh(f"repos/{repo}/actions/workflows/{wf}/runs?branch={branch}"
                       f"&event={event}&per_page=60")
        except subprocess.CalledProcessError:
            continue                       # the workflow does not exist (yet)
        for r in data["workflow_runs"]:  # type: ignore[index]
            out.append(Run(r["id"], r["head_sha"][:7], event, r["created_at"], r["status"],
                           _first_attempt(repo, r)))
    return sorted(out, key=lambda r: r.created, reverse=True)


def streak(rs: list[Run]) -> tuple[list[Run], Run | None, list[Run]]:
    """(counted green runs, newest newest-first; the run that broke it; pending runs)."""
    counted, seen, pending = [], set(), []
    for r in rs:
        if r.status != "completed":
            pending.append(r)
            continue
        if r.first != "success":
            return counted, r, pending
        if r.event == "push" and r.sha in seen:
            continue                       # one push run per commit
        seen.add(r.sha)
        counted.append(r)
    return counted, None, pending


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/ci_streak.py")
    ap.add_argument("--repo", default="tridentic/openverifiers")
    ap.add_argument("--branch", default="v1")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    counted, broke, pending = streak(runs(a.repo, a.branch))
    if a.json:
        print(json.dumps({"streak": len(counted), "runs": [r.__dict__ for r in counted],
                          "broken_by": broke.__dict__ if broke else None,
                          "pending": [r.__dict__ for r in pending]}, indent=2))
        return 0
    print(f"CI streak (D-034): {len(counted)} green in a row")
    for r in counted:
        print(f"  {r.id} {r.event:8} {r.sha} {r.created} {r.first}")
    if broke:
        print(f"  broken by {broke.id} {broke.event} {broke.sha} {broke.created} "
              f"(first attempt: {broke.first})")
    for r in pending:
        print(f"  pending {r.id} {r.event} {r.sha} {r.created}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
