"""The CI trust anchor for approval keys (D-032): allowed_signers vs GitHub signing keys."""

from __future__ import annotations

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "anchor", Path(__file__).resolve().parents[2] / "scripts" / "check_signing_anchor.py")
assert spec and spec.loader
anchor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(anchor)

FILE = ('founder namespaces="git" ssh-ed25519 AAAAone founder@x\n'
        "# a comment\n"
        "founder sk-ssh-ed25519@openssh.com AAAAtwo\n")


def test_blobs_reads_allowed_signers_and_github_key_lines() -> None:
    assert anchor.blobs(FILE) == {"AAAAone", "AAAAtwo"}
    assert anchor.blobs("ssh-ed25519 AAAAone\n") == {"AAAAone"}


def test_mismatch_warns_until_confirmed_then_fails() -> None:
    local = anchor.blobs(FILE)
    assert anchor.verdict(local, local | {"AAAAx"}, confirmed=True)[0] == "ok"
    assert anchor.verdict(local, set(), confirmed=False)[0] == "warning"  # no key yet
    assert anchor.verdict(local, {"AAAAone"}, confirmed=False)[0] == "error"  # armed
    assert anchor.verdict(local, {"AAAAone"}, confirmed=True)[0] == "error"
    assert anchor.verdict(local, None, confirmed=True)[0] == "error"      # cannot read GitHub
    assert anchor.verdict(set(), set(), confirmed=False)[0] == "warning"
    assert anchor.verdict(set(), {"AAAAone"}, confirmed=False)[0] == "error"
