"""The library surface as it is used today (no documented SDK at this commit).

Run from the repository root: python docs/masterbook/examples/sdk_demo.py
"""

from openverifiers.checker import verdict
from openverifiers.engine import ask, run
from openverifiers.rawtext import parse, parse_atom
from openverifiers.runner import render, run_file

# 1. A whole .ov file: check, lower, evaluate, check the trace, answer the queries.
res = run_file("examples/chem/q11.ov")
for a in res.answers:
    print(a.plan.query.text, "->", a.verdict, sorted(a.trust_base))
print(render(res).splitlines()[1])

# 2. RawOV directly: evaluate (untrusted), check (trusted), ask.
prog = parse(open("docs/masterbook/examples/labels.rawov").read())
r = run(prog)
q = parse_atom("warn(lawn)")
print("warn(lawn), all assumptions:", type(ask(r, q)).__name__)
print("warn(lawn), no assumptions: ", type(verdict(r.model, q, frozenset())).__name__)
print("trace steps:", len(r.trace.steps), "strata:", dict(r.trace.strata))
