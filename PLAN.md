# OpenVerifiers v1 plan

What v1 builds is set by the v1 brief. This file covers how it gets built, in
what order, and what could go wrong. Each milestone ends with the full test
suite green and its own commit.

## Starting point

The repo has two earlier systems. Both keep working, and both move under `src/`.

| code | what it is | v1 fate |
|---|---|---|
| `openverifiers/legacy/` | pre-M1 pydantic runtime (linear traces, physics relations, Claude Code hook). 202 tests | moved to `src/openverifiers/legacy/` unchanged |
| `openverifiers/{kernel,domains,proposers,...}` | Milestone-1 step-DAG verifier: unit-aware math pack, sympy/z3 hooks, mutation benchmark. 108 tests | moved to `src/openverifiers/m1/`. Its ideas are reused (see below), its API is frozen |

What v1 reuses from M1:

- **Ideas.** Proposers are untrusted, hooks fail closed, unknown never passes
  silently, rejections carry structured reasons, and trace filters are success
  path vs failure trail.
- **Code.**
  - The SI dimension-vector algebra in `m1/domains/math/units.py` becomes the
    `units` plugin, rewritten to exact rationals.
  - The safe sympy parsing and residual check become the `sympy` plugin.
  - The z3 root-uniqueness check becomes part of the `z3` plugin.
- **Not reused.**
  - M1's proof format (pre-chosen step DAG with effects). v1 derives proofs by
    evaluation, which RawOV rules need.
  - The M1 kernel itself. It has no rules, unification, negation or labels.

`MIGRATION.md` lists every breaking change.

## Module map (`src/openverifiers/`)

| module | role | trusted | strict mypy | milestone |
|---|---|---|---|---|
| `raw/terms.py` | terms, atoms, literals, rules, program, standard term order, matching | yes | yes | M0 |
| `raw/labels.py` | signed environments, antichain labels, combine/negate/minimise | yes | yes | M0 |
| `raw/builtins.py` | exact rational arithmetic with dimensions, comparisons, `sort_args` | yes | yes | M0 |
| `raw/text.py` | canonical RawOV text: printer and small recursive-descent parser | yes | yes | M0 |
| `checker/` | trace re-verification: local justification, closure certificate, strata, verdict recomputation | yes | yes | M0 (+M2 plugin re-checks) |
| `kernel/` | stratifier, semi-naive labelled evaluator, budgets, blocked-frontier search, verdict construction | no | yes | M0 |
| `kernel/semiring.py` | `Semiring` protocol: Bool, Label, Why, Count, Tropical | no | yes | M2 (Label in M0) |
| `lang/` | Lark grammar, AST, type checker, units, errors with spans | no | partial | M1 |
| `lower/` | OV AST → RawOV (deterministic, keeps spans) | no | partial | M1 |
| `raw/formula.py` | object-layer formulas as RawOV terms; exact ground evaluator (sets, tuples, cycles, `dist`, `angle`) used to re-check every instance | yes | yes | M1b |
| `objects/` | concept classes: inheritance (diamond-safe), expansion of invariants over finite generators with symmetry, FIND/UNIQUE/COUNT/CHECK/COUNTEREXAMPLE, theorem checking | no | yes | M1b |
| `plugins/` | `units`, `sympy`, `z3`, `chem`; one `Plugin` protocol | no | partial | M2 |
| `trace/` | OVTrace JSONL plus text/JSON/DOT/HTML renderers | no | partial | M3 |
| `state/` | OVState canonical JSON, SHA-256, load/import, optional ed25519 | yes (hash+load) | yes | M3 |
| `okql/` | query grammar, planner, verdicts, why/why-not/what-if/near/depends | no | yes | M4 |
| `prover/` | backward chaining, abduction, Search/Constraint/LLM proposers, gap report | no | partial | M6 |
| `cli/` | `ov run, check, lower, query, prove, bench, add, serve` | no | no | M3+ |
| `mcp/` | optional MCP server | no | no | M7 |
| `packages/` | `.ov` standard library (content) | — | — | M5 |

**Trusted base:** `raw/` + `checker/` + `state/{hash,load}`. CI fails if it
exceeds 1,500 non-blank, non-comment lines. A test parses the imports and fails
if `checker/` imports `kernel`, `prover` or `okql`.

## Core semantic decisions (full definitions go in `docs/SEMANTICS.md`)

1. **Labels use signed environments.** An environment is a set of literals:
   `a` means assumption a is active, and `¬a` means it is not.
   - A context C (the set of active assumptions) satisfies e when the positive
     part of e ⊆ C and the negated part of e ∩ C = ∅.
   - A closed-world `not p` gets the label "negation of label(p)": the
     minimal hitting sets of label(p) with every literal flipped.
   - This keeps every label exact under stratified negation, which makes
     `WHAT IF ASSUME/RETRACT <assumption>` a pure label lookup even through
     negation. The brief's `{∅}`/`{{a}}` labels are the special case with no
     negations.
   - The q11 uniqueness argument needs this: `B = pent-1-ene` holds in
     `{single_major}` *because* the competing candidate is eliminated only
     under it.
2. **The trace is a certificate, not a log.** Each fired step records the
   head atom's *cumulative* label after the firing, plus `prev` (the atom's
   previous step) and premise step ids, which must be earlier in the trace.
   The checker verifies two things:
   - *Local justification:* rule exists, head and body match the
     substitution, builtins hold, `label = min(label(prev) ∪ combine(premises))`.
     This makes every claimed label env sound and the trace well-founded.
   - *Closure:* one pass of rule matching over the claimed model for each
     stratum. No claimed-missing derivation may exist. This makes the model
     exactly the least labelled model, which is what closed-world negation
     and refutation rely on.

   Checking closure is one pass, not a fixpoint, so the checker stays smaller
   and simpler than the evaluator.
3. **Open-world `not p` lowers to the positive literal `neg p`.** It can be in
   the same stratum. Only closed-world `not` creates a stratification edge.
4. **Budgets.** Step count, term depth, atom count, label size and wall time.
   - Exceeding one marks the stratum *incomplete*. Evaluation stops at that
     stratum, because the strata above it would rely on its completeness.
   - Sound positive answers (PROVEN, and REFUTED through `neg`) survive.
   - Anything that needs completeness becomes `UNKNOWN(budget)`.
   - A label over its size cap marks its atom *truncated*. Negation over a
     truncated atom is blocked, and its own non-PROVEN verdict becomes
     `UNKNOWN(budget)`.
5. **Verdicts are computed by the checker module** from the checked model. The
   kernel adds only UNKNOWN's `missing` frontier, which is untrusted, and the
   checker confirms that each listed atom is indeed not established in C.
6. **Generator variables (q11's A, B).** A stated fact about an unknown entity
   eliminates a candidate only when its contradiction is *derived*. A value is
   PROVEN only when exactly one candidate survives a complete domain. Several
   survivors give UNKNOWN; none gives INCONSISTENT. In M0 this is hand-written
   RawOV; M1 lowering generates it.
7. **Lowering decisions (M1).**
   - A head equation becomes one rule per solvable slot.
   - Functional predicates and fields get a clash rule (`neg f(x, v2)` on a
     second value), so disagreements surface as INCONSISTENT.
   - Facts that are not atoms become `neg ov.consistent` checks.
   - Unknowns are solved by the generator semantics of point 6, generated
     per connected component.
   - Open-world `not` lowers straight to the positive literal `neg p`.

   Details are in `docs/LANGUAGE.md`.
8. **Object layer (§3.7, added to the brief after M1 was planned).**
   - A `fact type` lowers to a RawOV *class definition*: its property names
     and one formula, the conjunction of its own and inherited invariants
     (a shared ancestor once). Formulas are RawOV terms, so they print,
     parse and round-trip like everything else.
   - Formulas stay exact: `dist` comparisons are squared, `angle(a,b,c) = θ
     deg` becomes a polynomial condition on the dot product for θ in
     {0, 30, 45, 60, 90, 120, 135, 150, 180}. Other angles are rejected,
     never approximated.
   - Solving (FIND, UNIQUE, COUNT, theorems, COUNTEREXAMPLE) is untrusted:
     the expander turns the formula into polynomial constraints and z3
     solves them. Every model is re-checked by the trusted ground evaluator
     in `raw/formula.py`, which enumerates *all* cyclic orders (no symmetry
     pruning), so pruning in the solver cannot hide a wrong answer.
   - Unsat answers (UNIQUE, theorem PROVEN, empty class) cannot be checked
     by substitution. They are re-solved in a fresh solver, as the brief
     allows for unsat cores, and the result says so.
   - Theorems and class consistency are checked on a generic instance whose
     collection sizes come from `count(p) = n` invariants. A class with an
     unbounded collection gives UNPROVEN, not a guess.
9. **`WHAT IF RETRACT <fact>`.** Facts have the label `{∅}`, so retracting a
   fact is a re-run, not a lookup. M4 adds an opt-in mode that tags scenario
   facts with hidden tokens so fact retraction is a lookup too. M5 measures
   both modes.

## Milestones

| | deliverable | exit criteria |
|---|---|---|
| **M0** ✅ | `raw/`, `kernel/`, `checker/`, labels, verdicts, stratified negation, budgets. q11 in hand-written RawOV | round-trip and hypothesis tests; stratification errors; checker rejects 100% of trace mutations; q11 reference answers including `{single_major}` |
| **M1** ✅ | `lang/` (Lark, LALR), type and unit checker, `lower/` with spans, error codes, `docs/LANGUAGE.md` | §3.5 physics test and §3.6 q11 run from `.ov`; error-code tests with exact spans |
| **M1b** ✅ | object layer (§3.7): `fact type`, `property`, `invariant`, `theorem`, `derived`, `extends` (diamond), `Set`/`List`, generators `cycles`/`orderings`/`subsets`/`pairs` with symmetry, instance patterns, FIND / PROVE UNIQUE / COUNT / CHECK IS / COUNTEREXAMPLE, `ov check` for theorems, `math.geometry` package. Needs z3 early (pulled forward from M2) | §3.7 square: PROVEN (3,5), PROVEN UNIQUE, trace solve → re-check → uniqueness unsat; every `math.geometry` theorem proven; a false theorem refuted with a checked counterexample; an empty class reported INCONSISTENT; symmetry pruning never changes a verdict |
| **M2** | plugin protocol plus `units`, `sympy`, `z3`, `chem` (structure generator for isomers); checker re-verification of models, cores and solutions; semiring family | buggy-plugin tests rejected; all semirings agree with Bool on the derived set; z3 cores become nogoods |
| **M3** | OVTrace renderers (text, JSON, DOT, single-file HTML), OVState with hash, import and ed25519, `ov` CLI | tampered state hash rejected; import never raises trust; CLI snapshot tests |
| **M4** | OKQL: PROVE, FIND, WHY, WHY NOT, WHAT IF, NEAR, DEPENDS ON, EXPLAIN; `docs/OKQL.md` | WHAT IF by lookup equals a full re-run (property test); answers re-checked |
| **M5** | packages (math, logic, physics, chem, agent, geometry) with ≥10 tests each; 7 benchmark suites (geometry/object layer added) with hand-written gold; `ov bench` and ablations | minimum suite sizes met; false-PROVEN = 0; `results/<date>/` written |
| **M6** | OVProver: AND–OR backward chaining, abduction (hitting sets), Search and Constraint proposers, optional LLM proposer, plan synthesis, gap report | the prover cannot reach the `state/` write APIs (structural test); synthesis targets in the agent suite |
| **M7** | docs, Dockerfile, CI gates, `scripts/reproduce.sh`, MCP server, `KNOWN_LIMITATIONS.md`, `REPORT.md`, Apache-2.0 relicense, `CITATION.cff` | definition-of-done checklist |

## Risks

| risk | mitigation |
|---|---|
| Signed labels blow up exponentially (hitting sets) | label-size budget makes the atom *truncated*, which is sound; report label sizes in the benchmarks |
| Checker closure pass is slow on 10k-fact programs | per-predicate first-argument index; closure only for strata a verdict depends on is a later optimisation if needed |
| Chemistry scope creep | v1 covers acyclic alkenes, carbonyls, alkyl halides and cyanohydrins as canonical substituent trees; RDKit is optional; names come from a structure→name table, but answers never do |
| LALR conflicts in a keyword-led grammar | grammar kept small; Earley fallback only per rule, documented |
| Nonlinear real solving (z3 nlsat) is slow or returns algebraic, non-rational models | budgets give `UNKNOWN(budget)`; irrational models cannot be re-checked exactly and give `UNKNOWN(plugin_unknown)` |
| Benchmark gold drift | gold is hand-written with a comment per case and never produced by running OV; a test enforces that each case has a comment |
| Relicensing MIT → Apache-2.0 | requested by the brief; done in M7 with a NOTICE line; flagged in MIGRATION.md |
| Two older systems in one package | each is isolated under `m1/` and `legacy/`, excluded from the v1 coverage and mypy gates, and removable later without touching v1 |
