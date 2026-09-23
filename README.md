# OpenVerifiers

**Deterministic verification for AI-generated reasoning — typed core, no search, no DSL.**
Write a proof in Python, get a pass/fail/inapplicable verdict plus a JSON audit trace.

## The model in one line

LLM proposes, logic constrains: the model is nondeterministic, the envelope it
operates inside is not. Every step of a candidate proof is checked against a
declared rule; nothing is searched for, nothing is scored by an LLM judge.

## Typed core (the ground truth layer)

| Type | What it is |
|---|---|
| `Dimension` | 7 SI base exponents with `*` / `/` / `**` — compound dimensions compose, never hand-declare |
| `Unit` | real types (`Meter()`, `Joule()`, ...); a unit's `dimension` is composed from SI bases |
| `PhysicalObject` / `PointObject` | ownership/context; core code depends only on the base |
| `Fact` → `Quantity` / `ActionFact` | physics facts carry a typed `unit` (dimension is *derived*, never stored); coding facts carry no unit |

Because a `Quantity`'s dimension is read off its `unit` and cannot be set
independently, the "unit string vs dimension dict disagree" bug class is
structurally impossible — not patched, impossible.

```python
from openverifiers import Quantity, MeterPerSecond, PointObject
q = Quantity(value=10.0, unit=MeterPerSecond(), owner=PointObject(id="car_1"))
# the verbose canonical form always exists; Quantity.from_str("10 m/s") is a
# thin wrapper that builds exactly the object above — no bypass path.
```

## Controllers — the two ways rules become runnable Transformations

Both produce standard `Transformation` objects; the engine never knows which
kind produced one. Zero domain code lives in the controller classes.

**EquationController** — one registration, every solve direction:

```python
from openverifiers.domains.physics import SUT   # s = u t + (1/2) a t^2
from openverifiers import Quantity

s = SUT.solve_for("s",
                  u=Quantity(value=5.0, unit=SUT.vars["u"]),
                  a=Quantity(value=2.0, unit=SUT.vars["a"]),
                  t=Quantity(value=10.0, unit=SUT.vars["t"]))
# -> Quantity(value=150.0, unit=Meter())
```

Kinematics (SUVAT), dynamics (`F = m a`, shared-owner checked), and energy
(`KE`, `W`) are each one `EquationController` — porting a direction is
`solve_for("x", ...)`, not a new rule. Momentum conservation is NOT an
equation-solve: it is a **condition**.

**ConditionController** — named predicates over facts:

```python
from openverifiers import ConditionController
from openverifiers.domains.coding import default_conditions

coding = ConditionController("coding-invariants", default_conditions())
per_action, claims = coding.check_trace(actions)
# claims surface explicitly-unknown facts; verdicts are never guessed
```

Conservation laws (`domains/conservation.py`) are conditions too —
`sum(before) == sum(after)` with the same 1e-6 relative tolerance every other
numeric comparison uses.

## Verdicts

`pass` / `fail` / `inapplicable` — per check, never blended into one score.
A fact with `status="unknown"` makes its check `inapplicable`, never a silent
pass or fail, and is named in the unverifiable-claims list.

## Engine & audit

```python
from openverifiers import Engine
from openverifiers.formats import save_audit

t = SUT.as_transformation("s")
result = Engine().run(t, {u: ..., a: ..., t: ...})
save_audit("run.ovpv", result)   # JSON audit trace, written AFTER the run
```

`.ovpv` is JSON written by the engine — never hand-authored, never parsed back
in. The verification surface is Python.

## What is NOT here (by design)

- **No search.** `solve_for` solves exactly the declared equation for exactly
  the named unknown; a variable outside the equation is a hard error. No
  registry, no backward chaining, no cycle detection.
- **No hand-written per-direction rules.** One equation registration covers
  all its variables.
- **No DSL, no parser, no viz tool.** Rules and proofs are Python; the audit
  trace is the artifact.
- **No LLM-judge/statistical layer.** Every verdict is deterministic and
  replayable.
- `experimental/` holds archived pre-typed-core modules (route SAT, circuits,
  proof trees) — not shipped, not imported.

## Tests

## v2 — trace-driven, proof-capable, observable, multi-domain

`openverifiers/v2.py` adds the second-generation entrypoint:

* **Closed DSL** (`parse_dsl`) — steps are Pydantic-validated records; the
  parser has no code-execution paths. Attempted injection is unparsable.
* **Whitelist registry** (`Registry`) — `Grammar`s carry named transformations
  and baseline facts; the runner dispatches ONLY through registered names.
  Unknown names and dynamic-attribute tricks fail closed (`invalid`).
* **Proof semantics** — `assume`/`end` scopes with conditional discharge
  (produces an `ImplicationFact`), `end contradiction` with conflict detection
  + grammar-declared exclusive pairs, plus `math` grammar patterns for modus
  ponens and induction. The induction step is CHAIN-validated, not shape-only:
  `proof.step` consumes its predecessor (so the implication's
  `DerivationRecord` names the `P(k)` fact it extends) and
  `induction.combine` requires the base's id inside that chain plus one
  closed-form expression agree across base/step/forall. Honest claim about
  what induction guarantees: *the forall conclusion is trace-derived from a
  registered `P(k)->P(k+1)` step whose derivation chain names the same `P(0)`
  base, all agreeing on one closed form — the algebra *inside* the step
  remains a declared assertion, not a verified computation.*
* **Provenance tiers** — every fact is `verified` | `extracted` |
  `assumption-dependent` (`Fact.provenance` / `effective_provenance`); renders
  and `submit()` payloads report tier counts.
* **Typed scenes** (`openverifiers/scenes.py`) — harness-authoring surface
  for frozen contexts: `with <object> as owner:` scoped construction
  (pythonic-verifiers ergonomics; `PhysicalObject.__enter__`), typed
  `owner: PointObject` references on framed properties (never string-key
  conventions), label==id enforcement, owner/frame consistency validation,
  and `to_context()` producing the exact `dict[str, Fact]` submit consumes.
  Domain grammars carry **no scenario objects** — every scene builds fresh
  frames/owners (see chase_v2 example + `tests/test_v2_scenes.py`).
* **Domains** — `domains/math.py` (arithmetic + proofs), `law.py`
  (statute-element slice), `business.py` (compound value), `english.py`
  (extraction adapter + agreement). `domains/standard_grammars()` bundles them.
* **Syllabus physics primitives** — `domains/physics_primitives.py` +
  `domains/algebra.py`: ONE textbook relation per registered transformation
  (~60 relations across kinematics/dynamics/energy/SHM/waves/heat/
  electrostatics/circuits/magnetism/optics/modern), each usable numerically
  (bind all-but-one variable) or symbolically (leave the output + a shared
  unknown free -> ExpressionFact). Composition is the AGENT-AUTHORED trace
  via the generic `alg.equate` step — NO pre-composed scenario
  transformations. Dataset: `datasets/physics_syllabus_problems.csv` (200
  HSC/JEE-A/BUET archetypes with per-problem solve chains);
  `datasets/coverage_report.py` publishes
  `docs/coverage_report.md` (192/200 solvable today, 8 structurally
  out-of-scope calculus/ODE flagged). Proven e2e: `examples/chase_v2.py`,
  `examples/incline_energy.py`, `examples/heater_thermal.py`.
* **Entrypoints** — `submit(mission, traces=..., background=...)` returns a
  JSON-consumable dict; `python -m openverifiers trace FILE.trace --fact a=3`
  renders the scope tree to a terminal (see `examples/math_proof.trace`).

## Claude Code gate plugin

`plugin/` is a PreToolUse gate that runs every intercepted tool call through
`submit()` before letting it through:

* `.claude/settings.json` wires the hook; `plugin/.claude-plugin/plugin.json`
  is the plugin manifest.
* `plugin/frozen.py` is the ONLY harness-authored surface: frozen per-grammar
  contexts, mission targets, and the closed tool->transformation mapping.
  The hook (`plugin/pre_tool_use.py`) never builds facts or queries.
* Dispatch stays in the Registry: the mapping only picks a registered
  transformation name; resolution, whitelisting and failure handling are
  run_trace/submit's. Unmapped tools and unknown names are blocks.
* Decisions carry the verdict `reason` (e.g. `z == 9.0 canonical, expected
  12.0`) so the agent can retry with a corrected call.

Run the demo: `python3 plugin/demo_gate.py` (5 scenarios: legal allow,
semantic-violation block, unknown-ref block, missing-field block, unmapped
block). Tests: `tests/test_v2_plugin_gate.py` exercises the real hook over
stdin.

## Status database

`status/` tracks the project's families, decisions, and shipped slices as a
machine-readable database. Core model details live in `model.py`, `facts.py`,
`units.py`, `controllers.py`, `engine.py`.

## License

MIT