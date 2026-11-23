"""ov gate: the commit gate (CLI, pre-commit, Action, MCP)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openverifiers.gate import check_file, main
from openverifiers.mcp_gate import handle

ROOT = Path(__file__).resolve().parents[2]


def test_gate_checks_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    good = ROOT / "tests" / "v1" / "why.ov"
    bad = tmp_path / "bad.ov"
    bad.write_text("package probe.bad\nfact type T {\n  property x: Real\n"
                   "  invariant one: x = 1\n  theorem two: x = 2\n}\n")
    broken = tmp_path / "broken.ov"
    broken.write_text("package probe.broken\nfrob\n")
    assert check_file(good)[0]
    ok, line = check_file(bad)
    assert not ok and "T.two" in line
    assert not check_file(broken)[0] and "does not load" in check_file(broken)[1]
    assert main([str(good)]) == 0 and main([str(good), str(bad)]) == 1
    assert "ov gate: FAIL" in capsys.readouterr().out
    reply = json.loads(handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
        "name": "check_files", "arguments": {"paths": [str(good), str(bad)]}}}, good, False)
        or "{}")
    body = json.loads(reply["result"]["content"][0]["text"])
    assert body["ok"] is False and len(body["files"]) == 2
