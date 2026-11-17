# Research Synthesis — What Prior Art Means for OpenVerifiers

Status: this document is the decision bridge between the six research briefs in
this directory and the OpenVerifiers design in [`../design.md`](../design.md)
and [`../newer-additions.md`](../newer-additions.md). Every statement here is
downstream of the cited briefs; where a finding conflicts with a prior design
decision it is flagged explicitly with **CONFLICT** and the recommended
resolution.

Briefs: [01 frames/KR](01-frames-kr.md) · [02 RDF/OWL/reification](02-rdf-owl-reification.md) ·
[03 DL ABox/TBox](03-dl-abox-tbox.md) · [04 path analysis/SEM](04-path-analysis-sem.md) ·
[05 Bayesian networks](05-bayesian-networks.md) · [06 property graphs](06-property-graphs.md)

---

## 1. What prior art validates (no design change needed)

- **TBox/ABox naming and split.** The verifier's two content sources — domain
  knowledge vs target/input context — are exactly the Description Logic TBox
  (terminology/schema) / ABox (instance assertions) split. The names are
  canonical in the literature ([03](03-dl-abox-tbox.md)); keep them, and keep
  the architectural separation clean. Matches design addition #9.
- **First-class Unknown == open-world semantics.** DL reasoners work under the
  Open-World Assumption: absence of a fact is *unknown*, never false. That is
  precisely the semantics of our Unknown node (why-unknown +
  what-evidence-would-resolve) ([03](03-dl-abox-tbox.md)). Verdict vocabulary
  should be **verified / contradicted / unverified-unknown** — never emit
  "false" from absence. **CONFLICT with user intuition**: users expect
  closed-world (DB) behavior; the UNKNOWN verdict must be rendered distinctly
  from FALSE everywhere.
- **DAG + no loops.** Wright's path diagrams, Bayes nets, and DL class
  hierarchies are all DAGs with the same cycle prohibition; the no-loops rule
  extends naturally to the is-a and part-of axes ([01](01-frames-kr.md),
  [04](04-path-analysis-sem.md)).
- **Transformation = the relation between facts.** Frames' procedural
  attachment (demons) failed because computation hid inside slot access; the
  corrective is exactly what OpenVerifiers already does: computation lives in
  explicit Transformation nodes with preconditions, and the trace records it
  ([01](01-frames-kr.md)). Hooks stay *declared on* slots but *fired through*
  Transformations.

## 2. The flagged risk (addition #4) is real and demands a guardrail

**CONFLICT-confirmed.** Correlation is not transitive, and naive chained
multiplication of correlation coefficients is a statistical error with three
independent failure modes: (a) a valid correlation matrix only bounds r_AC
(PSD constraints, 0.62–1 for r=0.9 both edges — the product 0.81 is one point
in the interval, not the value); (b) collider structures produce strong
pairwise correlations with zero chain correlation (worked counterexample in
[04](04-path-analysis-sem.md)); (c) confounding inflates edges with non-causal
components.

What is legitimate: multiplying **path coefficients along a genuine causal
chain with defined error terms** — that is Wright's tracing rule, which equals
"product of correlations" only in the single-open-chain, uncorrelated-errors
case ([04](04-path-analysis-sem.md)). Correlations are evidence for a
structure, never the structure itself.

**Recommended guardrail (documents into the grammar, implements as a verifier
capability):** `chain-composition` rule that composes a chain only when every
edge is a declared functional/causal relation (mechanism + direction), the
graph is acyclic, every endogenous node declares an error term with defined
orthogonality, no unmodeled confounder is flagged, and multi-path composition
uses the trace-sum (Σ of path products), not a single product. Otherwise: emit
an Unknown node with why-unknown ("correlation chaining without defined causal
structure") and evidence-needed listing the missing declarations. **Default is
refusal with a diagnostic Unknown, never a silently computed number.**

Uncertainty propagation along legitimate paths uses the delta rule
(var(p) via partial derivatives — covariance terms between coefficients
estimated from shared data must not be silently zeroed) ([04](04-path-analysis-sem.md)).

## 3. Typed composition (addition #1)

Frames give the right vocabulary: **slot descriptors** (name, type,
cardinality, optional, owner/context, `default_candidate`, `hook_ref`), is-a
(inheritance with **restriction-only** overrides) and part-of (typed,
cardinality-marked, depth-capped) as **two orthogonal axes**, and defaults that
are **candidates, never silent truth** ([01](01-frames-kr.md)).

**CONFLICT:** frame defaults exist to fill unknown slots; our Unknown node
exists to refuse fabrication. Resolution: `default_candidate` is query-time /
refinement-mode only; a default-derived value entering a derivation must be
marked `derived` with provenance visible in the trace, never truth.
Multiple-inheritance conflicts: refusal → Unknown with both parents' constraints
as evidence, never ordering- or lattice-based silent resolution.

Also: inherited slot resolution re-checks preconditions (parent constraints
still bind); is-a cycles rejected like graph loops; part-of is transitive +
irreflexive with an explicit depth cap in the grammar.

## 4. OWNER and relationship context (additions #2, #3)

The value-object / n-ary pattern is the recommendation (consistent across W3C
n-ary Note, SOSA/SSN, QUDT, Wikidata statements): promote a contextualized
relationship to a typed node carrying value + owner + reference-frame +
time + uncertainty as typed edges/attributes ([02](02-rdf-owl-reification.md)).
This keeps the fact a single value-bearing node that solver hooks can consume
(frame conversion, unit check, uncertainty propagation), and stays inside DL
expressivity (class restrictions), unlike rdf:Statement reification, which has
no inferential semantics and quadruples triples.

Patterns to import, serialization to skip:
- **RDF-star quoted triples** (RDF 1.2, 2025): borrow the *shape* — a Fact
  node wrapping an asserted relationship with context edges; do not adopt the
  serialization (ecosystem young).
- **Named graphs / quads**: use per PROOF/PATH step for provenance (one graph
  per derivation step), not per-attribute context.
- **Property graphs**: two-variant design — loose relationships are typed edges
  with optional attribute maps; promote to context nodes when the context must
  be queried or rendered in the trace ([06](06-property-graphs.md)).

Hard requirement: **context renders in the trace**. "velocity 25.0" without
`frame=ground, owner=car1` is a different claim. `estimated`/confidence
crossings render as edge context annotations.

## 5. Structural layer: adopt DL discipline (addition #9 deepens)

Endorsed with a profile discipline ([03](03-dl-abox-tbox.md)):
- **Structural layer** = DL reasoner as oracle for global ABox consistency
  (a per-rule DAG walk cannot see contradictions between distant assertions),
  classification/subsumption closure, and value-restriction typing
  (`Car ⊑ ∃hasVelocity.PhysicalQuantity`). Profile: EL++/OWL 2 EL or RL keeps
  worst case polynomial; full OWL 2 DL is NExpTime-complete — **profile choice
  is a product decision, fixed in the TBox design phase**.
- **Arithmetic layer** = sympy/Z3 from rule preconditions. **CONFLICT for a
  tempting shortcut:** DL + arithmetic is undecidable in general, and even
  EL++ with linear constraints is NP-complete ([03](03-dl-abox-tbox.md)) — do
  not encode numeric preconditions as DL axioms.
- **Statistical layer** = LLM-judge + confidence/interval on estimated links.
- Scoped derivation rules (our Transformations) are **not** DL GCIs: a GCI
  applies to every individual; a rule precondition is scoped to a derivation.
  Keep both tiers; Datalog+/- / ELP / DL-Lite combined approach are the
  literature precedents if a single engine is ever wanted.
- Identity: DL has no unique-name assumption; two fact nodes with distinct ids
  may denote one individual — needs an explicit sameAs/differentFrom policy
  before DL consistency checking is trustworthy.

## 6. Statistical/correlation layer (additions #2, #4, #5)

Bayesian networks are the tractability answer for the "astronomical growth"
fear: factor the joint distribution over the DAG (O(n·2^k) parameters for
bounded parent sets) instead of storing every pairwise correlation; inference
is exact on polytrees, junction-tree/elimination exact in general with
treewidth-bounded cost, NP-hard in the worst case ([05](05-bayesian-networks.md)).
A BN is a compact *distribution*, not a causal claim — edges need causal
justification (do-calculus, interventions) before they compose as effects.

Positioning for OpenVerifiers:
- **SEM/path analysis** = the composition law when chains are causal claims
  with error terms (addition #4's legitimate path).
- **Bayes nets** = the tractability machinery when the loose/statistical layer
  grows past ~10–20 correlated variables or chain depth > 3
  ([05](05-bayesian-networks.md)).
- Both are confirmed recommendations only for the statistical pipeline; the
  deterministic core stays exact. v1 engines: none (see decisions).

## 7. Property graphs: storage substrate, not semantic authority

The Fact/Transformation model maps directly onto labeled property graphs:
fact → :Fact node (status as property), Transformation → typed edge with
precondition/solver_hook/relation properties, Unknown → first-class node with
why/evidence fields, trace → typed directed edges ([06](06-property-graphs.md)).
Adopt LPG as the **storage/query substrate** when the trace store and KB need
graph queries (success-path/failure-trail views are path queries). Do NOT adopt
LPG as the semantic authority: no formal semantics, no entailment/consistency,
closed-world default that clashes with first-class Unknown, and rule/solver
semantics would leak out of the verifier core.

## 8. Decision record (updated statuses)

| Addition | Status after research | Concrete change |
|---|---|---|
| #1 inheritance/composition | finalized v1 (modeled via slot descriptors) | Fact attributes become typed slot descriptors; is-a + part-of orthogonal axes; depth cap; `default_candidate` never truth |
| #2 open/loose relationships | finalized v1 (two-variant edges) | typed edges with optional attribute maps; promote to context node when queried/traced |
| #3 OWNER/context | finalized v1 (value-object pattern) | relationship-to-node with owner/frame/time/uncertainty edges; context renders in trace |
| #4 proportionality chains | **guardrail required** | `chain-composition` rule: refusal-with-Unknown unless causal edges + error terms + no confounder; trace-sum for multi-path |
| #5 first-class uncertainty | finalized v1 | add `estimated` status + confidence/interval; trace marks estimated-link crossings; delta-rule propagation |
| #6 PROOF/PATH object | finalized v1 (unchanged) | ID-or-attribute-match output identification; ambiguity raises, never silent pick |
| #7 test case structure | finalized v1 (unchanged) | per-domain; prompt + literal facts both provided; engine isolated from NL extraction |
| #8 PATH viewer | finalized v1 direction | standalone web app; LPG-style rendering from trace store |
| #9 two content sources | finalized v1 (deepened) | TBox/ABox naming; DL reasoner optional oracle; OWA verdict vocabulary verified/contradicted/unverified-unknown |

## 9. Resolution map and prioritized actions

Per-item research disposition for the nine additions, then the three-bucket
action list. Tags use the wiki convention from `openwiki/INSTRUCTIONS.md`
(`[v1]` finalized v1 scope, `[out-v1]` out of scope, `[open]` open research
feeding a not-yet-finalized decision).

| Addition | Research disposition | Bucket |
|---|---|---|
| #1 inheritance/recursive composition | **resolved** → slot descriptors + is-a/part-of axes | act now |
| #2 open/loose relationships | **resolved** → two-variant typed edges | act now |
| #3 OWNER/context | **resolved** → value-object/context-node pattern | act now |
| #4 proportionality chains | **resolved** → guardrail specified; implementation pending | act now |
| #5 first-class uncertainty | **resolved** → `estimated` status + trace markers | act now |
| #6 PROOF/PATH object | **informed** (ambiguous-match precedent in property graphs); design unchanged | tag only |
| #7 test case structure | **unaffected** by this research | tag only |
| #8 PATH viewer | **partially informed** (trace views = LPG path queries); build target unchanged | tag only |
| #9 two content sources | **resolved/deepened** → TBox/ABox + DL consistency oracle | act now |
| minimal universal root logic | **unaffected** — explicit separate thread | open research |

### Act now — change `ARCHITECTURE.md` or the SDK

1. **Chain-composition guardrail** (addition #4) — highest priority: fixes a
   real correctness hole. Correlation chains are never point-multiplied; the
   `chain-composition` rule from [04](04-path-analysis-sem.md) becomes a
   verifier capability with five gates (declared functional/causal edges,
   acyclicity, defined error terms with orthogonality, no flagged unmodeled
   confounder, trace-sum over multiple open paths). Default behavior: refusal
   with a diagnostic Unknown, never a computed number.
2. **First-class `estimated` status + trace markers** (addition #5) — the
   status vocabulary gains `estimated` carrying confidence/interval; every
   derivation crossing a non-exact link renders as an edge annotation; path
   products propagate uncertainty via the delta rule with covariance terms
   ([04](04-path-analysis-sem.md), [05](05-bayesian-networks.md)).
3. **Typed slot descriptors + orthogonal is-a/part-of axes** (addition #1) —
   Fact attributes become `SlotDescriptor` (`name`, `type`, `cardinality`,
   `optional`, `owner/context`, `default_candidate`, `hook_ref`); is-a
   inherits by restriction only, part-of is transitive/irreflexive with a
   grammar depth cap; `default_candidate` is never truth
   ([01](01-frames-kr.md)).
4. **OWNER/context via the value-object pattern** (additions #2/#3) —
   contextualized relationships promote to context nodes carrying
   owner/frame/time/uncertainty as typed edges; loose relationships keep the
   typed-edge-with-attribute-map variant; context renders in every trace view
   ([02](02-rdf-owl-reification.md), [06](06-property-graphs.md)).
5. **TBox/ABox naming + OWA verdict vocabulary** (addition #9) — naming
   already adopted; codify the verdict triad verified / contradicted /
   unverified-unknown and render UNKNOWN distinctly from FALSE
   ([03](03-dl-abox-tbox.md)).

### Tag updates only — `docs/newer-additions.md`

- #1, #2, #3: change status from "open research" to **finalized v1 direction
  (research-informed)** — the act-now items above define the concrete shape.
- #4: keep "must inform design"; sharpen the pointer to the specified
  guardrail in [04](04-path-analysis-sem.md).
- #6: unchanged; optionally note the ambiguous-match requirement now has
  property-graph uniqueness/constraint precedent ([06](06-property-graphs.md)).
- #5, #7, #8, #9: already correctly tagged; no change.

### Genuinely open research — record, do not act

- DL profile selection against the physics TBox (EL vs RL vs QL) — product
  decision deferred until the grammar/TBox exists ([03](03-dl-abox-tbox.md)).
- sameAs/differentFrom identity policy — prerequisite before DL consistency
  checking is trustworthy ([03](03-dl-abox-tbox.md)).
- BN structure learning from trace history — deferred, benchmark-gated if ever
  adopted ([05](05-bayesian-networks.md)).
- Trace-storage scaling — unchanged [open] ARCHITECTURE.md §9 question.
- Auto-extraction benchmark-gate curation — unchanged [open].
- Minimal universal root logic — [out-v1], separate thread.

## 10. Out of scope for v1 (unchanged from the dispatch, now source-referenced)

- Minimal universal root-logic discovery — open research thread only.
- Auto grammar extraction — benchmark-gated future work.
- Non-physics domains (wealth/status/car chain is a design thought experiment).
- v1 code: BN inference engine (pgmpy), SEM estimation (semopy), DL reasoner as
  a required dependency (optional oracle later), RDF serialization, graph
  database. The v1 implementable core is unchanged: exact symbolic derivation
  + the new guardrail + uncertainty status on the model.

## 11. Open research threads (not blocking v1)

- Root-logic minimal set.
- BN structure learning from trace history (Chickering's GES,
  [05](05-bayesian-networks.md)) — retroactive grammar discovery; must still
  pass the benchmark gate.
- sameAs/differentFrom policy for the identity question.
- DL profile selection exercise against the physics TBox (EL vs RL).