# OpenVerifiers Masterplan (MP-1.2)

Nov 22, 2026 (amended Nov 23, 2026; MP-1.1: D-029; MP-1.2: D-030, D-031) · Founder

The single reference for building OpenVerifiers, from the trusted kernel to frontier science, across six major releases. Every report, directive and change refers back to a section of this plan.

## 1. Summary

**Thesis: the clarity revolution.** As AI makes more of the world's decisions, the scarce resource is not intelligence but *justification*. OpenVerifiers (OV) makes justification cheap, clear and checkable. It is one language for writing knowledge, rules, goals and trade-offs, and one engine that checks, solves, propagates, optimizes, plans and explains. Every answer carries its cause-and-effect chain.

**The invariant (MP-INV), which no release may break:**

> Nothing becomes TRUE unless it traces, through checked rules, back to declared axioms, laws, definitions and stated facts. Agents, LLMs, solvers, procedures and the prover may propose; only the trusted kernel decides.

**The division of labour (MP-DOL), which sits beside the invariant:**

| Who | Owns | Never |
| --- | --- | --- |
| **AI** | Creativity and drafting: conjectures, strategies, lemmas, constructions; drafting OV from text and prose from proofs | Decides truth |
| **OV (structured tools)** | Truth and bookkeeping: checking every step, assumptions, dependencies, trust, deterministic rendering | Guesses |
| **Humans** | Meaning and values: approving definitions, main statements, laws and assumptions; choosing trade-offs | Read every step (the kernel does that) |

**The shared artifact:** one proof object with two synchronized views, formal for machines and readable for people. Both are generated from the same source, so agents and humans trust the same thing. AI may write proof bodies freely; anything that carries meaning (definitions, main statements, laws, assumptions) needs human sign-off.

**The four verdicts:** every answer is exactly one of:

- `PROVEN(proof, assumptions, trust_base)`
- `REFUTED(proof, assumptions, trust_base)`
- `UNKNOWN(missing, reason)`
- `INCONSISTENT(conflict_set)`

Optimisation answers add one honest qualifier: "best found, within X% of the best possible" when optimality isn't proven.

**Six major releases**, each proving something the next one depends on:

| Release | Codename | Proves |
| --- | --- | --- |
| v1 | Bedrock | OV never gives a wrong answer, on real exams and real agent policies |
| v2 | Engine | OV finds answers and makes trade-offs, not just checks them (the NDC school-year flagship) |
| v3 | Lens | Anyone can read, learn from and argue with the reasoning (readable surface, EXPLAIN, fallacies, SAT) |
| v4 | Atlas | Knowledge at scale stays consistent (the super ontology: packages, mappings, adapters, olympiad tier) |
| v5 | Sentinel | Agents and enterprises run on justified decisions (agent protocol, policy platform, LifeOS) |
| v6 | Frontier | The ceiling is very high (Lagrangian mechanics, the 3-body problem, special and general relativity) |

**What "done" means overall:**

- A person or an agent can state any well-defined problem in OV.
- OV returns a checked answer or an honest UNKNOWN that names what is missing.
- Anyone can read *why*, at the depth they choose.

**Companion pages:**

- OpenVerifiers Architecture Diagrams (https://claude.ai/artifact/7i5zyjAfuCekESSU8RaCqp): the stack, the pipeline, the trust boundary, query modes, a cause-and-effect chain, multi-domain handling, both languages annotated, and the roadmap;
- the Vision Notes (the source of every requirement here);
- the Language & Runtime Spec v0.1 (superseded where this plan differs).

## 2. Pushbacks: the calls I'm making

Each call keeps the vision intact but changes *how* it gets built, so the whole thing stays believable and actually ships.

1. **General-purpose, but the program is never trusted.** OV gets `procedure` blocks (loops, recursion, data structures, calls into Python). Their *outputs* are trusted only through checked certificates. The kernel itself stays small and non-Turing-complete. We won't build a Python competitor: no networking, I/O frameworks or UI in the standard library.
2. **"Solve anything" becomes "solve anything definable, or say exactly why not".** Undecidable or intractable questions return `UNKNOWN(budget | undecidable_fragment)`. Budgets are deterministic (node and step counts), so the same input gives the same verdict on every machine.
3. **The super ontology grows through quality, not bulk.** No mass ingestion before v4. A package earns its place with few axioms, proven theorems and tests. Imported data are always `fact`s with provenance, never `axiom`s. Cyc's 40 years are the warning.
4. **Frontier physics waits for v6.** GR and the 3-body problem are in the plan for real, but they don't pull resources before the trust, solver and clarity releases are done. The 3-body target is honest: conserved quantities, Lagrange points, special orbits and rigorous finite-time enclosures, not a closed form.
5. **Natural language is never trusted.** The readable surface (OV-Prose) is a *controlled* language that round-trips with OV. Free-text-to-OV translation by LLMs stays outside the trusted base, and faithfulness checks watch it.
6. **Probability is mathematics, not truth.** Probability theory can be a package that proves exact probabilities. A `confidence` attached to a fact stays metadata and never changes a verdict.
7. **Humans own values.** The trade-off engine proves what is feasible and optimal *given* the weights; people choose the weights and make the decision.
8. **One release at a time.** No parallel releases. Each one ends with exit criteria met and a report. With one founder and AI builders, focus is the scarce resource.
9. **v1 first, for a reason.** Aim to have the v1 capability report ready before US Regular Decision deadlines (early January 2027). It's the research artifact, and every later release leans on its credibility.
10. **Open core.** The language, kernel, checker and standard packages are open source. Recommendation: Apache-2.0 for its patent grant, but it's the founder's call. The hosted platform, enterprise packs and the agent product (v5) can be commercial.

## 3. Architecture: ten layers, bottom to top

Trust flows upward from a small checked core; ambition lives at the top. The diagrams page draws this stack, the pipeline and the trust boundary.

| Layer | Name | Contents | Trusted? |
| --- | --- | --- | --- |
| L0 | Exact arithmetic | Rationals, quadratic surds, rigorous intervals, polynomial normal forms | **Yes** (audited unit A, cap 700 per D-030) |
| L1 | Kernel checker | RawOV data model, trace checker, certificate checker (identities, ideal membership, later SOS), state hash and load | **Yes** (unit B; total TCB cap 2,300 per D-030) |
| L2 | Evaluator | Semi-naive Datalog, signed ATMS labels, stratified negation, semirings, deterministic budgets, incremental re-evaluation | No: re-checked by L1 |
| L3 | Solvers & procedures | z3, sympy, small-scope search, optimizers (MaxSAT / OMT / MIP), validated ODE (v6), `procedure` + FFI | No: they return certificates |
| L4 | Lowering | Type and unit checking, class compilation, generators, desugaring to RawOV with source spans | No: deterministic and tested |
| L5 | Languages | **OV** (the work and proof language), **OKQL** (the query language), **OV-Prose** (the readable surface, v3) | No |
| L6 | Knowledge | Packages (the theory tower), theory mappings, adapters, OVState stores, registry (v4) | Content, governed (section 6) |
| L7 | Modes | CHECK · PROPAGATE · SOLVE/FIND · COMPUTE · OPTIMIZE/PARETO · PLAN (OVProver) · EXPLAIN · WHAT IF | No: their answers are verdicts from L1 |
| L8 | Interfaces | `ov` CLI, Python SDK, MCP server, `ov gate` (CI and pre-commit), LSP and editor, trace viewer, REST server (v5) | No |
| L9 | Applications | Exams and education, the NDC planner, agent guardrails, enterprise policy, LifeOS, science | No |

**Three rules hold the stack together:**

- **Proposers can't write truth.** L2–L9 can only hand L1 something to check: a trace, a certificate or a candidate. Only L1 issues verdicts and writes OVState.
- **Every verdict names its trust base.** `{kernel}` when fully checked; `{z3_unsat, red:…}` when it rests on an unchecked solver result. `--strict` refuses everything not `{kernel}`.
- **Every low-level step links back** to the OV line, and later the OV-Prose sentence, that caused it. This is the cause-and-effect chain.

## 4. The work language (OV)

OV is where knowledge, scenarios, goals and proofs are written. **One grammar for every domain:** domains differ only in their packages.

### 4.1 Constructs

| Construct | Purpose | Trust level |
| --- | --- | --- |
| `package name @ver` / `import` | Versioned module; imports packages or trusted OVStates | — |
| `axiom` | Mathematical foundation (ordered field, coordinates, derivative) | Trusted, governed |
| `law` | Empirical law of nature or of an institution (Newton, a school rule, a company policy) | Trusted *as a claim*; counted in the claim ratio |
| `definition` | Introduces a new symbol; must be conservative (checked by `ov audit`) | Adds no trust |
| `type` / `fact type T extends U` | Classes: `property`, `invariant … because: …`, `derived`, `law`, `theorem`, `lemma` | Invariants are definitions |
| `theorem` / `lemma` | A claim that must be PROVEN; optional `by` hints | Never trusted until proven |
| `transformation` | Reusable `f(facts) -> facts` with `requires` / `ensures` | Lowered to rules |
| `controller` | Composition (`pipe`, `branch`, `guard`); orders rules, never adds truths | — |
| `generator` | Finite candidate domains (`isomers(C5H10)`, `cycles(S)`, `slots(week)`) | — |
| `procedure` | General-purpose computation; returns `result + certificate` | Untrusted until its certificate is checked |
| `scenario` | A context: `uses`, `extends`, `entity`, `fact`, `assume` | Facts and assumptions, labelled |
| `goal` | `must` / `minimize` / `maximize` / `prefer` / `priority` for the trade-off engine | Human-owned values |
| `target` | Input to OVProver (`must` / `prefer`) | — |
| `test` | `query … expect VERDICT [value]`; protected as gold | — |

### 4.2 Formatting

```ov
package physics.mechanics @1.0
import math.calculus

fact type Body {
  property mass: Mass
  property x: Position over t: Time
  invariant positive_mass: mass > 0 kg       because: "mass is defined as positive"
  derived  v: Velocity = deriv(x, t)
  derived  a: Accel    = deriv(v, t)
}

law newton2(b: Body): net_force(b) = b.mass * b.a

theorem work_energy(b: Body, t1, t2: Time):
  integral(net_force(b) * b.v, t1, t2) = 1/2*b.mass*b.v(t2)^2 - 1/2*b.mass*b.v(t1)^2
  by rewrite newton2, calculus.chain_rule, certificate identity

scenario incline uses physics.mechanics {
  entity block: Body { mass = 2 kg }
  entity ramp: Incline { angle = Angle{ sin = 3/5, cos = 4/5 } }
  assume frictionless(ramp)
  fact   on(block, ramp)
}

goal ndc_routine {
  must     no_clash(teachers), lab_hours(g) >= required(g) for g in lab_groups
  minimize teacher_overload weight 3
  prefer   labs_before_lunch
}
```

**Formatting rules:**

- Keywords lead every statement.
- One statement per line (indented continuation for long expressions).
- Every quantity has a unit.
- Every invariant has a `because:` (the reviewer audits these for hidden laws).
- Names are `snake_case`; types are `PascalCase`.
- Comments start with `#`.

### 4.3 Proof hints

`by` hints guide the prover. They are untrusted shortcuts, and the result is checked either way:

- `by rewrite L1, L2`
- `by induction n`
- `by cases c`
- `by lemma name`
- `by certificate identity | ideal | sos`
- `by search budget 10000`

With no hint, OV tries the automatic strategy. A failed hint gives `UNPROVEN` with the reason, never a silent pass.

### 4.4 What OV lowers to

- **RawOV:** atoms, rules, constraints, domains and world policies, each labelled and linked to its source span.
- **OVTrace:** JSON lines of steps. Each step records its rule, substitution, premises, label, plugin call, certificate and source span.
- **OVState:** canonical JSON plus a SHA-256 hash. Importable, never raising trust.

## 5. The query language (OKQL)

OKQL is the single interface to every mode. Queries run against a live program (`ov run`), a saved OVState (`ov query`), or through the SDK and MCP.

### 5.1 Grammar (core)

```okql
query    := head [IN scenario | USING state] [UNDER assume_list] [options]
options  := STRICT | BUDGET n | DEPTH n | LIMIT n | AS text|json|dot|prose | AT LEVEL student|expert|auditor | LANG en|bn

head :=
    PROVE claim                          -- verdict + proof
  | CHECK x IS Type | CHECK argument a   -- every invariant / every inference step
  | FIND ?x[: T], ... WHERE conds [UNIQUE | COUNT]
  | WHY claim | WHY NOT claim            -- minimal proof / blocked frontier (missing antichain)
  | WHAT IF (RETRACT f | ASSUME g)+ THEN query
  | PROPAGATE [scenario] [DEPTH n]       -- everything that newly follows, each with its cause chain
  | COMPUTE procedure(args)              -- result + certificate + its check
  | OPTIMIZE x FOR goal                  -- optimum with proof, or best found + gap
  | PARETO x OVER m1, m2, ...
  | WHY NOT option | WHAT WOULD IT TAKE option | SENSITIVITY x TO weight w | TRADE a FOR b
  | PLAN FROM state TO target            -- OVProver: plan + trace + gap report
  | EXPLAIN query                        -- the cause chain rendered for people
  | NEAR claim [WITHIN k] | DEPENDS ON f | AUDIT package
```

### 5.2 Examples

```okql
FIND ?a WHERE incline.block.a = ?a                       IN incline
WHAT IF RETRACT frictionless(ramp) THEN FIND ?a WHERE incline.block.a = ?a
FIND ?p: Point WHERE Square{ vertices = {(3,1),(1,3),(5,3),?p} } UNIQUE
CHECK argument socrates_mortal AS prose
PARETO routine OVER teacher_overload, student_idle_periods IN ndc_2027
WHY NOT routine_B IN ndc_2027
EXPLAIN WHY optically_active(add(C, HCN)) = false AT LEVEL student LANG bn
```

### 5.3 The result format (same for every mode)

```text
PROVEN   ?a = 6 m/s^2
  assumptions  {frictionless}
  trust        {kernel}
  proof        newton2 <- weight_component(block, ramp) <- given mass, angle   [trace q3#41]

UNKNOWN  (missing)
  missing      one of: { mu(ramp) } | { friction_force(block) }
  checked      each alternative, when added, makes the query PROVEN

OPTIMAL  routine_A   teacher_overload = 2, idle = 14
  proof        no routine with overload < 2 exists   (certificate: unsat core, checked)
```

- JSON output carries the same fields for agents.
- `AS prose` renders the cause chain as numbered sentences, each linked to the OV line it came from.

## 6. Multi-domain handling

One core, many theories. A question loads only the theories it needs, and cross-domain questions compose theories rather than merging them.

### 6.1 The theory tower

- **Foundations:** `math.core` (ordered field, integers, sets), `logic.core` (connectives, quantifiers, argument structure).
- **Mathematics:** `math.calculus` → `math.vector` → `math.ode` (v6); `math.geometry`, `math.trig`, `math.combinatorics`, `math.probability`.
- **Sciences:** `physics.mechanics` → `physics.electric`, `physics.thermal`, `physics.optics`, `physics.modern` → `physics.lagrangian` → `physics.relativity` (v6). `chem.core` → `chem.organic`, `chem.equilibrium`, `chem.electro`.
- **Institutions and agents:** `org.scheduling` → `policy.ndc`; `agent.workflow` → `policy.refunds`, `policy.repo`; `law.eligibility`.
- **Arguments:** `logic.arguments` (validity, the fallacy detectors), `exam.sat` (passage, claims, answer choices).

Each package declares:

- its axioms by kind (foundation / law / definition);
- its theorems and their proof status;
- its tests;
- its dependencies.

`ov audit` shows the axiom and claim ratios and the dependency DAG down to the foundations.

### 6.2 Composing domains in one scenario

```ov
scenario lab_safety uses chem.core, physics.thermal, policy.ndc {
  entity rxn: Reaction { equation = "2 H2 + O2 -> 2 H2O" }
  fact   heat_released(rxn) = 572 kJ
  query  PROVE allowed(rxn, lab3) UNDER assume supervised(lab3)
}
```

- **Name collisions** are resolved by qualified names (`physics.thermal.Energy`).
- **Contradictions between domains** surface as INCONSISTENT, naming both sources.

### 6.3 Theory mappings (bridges between domains)

```ov
map physics.mechanics.Body -> math.ode.Particle { mass -> m, x -> state[0], v -> state[1] }
```

- A mapping is itself checked: every axiom of the target must be PROVEN of the source under the mapping.
- Theorems then transfer along the mapping with their trust intact (the "little theories" idea).

### 6.4 Knowledge adapters

- **Scientific data:** CODATA constants, the periodic table, unit systems.
- **Knowledge graphs:** Wikidata via SPARQL; OWL/RDF ontologies.
- **Organisational data:** CSV, spreadsheets, SQL tables (NDC rosters, rooms, teachers).
- **Rules written in prose:** policies and regulations, drafted into OV by an LLM, then reviewed and faithfulness-checked before acceptance.

Imported data enter as `fact`s with `source` / `version` / `retrieved_at` provenance, and never as axioms or laws.

## 7. Release plan

Releases ship in order. A release is done only when **every** exit criterion is met and reported with evidence. Release numbers are referenced as `MP-v1 §scope` in reports.

### v1 Bedrock (trust), in progress

**Scope:**

- kernel, checker and signed ATMS labels;
- OV core plus the object layer;
- OKQL core: PROVE, CHECK, FIND (UNIQUE, COUNT), WHY, WHY NOT, WHAT IF, COUNTEREXAMPLE;
- exact arithmetic, intervals, certificates (identity and ideal membership);
- `trust_base` and `--strict`;
- libraries at HSC to JEE level: math, physics (mechanics, electric, thermal, optics, modern), chemistry (core, organic);
- OVTrace and OVState, with JSON-only traces;
- `ov` CLI, Python SDK, MCP, and `ov gate`;
- the `agent.workflow` guardrail package with a tool-call gate.

**Exit criteria:**

1. 0 false PROVEN over every gold-first case: JEE 30, JEE Main 2025: 45 problems drawn mechanically (15 per subject), gold from NTA's official final answer keys, A-level 30 if sources arrive, agentic 20, breadth 35, adversarial 50. (D-031: replaces HSC 45; HSC becomes a v1.1 tier, run when papers are supplied.)
2. A capability report with the domain × tier matrix and the failure taxonomy.
3. 0 unsound mutants accepted, including the object path.
4. ≥ 60% of library theorems at `{kernel}` trust.
5. Total TCB ≤ 2,300 lines (D-030).
6. CI green 20 runs in a row; `reproduce.sh` regenerates every table.

**Non-goals:** optimisation, the readable surface, adapters.

### v2 Engine (solver + trade-offs)

**Scope:**

- PROPAGATE;
- the `goal` syntax and the trade-off engine: OPTIMIZE, PARETO, WHY NOT, WHAT WOULD IT TAKE, SENSITIVITY, TRADE;
- optimality certificates (an unsat proof that nothing better exists, or a proven bound plus gap);
- `procedure` + certificates + FFI;
- a formal plugin protocol;
- OVProver PLAN with abduction and gap reports;
- the missing-facts antichain with verification;
- incremental evaluation;
- the `org.scheduling` package;
- **flagship: the NDC school year** (lab groups, routines, quizzes, teacher workload) on real data.

**Exit criteria:**

1. A full term's routine computed for NDC, with every hard rule PROVEN satisfied.
2. The Pareto front reported, and at least one NDC staff member reviewing it.
3. Every OPTIMAL claim carries a checked certificate.
4. The scheduling suite compared against a MiniZinc baseline.
5. 0 false PROVEN maintained on all v1 suites.

### v3 Lens (clarity)

**Scope:**

- OV-Prose: a controlled-English surface that round-trips with OV;
- `EXPLAIN AT LEVEL` (student / expert / auditor) in English and Bangla;
- `logic.arguments` with the fallacy detectors;
- the `exam.sat` Reading & Writing and Math suites;
- the trace viewer (web);
- an LSP and VS Code extension with hover-to-see-proof;
- the docs site and tutorial.

**Headline feature: OV-Paper (proof to paper)**, which turns any OV proof into a readable paper or argument:

- **statement cards:** the theorem in plain language, with every definition and assumption it rests on. This is what humans must check;
- **auto-generated blueprints:** the lemma dependency graph, with one sentence of idea per lemma;
- **folding:** key steps shown (case splits, constructions, new lemmas); routine steps collapsed;
- **two-way links:** every sentence links to its formal step and trace, and back;
- **rendering:** deterministic templates are the trusted view. LLM-polished prose is labelled, and checked by re-formalizing it and comparing;
- **idea credit:** each lemma records who or what proposed it (human, AI, retrieved paper);
- **export:** LaTeX, PDF, HTML.

**Exit criteria:**

1. A SAT suite (≥ 60 R&W + 40 Math, with official answers).
2. A fallacy suite.
3. OV-Prose round-trip on 100% of package statements.
4. A small reader study: students explain answers from `EXPLAIN` output.

**Plus, for OV-Paper:** every v1 library theorem and every capability-report answer renders as a paper with statement cards and a blueprint. Readers in a small study can identify the main idea of a proof from the paper alone. Round-trip drift is flagged on every polished render.

### v4 Atlas (the super ontology)

**Scope:**

- a package registry with versions and governance (review for every new axiom or law);
- theory mappings;
- the adapters (CODATA, periodic table, Wikidata, CSV/SQL, OWL/RDF, policy drafting);
- surfacing of conflicts between sources;
- scale: indexing, 10⁶ to 10⁷ facts, incremental queries;
- shareable OVState knowledge bases;
- the olympiad tier, with SOS certificates for inequalities and invariants for combinatorics.

**Exit criteria:**

1. ≥ 25 governed packages.
2. Cross-package queries over mappings.
3. A 1M-fact benchmark under its targets.
4. An olympiad suite with honest numbers.

### v5 Sentinel (agents + enterprise)

**Scope:**

- **the agent justification protocol:** every action is pre-checked (allowed / forbidden + the rule it falls under) and post-logged (the cause chain);
- integrations: Claude Code hooks, MCP, and common agent frameworks;
- enterprise policy packs;
- a multi-tenant server with an audit store;
- dashboards;
- the TypeScript SDK;
- **LifeOS / Snayu integration** (study-roadmap and goal-plan validation).

**Exit criteria:**

1. 1–3 design partners.
2. An agent policy benchmark with 0 forbidden actions let through.
3. Audit trails accepted by a partner's reviewer.

### v6 Frontier (science)

**Scope:**

- multivariable and vector calculus;
- ODEs with validated (interval) integration;
- Lagrangian and Hamiltonian mechanics, with conserved quantities from symmetries;
- the 3-body results (Lagrange points, special orbits, finite-time enclosures);
- special relativity;
- tensor calculus leading to GR;
- olympiad physics.

**Exit criteria** (theorem milestones, each PROVEN):

1. Kepler's laws from Newtonian gravitation.
2. The 5 Lagrange points of the restricted 3-body problem.
3. Time dilation from the Lorentz transformation.
4. Schwarzschild perihelion precession to first order.

## 8. Cross-cutting programs

These run through every release and appear in every report.

| Program | Rules | Reported every time |
| --- | --- | --- |
| **Trust** | Small audited units; "No trusted check may ever be removed or weakened to fit a cap. If a cap blocks work, report it; caps change only by a masterplan decision." (D-030); certificates over solver trust; mutation testing of every trace path; differential testing of the solver-side symbolic layer; deterministic budgets | Total and per-unit TCB lines · unsound mutants accepted (must be 0) · share of theorems at `{kernel}` · `--strict` pass rates |
| **Evaluation** | Gold first and alone, before OV runs (the git history proves the order); gold from official keys or dual independent solutions; problem lists drawn mechanically; the ratchet (the failing set may only shrink); no gold edit without the founder's `Gold-Change-Approved-By` trailer | Per-suite cases, false PROVEN (must be 0), false REFUTED, UNKNOWN precision, failure taxonomy, gold provenance |
| **Faithfulness** | Scenarios contain only the givens; a lint for leaked answers; a reviewer agent that never sees the gold; every invariant has a `because:`; `EXPLAIN --nl` renders for human comparison; mistranslation cases in the adversarial suite | Flags raised, flags confirmed, mistranslations caught by each layer |
| **Performance** | Agents need tight loops; targets are tracked in an uninstrumented bench job | `ov check` p95 (rules < 300 ms, objects < 2 s); q11 < 1 s; incremental re-check < 100 ms; 10k facts < 5 s; seed variance |
| **Clarity of errors** | Every error has a code, a source span, a caret and a fix hint; every UNKNOWN names source-level facts, never internal atoms | New error codes, and any message that regressed |
| **Generality** | A new language feature needs 3 domains using the same syntax, or it belongs in a package | The feature → domains list for every language change |

## 9. Working agreement

**Roles:**

- **Founder:** owns the vision, the values and every final decision. The founder is the only human approver for gold changes, new axioms or laws in governed packages, licence and public naming, and changes to this masterplan. Referred to as "the founder" in all project material.
- **Claude (inventor and CTO, in claude.ai):** owns this plan, the architecture and the release scoping. Reviews every report against the exit criteria, writes directives, and pushes back when work drifts from MP-INV.
- **Claude Code (engineering, in the repo):** builds, tests and reports. Proposes deviations; never makes them silently.

**How the plan is used:**

1. `MASTERPLAN.md` (an export of this doc) lives at the repo root. Claude Code reads it at the start of every session.
2. Every directive and report cites sections (`MP-v1 exit 4`, `MP-§8 Trust`).
3. **Reports** follow one shape: what was done against the scope · exit-criteria status with evidence (commands and outputs) · the cross-cutting numbers (section 8) · deviations · shortcuts found · decisions needed, each with a recommendation.
4. **Checkpoints (D-028):** Claude Code writes a report at each checkpoint and continues without waiting. It stops for an approval packet, a false PROVEN, a trusted-code cap, CI red it cannot fix, or any gold or meaning change not covered by an approval the founder actually gave.
5. **Approvals (D-024):** gold and meaning approvals are the founder's own act. Claude Code batches everything into one approval packet (reviewer-classified, with references); the founder approves or rejects in one reply; Claude Code records exactly that decision. No agent ever approves on the founder's behalf.
6. **Changes to this plan** are versioned (MP-1.0 → MP-1.1 …). Each one adds a decision-log entry, and only the founder approves.
7. **When in doubt, priorities run:** soundness → honesty of verdicts → generality across domains → clarity of errors and traces → speed → features.

## 10. Risks and open decisions

| Risk | Why it matters | Mitigation |
| --- | --- | --- |
| Formalization errors (a faithful-looking OV file that models the wrong thing) | The verdict is only as good as the reading of the problem; this is the field's unsolved problem | The faithfulness program; explicit assumptions; reader review; it's a research contribution in its own right |
| Solver trust creeping into PROVEN | z3 is huge and unverified | Certificates first; `trust_base`; `--strict` numbers reported every time |
| Scope explosion ("limitless possibilities") | Founder focus is the scarce resource | One release at a time; exit criteria; non-goals |
| JEE and olympiad problems beyond the current language | Hard problems need vectors, ODEs, diagrams | The failure taxonomy points to the next language feature; no answer is ever faked |
| Performance at scale | Agents and the NDC planner need speed | Incremental evaluation (v2), indexing (v4), the latency targets |
| Being out-built by bigger players (Lean, Bend, labs) | Code verification is crowded | Our lane is **verified knowledge and decisions under uncertainty**: UNKNOWN, assumptions, trade-offs, cross-domain. Nobody else owns it |
| Solo-founder bandwidth and the application season | v1 doubles as the research artifact | v1 first; capability report targeted before early-January deadlines |

**Open decisions for the founder:**

1. Licence: Apache-2.0 (recommended) or MIT.
2. Public name and branding: OpenVerifiers / OV / OKQL / OV-Prose.
3. HSC and A-level sources (asked in the next approval packet).
4. The NDC partnership: who at the college to approach, and when (v2 flagship data).
5. Whether Snayu AI is the company that carries OV (open core) and LifeOS.

## 11. Decision log

Newest first. Every future change to this plan adds a row here.

| ID | Date | Decision | Decided by |
| --- | --- | --- | --- |
| D-031 | 2026-11-23 | v1 exit criterion 1 amendment: "Replace \"HSC 45\" with \"JEE Main 2025: 45 problems drawn mechanically (15 per subject), gold from NTA's official final answer keys\". Fetch papers and keys only from official NTA domains (list them in the report). If NTA does not publish both papers and keys, stop and report instead of substituting another source. HSC becomes a v1.1 tier, run when papers are supplied." | Founder (reply to packet dd2d4fd885a8) |
| D-030 | 2026-11-23 | Trusted-code budget: "New caps: unit A 700, raw/formula.py 450, main 1,150; total 2,300 (hard). The total stays the headline number in every report." New rule, MP §8 Trust: "No trusted check may ever be removed or weakened to fit a cap. If a cap blocks work, report it; caps change only by a masterplan decision." "Restore, first, the OVState loader's sortedness and groundness checks, and their tests (unsorted states refused again)." Then spend, in order: (1) surd-valued uniqueness certificates, Q(√d) multipliers and values; (2) π in integrands; (3) ln in the exp ring (d ln u = u'/u with u > 0 checked). Real algebraic numbers: deferred to v2 (only phys p1q10 needs them) | Founder (reply to packet dd2d4fd885a8); CTO rationale |
| D-029 | 2026-11-23 | Trusted-code budget: the total stays a hard 2,000; per-unit caps become movable within it: unit A 500, raw/formula.py 410, main 1,090 (= 2,000). Every report gives each unit and the total. Trusted lines are spent in this order: state hash/load (C6), integer/modular arithmetic (C4), pi inside integrands (about 10 lines), then anything else | Claude (CTO); approved by the founder (2026-11-23 message) |
| D-028 | 2026-11-23 | Claude Code works through engineering checkpoints without waiting for a go-ahead and writes a report at each one. It stops for a false PROVEN, a trusted-code cap, CI red it cannot fix, and every gold or meaning approval, which stays the founder's own act. The founder is referred to as the founder | Founder |
| D-027 | 2026-11-23 | v1 language scope adds integers and modular arithmetic, verified closed-form ODE solutions, and polynomial for-all statements over the reals via SOS certificates. Inverse trig moves to v2; general ODE solving to v6 | Claude (CTO) |
| D-026 | 2026-11-23 | Engine priority: exact arithmetic over Q(pi) in the checker, then the exp differential ring in the trusted normal form, then uniqueness certificates | Claude (CTO) |
| D-025 | 2026-11-23 | drafts/ accepted for unapproved libraries: never loaded under --strict, never in headline numbers. The meaning gate covers any package file anywhere outside drafts/. A derivable result is a theorem, never a law | Claude (CTO) |
| D-024 | 2026-11-23 | One-pass approvals: the agent prepares one approval packet, with each meaning line classified by a reviewer and given a reference. The founder reads it and approves or rejects it in one reply, and the agent records exactly that decision. No agent ever approves gold or meaning on the founder's behalf | Founder + Claude |
| D-023 | 2026-11-22 | MP-DOL (AI drafts, OV decides, humans own meaning) adopted beside MP-INV; OV-Paper (proof to paper: statement cards, blueprints, folding, two-way links, idea credit) is the v3 headline; v1 traces carry the hooks OV-Paper needs | Founder + Claude |
| D-022 | 2026-11-22 | MP-1.0 adopted: six releases (Bedrock, Engine, Lens, Atlas, Sentinel, Frontier); the ten-layer architecture; procedures with certified outputs; OV-Prose as a controlled surface | Claude (CTO), pending the founder |
| D-021 | 2026-11-22 | Certificates (identity, ideal membership) checked in a trusted exact-arithmetic unit, cap 450; total TCB cap 2,000; differential testing of the solver-side calculus | Claude (CTO) |
| D-020 | 2026-11-22 | The claim ratio (class level) is the target; the strict ratio is reported too; every invariant needs `because:` | Claude (CTO) |
| D-019 | 2026-11-22 | Trig as (cos, sin) with cos²+sin²=1; rigorous intervals for transcendental functions; `tolerance` implemented; exact surds | Claude (CTO) |
| D-018 | 2026-11-22 | JEE gold from official keys; HSC gold from dual independent solutions; problem lists drawn mechanically, before the library work | Claude (CTO) |
| D-017 | 2026-11-21 | M-CAP: few axioms (foundation / law / definition), everything else a proven theorem; `ov audit` | Founder + Claude |
| D-016 | 2026-11-21 | `missing` = a verified antichain of minimal alternative sets | Claude (CTO) |
| D-015 | 2026-11-21 | Deterministic node budgets; wall clock only as a backstop | Claude (CTO) |
| D-014 | 2026-11-21 | WHAT IF RETRACT on facts answered by labels (hidden retractable assumptions) | Claude (CTO) |
| D-013 | 2026-11-21 | Solver reductions listed in `trust_base`; `--no-reductions` switch | Claude (CTO) |
| D-012 | 2026-11-21 | COUNTEREXAMPLE returns the theorem's verdict | Claude (CTO) |
| D-011 | 2026-11-21 | `trust_base` on every verdict; `--strict` | Claude (CTO) |
| D-010 | 2026-11-21 | Gold-diff gate; gold first and alone; the ratchet | Claude (CTO) |
| D-009 | 2026-11-21 | `ov gate` commit gate (from Bend 2); faithfulness as its own workstream | Claude (CTO) |
| D-008 | 2026-11-20 | The object layer: `fact type`, invariants versus theorems, `Set` not `List`, PROVE UNIQUE, COUNT | Founder + Claude |
| D-007 | 2026-11-19 | The four verdicts; three trust levels; open world by default | Founder + Claude |
| D-006 | 2026-11-19 | MP-INV: proposers propose, only the kernel decides | Founder + Claude |
| D-005 | 2026-11-19 | Pipeline OV → RawOV → OVTrace → OVState; OKQL; OVProver | Founder |
| D-004 | 2026-11-19 | The name "KQL" is taken (Kusto, Kibana); use OKQL | Claude |
| D-003 | 2026-11-19 | Package-based super ontology, not a monolithic knowledge base | Claude |
| D-002 | 2026-11-17 | OpenVerifiers is the main work; LifeOS second | Founder |
| D-001 | 2026-11-18 | Core idea: f(facts) → facts as composable controllers, with graph pathways as proofs | Founder |
