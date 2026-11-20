# OpenVerifiers v1 progress

A live checklist. [PLAN.md](PLAN.md) holds the milestone design. This file
tracks what is actually done, grouped by the four product pillars. `[x]` means
built, tested and committed. `[~]` means partly done. `[ ]` means not started.

**Now:** M0, M1 and M1b (the object layer, §3.7 of the updated brief) are done (branch `v1`, not pushed). M2 (plugins) is next.

## Foundation: trusted core (M0) ✅

- [x] RawOV terms: symbols, strings, variables, compounds, exact rationals with units
- [x] Canonical RawOV text format: printer and parser, round-trip tested
- [x] Signed assumption labels (ATMS): conjoin, disjoin, negate, minimise
- [x] Stratifier with exact negative-cycle errors
- [x] Semi-naive labelled evaluator (checked equal to naive evaluation)
- [x] Budgets: steps, atoms, depth, label size, wall time, giving `UNKNOWN(budget)`
- [x] Open/closed world per predicate; strong negation `neg p`
- [x] Trace format (JSON lines) with cumulative labels
- [x] Independent checker: local justification, closure certificate, negation refs
- [x] Four verdicts: PROVEN / REFUTED / UNKNOWN(reason) / INCONSISTENT(conflict set)
- [x] WHAT IF assume/retract an assumption, done by label lookup and checked against a re-run
- [x] q11 chemistry question hand-written in RawOV, all four reference answers
- [x] TCB gate: 1,217 of 1,500 lines; the checker cannot import the kernel
- [x] Mutation testing: 100% of non-equivalent trace mutants rejected, including traces of lowered `.ov` programs
- [ ] CI run on GitHub (workflow written but never pushed or run)

## 1. DSL language (`.ov`): M1 ✅

| your note | status | milestone |
|---|---|---|
| Robust syntax, LALR grammar, errors with exact spans | [x] Lark LALR with no conflicts; 18 diagnostic codes with caret and hint, each tested with its exact span | M1 |
| Native equations and inequalities, exact units | [x] `=` is solved for whichever slot is missing; 31 units, 24 quantity types; `kg + m` is E301 | M1 |
| Core types: Fact | [x] `fact`, `assume`, `confidence`, `source` | M1 |
| Core types: Transformation | [x] `transformation ... requires ... ensures ...` | M1 |
| Core types: Controller / Generator | [x] generators with candidate elimination; controllers with guards (`pipe`/`branch` are ordering only) | M1 |
| Scenarios | [x] `scenario s uses pkg extends other { ... }` | M1 |
| Sugar lowered to fundamental facts and relations (OV → RawOV) | [x] deterministic, keeps spans, round-trips through RawOV text | M1 |
| Type and unit checker | [x] entity sorts with inheritance, quantity dimensions | M1 |
| `import physics` and other domain packages | [~] `import` and `uses` work; `math.core`, `physics.mechanics`, `chem.organic` exist; full content in M5 | M1 / M5 |
| Separate math packages (e.g. topology) | [~] `math.geometry` (classes, theorems, 13 tests); others M5 | M1b / M5 |
| Object layer: `fact type`, `property`, `invariant`, `theorem`, `extends` (diamond) | [x] invariants define, theorems are proven by the runner; empty classes are INCONSISTENT with the conflicting invariants | M1b |
| Collections and generators (`Set`, `List`, `cycles`, `orderings`, `subsets`, `pairs`) with symmetry | [x] identical orderings merged; verdicts equal with symmetry off (tested) | M1b |
| Instance patterns `T{field = ?x}` | [x] nested record patterns; sets with unknown elements split by coincidence | M1b |
| `derived` properties | [~] substituted inline; no unit check, no `requires` | M1b |
| Plugins: units, sympy, z3, chem, with results re-checked | [~] z3 for the object layer, every model re-checked by the trusted evaluator; the plugin protocol and the rest are M2 | M1b / M2 |
| Authored by an agent | [ ] (error codes and hints are built for it) | M6 |
| Auto-derived by algorithmic solvers | [ ] later | after v1 |

## 2. `ov` CLI and runtime

| your note | status | milestone |
|---|---|---|
| Library API | [x] `lang.load`, `lower.lower`, `runner.run_file`, `engine.run/ask` | M0–M1 |
| `ov program.ov --verbose` | [~] `python -m openverifiers.runner file.ov --verbose` works; the `ov` command is M3 | M3 |
| OV → RawOV | [x] | M1 |
| RawOV → OVTrace | [x] | M0 |
| Trace renderers: text, JSON, DOT, HTML | [~] text proof listing only | M3 |
| OVTrace → OVState: trusted, hashed, re-importable | [ ] | M3 |
| Importing a state never raises its trust | [ ] | M3 |

## 3. OKQL query language

| your note | status | milestone |
|---|---|---|
| Was a fact derived? (PROVE / FIND) | [x] inline in `.ov` (`query PROVE ...`, `query FIND ?x WHERE ...`) | M1 |
| Object queries: FIND over a pattern, PROVE UNIQUE, COUNT, CHECK x IS T, COUNTEREXAMPLE | [x] solve → exact re-check → block and re-solve; brief §3.7 square: PROVEN (3,5), PROVEN UNIQUE | M1b |
| Near match (NEAR) | [ ] | M4 |
| WHY / WHY NOT | [~] proofs and missing frontier exist; no query syntax | M4 |
| WHAT IF | [x] `WHAT IF RETRACT <fact or assumption> / ASSUME <name> THEN ...` | M1 |
| DEPENDS ON, EXPLAIN | [ ] | M4 |
| Queries over a saved OVState | [ ] | M4 |

## 4. OVProver

| your note | status | milestone |
|---|---|---|
| Given a target, generate a program that satisfies it | [~] `target { must ...; prefer ... }` parses and type-checks; no prover yet | M6 |
| Or satisfy as much as possible (gap report) | [ ] | M6 |
| Backward chaining and abduction (which facts are missing) | [ ] | M6 |
| Search, Constraint and optional LLM proposers, all untrusted | [ ] | M6 |
| The prover cannot write trusted state | [ ] | M6 |

## Evaluation and release

- [~] Standard packages: `chem.organic` has 10 tests; `math.geometry` 13 tests and 7 proven theorems; `physics.mechanics` 1; `math.core` is vocabulary only (M5)
- [ ] 6 benchmark suites with hand-written gold; `ov bench` with ablations (M5)
- [ ] Docs, Dockerfile, `reproduce.sh`, MCP server, Apache-2.0, `CITATION.cff` (M7)

## Numbers

| | M0 | M1 | M1b |
|---|---|---|---|
| tests | 413 | 459 | 486 |
| q11 end to end | 0.02 s (RawOV) | 0.25 s (`.ov`: parse, check, lower, evaluate, check trace) | same |
| §3.7 square, end to end (FIND, UNIQUE, class and theorem checks) | — | — | about 0.7 s |
| `math.geometry` (13 tests, 7 theorems, 9 classes) | — | — | about 3–10 s |
| trusted lines | 1,217 | 1,217 (the front end is untrusted) | 1,413 (+ `raw/formula.py`, the exact evaluator) |
| lowered q11 mutants rejected | — | 2,618 / 2,618 | same |
