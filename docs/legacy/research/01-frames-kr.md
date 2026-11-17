# Frames and frame-based knowledge representation — research brief

Status: **Research brief [open] — feeds design addition #1** (node inheritance + recursive composition). Open research → feeds `docs/research/synthesis.md`. Companion briefs: `02-rdf-owl-reification.md`, `03-dl-abox-tbox.md`, `06-property-graphs.md`. Non-transitive-slot flag (takeaway 9) also touches additions #4/#5: see `04-path-analysis-sem.md`, `05-bayesian-networks.md`.

## What it is

Frame-based KR is the idea, introduced by Marvin Minsky in 1974 ("A Framework for Representing Knowledge", MIT AI Memo 306), that knowledge about stereotyped situations should be stored as **frames** — structured records with named **slots** whose **fillers** are values or references to other frames. A frame for "car" carries slots like body, chassis, engine, owner, top-speed; a specific car is an *instance* inheriting those slots.

Minsky's motivation was perception and expectation, not database modeling. A frame is an *expectation device*: when you perceive a scene or read a sentence, you select a frame, and its slots tell you what to look for next; missing or anomalous fillers produce expectations or "frame failure" (reject the frame, try another). Slots thereby let a system **fill in missing information** — assume a chair has four legs unless evidence says otherwise — which is exactly the "verify claims by completing the picture" posture OpenVerifiers wants.

Key mechanisms in Minsky's paper:

- **Slots with defaults**: each slot has a default assignment used when no specific filler is known; the default can be overridden by new evidence.
- **is-a inheritance**: frames are organized in taxonomic networks ("is a kind of"); a frame inherits slots, defaults, and constraints from its parent frame type.
- **Part-whole decomposition**: a frame's filler can itself be a frame (car → engine → piston), so knowledge decomposes recursively.
- **Prototypes**: a frame is a prototypical instance of its category, not a cleaned-up abstraction; defaults carry the prototype's typical values.
- **Procedural attachment**: slots can carry attached procedures (demons, "if-needed"/"if-added"/"if-removed") that compute a filler or run side-effects when the slot is accessed or changed.
- **Semantic/formal links**: Minsky sketched is-a, a-ko, and part-of link types and worried explicitly (in the paper's sections and later commentary, e.g. the 1981 reprinting) that representations risk being either too "logical" and brittle or too "procedural" and unmotivated — a dichotomy later KR history kept playing out.

Why frames were introduced: earlier semantic networks (Quillian 1968) had associative links but no notion of *expected structure*; logic-based systems had formal semantics but no machinery for typicality or default completion. Frames supplied structured, expectation-driven, default-completing representation tuned for perception and language understanding.

Three properties of Minsky's design matter most for a claim verifier:

- **Defaults are hypotheses, not facts.** A default filler is the system's best guess for the stereotyped case; the frame machinery exists to detect when the guess fails. This is a *generative* view: representation actively proposes missing structure, which is what a verifier does when it asks "for this target to hold, what else must be true?"
- **Frames compose.** "The frame for a room has slots for walls, ceiling, floor, door…" and each of those has its own frame. Minsky stated part-whole structure as first-class: a top-level frame's terminals can be filled by other frames ("a frame for 'bird' has a slot 'is-a' filled by 'animal'..."). Composition and taxonomy are both fundamental, not incidental.
- **Failure is data.** "Frame failure" — incoming evidence that contradicts a slot or its constraints — is not an error but a signal to switch frames or specialize. A verifier that treats contradiction as failure loses the diagnostic value; one that records why the frame failed gains an explanation engine.

Working shape of a frame system: a *class frame* (car) declares slots and defaults; *instance frames* (my-car) inherit the slots and override or fill them; *subclass frames* (sedan) add slots or restrict inherited ones. Inheritance is what makes frames economical, and defaults are what make them productive — but both are also what made class-frame systems non-monotonic and hard to audit, which the next forty years of KR research (KL-ONE, description logics) spent fixing. The canonical failure mode: "birds fly" (default) + "Tweety is a bird" + "Tweety is a penguin" — an inheritance system that resolves Tweety's flight status silently either lies or must implement a separate, non-classical override logic.

Frame systems did not get rigorous formal semantics until the mid-1980s: Brachman's 1977 critique ("What's in a Concept") and KL-ONE (1985) rebuilt frame structure on interpretation-based semantics, producing the description-logic line (AC, EL, OWL 2 DL = SROIQ) — formally defined classes, roles/restrictions (the slot descendants), and instance assertions, with sound, complete, terminating reasoners; see `03-dl-abox-tbox.md`. Property graphs went the other way: no schema, no semantics, maximal looseness; see `06-property-graphs.md`. OpenVerifiers sits between: a checkable schema (grammar/TBox) plus open relationships, so it must choose what to import from each tradition deliberately rather than by accident.

Minsky's paper itself was exploratory, not a spec: it worked through vision (perceiving a room), language (narratives about opening a door), and memory, and closed by listing open problems — how to choose the right frame, substitution rules, and how defaults should be learned. Read that way, frames are less a formalism and more a research program; every later system (FRL, KRL, KL-ONE) is an attempt to pin down one corner of it. That is why "which frame" and "what to fill" remain live design questions for OpenVerifiers' grammar builder: the grammar is effectively the frame library, and the verifier is the frame matcher that must also survive frame failure without pretending nothing happened.

The frame idea also carried a theory of language as expectation: Minsky framed sentence comprehension as activating frames that supply unstated participants — parsing "he opened the door" activates a door-frame that fills in hinge, knob, opening motion. That is the same "fill in the gaps" mechanism, and it prefigures both modern event schemas and LLM slot-filling. For OpenVerifiers the point is practical: the grammar-to-target path (input context from a natural-language claim) is a frame-matching step, and its output must be typed slots + Unknowns, never silently defaulted values.

## Prior art systems

- **FRL (Frame Representation Language) — Roberts & Goldstein, MIT AI Memo 408, 1977.** First practical implemented frame language; `AKO` ("a kind of") slots drive inheritance, defaults, and procedural attachment; showed frames were implementable and teachable.
- **KRL (Knowledge Representation Language) — Bobrow & Winograd, Cognitive Science 1(1), 1977.** Frames as "units" implemented in Lisp; added prototypes, "perspectives" (viewing one entity from multiple descriptors), and *procedural semantics* (description matching as the inference engine); aimed at language understanding.
- **KL-ONE — Brachman & Schmolze, Cognitive Science 9(2), 1985.** The corrective: frames re-built with formal, model-theoretic meaning. Concepts and roles with structured subsumption ("structured inheritance networks"); a classifier that computes subsumption and places new concepts in the taxonomy automatically. Direct ancestor of description logics.
- **Description logics (AC-family, EL, OWL DL)** — Baader, Brandt, Lutz "Pushing the EL Envelope" (IJCAI 2005); OWL 2 W3C Recommendation. Formal semantics, decidable subsumption/classification, tractable EL profile; OWL 2 DL (SROIQ) is the standard ontology language; reasoners (HermiT, Pellet) check consistency across schema and instance assertions. See `03-dl-abox-tbox.md` for the TBox/ABox mapping.
- **Ontology engineering practice** — Noy & McGuinness "Ontology Development 101" (Stanford); Gruber's definition of an ontology (explicit specification of a conceptualization). Disciplines: name concepts and slots precisely, decide single vs multiple inheritance, declare disjointness, prefer defining constraints over prose, keep schema (TBox) separate from instances (ABox).
- **Property graphs** — labeled nodes/edges, no built-in schema or semantics; the "open and loose" extreme. Positioned in `06-property-graphs.md`.

## What frames got right

- **Structured defaults**: defaults turn a sparse frame into an operational model — slots you never stated still have a value to reason with. This is the original "complete the picture from expectation" move, and it is precisely what a verifier needs to *generate* candidate fillers and then check them.
- **Typed, named slots**: named slots with expected types/constraints give structure to what would otherwise be a flat bag of properties; they made partially specified objects modelable (you can ask "what's the engine slot?" before you know the answer).
- **Part-whole decomposition**: recursive decomposition (car → chassis → frame member) matches how experts actually slice problems, and gives each level its own slots and derivations — the model OpenVerifiers' "recursive sub-information" is reaching for.
- **Prototype + inheritance**: is-a inheritance lets one definition serve a whole category; prototypes let a system reason with "typical" values without enumerating them.
- **Expectation-driven processing**: matching a frame against input focuses attention and detects missing or anomalous data — a natural fit for turning a target claim into slots-that-must-be-filled (deduction) and for knowing when evidence is incomplete.
- **Engineering and teaching practice**: FRL/KRL created the first real tooling culture around slot editing and inheritance; Ontology 101 (2001) is its direct descendant — naming discipline, explicit hierarchies, declared disjointness. The practical layer survives even where the formalism died.
- **An informal account of defeasible reasoning**: default override and frame failure are, in spirit, non-monotonic reasoning before nonmonotonic logic existed. OpenVerifiers gets the benefit for free by keeping Unknown first-class: override becomes "new evidence → mark previous filler as resolved-Unknown/deprecated", no special logic needed.

## What frames got wrong / limiting

- **No formal semantics**: FRL/KRL frames were Lisp data structures; what inheritance meant, what a slot "was", and what a default *claimed* were all implementation choices. Two frame systems meant two different inheritance behaviors; nothing was checkable.
- **Defaults are non-monotonic**: defaults get overridden (the canonical "Tweety": birds fly by default, but Tweety is a penguin). Overriding without recording it destroys the ability to audit *what was assumed*; in a verifier that is fatal.
- **Inheritance conflicts resolved ad hoc**: multiple parents with conflicting slot values/types were resolved by AKO-path ordering or first-wins heuristics — arbitrary, unrepeatable, unprincipled. KL-ONE existed largely to fix this.
- **Procedural attachment became a dumping ground**: demons (if-needed/if-added) hid computation and side effects inside slot access; reasoning became untraceable and system-specific. The logic-based camp (Brachman's 1977 "What's in a Concept" critique) objected that this conflated structure, meaning, and computation.
- **is-a overloaded**: frame networks freely mixed class membership, property inheritance, and part-whole links under one "is-a" umbrella; the KL-ONE line of work spent years disentangling subsumption from attributes from individuals (see also `03-dl-abox-tbox.md`).
- **Defaults and constraints were indistinguishable**: a default value and an invariant requirement lived in the same slot, so systems could not tell "typical" from "required"; OWL later formalized restrictions and simply dropped defaults. OpenVerifiers must keep `default_candidate` and `precondition` as separate fields, never one.
- **Part-of stayed a slot like any other**: transitivity, disjointness of parts, and whether parts inherit container properties were left unstated; OWL composite properties and property-graph edge semantics later had to re-decide all of it. For OpenVerifiers: part-of must be a first-class typed axis with declared transitivity and a depth cap (see Conflicts), not an attribute.

## OpenVerifiers takeaways

For Fact nodes (typed attributes), Transformation preconditions, first-class Unknown, inheritance + part-of decomposition, and solver hooks on inherited slots:

1. **Model attributes as typed slot descriptors, not bare fields.** A Fact node attribute slot = `{name, type, cardinality, optional, owner/context, default_candidate, hook_ref}`. This is the single most portable frame idea: structure without semantics is exactly what frames became, and typed descriptors are what let a verifier check preconditions mechanically. (Minsky 1974; Ontology 101 practice of slot typing.) Concretely, the part-of slot of a `car` Fact:

```python
SlotDescriptor(
    name="engine",
    type="EngineFact",            # filler must be a Fact node of this type
    cardinality=(0, 1),           # 0..1: optional part; (1,1) would be mandatory
    owner="car",                  # OWNER/context lives on the descriptor (addition #3)
    default_candidate=None,       # provisional value for query-time display only
    hook_ref="sympy.mass_balance",# declared; fires ONLY via an explicit Transformation
    part_of=True,                 # part-of axis, distinct from is-a inheritance
)
```

2. **No silent defaults — defaults become `default_candidate`, a provisional derived value, never a truth.** Frames filled unknown slots with defaults as if known. OpenVerifiers already has the better tool: keep the slot empty + first-class Unknown (why-unknown, what-evidence-would-resolve), and store the default as an *additional candidate* the verifier can try to verify. If a default-derived value does enter a derivation, the Fact status must be `derived` (from default), visibly flagged in the trace — never `truth` or `unverified_truth`. This inherits frame completion power without non-monotonic dishonesty.

3. **is-a hierarchy inherits slot descriptors + constraints, with strict override rules.** Subclass may *restrict* an inherited slot (narrower type, tighter cardinality, stronger precondition) but may not loosen it or silently change the filler. A subtype violating a parent slot constraint is a classification error (KL-ONE's subsumption check). Multiple-parent conflicts are not resolved by ordering: they produce an explicit conflict → Unknown node with both parents' constraints as evidence. Deterministic, auditable, matching the DAG/no-loops rule.

4. **Keep two orthogonal axes: is-a (subtype) and part-of (composition).** Do not collapse them. part-of slots are typed, cardinality-marked (0..1 vs 1..1), and optional by default — a car may lack an engine (trailer?) without being inconsistent; a missing 1..1 part *is* an inconsistency the verifier should flag. Recursive decomposition = part-of slots whose fillers are themselves Fact nodes with their own typed slots. This is typed composition, not nested dicts (design directive, confirmed by KL-ONE's structural distinction and Ontology 101).

5. **Solver hooks attach to slot descriptors but fire only via explicit Transformation nodes.** The frame lesson: implicit demons make reasoning untraceable. A hook (sympy/Z3 backend) is *declared* on the slot descriptor and inherited with it, but execution requires an explicit Transformation node whose precondition covers the slot's type/cardinality checks. Inherited hooks keep their inherited preconditions; the trace shows the Transformation, not magic inside attribute access.

6. **Inherited slot resolution must re-check preconditions, then either derive or produce Unknown — never re-use a stale parent filler.** When a subclass Fact fills an inherited slot, the parent's constraints still bind (KL-ONE style restriction); if the candidate filler cannot satisfy them, result is Unknown-with-reason, and the reason record includes the violated constraint. This makes inheritance a *checkable* operation instead of a copy operation.

Suggested deterministic resolution procedure for an inherited slot on a concrete Fact:

1. Collect slot descriptors along the is-a path; subclass descriptors supersede parent descriptors only by *restriction* (type narrowing, cardinality tightening, precondition strengthening). A widening or conflicting override is a conflict — emit Unknown with both descriptors as evidence.
2. Bind instance fillers from input context. A mandatory (1..1) slot with no filler and no derived candidate is an inconsistency, not an auto-fill.
3. `default_candidate` is used only at query/render time and in "try this candidate" refinement mode; it never enters a derivation with truth status.
4. If a Transformation references the slot, evaluate its precondition against the current filler; fire the hook through the Transformation and record a derived edge.
5. Never reuse a parent instance's stale filler; re-derive or leave Unknown.

7. **TBox/ABox split falls out naturally**: the grammar/TBox is the is-a hierarchy + typed slot descriptors + Transformation preconditions; the input context is instance fillers (ABox). Classification (subsumption) is the DL-flavored check available to deduction; induction is the forward counterpart. Keep the two content sources exactly as scoped (design §9) — frames show what happens when schema and instances bleed into one soup. See `03-dl-abox-tbox.md`.

8. **Declare slot-owner/context on the descriptor** (the OWNER problem, design addition #3): a slot's type can be "velocity with owner=car1, reference-frame=ground". This is the frames way to avoid a single global attribute table and is compatible with the reification work in `02-rdf-owl-reification.md`.

9. **Non-transitivity flag on inherited links**: slots expressing proportionality/correlation chains must *not* inherit transitivity through the is-a or part-of hierarchy — that would mathematically smuggle correlation-transitivity (flagged risk, additions #4; see `04-path-analysis-sem.md`, `05-bayesian-networks.md`). Mark such slot descriptors `non-transitive` with an error term/confidence field, per finalized first-class uncertainty (addition #5).

Worked example (car → sedan → my-car): `car` Fact declares part-of slots body, chassis, engine (0..1, typed); `sedan` (subclass via is-a) inherits all descriptors, restricts engine to `InternalCombustionEngine` (narrower type — allowed), adds slot trunk (1..1). `my-car` (instance) fills body, chassis, trunk from input context; engine stays **empty** with an attached Unknown node ("no engine evidence yet; would resolve by: engine mount inspection"). The grammar supplies `default_candidate=None`, so no phantom engine is fabricated; if the physics question needs mass, induction can either find a verified engine fact or produce Unknown-with-evidence-need, never a guessed mass. The inherited `hook_ref` (mass_balance) is available but fires only when a Transformation node explicitly invokes it with the precondition "engine slot filled". Inheritance here is *constraint propagation + check*, not value copying.

Frame concept → OpenVerifiers mapping:

| Frame idea (Minsky 1974; KL-ONE 1985) | OpenVerifiers construct |
|---|---|
| frame / concept | Fact node + SlotDescriptors (grammar/TBox side) |
| instance frame | Fact node with fillers (input context / ABox) |
| slot | typed attribute descriptor on Fact node |
| filler | value or reference to child Fact node |
| is-a / AKO | subtype relation: inherits descriptors, restriction-only overrides |
| part-of / decomposition | typed part-of slots, cardinality-marked, recursive |
| default assignment | `default_candidate` — query-time provisional, never silent truth |
| constraint (KL-ONE role restriction) | Transformation precondition / slot type+cardinality |
| procedural attachment (demon) | `hook_ref`, fired ONLY via explicit Transformation |
| frame failure → new frame | contradiction recorded → Unknown with why + evidence-needed |
| classification / subsumption | subtype-consistency check during inheritance resolution |

**Adopt vs avoid — summary.** Adopt: typed slot descriptors (takeaway 1); explicit empty/unknown fillers with defaults-as-candidates (2); is-a hierarchy with restriction-only inheritance (3); part-of decomposition as a separate typed axis (4); solver hooks declared on slots but fired only through explicit Transformations (5). Avoid: unconstrained defaults silently filling values (frames' core flaw for a verifier); inheritance-conflict resolution by AKO ordering; procedural attachment/demons as hidden slot behavior; collapsing the TBox into the ABox; inheriting part-of relationships as if they were is-a.

## Conflicts / flags

- **Defaults vs first-class Unknown: direct tension.** Frames exist to fill unknown slots by default; OpenVerifiers made Unknown a first-class citizen with why-evidence. Resolve by takeaway #2: defaults survive as *candidates*, never as resolutions. Anything else silently fabricates the very claims the tool exists to check.
- **Non-monotonic inheritance vs the deterministic DAG.** Frame default inheritance is defeasible (Tweety) and therefore non-monotonic — new evidence withdraws a conclusion. OpenVerifiers' DAG with no loops and a verbose deterministic trace is monotonic in spirit. Options: (a) keep defaults out of the verification path entirely (only query-time display), or (b) persist default-derived values as `derived` with the default's provenance, so re-verification after new evidence is honest rather than silently revised. Recommend (b) with (a) as the default UI posture.
- **Value conflicts under multiple inheritance are unsolved in prior art.** KL-ONE/DL resolve conflicts only when slots are formal roles with domain/range; conflicting *constant* fillers have no principled resolution anywhere in the tradition. Recommend explicit refusal → Unknown node rather than lattice-join heuristics: silently averaging two conflicting inherited constraints is exactly the false-precision behavior OpenVerifiers rejects.
- **Procedural attachment is the ancestor of solver hooks.** Porting demons into slot access would reproduce frames' untraceability. The design already has Transformation nodes with preconditions — keep hooks attached-to but fired-through-Transformations, or the deterministic core becomes a black box. Takeaway #5.
- **Open/loose relationships vs typed slots.** The design wants open, loose relationship types (addition #2); frames show untyped everything rots (no checks possible). Position: *facts* get typed slot descriptors; *relationships between facts* stay open-labeled edges (property-graph style, `06-property-graphs.md`). Do not let looseness leak back into Fact attributes.
- **OV's derived-status semantics** must distinguish `derived-from-axiom` (sound, monotonic) from `derived-from-default` (defeasible) from `estimated/statistical` (uncertainty-marked, addition #5) — frames flattened all three into "inherited", and that flattening is the root of most frame-system failures.
- **is-a cycles must be rejected like graph loops.** Inheritance is a partial order; the no-loops DAG rule applies to the is-a axis too (KL-ONE and OWL both forbid class cycles where a class subsumes itself). State it explicitly: the same dedup/ancestor rule that blocks Fact-graph loops must block inheritance cycles, or a "self-inheriting" class silently breaks classification.
- **Restriction-only inheritance may be too strict for default-bearing slots.** KL-ONE-style inheritance assumes slots are formal roles; OV wants defaults-as-candidates on slots. They coexist only if `default_candidate` is inherited *as a candidate*, which subclasses may legitimately refine down the is-a chain — decide the rule explicitly: candidates may be refined (better default), constraints may only be tightened.
- **Classification is passive; verification is active.** DL reasoners answer subsumption/consistency queries but do not *generate* candidate fillers — frame defaults did the generating, and OV's induction is the generator. Prior art contains no sound way to combine both; the design must keep the generator (induction) separate from the checker (classification), with derived edges carrying provenance. Otherwise "suggested filler" and "verified filler" blur — exactly the blur that sank frames.
- **Part-of is transitive and irreflexive**: a part of a part is a part, but nothing is part of itself — consistent with the DAG rule, but composition depth must be bounded or the trace explodes (frames never addressed recursion cost; KRL-style description matching blew up computationally). Recommend an explicit part-of depth cap in the grammar and cycle detection on part-of edges, mirroring the Fact-graph loop rule.
- **Slot filling vs verification vocabulary**: frames treated filling a slot as inference; a verifier must treat filling as a claim to check. When the verifier itself fills a slot (derived), downstream checks must know the filler is provisional — do not let derived fillers become unmarked premises; tie into finalized derived-status semantics (addition #5).

## Sources

- [Minsky, "A Framework for Representing Knowledge", MIT AI Memo 306 (1974) — archived copy](https://web.archive.org/web/2020/https://dspace.mit.edu/handle/1721.1/6089) — the primary source: frames, slots, defaults, is-a, part-whole, prototype theory, expectation-driven perception.
- [Roberts & Goldstein, "The FRL Primer", MIT AI Memo 408 (1977) — archived copy](https://web.archive.org/web/2020/https://dspace.mit.edu/handle/1721.1/5770) — authoritative documentation of FRL: AKO inheritance, defaults, procedural attachment in a real system.
- [Bobrow & Winograd, "An Overview of KRL" (Cognitive Science 1(1), 1977) — canonical DOI](https://onlinelibrary.wiley.com/doi/10.1207/s15516709cog0101_2) — primary statement of KRL: prototypes, perspectives, procedural semantics; metadata cross-checked via [dblp record](https://dblp.org/rec/journals/cogsci/BobrowW77.html). (Publisher site blocks automated fetching; article itself is the authority.)
- [Brachman & Schmolze, "An Overview of the KL-ONE Knowledge Representation System" (Cognitive Science 9(2), 1985) — archived copy](https://web.archive.org/web/2019/https://onlinelibrary.wiley.com/doi/10.1207/s15516709cog0902_1) — the formal-semantics correction to frames: structured inheritance networks, subsumption, classifier; also [dblp record](https://dblp.org/rec/journals/cogsci/BrachmanS85.html).
- [Baader, Brandt, Lutz, "Pushing the EL Envelope" (IJCAI 2005) — dblp record](https://dblp.org/rec/conf/ijcai/BaaderBL05.html) — authoritative metadata anchor for the EL description-logic family (tractable subsumption), the modern successor guaranteeing the properties KL-ONE aimed at.
- [W3C, "OWL 2 Primer" (2012)](https://www.w3.org/TR/owl2-primer/) — official tutorial defining OWL 2 DL/EL/QL profiles, classes, restrictions, inheritance semantics; the current standard encoding of frame-inheritance ideas with formal semantics.
- [Noy & McGuinness, "Ontology Development 101" (Stanford, 2001) — archived copy](https://web.archive.org/web/2020/https://protege.stanford.edu/publications/ontology_development/ontology101-noy-mcguinness.html) — the standard practical methodology: concept/slot naming, inheritance decisions, disjointness, TBox/ABox discipline.
- [Gruber, "What is an Ontology" (1993/2007, Stanford)](https://tomgruber.org/writing/ontology-definition-2007.htm) — authoritative definition of ontology as explicit specification of a conceptualization, still the most-cited framing; also grounds the grammar/TBox = domain-knowledge-spec split.
- Source-check note: canonical Wiley DOI links block automated fetch (humans can browse them); every other URL above verified reachable (200) at write time — dblp records via https://dblp.org, Internet Archive copies via web.archive.org, W3C and tomgruber.org direct.