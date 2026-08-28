# Property Graphs (LPG / Neo4j / Cypher) as a Pragmatic Implementation Reference

**Status:** Research brief — feeds design additions **#1** (recursive node composition), **#2** (open/loose typed relationships), **#3** (OWNER/context attributes). Sibling briefs: `05-*.md` (RDF/OWL), `07-*.md` (frames), `08-*.md` (path analysis/SEM), `09-*.md` (DL + ABox), `10-*.md` (Bayesian nets).

## What it is

The **property graph** model (also "labeled property graph", LPG — the term Neo4j uses for its own dialect) is the data model behind Neo4j, and in similar form behind Memgraph, Amazon Neptune, TigerGraph, and others. Per the official Neo4j "Graph database concepts" guide, the model consists of:

- **Nodes** — entities (discrete objects) of a domain. Nodes carry zero or more **labels** that classify them (e.g. `:Person`, `:Actor`).
- **Relationships** — a connection between a source node and a target node. A relationship **always has a direction**, **must have exactly one type**, and connects exactly two nodes (self-relationships allowed).
- **Properties** — key-value pairs that may be stored on **both nodes and relationships**. Values are numbers, strings, booleans, or homogeneous lists.

The decisive contrast with RDF: **RDF's data model is a set of triples, so there is no native place for edge properties**; property graphs make "attributes on the relationship itself" a first-class, native feature. This is exactly what OpenVerifiers needs for derivation metadata (solver used, confidence, owner, timestamps) hanging off the *edges between facts* rather than being squeezed into reified nodes.

Why this brief exists: OpenVerifiers' core ontology — typed Facts as nodes, typed Transformation/rule edges between them, attributes (status, source, derivation, owner) on both — is structurally an LPG. This brief assesses how far to adopt LPG as storage/query substrate and where the model must be rejected (verification semantics live above the graph, not in it).

## The data model in detail

### Nodes and labels

- A node represents an entity; the simplest graph is a single node with no relationships.
- Labels classify nodes ("all nodes with a certain label belong to the same set") and enable indexed access and query planning.
- **A node can have zero to many labels**; labels can be **added and removed at runtime** — Neo4j's own docs use a `Suspended` label for temporarily-suspended bank accounts. So labels dual-purpose: permanent typing *and* transient state marking.
- Multiple labels per node are normal (e.g. `:Person:Actor`). Naming convention: PascalCase (`:VehicleOwner`).

### Relationships (edges)

- Every relationship connects a source and target node, has **one direction**, and **must have a type** (exactly one, e.g. `:ACTED_IN`, written SCREAMING_SNAKE_CASE).
- Direction "can be disregarded where not useful" — no need for duplicate reverse relationships; queries traverse either way.
- **Relationships can have their own properties** (key-value), e.g. `roles: ['Forrest'], performance: 5` on an `ACTED_IN` edge.

### Properties

- Key-value pairs on nodes *and* relationships. Value domain: number (int/float), string, boolean, homogeneous lists (no nested objects/arrays of mixed type in Neo4j's property value model).
- Keys are case-sensitive (`name` ≠ `Name`); convention camelCase (`firstName`).

### Schema: indexes and constraints

Neo4j is **schema optional**: "you can create data... without defining a schema up front." Schema = indexes + constraints, introduced when desired:

- **Indexes** — performance only.
- **Property uniqueness constraints** — combined property values unique for all nodes with a label (or all relationships with a type).
- **Property existence constraints** — a property must exist for all nodes of a label / relationships of a type (Enterprise Edition).
- **Property type constraints** — a property must have a required type (Enterprise Edition).
- **Key constraints** — existence + uniqueness combined (Enterprise Edition).
- Newer versions add **graph types**: a schema-fixed, declarative definition of the graph's shape, recommended over ad-hoc `CREATE CONSTRAINT` statements.

Note the engineering irony for us: the *strongest* schema enforcement (existence, typing) is gated behind the commercial edition, and even the base product's uniqueness is per-(label, property-combination), never a global node identity. For OpenVerifiers, identity/uniqueness of Facts must be enforced by the application layer, not trusted to the store.

### Formal status of the model

The LPG has **no ISO/W3C formal semantics equivalent to RDF**. The frequently-cited formal definition is Renzo Angles' "The Property Graph Database Model" (AMW 2018): a graph `G = (N, E, ρ, λ, π)` — finite node set `N`, edge set `E`, endpoint function `ρ: E → N×N`, labeling function `λ: (N∪E) → 2^L` (sets of labels on nodes *and* edges), property function `π: (N∪E) → R` (records on both). That paper explicitly proposes integrity-constraint notions because the industry has none standardized. Schema/integrity semantics remain an open research area (e.g. EDBT 2023 "A Formal Design Framework for Practical Property Graph Schemas").

## Cypher in brief

Illustrative only — syntax for the model, not a tutorial:

```cypher
-- Node with label + properties; relationship with type + edge properties
CREATE (:Fact {id: 'f1', value: 'x > 0', status: 'truth'})
       -[:DERIVES {via: 'solver:z3', confidence: 1.0}]->
       (:Fact {id: 'f2', value: 'x >= 0', status: 'derived'})

-- Pattern match: typed edge, both directions, property filters
MATCH (f1:Fact)-[r:DERIVES]->(f2:Fact)
WHERE f1.status = 'truth' AND r.confidence > 0.5
RETURN f1.id, f2.id, r.via

-- Variable-length / path query (failure trail from a target)
MATCH p = (target:Fact {id: 'g1'})<-[:DERIVES*1..5]-(a)
RETURN p

-- Uniqueness constraint (node key)
CREATE CONSTRAINT fact_id IF NOT EXISTS FOR (f:Fact) REQUIRE f.id IS UNIQUE
```

Pattern syntax essentials: `(n:Label {prop: val})` for node patterns, `-[r:TYPE {prop: val}]->` for typed directed edges, `<-[:TYPE]-` to traverse inbound, `*1..5` for bounded path length, `p = (...)-[...]->(...)` to bind a whole path. GQL (ISO) and openCypher share this pattern language; Neo4j-specific property existence uses `n.prop IS NOT NULL` in constraint DDL.

## LPG vs RDF vs RDF-star

| Aspect | Property graph (LPG) | RDF / RDF 1.1 | RDF-star (→ RDF 1.2) |
|---|---|---|---|
| Statement unit | Node / typed directed edge | Subject-predicate-object triple | Triple, plus **quoted triples** (triple terms) as subject/object of other triples |
| Edge (predicate) attributes | **Native**: properties on relationships | Not possible → **reification** (statement becomes a resource) or n-ary relation patterns (verbose, bloats the graph) | Possible: e.g. `<<:a :b :c>> :certainty 0.9` — compact "statements about statements" |
| Typing | Labels on nodes (0..n), exactly one type per edge | Classes/properties via RDFS/OWL vocabulary, global IRIs | Same as RDF |
| Schema/consistency | Optional; indexes + constraints (uniqueness, key, existence; some Enterprise-only); graph types in newer versions | RDFS/OWL axioms; SHACL shapes for validation | Same as RDF |
| Semantics | **No standardized model-theoretic semantics**; closed-world, negation-as-failure pragmatic behavior | **Model-theoretic, open-world** semantics (RDF 1.1 Semantics); entailment regimes (simple, RDFS, OWL) | Extends RDF semantics to quoted triples |
| Reasoning/entailment | None standardized; engines do pattern matching only | RDFS/OWL/DL entailment, reasoners, SPARQL entailment regimes | Extends SPARQL/RDF regimes |
| Query language | Cypher (openCypher), **GQL** (ISO/IEC 39075:2024), SQL/PGQ (ISO 9075-16) | SPARQL 1.1 / 1.2 | SPARQL-star |
| Entity identity | Local, engine-assigned; app-level keys via constraints | Global IRIs | Global IRIs |

Key facts behind the table:

- **RDF-star** originated 2014 (Hartig & Thompson, "Foundations of RDF* and SPARQL*") as a concise way to state facts about facts. The W3C RDF-star Working Group charter (2022) states it "has become quite popular, especially as a means to provide interoperability between RDF and Property Graphs"; its deliverables are now the **RDF 1.2** family (Recommendations), where quoted triples are called **triple terms**.
- **GQL**, ISO/IEC 39075:2024, published April 17, 2024 — the first ISO standard for a property-graph query language. It builds on openCypher, PGQL, GSQL, and G-CORE; its Graph Pattern Matching (GPM) is shared with SQL/PGQ in SQL:2023; it supports **schema-fixed and schema-flexible** variants (graph types). openCypher (specification + Technology Compatibility Kit at opencypher.org) was the documented inspiration for GQL; the openCypher project has effectively wound down new language work in favor of GQL.

Strengths of LPG for a tool like OpenVerifiers: pragmatic schema-flexibility; edge properties native; rich path/traversal query language with a now-ISO-standardized surface; large tooling ecosystem; fast local pattern matching.
Weaknesses: no formal semantics (unlike RDF's model theory); **no standardized entailment/reasoning** — the engine never derives or checks consistency for you; closed-world conventions baked into query behavior; ontology/consistency tooling far less mature than the RDF/OWL/SHACL stack; edge property semantics differ across vendors (constraint enforcement varies, even between Neo4j editions).

## OpenVerifiers takeaways

### (a) Fact/Transformation model maps directly onto LPG

| OpenVerifiers ontology | LPG mapping |
|---|---|
| Fact node (`id`, `value`, attributes) | Node, label `:Fact`; `id`/`value` as properties; typed attributes as properties |
| Fact `status` (truth / truth_verified / derived / target / unknown) | Property on the Fact node (preferable to labels: status transitions by `SET`, keeps history-free single source; labels would burn the runtime-mutable dimension on something that is *not* state marking) |
| Transformation/rule node (precondition, relation, solver hook) | **Relationship** with a single type (`:TRANSFORM`, `:DERIVES`, `:REFUTES`) + properties for `precondition`, `relation`, `solver_hook` — OR a rule node with outgoing edges if the rule itself must be recursively decomposed (see design addition #1) |
| Unknown node (`why_unknown`, `what_evidence_would_resolve`) | Node `:Unknown` with those two properties, attached to the fact it shadows via a typed edge — first-class node, exactly as the ontology demands |
| Derivation reference | Edge property (`derivation: 'https://…/rule-37'`) or a separate provenance edge/node — LPG allows either; edge property is the cheap default, node when provenance must carry its own attributes (addition #3 culture) |
| OWNER / context / reference-frame (velocity belongs to car1) | Edge property (`owner: 'car1'`, `frame: 'road'`) — the native LPG answer, equivalent to what RDF needs reification/RDF-star for — or a **context node** with incoming `:IN_CONTEXT` edges when context participates in reasoning (addition #3 "reification-style context on relationships") |
| Trace DAG (induction + deduction, loops forbidden) | Directed graph, edges typed `:DERIVES`/`:USES`/`:FROM_TARGET`; loop-freedom enforced in the verifier (no constraint type for "no cycles" exists in Neo4j — shortest-path/cycle detection must be application logic) |
| Variance/statistical values | Plain properties (`confidence`, `interval`) on edges; crossing an "estimated" edge is a flagged risk (see `08-path-analysis.md`, `10-bayesian-nets.md`) |

The node-inheritance/recursive composition of addition #1 maps to LPG as "a Fact node may itself be target of `:COMPOSED_OF` edges into sub-Facts" — i.e. typed composition edges, not nested dicts, which is precisely the LPG idiom (nodes compose graphs; labels classify at any depth).

### (b) What to adopt — storage/query substrate

Adopt LPG as the **physical storage and query substrate** for:

1. **The trace store** — every trace is a DAG of Fact nodes + typed Transformation edges + properties; write once, query many times for renders.
2. **The knowledge base** — ABox-style input context (target + givens) as nodes/edges; TBox/domain knowledge as typed rule edges or rule nodes.
3. **Query capability** — pattern/path queries give free implementation of the success-path / failure-trail views (below), plus existence checks ("is `g1` reachable from any `truth` fact?"), without writing traversal code.
4. **Consistency guards that DO exist** — uniqueness/key constraints on Fact `id`; labels per-kind for cheap partition (`:Unknown` vs `:Fact`).

A Python process using an embedded LPG engine (or a thin in-memory LPG with a Cypher-ish pattern API) covers all four with one model. The model is simple enough that the in-repo `model.py` can stay the source of truth and the LPG layer a serializer/querier — not a second schema.

### (c) What NOT to adopt — and why

- **No formal semantics, no entailment.** Verification claims ("target `g` is entailed by givens + rules") require model-theoretic justification; LPG engines only pattern-match. The verifier (Z3/sympy hooks, rule application, induction/deduction) must remain the semantic engine; the graph is its working memory, never its justification.
- **Closed-world habit is wrong for us.** LPG query behavior assumes absence = false. OpenVerifiers has first-class `unknown` and `unverified_truth`; absence of a derivation edge must never be rendered as falsity. Status must be an explicit property, and query filters must handle "no path found" as *unknown*, not *refuted*.
- **No standardized consistency/typing.** Existence/type constraints are Enterprise-only in Neo4j; there is no standard DL-style consistency checking. Later DL-style consistency (see `09-dl-abox.md`) needs RDF/OWL-family semantics, not LPG constraints.
- **Rule semantics live above the graph.** Preconditions with variables, solver hooks, and rule composition are not expressible in the LPG model itself — they parameterize edge application. Keep Transformation as code/spec objects that *compile to* edges.
- **Correlation/proportionality chains** (flagged risk in addition #4) get zero guardrails from LPG: nothing in the model stops you adding a `:IMPLIES` edge from `A~B` to `B~C` and drawing a false transitive conclusion. Path-analysis/SEM and Bayesian-net formalisms (siblings `08`, `10`) must police this; LPG only stores and queries.

### (d) Interplay with trace rendering

Trace rendering is where LPG pays for itself:

- **Success path:** `MATCH p = (target)-[:DERIVES*1..]->(root:Fact {status:'truth'})` — one path query returns the induction chain; render filters (which rule kinds, which solvers) are `WHERE` clauses on edge properties.
- **Failure trail:** `MATCH p = (target)<-[:ATTEMPTED*1..]-(attempt)` plus `:BLOCKED_BY` edges into `:Unknown` nodes — the renderer shows *why* a branch died by materializing the unknown's `why_unknown` / `what_evidence_would_resolve` properties at the failure point.
- **Verbose-trace filters** map to property predicates: hide solver-internal steps → `WHERE r.kind <> 'solver_internal'`; show only statistical-crossing edges → `WHERE r.estimated = true` (ties to uncertainty flagging, addition #5).
- Because the graph is queried (not traversed in Python), views are declarative and cheap to re-render with different filters — no re-walking of the trace object.

Net: **adopt LPG as the persistence + query model for trace and KB; keep all verification semantics (truth, entailment, consistency, solver hooks, uncertainty policy) in the verifier core; treat the graph as the substrate, never as the authority.**

## Conflicts / flags

- **LPG "type" asymmetry:** nodes have 0..n labels, edges exactly 1 type. If a Transformation ever needs multiple simultaneous classifications, edge-type-only forces either composite types or an intermediate rule node — decide up front (recommended: rule node when recursive composition kicks in, add. #1).
- **Uniqueness is not identity:** Neo4j uniqueness constraints are scoped to (label, properties), and the real enforcement requires Enterprise features for existence/types. Fact id uniqueness must be asserted by the verifier, not relied on from the store.
- **Vendor divergence:** constraint sets and semantics differ between Neo4j editions and between LPG engines; don't write docs as if "the" LPG standard exists. GQL 39075 standardizes the query language surface, not engine semantics/schema behavior.
- **Cypher vs GQL drift:** openCypher stabilized at 9 (2024.2 artifacts) and the project pivoted to GQL; Neo4j's Cypher manual now documents graph types as the preferred schema path. Code examples in this brief use current Neo4j Cypher; treat them as illustrative, and prefer GQL-aligned patterns where available.
- **RDF-star conflation caution:** RDF 1.2 triple terms look like edge properties but keep RDF semantics and are *not* the same as LPG edge properties (no local engine identity, no CWA); any interop mapping between our LPG substrate and RDF must go through explicit translation, not wishful equivalence.
- **Uncertainty:** exact GQL conformance status of each engine (Neo4j, Memgraph, Neptune) at the time of writing is vendor-rolling and not verified here; verify per-engine before committing any code.

## Sources

- Neo4j Getting Started — Graph database concepts (property graph model: nodes, labels, relationships, types, properties): https://neo4j.com/docs/getting-started/appendix/graphdb-concepts
- Neo4j Cypher Manual — Constraints (uniqueness/existence/type/key; Enterprise gating; graph types): https://neo4j.com/docs/cypher-manual/current/schema/constraints/
- openCypher — Resources (Cypher spec, TCK, grammar; openCypher 9 as the last pre-GQL release): https://opencypher.org/resources/
- GQL Standard site (ISO/IEC 39075:2024 published 2024-04-17; DML/DDL, graph types, schema-fixed/flexible; GPM shared with SQL/PGQ): https://www.gqlstandards.org/
- W3C RDF-star Working Group Charter (quoted triples; "statements about statements"; interop between RDF and Property Graphs; deliverables → RDF 1.2): https://www.w3.org/2022/08/rdf-star-wg-charter
- RDF 1.2 Concepts and Abstract Syntax (triple terms; graph comparison): https://www.w3.org/TR/rdf12-concepts/
- R. Angles, "The Property Graph Database Model", AMW 2018, CEUR-WS Vol-2100 (formal LPG definition `G=(N,E,ρ,λ,π)`; integrity-constraint notions): https://ceur-ws.org/Vol-2100/Angles18.pdf
- "A Formal Design Framework for Practical Property Graph Schemas", EDBT 2023 (schema design for LPG as open research): https://openproceedings.org/2023/conf/edbt/3-paper-119.pdf
- RDF 1.1 Semantics (model-theoretic semantics; entailment regimes; contrast to CWA): https://www.w3.org/TR/rdf11-mt/
- O. Hartig, B. Thompson, "Foundations of RDF* and SPARQL*" (2014; original RDF-star proposal, per WG charter): https://arxiv.org/abs/1406.3399