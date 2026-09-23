#!/usr/bin/env python3
"""Claude Code PreToolUse hook — gate tool calls through OpenVerifiers v2.

Pipeline (and nothing else):
    1. read the hook JSON from stdin (tool_name / tool_input)
    2. look the tool up in the closed MAPPINGS table (frozen.py)
    3. if mapped: translate the call into ONE trace step whose
       transformation-name and refs come from that static mapping
    4. call submit() with the harness-authored frozen context + target
    5. decide: allow on pass, block on anything else — with the verdict
       `reason` as the message so the agent can retry correctly

The registry (Registry.lookup inside run_trace/submit) is the load-bearing
whitelist: this script introduces zero new dynamic dispatch. An unmapped tool
or an unknown transformation name is a block, never a shortcut.
"""

import json
import sys

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)).rsplit("/", 2)[0])  # repo root

from openverifiers.v2 import submit                      # noqa: E402
from openverifiers.domains import standard_grammars     # noqa: E402
from openverifiers.plugin import frozen                 # noqa: E402


def _block(reason: str) -> dict:
    return {
        "decision": "block",
        "reason": f"OpenVerifiers: {reason}",
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "block",
            "permissionDecisionReason": f"OpenVerifiers: {reason}",
        },
    }


def _allow(reason: str) -> dict:
    return {
        "decision": "allow",
        "reason": f"OpenVerifiers: {reason}",
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": f"OpenVerifiers: {reason}",
        },
    }


def gate(tool_name: str, tool_input: dict) -> dict:
    mapping = frozen.MAPPINGS.get(tool_name)
    if mapping is None:
        return _block(f"tool {tool_name!r} has no mapping to a registered "
                      f"transformation — closed mapping table")

    trans_name = mapping["transformation"]
    grammar_name = mapping["grammar"]
    background = frozen.FROZEN_CONTEXTS[grammar_name]
    mission = frozen.TARGETS[grammar_name]

    # -- translate the call: the agent picks WHICH frozen ref feeds each
    #    statically-bound role. Roles live in the mapping; facts must name
    #    harness-frozen context keys (the runner enforces resolution again).
    args = []
    for field, binding in mapping["refs"].items():
        chosen = tool_input.get(field)
        if chosen is None:
            return _block(f"{tool_name}: missing required input field "
                          f"{field!r} (must name a frozen context ref)")
        if chosen not in background:
            return _block(f"{tool_name}: {chosen!r} is not a frozen context "
                          f"ref for grammar {grammar_name!r} "
                          f"(have: {sorted(background)})")
        args.append(f"{binding['role']}={chosen}")
    params = []
    for field in mapping["params"]:
        if field in tool_input:
            params.append(f"{field}={tool_input[field]}")
    out_id = mapping.get("output", "__gate__")
    step = f"{out_id} = {trans_name}({', '.join(args)})"
    if params:
        step += f" with {', '.join(params)}"

    # -- enforce: run_trace/submit resolves refs against the frozen context,
    #    and the registry is the ONLY way a name becomes code ---------------
    result = submit(mission, traces=[step], background=dict(background),
                    grammars=standard_grammars())
    if result["verdict"] == "pass":
        return _allow(f"trace + mission passed ({result['reason']})")
    return _block(f"{trans_name} call rejected: {result['reason']}")


def main() -> int:
    raw = sys.stdin.read()
    if not raw:
        print(json.dumps(_block("hook received no input — fail closed")))
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps(_block(f"hook input is not JSON ({exc}) — "
                                f"fail closed")))
        return 0
    if payload.get("hook_event_name") != "PreToolUse":
        return 0  # not our event: no decision, normal flow continues
    try:
        decision = gate(payload.get("tool_name", ""),
                        payload.get("tool_input", {}) or {})
    except Exception as exc:  # fail closed on ANY error
        decision = _block(f"gate error ({type(exc).__name__}: {exc}) — "
                          f"fail closed")
    print(json.dumps(decision))
    return 0


if __name__ == "__main__":
    sys.exit(main())