#!/usr/bin/env python3
"""End-to-end demo of the OpenVerifiers Claude Code gate.

Feeds synthetic PreToolUse hook payloads through the SAME code path the real
hook uses (`plugin/pre_tool_use.py::gate`), and prints each decision plus the
reason the agent would see.

Run:  python3 plugin/demo_gate.py      (from the openverifiers repo root)
"""

import json
import sys

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)).rsplit("/", 2)[0])

from openverifiers.plugin.pre_tool_use import gate  # noqa: E402


def hook_payload(tool_name, tool_input):
    return {"hook_event_name": "PreToolUse", "tool_name": tool_name,
            "tool_input": tool_input, "tool_use_id": "demo_1"}


SCENARIOS = [
    ("LEGAL, semantically correct",
     hook_payload("Tool__Math__Multiply", {"left": "a", "right": "b"}),
     "allow"),
    ("ILLEGAL, shape-legal but output violates frozen target "
     "(a*a = 9 != z=12)",
     hook_payload("Tool__Math__Multiply", {"left": "a", "right": "a"}),
     "block"),
    ("ILLEGAL, unknown/frozen-unresolvable ref (ghost is not in context)",
     hook_payload("Tool__Math__Multiply", {"left": "a", "right": "ghost"}),
     "block"),
    ("ILLEGAL, missing required input field",
     hook_payload("Tool__Math__Multiply", {"left": "a"}),
     "block"),
    ("ILLEGAL, tool has no closed-mapping entry",
     hook_payload("Tool__File__Edit", {"file": "x.py"}),
     "block"),
]


def main() -> int:
    failed = 0
    for title, payload, expected in SCENARIOS:
        decision = gate(payload["tool_name"], payload["tool_input"])
        actual = decision["decision"]
        status = "PASS" if actual == expected else "FAIL"
        if actual != expected:
            failed += 1
        print(f"[{status}] {title}")
        print(f"      tool={payload['tool_name']} input={payload['tool_input']}")
        print(f"      decision={actual} (expected {expected})")
        print(f"      agent-sees-reason: {decision['reason']}")
        print()
    print(f"{len(SCENARIOS) - failed}/{len(SCENARIOS)} scenarios correct")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())