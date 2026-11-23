"""The tool-call gate over MCP (C5): an agent asks before it calls a tool.

    python -m openverifiers.mcp_gate POLICY.ov [--drafts]

A Model Context Protocol server on stdio (JSON-RPC 2.0, one message per line),
standard library only. It offers one tool, ``check_tool_call(tool, target)``,
decided by the OV policy package POLICY.ov (which imports ``agent.workflow``
and states ``forbidden(t, x)``, ``needs_approval(t)``):

- ``refused``: the call is forbidden;
- ``needs_human``: it needs a human's approval first;
- ``permitted``: neither;
- ``unknown``: the policy does not decide it (an error, or names it cannot read).

A tool or target the policy does not name is never permitted by default: the
answer is ``needs_human`` (with no kernel verdict, so no trust is claimed).

Every decision is a verdict of the kernel (trust ``{kernel}``) on the scenario
"this one call is requested", with the policy's facts and rules. The server
never runs the tool; it only answers.

Untrusted glue: the verdicts are the kernel's.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, TextIO

from .lang.errors import OVError
from .objects.engine import Settings
from .runner import run_file

PROTOCOL = "2024-11-05"
_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
TOOL = {
    "name": "check_tool_call",
    "description": "Ask OpenVerifiers whether a tool call is allowed by the policy before "
                   "making it. Returns refused, needs_human or permitted, with the trust base.",
    "inputSchema": {"type": "object", "required": ["tool", "target"], "properties": {
        "tool": {"type": "string", "description": "the tool, as named in the policy"},
        "target": {"type": "string", "description": "what it acts on, as named in the policy"},
    }},
}


FILES_TOOL = {
    "name": "check_files",
    "description": "Run the OpenVerifiers commit gate on OV files: each must load and its "
                   "expectations, theorems and classes must hold.",
    "inputSchema": {"type": "object", "required": ["paths"], "properties": {
        "paths": {"type": "array", "items": {"type": "string"}}}},
}


def decide(policy: Path, tool: str, target: str, drafts: bool = False) -> dict[str, Any]:
    """The policy's verdict on one requested call."""
    if not (_NAME.match(tool) and _NAME.match(target)):
        return {"decision": "unknown", "why": "names must be lowercase identifiers"}
    text = policy.read_text()
    m = re.search(r"^\s*package\s+([\w.]+)", text, re.M)
    if m is None:
        return {"decision": "unknown", "why": "the policy file declares no package"}
    pkg = m.group(1)
    known = set(re.findall(r"\b(\w+)\b", text))
    unnamed = [n for n in (tool, target) if n not in known]
    if unnamed:
        return {"decision": "needs_human", "trust": [],
                "why": f"{', '.join(unnamed)} not named by the policy; ask a human"}
    decls = ""
    source = (f"package gate_request\nimport {pkg}\nscenario gate uses {pkg} {{\n{decls}"
              f"  fact request({tool}, {target})\n  query PROVE refused({tool}, {target})\n"
              f"  query PROVE needs_human({tool}, {target})\n"
              f"  query PROVE permitted({tool}, {target})\n}}\n")
    path = policy.parent / "__gate_request__.ov"
    try:
        res = run_file(path, source=source, files={str(path)},
                       settings=Settings(drafts=drafts))
    except OVError as e:
        return {"decision": "unknown", "why": "; ".join(d.message for d in e.diagnostics)}
    for a, name in zip(res.answers, ("refused", "needs_human", "permitted"), strict=True):
        if a.verdict == "PROVEN":
            return {"decision": name, "trust": sorted(a.trust_base),
                    "provisional": res.draft_packages}
    return {"decision": "unknown", "why": "the policy decides nothing for this call"}


def _reply(id_: Any, result: Any = None, error: dict[str, Any] | None = None) -> str:
    msg: dict[str, Any] = {"jsonrpc": "2.0", "id": id_}
    msg["error" if error else "result"] = error or result
    return json.dumps(msg)


def handle(msg: dict[str, Any], policy: Path, drafts: bool) -> str | None:
    method, id_ = msg.get("method"), msg.get("id")
    if id_ is None:                                   # a notification: no reply
        return None
    if method == "initialize":
        return _reply(id_, {"protocolVersion": PROTOCOL, "capabilities": {"tools": {}},
                            "serverInfo": {"name": "openverifiers-gate", "version": "0.1"}})
    if method == "tools/list":
        return _reply(id_, {"tools": [TOOL, FILES_TOOL]})
    if method == "tools/call":
        params = msg.get("params") or {}
        args = params.get("arguments") or {}
        if params.get("name") == FILES_TOOL["name"]:
            from .gate import check_file
            rows = [check_file(Path(str(p)), drafts) for p in args.get("paths") or []]
            return _reply(id_, {"content": [{"type": "text", "text": json.dumps(
                {"ok": all(ok for ok, _ in rows), "files": [line for _, line in rows]})}],
                "isError": not all(ok for ok, _ in rows)})
        if params.get("name") != TOOL["name"]:
            return _reply(id_, error={"code": -32602, "message": "unknown tool"})
        out = decide(policy, str(args.get("tool", "")), str(args.get("target", "")), drafts)
        return _reply(id_, {"content": [{"type": "text", "text": json.dumps(out)}],
                            "isError": out["decision"] == "unknown"})
    if method == "ping":
        return _reply(id_, {})
    return _reply(id_, error={"code": -32601, "message": f"unknown method {method}"})


def serve(policy: Path, drafts: bool, inp: TextIO, out: TextIO) -> None:
    for line in _lines(inp):
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            out.write(_reply(None, error={"code": -32700, "message": "parse error"}) + "\n")
            out.flush()
            continue
        r = handle(msg, policy, drafts)
        if r is not None:
            out.write(r + "\n")
            out.flush()


def _lines(inp: TextIO) -> Iterator[str]:
    for line in inp:
        if line.strip():
            yield line


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    pos = [a for a in args if not a.startswith("--")]
    if len(pos) != 1:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    serve(Path(pos[0]).resolve(), "--drafts" in args, sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
