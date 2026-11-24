#counter(heading).update(0)
= The big picture <ch1>

== The founding brief <brief>

The book is organised around the founder's original four-component brief. Here it is, verbatim (the build includes it from `docs/masterbook/brief.md`, copied from the CTO directive):

{{listing:docs/masterbook/brief.md::text}}

Component 1 is chapter 2, component 2 is chapter 3, component 3 is chapter 4 and component 4 is chapter 5. The #link(<compliance>)[brief compliance table] in the front matter maps every bullet to its section and status.

== The thesis and the two rules

*Intuition.* As AI makes more decisions, the scarce thing is not intelligence but _justification_: a reason a person or a program can check. OV's bet is that justification can be made cheap by splitting the work: anyone (a person, an LLM, a solver) may _propose_ a conclusion, and a small piece of code that is easy to audit _decides_ whether the proposal is justified by stated axioms and facts.

*Precise statement.* The masterplan states two rules that no release may break:

{{listing:MASTERPLAN.md:11-21}}

MP-INV is enforced in the code by one architectural rule: nothing reaches a caller unless the trusted checker accepted it. For rules, the engine passes the evaluator's trace to the checker as JSON text, and only the checked model answers queries {{src:src/openverifiers/engine.py:1-11}}. For the object layer, every kernel verdict leaves a JSON record that the trusted `checker/objects.py` re-decides; if a record is rejected, the verdict is withdrawn and becomes UNKNOWN {{src:src/openverifiers/runner.py:124-139}}.

MP-DOL (D-023) adds the human side: meaning-carrying lines (definitions, laws, axioms, main statements) need the founder's signed approval, while proof bodies and lemmas do not. That is enforced by the meaning gate (§3.11).

== The four verdicts and the trust levels

Every answer is exactly one of four verdicts {{src:MASTERPLAN.md:25-30}} {{src:src/openverifiers/checker/verdict.py:33-62}}:

#table(columns: (1fr, 3fr),
  [`PROVEN(proof, assumptions, trust_base)`], [the claim follows from the axioms, facts and the listed assumptions],
  [`REFUTED(proof, assumptions, trust_base)`], [its negation follows (or, for a closed-world predicate with a complete stratum, it is not derivable)],
  [`UNKNOWN(missing, reason)`], [neither; `reason` is one of `missing_facts`, `budget`, `plugin_unknown`, `open_world` {{src:src/openverifiers/checker/verdict.py:31}}],
  [`INCONSISTENT(conflict_set)`], [the stated facts and assumptions contradict each other; the conflict set names them],
)

*Trust levels.* D-007 records "three trust levels" {{src:MASTERPLAN.md:510}}, but no document in the repository defines them. What the code implements are three levels of what an _answer_ rests on, printed with every verdict:

+ `{kernel}`: trusted code checked everything (a rule trace, a re-checked model or a certificate). This is the only level `--strict` keeps. {{badge:IMPLEMENTED}} {{src:src/openverifiers/runner.py:47-50}}
+ solver-trusted: the trust base names `z3_unsat` (an unsat answer only z3 vouches for) and the `red:*` reductions it was computed under. `--strict` turns these into UNKNOWN(plugin_unknown). {{badge:IMPLEMENTED}} {{src:docs/SEMANTICS.md:186-202}}
+ provisional: the answer used a draft package from `drafts/` (loaded only with `--drafts`, never with `--strict`), and is printed as PROVISIONAL. {{badge:IMPLEMENTED}} {{src:src/openverifiers/runner.py:69-73}}

A second, independent ladder applies to _content_ (MP §4.1): an `axiom` is trusted, a `law` is trusted as a claim and counted in the claim ratio, a `definition` adds no trust, and a `theorem` is never trusted until proven {{src:MASTERPLAN.md:101-116}}. Appendix J records that "three trust levels" is undefined.

*Open world by default* (D-007): a predicate is open unless declared `world closed`; for an open predicate, "not derived" means UNKNOWN, never false {{src:docs/SEMANTICS.md:37-42}}.

== The ten-layer architecture

The masterplan's stack (MP §3) puts a small trusted core at the bottom and ambition at the top. @fig-layers shows each layer with the status this book finds for it.

{{fig:layers}}

#table(columns: (0.4fr, 1.2fr, 0.8fr, 3.6fr),
  [*layer*], [*name*], [*status*], [*what exists at bd2ed44 (modules), and what does not*],
  [L0], [Exact arithmetic], [{{badge:IMPLEMENTED}}], [`fractions.Fraction` everywhere; surds `raw/surd.py`; rigorous intervals `raw/interval.py`; $QQ(pi)$ `raw/qpi.py`; polynomial normal forms in `raw/certificate.py` {{src:scripts/tcb_size.py:26-29}}],
  [L1], [Kernel checker], [{{badge:IMPLEMENTED}}], [RawOV model `raw/program.py`, trace checker `checker/check.py`, certificate checker `raw/certificate.py`, records checker `checker/objects.py`, state hash/load `state/` {{src:scripts/tcb_size.py:19}}],
  [L2], [Evaluator], [{{badge:PARTIAL}}], [semi-naive Datalog with signed ATMS labels, stratified negation and deterministic budgets {{src:src/openverifiers/kernel/evaluate.py:51-57}}; semirings and incremental re-evaluation are not built {{mp:v2 Engine, MP §7 incremental evaluation}}],
  [L3], [Solvers and procedures], [{{badge:PARTIAL}}], [z3, a sympy certificate finder and a small-scope search in `objects/` {{src:src/openverifiers/objects/smallscope.py}}; optimizers, `procedure` and FFI are not built {{mp:v2 Engine, MP §7 procedure + certificates + FFI}}],
  [L4], [Lowering], [{{badge:IMPLEMENTED}}], [`lang/check.py` (names, types, units), `lower/lower.py`, `objects/compile.py` {{src:src/openverifiers/lower/lower.py}}],
  [L5], [Languages], [{{badge:PARTIAL}}], [OV and an OKQL subset embedded in `.ov` files {{src:src/openverifiers/lang/grammar.lark}}; OV-Prose is not built {{mp:v3 Lens, MP §7}}],
  [L6], [Knowledge], [{{badge:PARTIAL}}], [15 package files in `packages/`, drafts, OVState export and import {{src:src/openverifiers/state/load.py}}; theory mappings, adapters and a registry are not built {{mp:v4 Atlas, MP §7}}],
  [L7], [Modes], [{{badge:PARTIAL}}], [CHECK, FIND, UNIQUE, COUNT, WHY, WHY NOT, WHAT IF, COUNTEREXAMPLE {{src:src/openverifiers/lang/grammar.lark:78-87}}; PROPAGATE, COMPUTE, OPTIMIZE, PLAN, EXPLAIN are not {{mp:v2 Engine and v3 Lens, MP §7}}],
  [L8], [Interfaces], [{{badge:PARTIAL}}], [`ov` CLI, `ov gate` (CLI, pre-commit, GitHub Action), MCP tool-call gate {{src:src/openverifiers/gate.py:1-17}}; documented SDK, LSP, trace viewer and REST server are not built {{mp:v3 Lens and v5 Sentinel, MP §7}}],
  [L9], [Applications], [{{badge:PARTIAL}}], [exams (JEE Advanced 2025), agent guardrails (`agent.workflow`) {{src:src/openverifiers/packages/agent/workflow.ov}}; the NDC planner, LifeOS and enterprise policy are not built {{mp:v2 Engine and v5 Sentinel, MP §7}}],
)

Three rules hold the stack together (MP §3): proposers cannot write truth; every verdict names its trust base; every low-level step links back to the OV line that caused it {{src:MASTERPLAN.md:89-93}}. The third holds for rules (every RawOV item and every trace step carries a source span) and partly for the object layer (records name the class and invariant, not a span).

The pipeline that connects the layers:

{{fig:pipeline}}

And the trust boundary, drawn from the file lists in `scripts/tcb_size.py`:

{{fig:trust}}

== One end-to-end walkthrough: q11

We follow the organic-chemistry problem q11 (JEE-style; the first program the project ever ran end to end, {{commit:1f9c42b}}) from source to verdicts to a saved state. @fig-walkthrough summarises the artefacts.

{{fig:walkthrough}}

*1. The source.* Two isomers of C#sub[5]H#sub[10], called A and B, are unknown. A gives C and D on ozonolysis; D does not tautomerize; C's Grignard alcohol is tertiary; 2-chloropentane is a product of B with HCl. The scenario states exactly those givens and four queries:

{{listing:examples/chem/q11.ov}}

*2. RawOV.* The front end checks names, types and units, then lowers the scenario. The unknowns become _candidate relations_ (every combination the generator and arrows allow), each other statement becomes an _elimination_ rule, and a value is defined only when exactly one candidate survives. These are the RawOV items whose source span lies in `q11.ov` (the 77 rules of `chem.organic` are not shown):

{{gen:rawov_q11}}

Note two details. `fact not tautomerizes(D)` became a rule guarded by `'ov.assumption'('fact#q11.L6C3')`: a _hidden_ assumption, so that retracting this fact later is a label lookup instead of a re-run (D-014). And `2-chloropentane in add(B, HCl)` became a closed-world `not member(...)` with the product's structure spelled out as a term.

*3. Evaluation and the trace.* The semi-naive evaluator (untrusted) computes the model and writes every derivation as a JSON line: rule, substitution, premises, label, stratum and source span. Here are the header and two steps of the real trace file this build wrote:

{{gen:trace_excerpt}}

*4. The checker.* `checker/check.py` re-reads the program and the trace from JSON and accepts it only if every step is locally justified, negation references are final, and each complete stratum is closed (§3.6). If it rejects the trace, no answer is printed at all.

*5. The verdicts.* `ov run` prints one verdict per query, with its assumptions and trust base; `--verbose` adds the proof steps with their source lines:

{{run:ov run examples/chem/q11.ov --verbose}}

Read the four answers in plain language:

- A is 2-methylbut-1-ene, C butanone, D methanal: exactly one candidate survives every elimination, with no assumption.
- The anti-Markovnikov (peroxide) product of B with HBr is 1-bromopentane, but only under the stated assumption `single_major`; the answer's `assumptions {single_major}` says so.
- Adding HCN to butanone makes a stereocentre, but the product is racemic, so it is _not_ optically active: REFUTED, with a 27-step proof.
- WHAT IF the "D does not tautomerize" fact is retracted? Two candidates for A survive, so the answer is UNKNOWN and lists both.

*6. OVState.* The checked model's unconditional atoms can be saved, hashed and imported elsewhere:

{{run:ov state examples/chem/q11.ov --scenario q11 --out docs/masterbook/build/work/q11.json}}

Only atoms whose label contains the empty environment are written (217 here), so the state does not contain `1-bromopentane` (it rests on `single_major`). §3.9 shows an import.

*7. OKQL and WHAT IF.* The queries above are OKQL embedded in the file. The WHAT IF query was answered by re-running the program with the hidden assumption turned off in the context; the result lists the two surviving candidates. §4 covers every query form.

*Status of the walkthrough.* {{badge:IMPLEMENTED}} The whole chain runs in the build {{test:tests/v1/test_q11.py::test_q11_reference_answers}}. Two links are thinner than the brief imagines: no command writes the trace file (the book wrote it through the library), and the OVState cannot be queried directly by name (§4.3).
