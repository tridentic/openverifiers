# DL ABox/TBox formalism and consistency checking

**Status:** research brief [open]. Feeds `docs/design.md` (TBox naming already adopted) and `docs/newer-additions.md` (two-source separation, Unknown node, attribute ownership, hybrid symbolic/statistical core). Companion briefs: `research/02-rdf-owl-reification.md` (attribute/reference-frame context), plus the path-analysis and Bayesian-net briefs (statistical pipeline). All sources live; see Sources.

## What it is

Description Logics (DLs) are a family of knowledge-representation formalisms that model a domain as *concepts* (unary predicates over a domain — classes of things), *roles* (binary predicates — relationships between things), and *individuals* (constants — particular things). A DL knowledge base (KB) is the pair:

- **TBox** — the *terminological* component (schema): concept definitions, subsumption axioms ("every Car is a Vehicle"), role axioms (role hierarchies, transitivity, functionality). It is the general, domain-level knowledge.
- **ABox** — the *assertional* component (data/instance context): membership assertions about specific individuals ("car1 is a Car", "car1 hasVelocity v1"), plus equality/inequality between individuals.

This TBox/ABox split is the **standard, canonical name** for exactly the two-content-source separation OpenVerifiers already adopted: domain knowledge (grammar/rules/TBox) vs target/input context (givens, instance claims/ABox). `docs/design.md` and `docs/newer-additions.md` already use "TBox" for the domain side; that usage matches the DL literature and should be kept.

**Why DLs, not raw FOL.** Every DL is a *decidable fragment* of first-order logic: concepts are unary predicates, roles binary predicates, and the grammar is restricted (e.g., ALCQI embeds into the two-variable fragment with counting, `C²`; expressive DLs connect to the guarded fragment) precisely so that satisfiability, subsumption, and entailment remain decidable — with guaranteed termination. That guarantee is the entire reason to put a structural layer in a DL rather than in general FOL theorem proving: a verifier needs "does this hold?" to always answer, and a general theorem prover can run forever. The price of decidability is the expressivity ceiling discussed under Languages.

"DL" is a family, not one logic: `ALC`, `EL`, `SHOIQ`, `SROIQ`, `DL-Lite` and the OWL 2 profiles differ in which constructors they admit and therefore in worst-case complexity. Saying "the verifier should use DL reasoning" is underspecified until the *language* is chosen; everything in this brief that trades expressivity against tractability is really choosing that language.

## ABox/TBox in detail

**Worked micro-example (the shape OpenVerifiers deals in).** TBox: `Car ⊑ ∃hasEngine.Engine` (every car has an engine), `Combustion ⊑ ¬Electric` (disjoint fuel types), `hasEngine` functional (one engine per car). ABox: `car1 : Car`, `car1 hasEngine e1`, `e1 : Combustion`. Asking "is the input context consistent with domain knowledge?" = ABox consistency w.r.t. the TBox. It fails iff the reasoner finds no model — e.g., a second input claim `car1 hasEngine e2` with `e2 : Electric`: functionality forces `e1 = e2`, disjointness then demands one engine is both Combustion and not-Electric — contradiction, KB inconsistent, explanation returned. Point: the check is **global** (all individuals, all axioms at once), which a per-rule walk of a derivation DAG never performs. A rule engine derives; a reasoner decides.

**Name origin.** The T/ABox terminology dates to the earliest DL systems (KL-ONE line, 1980s); the handbook and the OWL 2 specifications define the modern usage. It is not an OpenVerifiers invention — adopting it keeps the project's vocabulary interoperable with the DL/ontology literature.

**Reasoning tasks.** Defined over the KB, in increasing order of use in a verifier:
- *Concept satisfiability* — can some individual exist that instantiates `C`?
- *Subsumption* — does `C ⊑ D` follow from the KB?
- **ABox consistency w.r.t. the TBox** — do the instance assertions contradict the schema? (The core "does the input context violate domain knowledge" check.)
- *Instance checking / entailment* — does `C(a)` (or `R(a,b)`) follow from the KB? I.e., is a claim entailed by TBox + ABox?
- *Classification* — compute all subsumption relations among the named concepts (the full concept lattice).
- *Realization* — for each individual, the most specific named concepts it instantiates.

## Languages and what expressivity costs

| Language | Constructs | Worst-case reasoning cost |
|---|---|---|
| `ALC` | `⊓ ⊔ ¬ ∃R.C ∀R.C`, top/bottom | Concept satisfiability **PSPACE-complete** (Schmidt-Schauß & Smolka 1991); with GCIs **EXPTIME-complete** (Tobies 2001, thesis) |
| `SHIQ` / counting variants | + role hierarchies, inverse roles, qualified counting | **EXPTIME-complete** (Tobies 2001) |
| `SHOIQ` / `SROIQ` (OWL 1/2 DL) | + nominals, cardinality restrictions | **NExpTime-complete** worst case (Tobies 2000; ALCQI with nominals and cardinality restrictions is NExpTime-complete) |
| `EL` / `EL++` | `⊤ ⊓ ∃R.C`, (EL++ adds role hierarchies, nominals, concrete domains fc.) | Subsumption/instance checking **polynomial** (Baader, Brandt, Lutz 2005; EL++ tractable under syntactic restrictions) |
| `DL-Lite` (OWL 2 QL) | limited role/class axioms | CQ answering **AC⁰ in data complexity** — queries rewrite to SQL |
| OWL 2 RL | Horn-like rule-expressible fragment | Polynomial, reason by forward chaining over triples (rule-engine style) |

Two caveats on that complexity arithmetic. First, worst-case bounds are *existential*: they say nothing about how hard typical ontologies are — ELK classifies SNOMED-scale EL ontologies in seconds-to-minutes, and HermiT handles many expressive ontologies fine in practice. Second, the profile choice is a *language* commitment, not a tuning knob: each profile forbids certain constructors outright (EL forbids disjunction, QL forbids role chains, RL loses completeness), so the choice must be driven by what the domain grammar actually needs to say — a verifier's TBox designer should start from "which axioms do I need?" and pick the smallest profile containing them.

## Reasoners and what consistency checking does

- **HermiT** — hypertableau calculus; the first reasoner to fully support OWL 2 DL; correctness via *ordering* and *blocking* strategies rather than traditional tableau clash-driven search (Shearer, Motik, Horrocks 2009, JAIR; ORE 2012 system description).
- **Pellet** — OWL-DL tableau reasoner with strong individual/datatype support and middleware (Sirin et al. 2007, J. Web Semantics).
- **FaCT++** — tableau decision procedure for `SHOIQ` (Tsarkov & Horrocks 2006).
- **ELK** — consequence-based reasoner for EL++/OWL 2 EL; concurrent classification; orders of magnitude faster on EL corpora (millions of axioms, SNOMED-class inputs) (Kazakov, Krötzsch, Simančík 2012).

**Three engine families (matters when OpenVerifiers picks one).**
- *Tableau-based* (Pellet, FaCT++, and HermiT's hypertableau): decide satisfiability by trying to construct a model, splitting on nondeterministic choices (disjunctions, qualified number restrictions), with blocking to keep the model finite. Full expressivity (OWL 2 DL), but worst-case exponential behavior and per-query cost.
- *Consequence-based* (ELK, and the CEL lineage): saturate the TBox with consequences by applying a fixed set of completion rules; polynomial in EL++/OWL 2 EL, massively parallelizable, best at classification of very large TBoxes — at the price of restricted expressivity (no full negation/disjunction).
- *Materialization/rewriting* (OWL 2 RL engines, DL-Lite rewriters): either forward-chain rules to closure (RL) or rewrite the query so the data stays untouched (QL). This is the family closest to OpenVerifiers' rule-rewriting engine — which is exactly why OV should know what it loses by staying there: no global consistency test, no classification, and (for RL) no completeness guarantee w.r.t. the DL semantics.

**Critical semantic defaults, both opposite to the typical verification/DB mindset:**
- **Open-world assumption (OWA):** a formula is true only if entailed; everything not entailed is simply **unknown**. Absence of a fact in the ABox never licenses "false". (OWL 2 Direct Semantics; Reiter's closed-world assumption is the DB alternative, below.)
- **No unique-name assumption (UNA):** two distinct names may denote the same individual unless explicitly asserted `≉`. DL reasoners never assume car1 ≠ car2 from their identifiers.

**A subtlety OpenVerifiers must internalize: anonymous fillers.** If the TBox says `Car ⊑ ∃hasEngine.Engine` and the ABox contains `car1 : Car`, the KB *entails* that car1 has some engine — but no engine individual need be named in the ABox. Under OWA the existential filler may be anonymous. So "car1 has an engine" is **verified** even though no `hasEngine` assertion exists; the verifier must not demand a witness node in the input context. This is the DL way of saying "the typing forces existence"; the inverse (finding or creating the witness) is what OV's own rule engine does when it materializes derived nodes.

**What consistency checking is not.** It is not per-claim validation (the rule engine already does that), not the proof walk itself, and not a lint that local checks can satisfy. Consistency is a *global fixed-point property* of the whole KB: it can fail for reasons invisible to any single derivation (two far-apart assertions, an anonymous filler forced into a clash, a functional-role collision). Conversely, consistency does not guarantee any particular claim — a consistent KB can entail, leave unknown, or contradict any given assertion. Treat the reasoner's answer as a verdict input, never as the proof.

## Open-World vs Closed-World (implications for unknown/verdict semantics)

- **CWA (Reiter 1978):** treat every atom not derivable from the KB as *false* ("negation as failure"). This is the database/Prolog default and the default mental model of most engineers and users: "the DB doesn't contain it, so it isn't."
- **OWA (DL/OWL default):** only derivable consequences are true; the rest are unknown. This is the semantics of an *incomplete* information source — right for verification, where the absence of a supporting fact is evidence of an incomplete input, not of a false claim.

Epistemically, OWA makes the reasoner answer "what is *knowable* from this KB", not "what is *true* in the world". That is precisely the stance a verifier of AI claims should take: the input context is a partial, possibly erroneous report, and domain knowledge is the fixed lens. Claim verification under OWA therefore reads: *entailed* = the claim follows no matter what the hidden parts of the world are; *contradicted* = no completion of the input can make the claim coexist with domain knowledge; *unknown* = some completions support it, some don't. This three-way epistemic grading is the semantic backbone of OpenVerifiers' verdicts and is the main reason to keep OWA rather than drift into database-style CWA.

**Worked verdict comparison (OWA vs CWA).** Input context: `car1 : Car`, `car1 hasOwner alice`, TBox: `Car ⊑ ∃hasOwner.Person`. Query: "does car1 have an owner named bob?" — not entailed under either assumption. Query: "is `car1 hasOwner bob` false?" — CWA: yes, false (not in the ABox); OWA: **unknown** (a model exists where that assertion holds; the input is simply silent). Query: "is it false that car1 has an engine?" — under OWA this is *contradicted*: the TBox entails `car1 hasEngine ?`, so its negation is inconsistent. Three verdicts, three meanings: entailed (verified), negated-by-TBox (contradicted), neither (unknown). This is precisely the verified / contradicted / unverified-unknown trichotomy OpenVerifiers needs.

**Recommendation (repeated in takeaways): keep OWA at the structural layer.** Reach for CWA-flavored rules (negation-as-failure, closed enumerations) only on explicitly closed subdomains where the user declares completeness ("these are all owners"). OWA + explicit Unknown makes "no evidence" a distinct, first-class verdict — never collapsed into "false".

## OpenVerifiers takeaways

**1. Adopt DL-style consistency checking for the structural layer — yes, with a profile discipline.**
- Split stays: **TBox = domain knowledge (grammar/rules)**; **ABox = target/input context + derived fact nodes**. This is the canonical, literature-standard decomposition; keep the names.
- Run a real reasoner (ELK for scale, HermiT for expressivity) as an *oracle* for two operations the rule engine cannot do itself:
  - **Global ABox consistency w.r.t. the TBox** — the rule engine walks the trace DAG and checks what is reachable; it never sees a contradiction between two individuals that is only visible by comparing all assertions simultaneously (e.g., class disjointness across distant branches, functional-role violations, TBox-driven conflicts).
  - **Classification / subsumption closure** — automatic derivation of the full subsumption lattice and inheritance of attributes down the hierarchy. Subsumption is *transitive and monotone*, which is exactly the "DAG of type relationships" the verifier's TBox layer wants — computed for free instead of hand-listed.

**Where in the pipeline to call the reasoner (operational pattern).** Three checkpoints, not one:
- *Ingestion/bootstrapping:* after the TBox is loaded and the input context is converted to ABox assertions, run ABox consistency once — a cheap gate that rejects self-contradictory inputs before any derivation work.
- *After derivation batches:* each time the rule engine materializes new facts and marks trace edges, re-check consistency of the grown ABox (or incrementally, for ELK-class engines). This is where "claimed derivation contradicts domain knowledge" is caught *globally*, e.g., a derived subtyping that violates a disjointness axiom two branches away.
- *On-demand:* classification/realization queries when the trace needs "what is the most specific type of node X?" or "what does the subsumption lattice imply about relation Y?" — the answers become new facts/edges in the trace with reasoner-cited provenance.

Each checkpoint is a decision, not a search: the reasoner returns entailed/consistent or the explaining contradiction, and the trace engine records it as a verdict node. Cost stays bounded because the DL layer is profile-restricted (poly in EL/RL), while the expensive expressive fragment (if ever needed) only runs behind the on-demand gate.
- Concrete fits with the newer-design additions: attribute ownership with owner context maps to DL value restrictions (`Car ⊑ ∃hasVelocity.PhysicalQuantity`); reification-style context on relationships maps to reified n-ary modeling via the ABox (see frames/OWL brief); TBox-level axioms give the `∀`-flavor "every X has property P" statements.

**2. The boundary: DL for structural/typed consistency, SMT/sympy for arithmetic.**
- DL + arithmetic is a well-known dead end in full generality: adding an arithmetic concrete domain to ALC with general TBoxes yields **undecidability** (Lutz's survey; ALC(D) with arithmetic concrete domains); even the mild extension of EL++ with linear constraints makes subsumption **NP-complete** (arXiv 1908.10405). So numeric preconditions (velocity limits, dose thresholds, proportionality checks) must **not** be encoded as DL axioms.
- Conversely, SMT solvers (Z3; SMT-LIB) decide arithmetic/array/UF theories but have no native ontology semantics. Keep the seam explicit: **type/consistency layer = DL reasoner; arithmetic layer = sympy/Z3 called from rule preconditions; statistical layer = LLM-judge with confidence/interval on estimated links** (per newer-additions).
- The hybrid literature supports this seam precisely:
  - **Datalog+/-** (Calì, Gottlob, Lukasiewicz 2012): tuple-generating dependencies unify the tractable DLs (EL, DL-Lite) with Datalog-style rules — one engine for both structural and Horn-rule deduction, poly-time in the guarded/linear/sticky fragments.
  - **ELP / Description Logic Rules** (Krötzsch, Rudolph, Hitzler 2008): Horn rules that are internalizable in OWL 2 while preserving polynomial reasoning — the formal license for "TBox axioms + forward rules in one framework."
  - **Combined approach for DL-Lite** (Lutz, Toman, Wolter 2009; Kontchakov et al.): materialize a canonical model, then answer queries by SQL over that materialization — a proven DL↔database hybrid; the pattern OV's trace engine resembles when it materializes derived nodes.
- Implementation note: Python-side loading/reasoner integration is feasible via libraries such as `owlready2` (loads OWL 2, delegates to HermiT/Pellet-class backends) or an OWL RL forward-chaining engine for the tractable path; sympy/Z3 already in scope.

**Proposed three-layer seam (structural / arithmetic / statistical):**

| Layer | Engine | Owns |
|---|---|---|
| Structural | DL reasoner (ELK for scale, HermiT for expressivity) | TBox axioms, ABox consistency, classification, subsumption closure, attribute ownership via value restrictions |
| Arithmetic | sympy / Z3 (SMT-LIB theories: LIA, LRA, UF) | numeric preconditions, thresholds, algebraic derivations, intervals/confidence unfolding |
| Statistical | LLM-as-judge + confidence/interval | estimated links, chained proportionality/correlation, anything non-monotone |

Hand-off rule: a rule precondition that is purely typed fires on reasoner-entailed facts; one that is purely numeric calls sympy/Z3; one that is both (e.g., "if X is a Car and its velocity exceeds 120 km/h") fires only when both sides succeed — the DL side supplies the typing, the SMT side the arithmetic. Neither engine ever takes the other's job: no arithmetic inside DL axioms (undecidable in general), no ontology semantics inside SMT.

**3. OWA/CWA decision (explicit):** **OWA is the correct default** for the verifier's structural layer. Missing information = `unknown`, matching the Unknown node's semantics; CWA ("missing = false") is only valid on subdomains the user declares complete. The verdict vocabulary should therefore be: **verified** (entailed), **contradicted** (consistency failure), **unverified/unknown** (neither — with why-unknown and resolving evidence on the node). Never emit "false" merely because a fact is absent.

**4. Costs to accept.** TBox engineering discipline (axioms are global `∀`-statements; they apply to every individual, so domain rules must be stated carefully to avoid over-constraining input contexts); reasoner integration and profile selection (EL++/RL keeps worst case poly; full OWL 2 DL is NExpTime-complete); OWA surprises for users who think database-style (must be surfaced in verdict rendering); identity semantics without UNA (two fact nodes may denote the same individual — decide sameAs handling, e.g., via reified identity evidence, rather than assuming distinct ids = distinct individuals).

## Conflicts / flags

- **DAG proof walk ≠ DL reasoning.** The induction/deduction trace is a *proof explanation*; classification/consistency is a *global closure*. Do not merge them: use the reasoner as a consistency gate and a fact generator, keep the trace for explanations. A verbose render-time-filtered trace cannot be produced by a reasoner (they give minimal justifications at best).
- **Rule preconditions are scoped; DL GCIs are universal.** Transformation rules with preconditions apply within a derivation; a TBox GCI applies to every individual in the KB. Encoding OV rules directly as GCIs would over-constrain. Keep two tiers: global TBox axioms (domain grammar) + scoped derivation rules (Horn/ELP-style or Datalog+/- where the tractable unification is wanted).
- **Correlation chains must not become role chains.** DL subsumption is transitive and monotone, so a TBox chain of proportionality would *look* like valid inference — but correlation is not transitive. Keep proportionality/correlation in the statistical pipeline (see path-analysis brief), never as DL role axioms; flagged risk in newer-additions stands.
- **OWA vs user expectation.** Users expect CWA. The UNKNOWN verdict must be rendered distinctly from FALSE everywhere, or the verifier silently turns into a closed-world checker and overclaims failures.
- **No UNA + distinct fact ids.** OV fact nodes have distinct ids by construction; without identity semantics the structural layer cannot know two nodes denote one individual. Needs an explicit sameAs/differentFrom policy in the ABox layer.
- **Profile choice is a product decision, not an implementation detail.** EL vs QL vs RL changes what the domain grammar may express (disjunction, role chains, completeness); switching profiles later is a TBox migration, so the profile should be fixed in the grammar/TBox design phase — see the "which axioms do I need?" rule under Languages.
- **Structural layer is not the whole verifier.** If DL consistency becomes the *only* mechanism, OpenVerifiers regresses to an ontology checker: no arithmetic (see the EL++-with-linear-constraints NP-completeness result), no estimated links, no confidence. The statistical pipeline (Bayesian-net and path-analysis briefs) stays load-bearing for exactly the claims the DL layer must refuse to touch.

## Sources

All URLs were checked live at the time of writing (2026-08-29); book/chapter citations are primary even where a deep link is to the publisher or an institutional page.

- Krötzsch, Simančík, Horrocks — *A Description Logic Primer* (arXiv:1201.4089): https://arxiv.org/abs/1201.4089
- Baader, Calvanese, McGuinness, Nardi, Patel-Schneider (eds.) — *The Description Logic Handbook: Theory, Implementation, and Applications*, Cambridge University Press (2003/2007): https://iccl.inf.tu-dresden.de/web/LATPub263/en
- Schmidt-Schauß, Smolka — *Attributive concept descriptions with complements*, Artificial Intelligence 48 (1991) 1–26 (introduces ALC; PSPACE-completeness): https://en.wikipedia.org/wiki/Description_logic
- Tobies — *The Complexity of Reasoning with Cardinality Restrictions and Nominals in Expressive Description Logics*, JAIR 12 (2000) 199–217: https://jair.org/index.php/jair/article/view/10254
- Tobies — *Complexity Results and Practical Algorithms for Logics in Knowledge Representation*, PhD thesis, Saarland University (2001, arXiv:cs/0106031): https://arxiv.org/abs/cs/0106031
- Baader, Brandt, Lutz — *Pushing the EL Envelope* (IJCAI-05; EL++ tractability): https://iccl.inf.tu-dresden.de/web/LATPub682/en
- W3C — *OWL 2 Web Ontology Language Profiles* (2nd ed.): https://www.w3.org/TR/owl2-profiles/
- W3C — *OWL 2 Web Ontology Language Document Overview*: https://www.w3.org/TR/owl2-overview/
- W3C — *OWL 2 Web Ontology Language Direct Semantics* (semantics; no UNA; model-based): https://www.w3.org/TR/owl2-direct-semantics/
- W3C — *OWL 2 Web Ontology Language New Features and Rationale* (profiles rationale; worst-case complexity): https://www.w3.org/TR/owl2-new-features/
- Shearer, Motik, Horrocks — *Hypertableau Reasoning for Description Logics*, JAIR 36 (2009) 165–228 (HermiT): http://www.cs.ox.ac.uk/boris.motik/pubs/smh08HermiT.pdf
- Horrocks, Motik, Wang — *The HermiT OWL Reasoner* (ORE 2012): https://ceur-ws.org/Vol-858/ore2012_paper13.pdf
- Sirin, Parsia, Grau, Kalyanpur, Katz — *Pellet: A practical OWL-DL reasoner*, J. Web Semantics 5 (2007) 51–53: https://www.sciencedirect.com/science/article/abs/pii/S1570826807000169
- Kazakov, Krötzsch, Simančík — *ELK: A Reasoner for OWL EL Ontologies* (TR, 2012): https://www.uni-ulm.de/fileadmin/website_uni_ulm/iui.inst.090/Publikationen/2012/KazKroSim12ELK_TR.pdf
- Kazakov, Krötzsch, Simančík — *ELK Reasoner: Architecture and Evaluation* (ORE 2012): https://ceur-ws.org/Vol-858/ore2012_paper10.pdf
- Tsarkov, Horrocks — *FaCT++ Description Logic Reasoner: System Description* (IJCAR 2006, LNCS 4130): https://link.springer.com/chapter/10.1007/11814771_26
- Reiter — *On Closed World Data Bases*, in Gallaire & Minker (eds.), Logic and Data Bases, Plenum Press (1978) 55–76: https://en.wikipedia.org/wiki/Closed-world_assumption
- Calì, Gottlob, Lukasiewicz — *A general Datalog-based framework for tractable query answering over ontologies*, J. Web Semantics 14 (2012) 57–83: https://www.sciencedirect.com/science/article/abs/pii/S1570826812000388
- Krötzsch, Rudolph, Hitzler — *Description Logic Rules* (ECAI 2008) / *ELP: Tractable Rules for OWL 2* (Reasoning Web 2008): https://ebooks.iospress.nl/pdf/doi/10.3233/978-1-58603-891-5-80 and https://link.springer.com/chapter/10.1007/978-3-540-88564-1_41
- Lutz, Toman, Wolter — *The Combined Approach to Query Answering in DL-Lite* (KR 2009): https://dl.acm.org/doi/10.5555/3031748.3031782
- Kontchakov, Lutz, Toman, Wolter, Zakharyaschev — *The Combined Approach to Query Answering in DL-Lite* (2010): https://cdn.aaai.org/ocs/1282/1282-7414-1-PB.pdf
- Lutz (et al.) — *Concrete domains in logics: a survey* (survey; arithmetic concrete domains vs decidability): https://hal.science/hal-03313291v1/document
- Baader, et al. — *Extending Description Logic EL++ with Linear Constraints* (2019, arXiv:1908.10405; EL++ + linear arithmetic NP-complete): https://arxiv.org/pdf/1908.10405
- Z3 (SMT solver): https://github.com/Z3Prover/z3 ; SMT-LIB: https://smt-lib.org ; SymPy: https://www.sympy.org ; owlready2 (Python OWL reasoner integration): https://pypi.org/project/owlready2/