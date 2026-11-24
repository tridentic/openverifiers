"""OpenVerifiers SDK quickstart (docs/SDK.md). Run from the repository root:

    python examples/sdk/quickstart.py
"""

from __future__ import annotations

import json

from openverifiers import sdk

# 1. Check a file: every query, with its verdict and what it rests on.
report = sdk.check("examples/chem/q11.ov")
for q in report.queries:
    print(f"{q.verdict:9} {q.query}")
    print(f"          values={list(q.values)} trust={list(q.trust)} "
          f"assumptions={list(q.assumptions)}")
print("ok:", report.ok)

# 2. Check source text, and catch a file that does not load.
demo = """package demo
type Thing
predicate checked(x: Thing) world closed
scenario s uses demo {
  entity a, b: Thing
  fact checked(a)
  query PROVE checked(a)
  query PROVE checked(b)
}
"""
for q in sdk.check_source(demo, name="demo.ov").queries:
    print(q.query, "->", q.verdict, "(kernel-checked)" if q.kernel_checked else "")
try:
    sdk.check_source("package broken\nfact q(z)\n", name="broken.ov")
except sdk.OVError as e:
    print("does not load:", sorted({d.code for d in e.diagnostics}))

# 3. The agent tool-call gate under a policy.
for tool, target in (("run_tests", "feature"), ("push", "main"), ("deploy", "prod"),
                     ("format", "disk")):
    d = sdk.gate_tool_call("drafts/policies/repo_policy.ov", tool, target, drafts=True)
    print(f"{tool} {target}: {d['decision']}")

# 4. Plain JSON for agents.
print(json.dumps(report.to_json()["queries"][0], indent=2))
