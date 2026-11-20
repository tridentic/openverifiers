# OpenVerifiers

Write domain knowledge as code, check every conclusion with a small trusted
kernel, and answer queries with a proof, a refutation, or an honest UNKNOWN.

> Nothing becomes TRUE unless it traces, through checked rules, back to
> declared axioms and stated facts. The evaluator proposes; only the checker
> decides.

**Status: v1 Milestones 0, 1 and 1b are done.** That covers the RawOV kernel
IR, the labelled evaluator, the independent checker, the `.ov` language front
end and its object layer (concept classes with invariants and proven
theorems). Plugins, OVState, OKQL and the prover come in later milestones; see
[PLAN.md](PLAN.md) and the checklist in [PROGRESS.md](PROGRESS.md). The
language is described in [docs/LANGUAGE.md](docs/LANGUAGE.md). The definitions are in
[docs/SEMANTICS.md](docs/SEMANTICS.md) and the shortcuts in
[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md). What moved is in
[MIGRATION.md](MIGRATION.md). The Milestone-1 step verifier still works under
`openverifiers.m1` ([docs/m1/](docs/m1/README.md)).

```bash
uv pip install -e ".[dev]"
python -m openverifiers.runner examples/chem/q11.ov --verbose   # HSC q11 from .ov
python -m openverifiers.runner examples/physics/newton2.ov       # the brief's physics test
python -m openverifiers.runner examples/geometry/square.ov --verbose  # §3.7: fourth vertex (3,5), unique
python -m openverifiers.runner src/openverifiers/packages/math/geometry.ov  # classes, proven theorems
python scripts/q11_raw.py          # the same q11 from hand-written RawOV (Milestone 0)
ruff check . && mypy && pytest -q  # 486 tests
python scripts/tcb_size.py         # trusted code must stay under 1,500 lines
```

| module | role | trusted |
|---|---|---|
| `openverifiers.raw` | RawOV terms, signed assumption labels, exact unit arithmetic, canonical text, trace format, the exact evaluator for class formulas | yes |
| `openverifiers.checker` | re-verifies every trace step, checks closure, computes verdicts | yes |
| `openverifiers.kernel` | stratified semi-naive evaluator with labels and budgets | no (checked) |
| `openverifiers.engine` | evaluate → check → verdict | no |
| `openverifiers.lang` | `.ov` parser (Lark LALR), names, types, units, error codes | no |
| `openverifiers.lower` | OV → RawOV, deterministic, keeps source spans | no |
| `openverifiers.objects` | concept classes: compile to RawOV formulas, expand to polynomial constraints, solve with z3, re-check every model, check theorems | no (re-checked) |
| `openverifiers.runner` | run a `.ov` file: queries, `expect` checks, proofs | no |
| `openverifiers/packages` | standard `.ov` packages: `math.core`, `math.geometry`, `physics.mechanics`, `chem.organic` | content |
