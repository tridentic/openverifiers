# ADR 0001 — The eight architectural decisions

Status: **accepted** · Date: 2026-09-23

These are the load-bearing decisions recovered from the vision brief and
approved in discussion. Every later design must cite an ADR or this one. A
change requires a superseding ADR with rationale — silent drift is forbidden.

---

## Q1. Internal representation: the logical graph

**Decision.** Replace the flat `dict[str, Fact]` ledger with an own minimal
typed graph (typed nodes + typed edges) as the store. Not a library
substrate, not a ledger with index views.

**Rationale.** Provenance, scope, permission, and query semantics are core
concerns; no library provides them without imposing its own model. An
own graph keeps the smallest principled surface the vision demands.

**Consequence.** Queries, scopes, provenance, and context/freeze all build
on the graph. Costly to reverse after Phase 2 — locked first for that
reason.

## Q2. The grammar language: data-first, domain-agnostic, not Python

**Decision.** Grammar and proof are written in one declarative domain
language that compiles to a shared IR. Python is the host engine, never the
logical language.

**Rationale.** Python-author grammar is unreadable, unrenderable, and
unusable by domain experts. Grammar, proof, and query must be data: tree +
JSON renderable, diffable, version-controllable. Both the proof language
and the grammar language compile into the same IR family.

**Rules held.**
1. The grammar language is declarative — no loops, no author functions.
   Computation lives in solver-backed relations.
2. Semantics precede syntax: IR (Phase 10) first, surface syntax last
   (Phase 13).
3. Grammar is text and renderable, for non-programmers and automated
   viewers alike.

## Q3. Conditions: declarative guards, engine-evaluated

**Decision.** A condition is a declarative boolean guard over input facts,
written in the grammar language: existence, typing, equality,
owner/frame consistency, numeric constraints, and multi-fact
interdependence in the same shape. The engine evaluates every guard and
records per-condition truth with witnesses in the trace. The agent can
never assert a condition result.

**Consequence.** The `Transformation.precond` closure / `ConditionController`
duplication is unified into one engine-evaluated declarative path
(Phase 5). Explainability is structural: every guard renders with its
witness.

## Q4. Query semantics: typed unification, restricted

**Decision.** Queries are patterns with holes over the typed relational
graph; the engine fills holes by typed unification with binding
substitution. Repeated holes must agree or the query fails. Verdicts are
entailed / contradicted / unknown; absence is never false (open-world).

**Restrictions (v1).** No negation-as-failure. No disjunction. Contradiction
is reported, never concluded from absence.

## Q5. Proof scopes: first-class proof boxes

**Decision.** Assumptions open first-class proof boxes — scoped derivation
regions with their own fact sets. Discharge: box proving `Q` under
`assume P` yields `P → Q`; box reaching a contradiction yields `¬P`
(reductio). Box-local facts cannot leak outside unqualified — enforced
structurally, not by discipline.

**Consequence.** The frozen context stays immutable; proof-time facts live
in boxes. The current stack-based `assume`/`end` in `run_trace` is the
seed, not the model.

## Q6. Model-backed judgments: typed seam, real soon

**Decision.** A `ModelJudgment` seam: input facts, model id, declared
output schema, policy, evidence references, reproducibility contract.
Deterministic steps stay pure; judgment steps are typed, evidenced, and
marked (`estimated` status, trace markers). Backends plug behind the seam —
a deterministic stub judge first to exercise the semantics, then Jev.

**Rules held.**
1. A judgment result is a typed fact with evidence, never magically trusted.
2. Judgments cannot produce `truth` — only judged/estimated facts.
3. The seam is built before the first LLM judge; retrofitting it later
   would rewrite the core.

## Q7. Engine derivation: intent-style steps, no free search

**Decision.** The agent names a transformation and its inputs; the engine
computes the output, checks the conditions, and records the derivation.
The agent never submits a computed value or precomputed condition result.
No free backward/forward search in v1.

**Rationale.** This is the vision §3 invariant operationalized. The
`EquationController.solve_for` pattern already demonstrates it; Phase 4
generalizes it to data.

## Q8. Permissions: per-proof capabilities

**Decision.** Capabilities are per-proof grants: allowed transformations,
allowed model/judge access, step budgets, context access. The plugin gate's
hardcoded mapping promotes into the core capability path (Phase 16).

**Rationale.** Without grants, any proof may invoke any registered
transformation or judge. Grants make the trust boundary explicit and
traceable.