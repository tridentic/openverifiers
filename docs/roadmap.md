# OpenVerifiers — Master Engineering Roadmap

Dependency-aware engineering graph. Status legend per task:
`[BLOCKED]` deps unmet · `[READY]` buildable now · `[IN PROGRESS]` ·
`[DONE]` · `[REJECTED]`.

Eight architectural decisions (Q1–Q8) are locked — see
`docs/decisions/0001-eight-architectural-decisions.md`. Nothing below may
silently contradict them; a change requires a new ADR.

Target architecture (one paragraph): a domain-agnostic logical verification
substrate. Facts live in a typed relational graph. Transformations consume
facts and derive facts; the engine performs the computation, the agent
supplies intent. Conditions are declarative guards the engine evaluates.
Grammar and proof are both written in one data-first domain language that
compiles to a shared IR — Python is the host, not the logical language.
Proof boxes give scoped assumptions with structurally impossible leakage.
Model-backed judgments are a typed seam with explicit evidence and
reproducibility contracts.

---

## Phase 0 — Repository hygiene `[READY]`

**Objective.** Repo installable from a clean clone, v2 work committed,
docs truthful. Nothing semantic.

**Dependencies.** None.

**Tasks.**
1. Add `pyproject.toml` (setuptools, flat layout) — `pip install -e .` must
   make `import openverifiers` work from anywhere. `[READY]`
2. Commit the uncommitted v2 working tree on a branch. `[READY]`
3. Prune dead/empty artifacts: `docs/master.md` (0 B), 
   `examples/english-grammar/1-basic.py` (0 B), README claims referencing
   deleted files (`examples/chase_v2.py`, `incline_energy.py`,
   `heater_thermal.py`, `math_proof.trace`, RESULTS.md benchmark),
   `status/` DB references to deleted `grammars/` and the `.ovpl` sketch.
   `[READY]`
4. Relocate syllabus catalogs (`examples/*/index.md`) to
   `docs/domain-scope/` — they are scope notes, not examples. `[READY]`
5. Keep the six stubbed Query subclasses but move them under a visible
   `# taxonomy stubs` marker (they document the contract; they must not be
   mistaken for shipped). `[READY]`
6. Add a CI test workflow (current `.github/workflows` only refreshes the
   OpenWiki). `[READY]`
7. Rewrite README to v2 reality. `[READY]`

**Acceptance.** `pip install -e . && pytest` green from repo root; no empty
files; no README claim points at a missing file.

**Risks.** Low. Test suite (202 passing) is the safety net.

---

## Phase 1 — Semantic foundations `[READY]`

**Objective.** `docs/semantics.md`: the minimal formal core, written before
more code. Definitions and invariants, explicitly tagged
`DEFINITION | INVARIANT | DECISION | OPEN QUESTION | IMPLEMENTATION NOTE`.

**Dependencies.** Phase 0.

**Tasks.**
1. Define: fact, entity, type, relation, transformation, condition,
   judgment, context, proof scope, derivation, provenance, query. `[READY]`
2. Write the invariant list (from the audit) + decision-derived invariants
   (Q1–Q8). `[READY]`
3. Trace the boundary: what the engine computes vs what the agent declares
   (§3 of the vision). `[READY]`

**Acceptance.** Every later phase cites `semantics.md`; no phase may redefine
a term it introduces.

**Open questions.** Term-language depth (deferred to Phase 10).

---

## Phase 2 — Core data model: the logical graph `[BLOCKED]`

**Objective.** The typed graph replaces the flat `dict[str, Fact]` ledger as
the store. (Q1 locked: own minimal typed graph.)

**Dependencies.** Phase 1 · ADR Q1.

**Tasks.**
1. `LogicalGraph` — typed nodes (fact/entity/relation/transformation/
   condition/judgment context) and typed edges (derives, assumes,
   contradicts, supports, refutes). `[BLOCKED]`
2. Identity layer — stable node refs; document the sameAs/differentFrom
   policy (research brief 03) before graph queries depend on it. `[BLOCKED]`
3. Immutability enforcement for frozen regions + derived render views
   (success-path/failure-trail/full survive as projections). `[BLOCKED]`
4. Port `context.py` ledger and `Graph` view onto the real store. `[BLOCKED]`

**Acceptance.** Query engine (Phase 6) reads this graph; 202 existing tests
green after the port.

**Risks.** Identity policy — relabeling attacks ride on string ids today.

---

## Phase 3 — Type / relation system `[BLOCKED]`

**Objective.** Typed relation declarations the grammar language (Phase 13)
instantiates.

**Dependencies.** Phase 2 · ADR Q2.

**Tasks.**
1. Type vocabulary: primitive `value` kinds (number/boolean/enum — already
   tagged in `facts.py`), unit-carried quantity types, entity types,
   slot descriptors (research synthesis §3), subtyping rules. `[BLOCKED]`
2. Typed relation declarations: `relation R over (T1, T2, ...)`. `[BLOCKED]`
3. Relation arity + role checking; type-check at load time. `[BLOCKED]`

**Acceptance.** A relation instance is well-typed by construction; a
wrong-type fact cannot bind to a relation slot.

---

## Phase 4 — Transformation model `[BLOCKED]`

**Objective.** Declarative transformations with solver-backed relations.
Agent names law + inputs; engine computes output (ADR Q7).

**Dependencies.** Phase 3 · ADR Q7.

**Tasks.**
1. Transformation record: `name, relation, inputs, conditions, output` —
   no Python closure as the source of truth. `[BLOCKED]`
2. Solver backends: sympy (algebra), numeric eval, Z3 (constraints) as
   adapter plug-ins behind the relation. `[BLOCKED]`
3. Intent-style execution: engine derives the output fact from the declared
   relation + inputs; agent never submits a computed value. `[BLOCKED]`

**Acceptance.** `EquationController` semantics reproduced as data; a wrong
value submitted by the agent is ignored/rejected, never blessed.

---

## Phase 5 — Condition engine `[BLOCKED]`

**Objective.** Conditions are declarative guards, engine-evaluated,
per-condition trace entries (ADR Q3).

**Dependencies.** Phase 4 · ADR Q3.

**Tasks.**
1. Guard language: existence, typing, equality, owner/frame consistency,
   numeric constraints — written in the grammar language, not Python. `[BLOCKED]`
2. Engine evaluates every guard; agent submits none. `[BLOCKED]`
3. Trace records each guard: name, truth value, witness
   (`same_owner(m,a) = true because owner(m)=car1 ...`). `[BLOCKED]`
4. Delete the `Transformation.precond` closure / `ConditionController`
   duplication in favor of one declarative path. `[BLOCKED]`

**Acceptance.** Fabricated-condition attack test: agent claims a condition
holds where it does not — engine contradicts, trace shows why.

---

## Phase 6 — Query engine `[BLOCKED]`

**Objective.** Ask the graph questions with holes; typed unification fills
them (ADR Q4).

**Dependencies.** Phase 2, Phase 3 · ADR Q4.

**Tasks.**
1. Pattern queries over typed relational structure
   (`velocity(owner=?, frame=ground)`). `[BLOCKED]`
2. Typed unification + binding substitution; repeated-holes agree or fail. `[BLOCKED]`
3. Verdict vocabulary: entailed / contradicted / unknown — never
   "false from absence" (OWA, research synthesis §5). `[BLOCKED]`
4. Restricted scope: no negation-as-failure, no disjunction in v1. `[BLOCKED]`

**Acceptance.** The tiger/deer-style demo becomes a real relational query:
"all facts about tiger in ground frame" returns structure, not a variable
name match.

---

## Phase 7 — Derivation / provenance graph `[BLOCKED]`

**Objective.** Derivation edges first-class; audit walks every derived fact
to roots.

**Dependencies.** Phase 2, Phase 4.

**Tasks.**
1. `derives` edges carry rule + inputs + output; cycle rejection at insert. `[BLOCKED]`
2. Provenance tiers (`verified | extracted | assumption-dependent`) attach
   to edges, not just fact metadata. `[BLOCKED]`
3. Dependency-walk API: ancestors, support set, circularity check. `[BLOCKED]`

**Acceptance.** Circular-proof test rejected with the cycle named.

---

## Phase 8 — Context / freeze / scope `[BLOCKED]`

**Objective.** Freeze is a semantic boundary, not an ergonomic zone
(ADR Q5, weak form).

**Dependencies.** Phase 2.

**Tasks.**
1. Context object: declared types, entities, relations, facts, permissions. `[BLOCKED]`
2. Structural immutability of frozen regions enforced by the graph layer,
   not convention. `[BLOCKED]`
3. Proof execution runs against frozen context only. `[BLOCKED]`

**Acceptance.** Post-freeze mutation test: any attempt to add/alter a frozen
fact fails at the store boundary.

---

## Phase 9 — Assumption / proof system `[BLOCKED]`

**Objective.** First-class proof boxes: nested assumption scopes,
discharge, reductio, leakage-proof isolation (ADR Q5, strong form).

**Dependencies.** Phase 5, Phase 7, Phase 8 · ADR Q5.

**Tasks.**
1. Proof box = scoped derivation region with own fact set. `[BLOCKED]`
2. Discharge: box proving `Q` under `assume P` produces
   `P → Q`; box reaching contradiction produces `¬P` (reductio). `[BLOCKED]`
3. Contradiction detection: conflicting values + declared exclusive pairs. `[BLOCKED]`
4. Leakage-proof: box-local facts never visible outside unqualified —
   enforced structurally. `[BLOCKED]`

**Acceptance.** Leakage test: derived-in-box fact referenced outside the box
with only `P → Q` transformation available — the raw fact is unreachable.

---

## Phase 10 — DSL AST / semantics `[BLOCKED]`

**Objective.** One shared IR; proof programs and grammar both compile into
it (ADR Q2). Semantics before syntax.

**Dependencies.** Phase 2, Phase 3 · ADR Q2.

**Tasks.**
1. Proof-program IR: typed step records (op, target, transformation,
   inputs, conditions, scope). `[BLOCKED]`
2. Grammar IR: type declarations, relation declarations, transformation
   records, guard declarations, judgment declarations. `[BLOCKED]`
3. Canonical rendering of IR to JSON/tree — both grammar and proof
   renderable and diffable. `[BLOCKED]`

**Acceptance.** The existing regex DSL parser (`v2.py`) is superseded; a
proof and a grammar render as structured trees with no Python class
semantics leaking.

---

## Phase 11 — DSL typechecker `[BLOCKED]`

**Objective.** Static validation of grammar and proof at load time.

**Dependencies.** Phase 10.

**Tasks.**
1. Declared types exist; relation arity/roles match; condition references
   resolve; transformation outputs type-match targets. `[BLOCKED]`
2. Grammar well-formedness lint (research brief 07 §6): every referenced
   fact kind, rule input, target type verified. `[BLOCKED]`

**Acceptance.** Wrong-type or dangling-reference grammar rejected with
the offending declaration named.

---

## Phase 12 — DSL execution `[BLOCKED]`

**Objective.** Interpreter over the IR; closed whitelist preserved.

**Dependencies.** Phase 10, Phase 11, Phase 5, Phase 7.

**Tasks.**
1. IR evaluator: dispatch through the registered transformation whitelist
   (today's `Registry` discipline, IR-native). `[BLOCKED]`
2. Proof boxes (Phase 9) as the execution scope model. `[BLOCKED]`
3. Existing v2 trace test suite re-expressed in IR passes. `[BLOCKED]`

**Acceptance.** `python -m openverifiers trace` renders IR proofs; old DSL
parsed only by a compatibility shim, then removed.

---

## Phase 13 — Domain definition language `[BLOCKED]`

**Objective.** The grammar-authoring language: data-first, declarative,
domain-agnostic (ADR Q2).

**Dependencies.** Phase 10–12 · ADR Q2.

**Tasks.**
1. Grammar language syntax finalized (semantics already fixed in Phase 10). `[BLOCKED]`
2. Renderer for grammar documents (human-readable + tree view). `[BLOCKED]`
3. Two spike domains written in the language: math, physics — one
   language, zero core changes. `[BLOCKED]`

**Acceptance.** English-grammar-style domain specifiable as types +
relations + transformations; no Python classes anywhere in it.

---

## Phase 14 — Deterministic domain engine `[BLOCKED]`

**Objective.** Engine computes, agent intends (ADR Q7); no free search.

**Dependencies.** Phase 12, Phase 13 · ADR Q7.

**Tasks.**
1. Intent-step execution full: agent names transformation + inputs, engine
   computes outputs, checks conditions, records derivation. `[BLOCKED]`
2. Bounded derivation mode (fixed-forward with explicit stop) if and only
   if a concrete domain shows need. `[BLOCKED]`
3. Numerical/symbolic ground decision per target (ARCHITECTURE.md §9 q6). `[BLOCKED]`

**Acceptance.** A proof step can never inject an agent-computed value;
engine output is the only path into the fact store.

---

## Phase 15 — Model-backed judgment engine `[BLOCKED]`

**Objective.** Typed judgment seam; deterministic and model-backed steps
compose without contaminating each other (ADR Q6).

**Dependencies.** Phase 12, Phase 14 · ADR Q6.

**Tasks.**
1. `ModelJudgment` seam: input facts, model id, declared output schema,
   policy, evidence refs, reproducibility contract. `[BLOCKED]`
2. `estimated` status + trace markers for judgment-crossed derivations
   (research synthesis §2 already finalised this). `[BLOCKED]`
3. Backends behind the seam: deterministic stub judge (exercises the seam
   without an LLM) then Jev. `[BLOCKED]`
4. Trust rules: what a judgment can and cannot feed (no judgment → truth). `[BLOCKED]`

**Acceptance.** Same seam serves decision-table stub and Jev; a judgment
fact is typed, evidenced, and never treated as deterministic truth.

---

## Phase 16 — Permission / trust model `[BLOCKED]`

**Objective.** Capabilities: per-proof grants over transformations, model
access, resource limits (ADR Q8). Plugin gate promotes to core.

**Dependencies.** Phase 9, Phase 14, Phase 15 · ADR Q8.

**Tasks.**
1. Capability record: allowed transformations, allowed judgments/models,
   step budget, context access. `[BLOCKED]`
2. Grant/deny evaluation inside execution; deny renders with the missing
   capability named. `[BLOCKED]`
3. `plugin/frozen.py` mapping table moves onto core capabilities. `[BLOCKED]`

**Acceptance.** Capability-deny test: proof touching an un-granted
transformation blocked with trace; plugin gate uses the same core path.

---

## Phase 17 — Domain packages `[BLOCKED]`

**Objective.** Real domains on the new core; core unchanged.

**Dependencies.** Phase 13–16.

**Tasks.**
1. Math: arithmetic + proof machinery (modus ponens, induction re-expressed). `[BLOCKED]`
2. Physics: relations (kinematics/dynamics/energy...) as data; dataset
   revive (200 problems). `[BLOCKED]`
3. Logic domain: assumption/contradiction exercises. `[BLOCKED]`
4. English grammar as a *test* domain proving the substrate generalizes —
   never a driver. `[BLOCKED]`
5. Business/law later, benchmark-gated per ARCHITECTURE.md §5.2 spirit. `[BLOCKED]`

**Acceptance.** Each domain lands with tests; zero core diffs between them.

---

## Phase 18 — Adversarial testing `[BLOCKED]`

**Objective.** The attack matrix from the vision §14, each class a
regression test.

**Dependencies.** Phase 14–17.

**Tasks.**
1. Fabricated facts/outputs/conditions; invalid transformations; missing
   preconditions; wrong entity/type/scope/unit/frame. `[BLOCKED]`
2. Variable-name injection; target injection; post-freeze mutation. `[BLOCKED]`
3. Assumption leakage; circular derivation; contradiction proofs. `[BLOCKED]`
4. Judgment abuse: model result fed as truth; unauthorized capability use. `[BLOCKED]`

**Acceptance.** Every row of the matrix has a failing-before /
passing-after test pair.

---

## Phase 19 — Benchmarks / evaluation `[BLOCKED]`

**Objective.** Replayable benchmark harness.

**Dependencies.** Phase 18.

**Tasks.**
1. Benchmark runner: problem sets + known answers + must-reject cases. `[BLOCKED]`
2. Physics dataset (200 problems) ported to the new engine; coverage
   report regenerated. `[BLOCKED]`
3. Adversarial suite as the admission gate (ARCHITECTURE.md §5.2). `[BLOCKED]`

**Acceptance.** Any future grammar auto-extraction must pass the gate to be
trusted (unchanged doctrine).

---

## Phase 20 — Developer experience `[BLOCKED]`

**Objective.** A domain author ships a grammar in one session.

**Dependencies.** Phase 13, Phase 17.

**Tasks.**
1. CLI (`verify`, `trace`, `render`) over the IR. `[BLOCKED]`
2. Trace/grammar viewers (terminal + web, per newer-additions §8). `[BLOCKED]`
3. Diagnostics: unsat-core-style "why not" (`conflicts`) when feasible. `[BLOCKED]`

**Acceptance.** Two fresh domains authored by someone else, no core help.

---

## Phase 21 — Documentation `[BLOCKED]`

**Objective.** Spec hierarchy per vision §19; spec matches code.

**Dependencies.** Phase 17.

**Tasks.**
1. `vision.md`, `semantics.md` (Phase 1), `architecture.md` rewrite,
   module docs (core-model, type-system, transformation-model,
   query-model, proof-model, context-model, model-judgments, security,
   domains). `[BLOCKED]`
2. All decisions in `docs/decisions/`; `status/` DB retired after
   migration. `[BLOCKED]`

**Acceptance.** Documented semantics == code behavior; no section tagged
`DEFINITION` contradicts an INVARIANT.

---

## Phase 22 — Paper / research artifact `[BLOCKED]`

**Objective.** A real contribution, not marketing.

**Dependencies.** Phase 19.

**Tasks.**
1. Contribution framing: typed judgment seam, proof-box scope model,
   domain-neutral grammar substrate — against the literature in
   `docs/research/` (brief 07 §4 is the key position). `[BLOCKED]`
2. Experiments: adversarial suite results, benchmark numbers,
   judgment reproducibility. `[BLOCKED]`

**Acceptance.** Draft paper + reproducible results artifact.

---

## Current status

- Q1–Q8 locked (ADR 0001, 2026-09-23).
- Phase 0 next: packaging, commit, prune, README.
- Then Phase 1 (`semantics.md`), then the Phase 13 grammar-IR spike with
  math + physics before any further core work.