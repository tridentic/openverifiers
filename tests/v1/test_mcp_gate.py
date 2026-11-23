"""C5: the tool-call gate over MCP, driven as a real stdio server."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "drafts" / "policies" / "repo_policy.ov"


def _session(*calls: tuple[str, str]) -> list[Any]:
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            *({"jsonrpc": "2.0", "id": 10 + k, "method": "tools/call",
               "params": {"name": "check_tool_call", "arguments": {"tool": t, "target": x}}}
              for k, (t, x) in enumerate(calls)),
            {"jsonrpc": "2.0", "id": 99, "method": "no/such"}]
    stdin = "\n".join(json.dumps(m) for m in msgs) + "\nnot json\n"
    out = subprocess.run([sys.executable, "-m", "openverifiers.mcp_gate", str(POLICY),
                          "--drafts"], input=stdin, capture_output=True, text=True, check=True,
                         cwd=ROOT)
    return [json.loads(line) for line in out.stdout.splitlines()]


def test_gate_decides_tool_calls_by_the_policy() -> None:
    replies = _session(("push", "main"), ("open_pr", "feature"), ("deploy", "prod"),
                       ("rm_rf", "home"), ("Bad Name", "x"))
    init, tools, *calls, bad_method, parse = replies
    assert init["result"]["serverInfo"]["name"] == "openverifiers-gate"
    assert tools["result"]["tools"][0]["name"] == "check_tool_call"
    got = [json.loads(c["result"]["content"][0]["text"]) for c in calls]
    assert [g["decision"] for g in got] == ["refused", "permitted", "needs_human",
                                            "needs_human", "unknown"]
    assert got[0]["trust"] == ["kernel"] and got[3]["trust"] == []   # unnamed: no verdict
    assert bad_method["error"]["code"] == -32601 and parse["error"]["code"] == -32700
