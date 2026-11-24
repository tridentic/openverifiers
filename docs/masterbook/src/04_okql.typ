= Component 3: OKQL <ch4>

*Intuition.* OKQL is how a person or an agent asks OV something. Every question gets one of the four verdicts with its trust base, and the question is always about _the proposition asked_: "is it proven?", "find the values", "why?", "why not?", "what if?".

*Where it lives.* {{badge:PARTIAL}} OKQL is not a separate language at this commit: a query is written inside a `.ov` file as `query <OKQL>`, optionally followed by `expect VERDICT [values] [assuming {…}]`, and `ov run` answers it {{src:docs/OKQL.md:1-10}}. The masterplan's standalone query interface (`ov query` against a saved state, `IN scenario`, `USING state`, `UNDER`, options such as `STRICT`, `LIMIT`, `AS json`) is not built {{mp:MP §5.1, v1 scope "OKQL core"}}.

== The grammar

{{badge:IMPLEMENTED}} {{src:src/openverifiers/lang/grammar.lark:78-90}} The implemented grammar, generated from `grammar.lark` (Appendix B has the railroad diagrams and the masterplan's full design):

{{gen:okql_ebnf}}

Every query is routed one of two ways: a _rule query_ (over predicates) becomes a query rule in the scenario's RawOV program and is answered from the checked model; an _object query_ (whose WHERE is a class pattern, or UNIQUE/COUNT/CHECK/COUNTEREXAMPLE) goes to the object engine {{src:src/openverifiers/objects/compile.py:657-662}}.

{{fig:okql}}

== Every implemented form, with a real query

=== PROVE

{{badge:IMPLEMENTED}} `PROVE lit`: PROVEN or REFUTED with a proof and its assumptions; UNKNOWN with the missing premises; INCONSISTENT with the conflict set {{test:tests/v1/test_q11.py::test_q11_reference_answers}}. Examples: q11's `PROVE optically_active(add(C, HCN))` (REFUTED, §1.5) and the gate scenario of §7.6.

=== FIND

{{badge:IMPLEMENTED}} `FIND ?x, ?y [WHERE conj] [LIMIT n]`. For rules, every binding with its own verdict; for scenario unknowns without WHERE, the value if exactly one candidate survives, else UNKNOWN with the candidates. For a class pattern, every solution up to the limit (default 16), each re-checked by the trusted evaluator {{src:docs/OKQL.md:14-31}}. q11's `FIND ?A, ?C, ?D` is a rule FIND; the square's fourth vertex is an object FIND (§7.3).

=== PROVE UNIQUE and COUNT

{{badge:IMPLEMENTED}} `PROVE UNIQUE ?p [WHERE C{…}]`: PROVEN if, after blocking the found solution, no other exists; REFUTED with two witnesses. `COUNT ?p WHERE C{…}`: the exact number of solutions, with a deterministic budget of 4,096 (D-027) {{src:docs/LANGUAGE.md:609-613}}:

{{listing:benchmarks/geometry/parallelogram_count/case.ov}}
{{run:ov run benchmarks/geometry/parallelogram_count/case.ov --verbose}}

The trust base `{kernel, z3_unsat}` says: the three points were re-checked by the kernel, and "there are no others" is z3's unsat, not checked by trusted code. Under `--strict` this becomes UNKNOWN. A uniqueness claim with a certificate reaches `{kernel}` (§7.4).

=== CHECK … IS

{{badge:IMPLEMENTED}} `CHECK T1{…} IS T`: PROVEN, or REFUTED naming each invariant the instance fails {{test:tests/v1/test_objects.py::test_check_is}}:

{{listing:benchmarks/geometry/check_rectangle_not_rhombus/case.ov}}
{{run:ov run benchmarks/geometry/check_rectangle_not_rhombus/case.ov}}

`CHECK x IS T` takes an instance written as a pattern, not a scenario entity {{src:KNOWN_LIMITATIONS.md:63-64}}; the masterplan's `CHECK argument a` (every inference step of an argument) is not built {{mp:v3 Lens, logic.arguments}}.

=== COUNTEREXAMPLE

{{badge:IMPLEMENTED}} `COUNTEREXAMPLE C.theorem` returns _the theorem's verdict_ (D-012): REFUTED with a counterexample the evaluator confirmed, PROVEN if the negation is unsat, UNKNOWN otherwise {{src:docs/OKQL.md:31}}:

{{listing:benchmarks/geometry/false_theorem_rectangle/case.ov}}
{{run:ov run benchmarks/geometry/false_theorem_rectangle/case.ov @@ exit=1}}

=== WHY and WHY NOT

{{badge:IMPLEMENTED}} `WHY lit` is the verdict of `PROVE lit` with its checked derivation, each step with its rule and source line. `WHY NOT lit` says what keeps `lit` from holding: the refutation if REFUTED; if UNKNOWN, the missing facts, each alternative a set of atoms that would make it PROVEN, re-checked against the model to be absent; if it holds after all, its derivation {{src:src/openverifiers/runner.py:352-369}} {{test:tests/v1/test_why.py::test_why_and_why_not}}:

{{listing:tests/v1/why.ov}}
{{run:ov run tests/v1/why.ov}}

=== WHAT IF

{{badge:IMPLEMENTED}} `WHAT IF (RETRACT f | ASSUME a) [AND …] THEN q`. Changing an assumption is a label lookup (context independence, §3.5); retracting a fact re-runs the program without it, unless lowering made that fact a hidden assumption (as for q11's `not tautomerizes(D)`) {{src:src/openverifiers/runner.py:108-113}} {{src:MASTERPLAN.md:503}}. A release plan on the approved `agent.workflow` package (the file declares no package, so it adds no meaning lines):

{{listing:docs/masterbook/examples/whatif.ov}}
{{run:ov run docs/masterbook/examples/whatif.ov}}

Read the answers: the release plan is valid _under_ `signed_off`; retracting that sign-off makes it REFUTED (closed world) and the answer says so with `{not signed_off}`; retracting the deploy step instead makes it valid with no assumption. The last line shows a weakness: `FIND ?i WHERE violation(release, ?i)` has no solution, and `violation` is a closed-world predicate, yet the answer is UNKNOWN(open_world) rather than "no solutions" (Appendix J).

== "Near match": what exists today <near>

The brief asks to check "whether a certain fact or a near match was derived". As of `bd2ed44`:

- *Exact match:* PROVE, WHY and FIND answer whether a fact, or any instance of a pattern, was derived, with the derivation. {{badge:IMPLEMENTED}} {{test:tests/v1/test_why.py::test_why_and_why_not}}
- *What would make it derived:* WHY NOT and UNKNOWN's `missing` list the alternative sets of premises that would make a query PROVEN (a depth-one, untrusted frontier, each atom re-checked absent; D-016 asks for a _verified minimal antichain_, which is v2). {{badge:PARTIAL}} {{src:src/openverifiers/engine.py:63-84}} {{mp:D-016, v2 Engine "the missing-facts antichain with verification"}}
- *Candidates:* an UNKNOWN FIND over scenario unknowns lists the surviving candidates (q11's WHAT IF). {{badge:IMPLEMENTED}} {{src:src/openverifiers/runner.py:186-196}}
- *NEAR claim WITHIN k* and *DEPENDS ON f* are not built. {{badge:PLANNED}} {{mp:MP §5.1 (NEAR, DEPENDS ON, AUDIT); no release assigned}}

*The design the masterplan specifies* (MP §5.1, verbatim):

{{listing:MASTERPLAN.md:186-204}}

`NEAR claim [WITHIN k]` and `DEPENDS ON f` appear only as these grammar heads; the masterplan gives no further semantics. Appendix J notes that `docs/OKQL.md` said they would arrive "in Milestone 4", which has passed without them.

== "A lot of potential": the planned modes <planned-modes>

Each mode below is in the masterplan; none is built. They are described in the future tense.

#table(columns: (1.4fr, 3fr, 1.2fr),
  [*mode*], [*what it will do (MP §5.1, §7)*], [*status*],
  [PROPAGATE [scenario] [DEPTH n]], [list everything that newly follows from a change, each with its cause chain], [{{badge:PLANNED}} {{mp:v2 Engine, MP §7}}],
  [COMPUTE procedure(args)], [run a `procedure` and return its result with a certificate and the certificate's check], [{{badge:PLANNED}} {{mp:v2 Engine, MP §7 procedure + certificates}}],
  [OPTIMIZE x FOR goal], [the optimum with an optimality certificate, or "best found, within X%"], [{{badge:PLANNED}} {{mp:v2 Engine, MP §7}}],
  [PARETO x OVER m1, m2], [the Pareto front of a trade-off], [{{badge:PLANNED}} {{mp:v2 Engine, MP §7}}],
  [WHY NOT option], [why a specific candidate (a routine, a plan) was not chosen], [{{badge:PLANNED}} {{mp:v2 Engine, MP §7}}],
  [WHAT WOULD IT TAKE option], [the minimal changes that would make an option feasible or optimal], [{{badge:PLANNED}} {{mp:v2 Engine, MP §7}}],
  [SENSITIVITY x TO weight w; TRADE a FOR b], [how the answer moves with a weight; the exchange rate between goals], [{{badge:PLANNED}} {{mp:v2 Engine, MP §7}}],
  [PLAN FROM state TO target], [OVProver: a plan, its trace and a gap report (ch. 5)], [{{badge:PLANNED}} {{mp:v2 Engine, MP §7}}],
  [EXPLAIN query [AT LEVEL …] [LANG en|bn]], [the cause chain rendered for people, at student, expert or auditor depth, in English or Bangla], [{{badge:PLANNED}} {{mp:v3 Lens, MP §7}}],
  [AUDIT package], [`ov audit` as a query], [{{badge:PLANNED}} {{mp:MP §5.1}}],
)

The v1 hooks that these modes will build on exist: every trace step carries its source span (EXPLAIN's two-way links), and `openverifiers.paper.blueprints` already emits statement cards, closures and proof roles as JSON (OV-Paper, v3) {{src:src/openverifiers/paper.py:1-25}}:

{{gen:blueprint}}

== The result format

*For people.* {{badge:IMPLEMENTED}} `ov run` prints, per query, the file and line, the query text, then the verdict line: values, `assumptions {…}`, `proof: n steps`, `trust {…}`, and for UNKNOWN the reason, the candidates and `missing:`; `--verbose` adds proof steps with source lines, or the object engine's steps {{src:src/openverifiers/runner.py:265-349}}. The masterplan's format (MP §5.3) is close but not identical: it names a trace reference (`[trace q3#41]`) and a `checked` line for UNKNOWN that the printer does not produce.

*For agents.* {{badge:PARTIAL}} There is no `AS json` for queries. JSON exists where it was needed: `ov audit --json`, `ov exam --json`, `ov bench`'s `results.jsonl`, the MCP gate's replies (§3.11), and the Python objects themselves (`Answer`, `ObjAnswer`) for library callers {{src:src/openverifiers/runner.py:34-60}}. A JSON result for every OKQL mode is planned {{mp:MP §5.3 "JSON output carries the same fields for agents"}}.

== Limitations

- Queries live only inside `.ov` files; no standalone OKQL front end, no queries against a saved state by name.
- An object query's WHERE is exactly one pattern {{src:KNOWN_LIMITATIONS.md:65-66}}.
- FIND on a rule predicate with no solution reports UNKNOWN(open_world) even when the predicate is closed-world (above), and an UNKNOWN FIND does not list missing facts, while PROVE does {{src:KNOWN_LIMITATIONS.md:191-194}}.
- `missing` is a depth-one heuristic, not the verified minimal antichain D-016 asks for.
