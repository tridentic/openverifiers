"""Claude Code gate plugin — end-to-end hook contract tests.

These shell out to the REAL hook script with synthetic PreToolUse payloads,
exactly as Claude Code would invoke it, and assert the allow/block proto.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]   # openverifiers repo root
HOOK = REPO / "plugin" / "pre_tool_use.py"


def run_hook(payload: dict) -> tuple[dict, int]:
    proc = subprocess.run([sys.executable, str(HOOK)],
                          input=json.dumps(payload), capture_output=True,
                          text=True, cwd=REPO, timeout=30)
    return json.loads(proc.stdout or "{}"), proc.returncode


def test_legal_call_allowed():
    out, code = run_hook({"hook_event_name": "PreToolUse",
                          "tool_name": "Tool__Math__Multiply",
                          "tool_input": {"left": "a", "right": "b"},
                          "tool_use_id": "t"})
    assert out["decision"] == "allow"
    assert out["reason"].startswith("OpenVerifiers:")
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_semantic_violation_blocked_with_retryable_reason():
    out, _ = run_hook({"hook_event_name": "PreToolUse",
                       "tool_name": "Tool__Math__Multiply",
                       "tool_input": {"left": "a", "right": "a"},
                       "tool_use_id": "t"})
    assert out["decision"] == "block"
    assert "z == 9.0 canonical, expected 12.0" in out["reason"]  # the retry hint


def test_unmapped_tool_blocked():
    out, _ = run_hook({"hook_event_name": "PreToolUse",
                       "tool_name": "Tool__File__Edit",
                       "tool_input": {"file": "x.py"}, "tool_use_id": "t"})
    assert out["decision"] == "block"
    assert "no mapping" in out["reason"]


def test_non_frozen_ref_blocked():
    out, _ = run_hook({"hook_event_name": "PreToolUse",
                       "tool_name": "Tool__Math__Multiply",
                       "tool_input": {"left": "a", "right": "ghost"},
                       "tool_use_id": "t"})
    assert out["decision"] == "block"
    assert "not a frozen context ref" in out["reason"]


def test_non_pre_tool_use_event_ignored():
    out, _ = run_hook({"hook_event_name": "PostToolUse",
                       "tool_name": "Anything"})
    assert out == {}  # no decision JSON -> Claude Code continues normally


def test_garbage_stdin_fails_closed():
    proc = subprocess.run([sys.executable, str(HOOK)],
                          input="not json", capture_output=True, text=True,
                          cwd=REPO, timeout=30)
    assert json.loads(proc.stdout)["decision"] == "block"