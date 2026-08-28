# RDF, OWL, and Reification for Context-Dependent Relationships

Status: **Research brief — feeds design additions #2 and #3 (OWNER problem)**.
Prior art: W3C RDF/OWL specifications, RDF-star/RDF 1.2, graph/KR literature.
Sibling briefs: `01-frames-kr.md`, `03-dl-abox-tbox.md`, `04-path-analysis-sem.md`,
`05-bayesian-networks.md`, `06-property-graphs.md`.

---

## What it is

RDF (Resource Description Framework) is the W3C standard for machine-readable graphs.
The substrate is the **triple** `(subject, predicate, object)` — e.g. `(car1, hasVelocity, v1)`,
`(v1, value, 25.0)`. Subjects are IRIs or blank nodes, predicates are IRIs, objects are IRIs,
blank nodes, or **typed literals** (`"25.0"^^xsd:double`, `"2026-08-29"^^xsd:date`,
language-tagged strings). Every triple names its predicate explicitly (typed edge); an RDF
graph is just a set of triples — no built-in boundaries or nesting, which is why "context on a
relationship" is a genuine modeling problem.

RDF has no first-class entity for "an assertion itself". To say *"the statement
`(v1, value, 25.0)` holds in frame `ground` and belongs to `car1`"* you must (a) reify the
triple into a node, (b) put it in a named graph, (c) use RDF-star quoted triples, or
(d) restructure the ontology so the relationship is a class instance. OWL (Web Ontology
Language) sits on top of RDF and adds formal semantics (class axioms, property restrictions);
it sets the expressivity ladder but gives reification no special logical meaning.

OpenVerifiers' OWNER problem (design addition #3) is exactly this: `velocity` is a Fact node,
but its meaning depends on *whose* velocity it is and *in which reference frame*. RDF/OWL
prior art is the canonical place for battle-tested answers.

## Reification and its alternatives

### RDF reification (statement-level metadata, 1999–2014 style)

The original W3C mechanism: instantiate the vocabulary `rdf:Statement`, `rdf:subject`,
`rdf:predicate`, `rdf:object` (plus `rdf:type`). Every annotated triple costs four extra triples:

```turtle
_:s1 a rdf:Statement ; rdf:subject car1 ; rdf:predicate hasVelocity ; rdf:object v1 .
v1 value "25.0"^^xsd:double ; belongsTo car1 ; inFrame ground .
```

Known costs, documented throughout W3C notes and the literature:
- **4+ triples per annotated statement**; 1:4 graph blowup.
- **No built-in semantics**: in the RDF 1.1 model-theoretic semantics, a reified statement
  does **not** entail the statement it reifies. "Bob claims X" never implies X; you must
  assert both separately.
- **Query awkwardness**: recovering the annotated triple needs joins over all three of
  `rdf:subject/predicate/object`; simple path queries become multi-hop.
- **No identity/uniqueness**: nothing stops two `rdf:Statement` nodes for the same triple,
  and they are never auto-merged.

RDF 1.1 Concepts and Semantics (W3C RECs, 2014) describe the vocabulary but give it no
inference power — the "reification has no special meaning" position that motivated RDF-star.

### Named graphs / quads (RDF 1.1, N-Quads, SPARQL GRAPH)

Context per **graph** instead of per triple: an RDF dataset is (default graph, set of named
graphs); N-Quads serializes each triple with a fourth graph-name element; SPARQL 1.1 queries
per-graph with `GRAPH <name> { ... }`.
- Cheap: no triple blowup, one extra element per triple.
- Natural for *document/provenance-scoped* context: "these triples came from source S /
  were derived in step D".
- Coarse: one name per graph, not per triple. A graph of thousands of facts cannot carry
  *per-fact* owner/frame without one-graph-per-assertion, which explodes and defeats the
  purpose. Annotating the graph name itself is again reification.
- **Fit for OpenVerifiers**: a PROOF/PATH step's output facts map naturally to a named graph
  per derivation step; per-attribute metadata (owner, frame) does not.

### RDF-star / RDF 1.2 (quoted triples — reification first-class)

RDF-star (research: Hartig, "Foundations of RDF\* and SPARQL\*", 2017; standardized in
**RDF 1.2**, W3C REC 2025) makes a **triple term** a first-class subject/object:

```turtle
<<(v1 value "25.0"^^xsd:double)>> belongsTo car1 ; inFrame ground .
```

- No quadrupling: the quoted triple is one term; any number of context predicates attach.
- Identity recovered: `rdf:reifies` links the quoted triple to a named reifier
  (`_ :st`) with `rdf:subject/predicate/object`, giving the assertion its own IRI when desired.
- Semantics still user-managed: `<<(s p o)>> p2 o2` does **not** by itself assert `s p o`;
  the quoted triple must also be asserted. Deliberate — citation/attribution without commitment.
- SPARQL 1.2 supports triple terms; tooling ecosystem still maturing (2025 REC).
- Nested "context on context" is expressible but read-heavy.
- **Fit**: closest standardized analogue to "Fact node with context attached to the
  relationship". OpenVerifiers borrows the *pattern*: a quoted-triple-like construct ≈ a Fact
  node wrapping the asserted relationship with context edges.

### n-ary relations and the Singleton Property pattern

W3C's canonical guidance ("Defining N-ary Relations on the Semantic Web", W3C Note 2006):
when a relationship has more than two participants (car1, velocity-value, frame) or carries
attributes, **stop modeling `(s,p,o)`; reify the relationship into a class**:

```turtle
_:v1 a VelocityAssertion ; hasObject car1 ; hasValue "25.0"^^xsd:double ;
     hasReferenceFrame ground ; hasTime "2026-08-29T12:00:00Z"^^xsd:dateTime .
```

This is the **value-object / observation pattern** — the same shape as OGC Observations &
Measurements and SOSA (`Observation` with `observedProperty`, `hasResult`,
`featureOfInterest`, `phenomenonTime`) and QUDT `Quantity` value objects. Cost: one extra
node per contextualized relationship; benefit: any number of context attributes, clean
queries, normal OWL reasoning via class restrictions.

The **Singleton Property** pattern (Nguyen/Bodenreider/Sheth, ISWC 2014) keeps the original
`(s,p,o)` shape: each assertion gets its *own property instance* `:hasVelocity#1` linked back
to the generic predicate via `sp:singletonPropertyOf`. It preserves `(s p o)` navigation but
pays with property proliferation, non-standard semantics, and fragile inference — largely
treated as superseded by RDF-star.

### OWL modeling (Lite / DL / Full)

OWL 1's historic ladder: **OWL Lite ⊆ OWL DL ⊆ OWL Full**. OWL 2 (REC 2012) reshaped it into
profiles: **EL / QL / RL** (tractable; large terminologies, query rewriting, rule engines) ⊆
**OWL 2 DL** (decidable SROIQ(D); main reasoner target — HermiT, Pellet, Openllet), with
**OWL 2 Full** (RDF-complete, undecidable, unrestricted punning) on top.

Consistent guidance across OWL 1/2 docs, Allemang & Hendler's *Semantic Web for the Working
Ontologist*, and the n-ary Note:
- Context **structural and recurring** (every VelocityAssertion *has* a frame and an owner):
  model as an **OWL class with restrictions** — the n-ary pattern — and reason over it
  directly. This is the DL-correct answer; subsumption and consistency checks work because
  context is inside the schema.
- Context **occasional metadata** on a few assertions: keep the edge, attach context via
  attributes/quoted-triple style. Adding a class per rare annotation bloats the TBox.
- OWL 2 DL tolerates class/individual punning but gives reification **no inferential
  semantics**: nothing says a reifier's content follows, nor that two reifiers of the same
  triple denote one assertion. Punning a property into a class to reify it drifts toward
  OWL 2 Full and out of reasoner reach — a practical reason reification is "frowned upon"
  in DL modeling.

The two-source split (input context vs domain grammar) is exactly the ABox/TBox split; the
n-ary class lives in the TBox, its instances in the ABox (see `03-dl-abox-tbox.md`).

## Prior art systems (brief)

- **Wikidata** — statements reified by design: each statement node carries qualifiers
  (context attributes), a rank (preferred/normal/deprecated), and references. Production
  reification at scale; qualifier-per-claim is exactly "OWNER/context on a relationship".
- **PROV-O** (W3C REC 2013) — provenance as graph: activities, agents, `wasGeneratedBy`,
  `used`, `wasDerivedFrom`. Attribution of *what derived from what* — maps to OpenVerifiers'
  derivation refs, including "estimate crossing" provenance.
- **SOSA/SSN** (W3C REC 2017) and **OGC/ISO Observations & Measurements** — the observation
  pattern: result + observed property + feature of interest + time + quality as first-class
  nodes. The mature standard for "a contextualized measurement" — direct prior art for a Fact
  node carrying owner/frame/uncertainty.
- **QUDT** — quantities/units/dimensions as value objects with `unit`, `quantityKind`,
  numeric value: the reference vocabulary for "25.0 with unit m/s in frame ground" facts.
- **Property graphs** (GQL, ISO/IEC 39075:2024) — edges are first-class entities *with their
  own properties*; the non-RDF answer to the same problem (see `06-property-graphs.md`).

## OpenVerifiers takeaways

**Recommendation: relationship-to-node (n-ary / SOSA / QUDT pattern).** Attach
OWNER/reference-frame/time/uncertainty to a relationship by promoting it to a typed node and
hanging the context off that node as typed edges/attributes. Rationale:

1. **Solver compatibility**: a context-node with value+owner+frame stays a single
   value-bearing Fact node whose context is visible to the solver hook (frame conversion,
   unit check, uncertainty propagation). rdf:Statement-style reification gives the solver
   nothing; the value-object pattern gives it everything.
2. **Reasoning**: OWL restrictions (`Velocity ⊑ ∃hasOwner.Car`, `Velocity ⊑ ∃hasFrame.Frame`)
   stay in DL; ABox consistency checking works. rdf:Statement is invisible to the DL.
3. **Occasional context**: contextless facts stay plain Fact nodes with no context edges —
   no forced empty attribute maps. Context is optional typed edges, not fixed schema.

**RDF-star/attribute-map hybrid for loose edges**: for open/loose relationships (addition #2)
not solver-checkable, a typed edge with an attribute map is acceptable (property-graph style);
the moment context must be *rendered in the trace* or *queried*, promote to a context node.
The deterministic core therefore needs both (a) typed edges with optional edge attributes and
(b) a context-node variant of a Fact — two variants of one construct, matching #2/#3.

**Named graphs for provenance, not per-attribute context**: a PROOF/PATH step's outputs map
to a named graph (or a `derivedBy` ref to the step node); owner/frame stay per-fact
attributes. Coarse per-graph context cannot express per-attribute OWNER.

**Context must appear in the trace**: the renderer must show, for every fact and
relationship, its context (owner, frame, uncertainty, source). A "velocity 25.0" line without
`frame=ground` is a different claim. Render filters hide/show context columns; crossings of
estimated links (design #5) render as context annotations on the edge.

**Uncertainty as first-class context attribute**: confidence/interval on the value object
(QUDT-style) or a `probabilistic` status on the Fact node; the n-ary pattern carries it with
no new machinery.

**Concrete mapping for design #3**:

```text
Velocity(car1, 25.0, frame=ground, time=t0)    # Fact node + context attrs
  ├─ owner → car1      (typed edge)
  ├─ frame → ground    (typed edge)
  ├─ value → 25.0      (typed/solver attribute)
  └─ confidence → 0.9  (optional; statistical variant)
```

For a chain (`car1 → body → chassis → … ∝ status`, design #4), each `∝` edge that is a
correlation carries `estimated=true`, `confidence`, and its path-analysis/Bayes
qualification per `04`/`05` — the context node is the home for that metadata too.

## Conflicts / flags

- **Reification gives no inference**: neither rdf:Statement nor RDF-star quoted triples imply
  what they annotate. OpenVerifiers must treat "fact asserted with context" as the assertion
  itself; RDF-star requires the quoted triple be *asserted* for the annotation to mean
  anything.
- **Node explosion**: promotion-to-node costs one node per contextualized relationship;
  without lazy promotion (attribute map until context is needed) small graphs bloat.
  Mitigate with the two-variant design above.
- **OWL DL ceiling**: punning-based reification drifts to OWL Full; keep n-ary classes
  conventional to stay in DL.
- **Named-graph coarseness**: quads mislead if used for per-attribute context; they are
  provenance-scoped, not attribute-scoped.
- **Chained-correlation context** (design #4): context on a ∝ edge must not be treated as
  transitive; carry the SEM/Bayes qualification on the context node and render it in the trace.
- **RDF 1.2 ecosystem**: quoted-triple tooling is young (2025 REC); OpenVerifiers borrows
  the *pattern*, not the serialization.

## Sources

- RDF 1.1 Concepts and Abstract Syntax (W3C Recommendation, 2014) — https://www.w3.org/TR/rdf11-concepts/
- RDF 1.1 Semantics (W3C Recommendation, 2014) — https://www.w3.org/TR/rdf11-mt/
- RDF 1.2 Concepts and Abstract Syntax (W3C Recommendation, 2025) — https://www.w3.org/TR/rdf12-concepts/
- RDF 1.2 Semantics (W3C Recommendation, 2025) — https://www.w3.org/TR/rdf12-semantics/
- N-Quads (RDF 1.1, W3C Recommendation, 2014) — https://www.w3.org/TR/n-quads/
- SPARQL 1.1 Query Language (W3C Recommendation, 2013) — https://www.w3.org/TR/sparql11-query/
- Defining N-ary Relations on the Semantic Web (W3C Working Group Note, 2006) — https://www.w3.org/TR/swbp-n-aryRelations/
- OWL Web Ontology Language Reference (OWL 1, W3C Recommendation, 2004) — https://www.w3.org/TR/owl-ref/
- OWL 2 Web Ontology Language Overview (W3C Recommendation, 2012) — https://www.w3.org/TR/owl2-overview/
- Hartig, O. — "Foundations of RDF\* and SPARQL\*" (2017) — https://arxiv.org/abs/1706.01689
- Nguyen, V., Bodenreider, O., Sheth, A. — "Don't like RDF reification? Making statements about statements using singleton property" (ISWC 2014) — https://doi.org/10.1007/978-3-319-11964-9_7
- Allemang, D., Hendler, J. — *Semantic Web for the Working Ontologist*, 3rd ed., ACM Books, 2020 — https://doi.org/10.1145/3382097
- PROV-O: The PROV Ontology (W3C Recommendation, 2013) — https://www.w3.org/TR/prov-o/
- SOSA/SSN: Sensor, Observation, Sample, and Actuator Ontologies (W3C Recommendation, 2017) — https://www.w3.org/TR/vocab-ssn/
- QUDT — Quantities, Units, Dimensions and Data Types ontology — https://www.qudt.org/
- Wikidata Help: Statements — https://www.wikidata.org/wiki/Help:Statements
- ISO/IEC 39075:2024 Information technology — Database languages — GQL — https://www.iso.org/standard/76120.html