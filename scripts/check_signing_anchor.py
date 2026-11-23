"""Compare .approvers/allowed_signers with the founder's GitHub signing keys (D-032).

    python scripts/check_signing_anchor.py

Read-only: it GETs https://api.github.com/users/<user>/ssh_signing_keys and never
writes to GitHub. <user> is $FOUNDER_GITHUB_USER (CI passes the repository variable,
or the repository owner). Every key in allowed_signers must be one of those
signing keys. While the account shows no signing key at all, a mismatch is a
warning; once it shows one (or $FOUNDER_SIGNING_KEY_ON_GITHUB=true), it fails
(packet 3, Part D: "switch the CI check from warn to fail once the API shows it").
Output uses GitHub Actions annotations. See docs/APPROVALS.md.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

SIGNERS = Path(".approvers/allowed_signers")
KEY_TYPES = ("ssh-", "sk-ssh-", "sk-ecdsa-", "ecdsa-")


def blobs(text: str) -> set[str]:
    """The base64 key blobs in an allowed_signers file (or in 'type blob comment' lines)."""
    out = set()
    for line in text.splitlines():
        toks = line.split("#", 1)[0].split() if not line.lstrip().startswith("#") else []
        for i, t in enumerate(toks[:-1]):
            if t.startswith(KEY_TYPES):
                out.add(toks[i + 1])
                break
    return out


def github_blobs(user: str, token: str = "") -> set[str]:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"https://api.github.com/users/{user}/ssh_signing_keys",
                                 headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return blobs("\n".join(k["key"] for k in json.load(r)))


def verdict(local: set[str], remote: set[str] | None, confirmed: bool) -> tuple[str, str]:
    """(level, message): level is "ok", "warning" or "error". Armed (mismatches fail)
    when confirmed or when the account shows any signing key."""
    bad = "error" if confirmed or remote else "warning"
    if not local:
        return bad, "no key in .approvers/allowed_signers"
    if remote is None:
        return bad, "could not read the founder's GitHub signing keys"
    missing = local - remote
    if missing:
        return bad, (f"{len(missing)} key(s) in .approvers/allowed_signers are not signing keys "
                     f"of the founder's GitHub account"
                     + ("" if confirmed or remote else
                        " (a warning while the account shows no signing key)"))
    return "ok", f"all {len(local)} approval key(s) match the founder's GitHub signing keys"


def main() -> int:
    user = os.environ.get("FOUNDER_GITHUB_USER", "")
    confirmed = os.environ.get("FOUNDER_SIGNING_KEY_ON_GITHUB", "").lower() == "true"
    local = blobs(SIGNERS.read_text()) if SIGNERS.exists() else set()
    remote: set[str] | None = None
    if user:
        try:
            remote = github_blobs(user, os.environ.get("GITHUB_TOKEN", ""))
        except (OSError, ValueError, KeyError) as e:
            print(f"signing anchor: {type(e).__name__}: {e}", file=sys.stderr)
    level, msg = verdict(local, remote, confirmed) if user else (
        "error" if confirmed else "warning", "FOUNDER_GITHUB_USER is not set")
    print(f"::{level}::signing anchor: {msg}" if level != "ok" else f"signing anchor: {msg}")
    return 1 if level == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
