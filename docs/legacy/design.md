# OpenVerifiers — Design History (Canonical Record)

Status: **finalized v1 scope** unless marked otherwise. Supersedes informal notes.
This is the conversation-level record: origins, decisions, and rationale.
The implementation spec lives in [`ARCHITECTURE.md`](../ARCHITECTURE.md); the
research that informs open design questions lives in
[`docs/research/`](research/).

## 1. Origin and scope

OpenVerifiers is an open-source Python toolkit for verifying AI agent claims —
plans, derivations, factual assertions — through two complementary pipelines:

- **Symbolic pipeline** (deterministic, solver-backed): Z3 for constraints,
  sympy for algebra.
- **Statistical pipeline**: LLM-as-judge for claims that do not reduce to
  formal logic.

It is meant to be usable standalone (Python SDK + CLI) or as an MCP tool any
agent can call.

### Founder's thesis

LLM agents produce confident-sounding output that is frequently internally
inconsistent, and almost nothing in the current agentic-AI ecosystem checks
*why* a claim is true — only whether it superficially looks right. OpenVerifiers
exists to make every claim trace back to explicit, checkable evidence.

### Candidate application domains (physics first, others later)

1. Personal high-stakes life planning (Snayu AI / LifeOS — the founder's
   original product).
2. Physics problem solving (JEE / CBSE / HSC level).
3. Lawyer / legal-contract agent.
4. Math proof checking.
5. Finance / financial-plan checking.
6. Medical / health-plan validation.
7. Code / refactor-plan verification.
8. Research-claim verification.
9. Travel itinerary planning.
10. Study-prep roadmap validation.

## 2. Core ontology (finalized v1)

- **Fact node**: `id`, `value`, `attributes` (typed, domain-specific),
  `status` (`truth` / `unverified_truth` / `derived` / `target` / `unknown`),
  `source`, `derivation reference`.
- **Transformation / rule node**: `precondition` (attribute/dimension/type
  checks that must hold before the rule applies), `relation` (the math/logic
  applied), `solver hook` (which backend resolves it — sympy, Z3, extensible
  per domain).
- **Unknown node**: first-class, not a failure state. Carries *why* it is
  unknown and *what evidence* would resolve it. Modeled like dark energy:
  acknowledged as unexplained rather than silently erroring.

## 3. Reasoning modes

- **Induction**: start from truth nodes, derive forward toward an unknown
  target.
- **Deduction**: start from the target, decompose backward toward known truths.
- The same fact/transformation structure supports both directions; no
  duplicated model.

## 4. Graph structure and trace policy

- Structure is a **DAG, not a tree**: no loops. Enforced via deduplication on
  fact identity and a rule forbidding edges back to ancestors. Loops were
  explicitly called "just confusion" — not a subtle case to allow.
- Trace storage is **fully verbose**: every path explored, every join point,
  every rejected branch and the reason for rejection, stored in full.
- Rendering is filtered on top of the same store: success-path-only,
  failure-trail, or full — these are views, not separate storage.

## 5. Grammar sourcing

- Two paths: **manual specification** (preferred/default) and **agent-based
  auto-extraction** (secondary, explicitly gated — an auto-extracted grammar
  must pass a benchmark suite of critical logical-checking tests before it is
  trusted).
- **v1: manual-only.** Auto-extraction is future work, benchmark-gated.

## 6. Root logic (explicit non-goal for v1)

- Domain-specific root facts/axioms are expected and fine.
- Whether a **minimal universal root-logic set** exists that all domain axioms
  reduce to is an open research question — **explicitly out of scope for v1**.
  Documented as a future research thread only.

## 7. Packaging

- Python SDK (core library) + CLI (thin wrapper) + MCP server (exposes
  `verify()` as an agent-callable tool).
- SDK/CLI/MCP boundary must stay clean: domain adapters must not leak internals
  into the wrong layer.

## 8. Implementation status (physically built, prior pass)

- Core engine, sympy solver hook, physics grammar (kinematics + mechanics),
  regex input extraction, CLI, 20-problem benchmark — **20/20 passing**.
- See [`ARCHITECTURE.md`](../ARCHITECTURE.md) and
  [`RESULTS.md`](../RESULTS.md). The vertical slice validated the deduction
  engine, dimension checking, and trace views.