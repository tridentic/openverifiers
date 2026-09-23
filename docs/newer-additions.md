# OpenVerifiers — Newer Design Additions and Open Questions

Status: each addition is marked **finalized v1**, **out of scope v1**, or
**open research feeding into a not-yet-finalized decision**. Research findings
for the open items live in [`docs/research/`](research/); the synthesis and
decision recommendations live in [`docs/research/synthesis.md`](research/synthesis.md).

---

## 1. Node inheritance and recursive composition

Information nodes support **inheritance / recursive sub-information**: a node
can have child nodes. Example: a "car" decomposes into body, chassis, engine,
etc., each potentially decomposing further. Not just data nesting — proper
typed composition, not an ad hoc nested dictionary.

Research directive: maps closely onto **frame-based knowledge representation**
(Minsky's "frames", 1974 — slots, fillers, inheritance between frame types).
Research what frame systems got right and what modern successors (description
logics, property graphs) do differently and better.

Status: **finalized v1 direction (research-informed)** → see `research/01-frames-kr.md` (slot descriptors + orthogonal is-a/part-of axes; decided in [`research/synthesis.md`](research/synthesis.md)).

## 2. Relationships beyond mathematical ones

Facts relate beyond solver-checkable equations — a car links to physical specs,
personal wealth, societal status, commute experience. Relationship types are
**open and loose**: at modeling time it is secondary whether a relationship is
handled by the symbolic or the statistical pipeline. The deterministic core
must house "loose"/statistical-style values, not just hard-solved ones.

Research directive: RDF triples, knowledge graphs, OWL ontologies as prior art
for typed, extensible relationships. Specifically **RDF reification** — the
standard technique for attaching context to a relationship itself (e.g.
"velocity's owner is car1, reference-frame=ground") instead of hacking context
in as a flat attribute.

Status: **finalized v1 direction (research-informed)** → see `research/02-rdf-owl-reification.md` (two-variant typed edges: edge-attribute map ↔ context node; decided in [`research/synthesis.md`](research/synthesis.md)).

## 3. Context-dependent attributes (the OWNER problem)

Velocity and mass have an OWNER (the object they belong to); time may be
global, or may not be — time dilation questions whether "global" is a wrong
modeling assumption depending on reference frame.

Research directive: reification and context-indexed facts in the KR literature;
how existing systems represent frame-of-reference-relative facts; concrete
design options.

Status: **finalized v1 direction (research-informed)** → see `research/02-rdf-owl-reification.md`
(frames-of-reference) and `research/03-dl-abox-tbox.md` (context indexed).

## 4. Proportionality/correlation chains — flagged mathematical risk

Example: car → body → chassis → [property] ∝ [property] ∝ … ∝ societal status,
defined explicitly in the grammar/TBox as a chain of proportionality
relationships. Flagged: can grow "astronomically" if not optimized.

Critical directive: naively chain-multiplying correlation coefficients is a
**known statistical fallacy** unless every edge is a genuine
functional/causal relationship with a defined error term. The correct existing
formalisms:

- **Path analysis** (Sewall Wright, 1920s) and its descendant **Structural
  Equation Modeling (SEM)** — chained causal/correlational paths with defined
  path coefficients and rules for combining direct and indirect effects.
- **Bayesian networks** — solve the "astronomical growth" problem via
  conditional-independence factorization instead of storing every pairwise
  correlation.

Do not let the system silently multiply correlation coefficients as exact
proportionality constants.

Status: **open research (must inform design)** → see
`research/04-path-analysis-sem.md` and `research/05-bayesian-networks.md`; the
`chain-composition` guardrail (refusal-with-Unknown unless causal edges + error
terms + no confounder) is specified in [`research/synthesis.md`](research/synthesis.md) §9.

## 5. Uncertainty must be first-class

If a statistical/correlational value lives inside the "deterministic core",
anything downstream must not silently inherit false certainty.
"probabilistic/estimated" should be a first-class fact status (alongside
truth/derived/unverified/unknown), carrying its own confidence or interval,
with the trace explicitly showing when a derivation crossed through an
estimated (non-exact) link. Preserves the "open and loose" goal without making
"verified" meaningless.

Status: **finalized v1 direction** (design decision); implementation details
informed by `research/04` and `05`.

## 6. PROOF/PATH object

Every test case has a candidate **PROOF/PATH object** describing the full
derivation from input to output. Output is identifiable **either by ID or by
attribute match**; an ambiguous attribute match (multiple facts match) must
raise an explicit error rather than silently picking one.

Status: **finalized v1**.

## 7. Test case structure (no regex extraction)

Test cases are per-domain (physics first). Each provides **both** the
natural-language prompt **and** the literal input facts/nodes (hand-specified,
not regex-extracted) — isolates testing the reasoning engine from testing the
NL extraction step.

Status: **finalized v1**.

## 8. Standalone PATH viewer

Small standalone web app that displays a PROOF/PATH object, both on its own and
run live through the verifier.

Status: **finalized v1 direction** (build target; not built in the research
pass).

## 9. Verifier's two content sources

The verifier operates over exactly two content sources: the **target/input
context** (what it was given) and the **domain knowledge** (grammar/rules/TBox).
Keep this separation clean architecturally — maps to the ABox/TBox split in
Description Logic (instance assertions vs schema/terminology). Research how DL
reasoners (HermiT, Pellet) handle consistency checking across this split — close
to what the verifier needs.

Status: **finalized v1 direction**; research informs the TBox representation →
`research/03-dl-abox-tbox.md`.