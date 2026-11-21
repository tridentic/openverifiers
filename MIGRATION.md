# Migration notes

Breaking changes, newest first. Each entry says what changed, why, and what
to do.

## M-CAP library layer (2026-11-22)

| change | before | after | what to do |
|---|---|---|---|
| new `.ov` keywords | `law`, `definition`, `lemma` were names | keywords (axiom kinds; class members) | rename anything named so (nothing in the repo was) |
| `physics.mechanics` | `axiom newton2` | `law newton2`, plus classes ConstantAcceleration, ConstantForce, UniformGravity, TwoBodyInteraction | none: the rule is unchanged |
| `math.core` | vocabulary only | quadratic, Vieta, AM-GM classes and theorems | none |
| class properties of a quantity type | unknowns refused (E206), formulas not unit-checked | unknowns allowed; formulas and pattern values dimension-checked (E301) | fix any E301 the checker now reports |
| WHAT IF RETRACT of a fact | re-ran the whole program | the fact is a hidden assumption; retracting it is a context change | none; answers are unchanged |

## v1 hygiene (change order v1.1, step 1)

| change | before | after | what to do |
|---|---|---|---|
| `ov` command | the pre-v1 step verifier (`ov check/trace/solve/bench/demo`) | the v1 CLI (`ov run FILE.ov [--verbose] [--strict]`) | use `ov-m1` for the old tool |
| `tolerance` | parsed and ignored | error E207 | remove it; arithmetic is exact |
| `derived` | substituted, not unit-checked | error E207 | inline the expression |
| `all x in C:` in a class body | one comparison chain | a quantifier whose body runs to the end of the enclosing body | put it last; use `->` for implications |
| names with a final digits part | `i-1` was one name | `i - 1` | none in the repo |
| `COUNTEREXAMPLE T.thm` | PROVEN when a counterexample exists | the theorem's verdict: REFUTED with the counterexample, PROVEN when none exists | flip `expect` lines |

## v1 Milestone 1b (object layer)

| change | before | after | what to do |
|---|---|---|---|
| new `.ov` keywords | `property`, `invariant`, `theorem`, `derived`, `exists`, `none`, `all`, `LIMIT`, `UNIQUE`, `COUNT`, `CHECK`, `IS`, `COUNTEREXAMPLE` were names | they are keywords | rename any entity, field or predicate that used one (none in the repo did) |
| `deg` | not a unit | a unit with its own dimension (angles stay exact) | none |

No dependency changes: z3-solver was already a runtime dependency.

## v1 Milestone 1 (OV front end)

| change | before | after | what to do |
|---|---|---|---|
| new runtime dependency | sympy, z3-solver | adds `lark>=1.1` (allowed by the v1 brief) | reinstall: `uv pip install -e ".[dev]"` |

Nothing else breaks: `openverifiers.lang`, `openverifiers.lower`,
`openverifiers.runner` and `openverifiers/packages/` are new.

## v1 restructure (branch `v1`)

| change | before | after | what to do |
|---|---|---|---|
| src layout | package at repo root `openverifiers/` | `src/openverifiers/` | reinstall: `uv pip install -e ".[dev]"`. Running from a checkout without installing needs `PYTHONPATH=src` |
| Milestone-1 verifier moved | `openverifiers.kernel`, `.domains`, `.proposers`, `.case`, `.cli`, `.demo` | `openverifiers.m1.kernel`, `openverifiers.m1.domains`, … | replace `openverifiers.` with `openverifiers.m1.` in imports. The API is unchanged and frozen |
| M1 benchmark moved | top-level `benchmarks` package, cases in `benchmarks/cases/` | `openverifiers.m1.benchmarks`, cases in `src/openverifiers/m1/benchmarks/cases/` | `python -m openverifiers.m1.benchmarks.run`. The top-level `benchmarks/` now holds the v1 `.ov` suites |
| `openverifiers.kernel` means something new | M1 step-DAG checker | v1 labelled Datalog evaluator (untrusted; the trusted parts are `openverifiers.raw` and `openverifiers.checker`) | code importing the old kernel must switch to `openverifiers.m1.kernel` |
| M1 docs moved | `README.md`, `STATUS.md`, `DECISIONS.md`, `docs/architecture.md` | `docs/m1/` | the root README now describes v1 |
| legacy hook path | `.claude/settings.json` ran `openverifiers/legacy/plugin/pre_tool_use.py` | `src/openverifiers/legacy/plugin/pre_tool_use.py` | none |
| `ov` CLI | M1 commands | still M1 until v1 Milestone 3, then the v1 CLI (`run, check, lower, query, prove, bench, add, serve`). M1 commands move to `ov-m1` | scripts calling `ov check <case.json>` should switch to `ov-m1` once M3 lands |
| license (planned, M7) | MIT | Apache-2.0, as requested by the v1 brief | none for users; contributors note the relicense |
