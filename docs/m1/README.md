# OpenVerifiers

A Python toolkit for checking the work of AI agents. Anyone, whether a solver, an
LLM, or a person, may *propose* a proof. A small trusted **kernel** *checks* it,
step by step, and says exactly what is wrong when it is wrong.

Status: research prototype, Milestone 1. See [STATUS.md](STATUS.md) for what
works, what doesn't, and the measured numbers. Design choices and their reasons
are in [DECISIONS.md](DECISIONS.md). End-to-end diagrams of every stage are in
[docs/architecture.md](docs/architecture.md).

## The idea

Describe a situation as **facts** (typed values: `v = 20 m/s`, a spec, some
source code) and a goal as **requirements** (constraints that must hold at the
end: `d == 1.8 km`, "all checks pass"). A **proof** is a set of **steps**, each
applying a named **transformation** `f(facts) -> facts` to specific input facts.
The steps form a DAG, and the kernel derives it from fact ids.

```
facts ──step──▶ derived facts ──step──▶ ... ──▶ facts that satisfy the requirements
          ▲                                          ▲
   proposer claims each step's outputs     kernel recomputes or rechecks every claim
```

Proposers are **untrusted**. The kernel is **trusted**, in the same way a
proof assistant's kernel is: it is small (stdlib only, no LLM, no network),
deterministic, and never takes a proposer's word for a step's result. For each
step it checks that:

1. the inputs exist and are established (not a `target` or `unknown`),
2. the inputs have the right types and the preconditions hold,
3. the claimed outputs equal the outputs it **recomputes**, or, for steps that
   cannot be recomputed (a code change, a judgment), the step's **checker**
   accepts them,
4. a *grounded* step cites a source that actually exists.

It then checks every requirement against the final state. It does not stop at
the first error. Every step is reported as accepted, rejected or skipped,
with a structured reason, so the result can be fed back to the proposer.

`unknown` is a first-class fact status, not an error. An unknown fact says
`why_unknown` and what `evidence_needed`. A proof that depends on one is graded
`undetermined`, which is different from `invalid`.

Everything domain-specific (fact types, transformations, equality, predicates,
sources) lives in **domain packs**. The kernel has no idea what a unit, a
derivative or a test suite is. Two packs ship today, `math` and
`code_requirements`, and both run through the same kernel with no
kernel changes.

## Trust tiers

Every transformation declares a tier, and the verdict reports what its
validity rests on.

| tier | meaning | examples |
|---|---|---|
| `hard` | deterministic: recomputed or mechanically checked | arithmetic with units, sympy solve with residual check, z3 uniqueness proof, running tests |
| `grounded` | backed by a retrieved source; the cited source must exist in the pack and the pack's checker must find the claim in it | a physical constant read from a CODATA table |
| `soft` | judgment (an LLM or a person); accepted only conditionally | "this summary is faithful" |

The **trust grade** of a valid proof depends only on the steps its satisfied
requirements actually rest on:

| grade | when |
|---|---|
| `fully_hard` | every supporting step is hard |
| `grounded` | some supporting step is grounded, none soft |
| `conditional_on_unverified_facts` | rests on initial facts marked `unverified` (listed) |
| `conditional_on_soft_steps` | rests on soft steps (listed in `soft_steps`) |
| `undetermined` | nothing is wrong, but a requirement depends on an `unknown` fact |
| `invalid` | some rule failed; see `failures` |

## Quick start

```bash
pip install -e ".[dev]"
ov-m1 check benchmarks/cases/math/math_braking_force.json        # verdict JSON; exit 0 = valid
ov-m1 trace benchmarks/cases/math/math_braking_force.json --filter success_path
ov-m1 solve benchmarks/cases/math/math_braking_force.json --proposer backward
ov-m1 demo repair       # an LLM-style proposer is rejected, gets the reasons, then accepted
ov-m1 bench run         # mutation benchmark table
```

A case file holds `facts`, `requirements`, `candidate_proof` and (optionally)
`expected_verdict`. See [openverifiers/case.py](openverifiers/case.py) and
[the braking example](benchmarks/cases/math/math_braking_force.json).
Trace filters: `full` (every decision), `success_path` (the accepted steps the
requirements rest on), and `failure_trail` (only rejections and skips, with
reasons).

## Adding a domain pack

A pack is a `DomainPack` value: fact types, transformations, and optionally
predicates and a source store. This complete example runs as-is and is
executed by the test suite:

<!-- readme-example -->
```python
from openverifiers.m1.kernel import (DomainPack, Fact, FactType, Precondition, Proof,
                                  Requirement, Selector, Step, Transformation, check)

def is_int(f): return None if isinstance(f.value, int) else "not an integer"
def even(inputs, params): return None if inputs["n"].value % 2 == 0 else "n is odd"

halve = Transformation("halve", "hard", inputs={"n": "int"}, outputs={"half": "int"},
                       preconditions=(Precondition("even", even),),
                       effect=lambda i, p: {"half": Fact("_", "int", i["n"].value // 2)})
PACK = DomainPack("parity", fact_types={"int": FactType("int", validate=is_int)},
                  transformations={"halve": halve})

facts = [Fact("n", "int", 10)]
proof = Proof((Step("s1", "halve", inputs={"n": "n"}, outputs={"half": Fact("h", "int", 5)}),))
goal = [Requirement("r", Selector("h"), "equals", {"value": 5})]
verdict = check(facts, goal, proof, PACK)
assert verdict.valid and verdict.trust_grade == "fully_hard"
```

Hooks return `None` for "fine" or a reason string. A transformation needs an
`effect` (recompute the outputs), a `checker` (judge claimed outputs), or
both. To use a pack from the CLI, put it in a module exposing `PACK` and add
one line to `openverifiers/domains/__init__.py:PACKS`. If a domain ever seems
to need a kernel change, that is a design problem to raise, not a patch to
make.

## Layout

```
openverifiers/kernel/      trusted: model.py (data types), check.py (rules), serialize.py (JSON)
openverifiers/domains/     math/ (units, formulas, sympy, z3), code_requirements/ (pytest in a subprocess)
openverifiers/proposers/   untrusted: forward chainer, backward decomposer, LLM adapter, repair loop
openverifiers/legacy/      the pre-Milestone-1 runtime, kept intact (see DECISIONS.md)
benchmarks/                cases, mutation generator, three-setup comparison, results/
tests/                     kernel/ (one passing + one failing test per rule), domains/, legacy/
```

## Development

```bash
ruff check . && mypy && pytest -q
```

`mypy` runs strict on `openverifiers.m1.kernel`. The kernel's purity (stdlib-only
imports) is enforced by a test.

## License

MIT
