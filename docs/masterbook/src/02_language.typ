= Component 1: the OV language <ch2>

== Design goals

*Intuition.* OV has to be writable by a physics teacher, an agent, and a compliance officer, and its every sentence has to turn into something a tiny checker can verify. So the language is deliberately small and regular: every statement starts with a keyword, there is one grammar for every domain, and domains differ only in their packages.

*The rules the masterplan sets* (MP §4.2 and §8 Generality) {{src:MASTERPLAN.md:152-159}}:

- keywords lead every statement, so newlines carry no meaning;
- every quantity has a unit; names are `snake_case`, types `PascalCase`; comments start with `#`;
- every invariant has a `because:`. {{badge:PLANNED}} This one is _not_ in the grammar: `invariant NAME ":" fbody` has no `because` clause, and no file in the repository uses one {{src:src/openverifiers/lang/grammar.lark:49-58}} {{mp:MP §4.2, §8 Faithfulness, D-020}}. Appendix J records the gap;
- a new language feature needs three domains using the same syntax, or it belongs in a package {{src:MASTERPLAN.md:439}}.

== Lexical structure

{{badge:IMPLEMENTED}} The tokens are defined at the bottom of `grammar.lark` {{src:src/openverifiers/lang/grammar.lark:134-154}}:

- *Names* are letters, digits and `_`, and may contain inner hyphens so that chemical names are single tokens: `pent-1-ene`, `2-chloropentane`, `1,1-dimethylcyclopropane`. A hyphen joins a part with a letter in it, or digits followed by another hyphen; so `a-b` is one name and `i-1` is `i - 1`.
- *Quantities* are a number optionally followed _on the same line_ by a unit expression: `10 N`, `2 m/s^2`, `0.5 kg`. The unit alternatives are spliced into the token's regular expression from `lang/units.py` at load time (`@UNIT@`). Numbers are exact rationals; `0.1` is $1 slash 10$.
- *Query variables* are `?x`; *strings* are `"..."`; *comments* run from `#` to the end of the line.

{{listing:src/openverifiers/lang/grammar.lark:134-154}}

The trap this creates, and the error that catches it: in a class body, `p > 0 t > 0` reads `0 t` as zero tonnes, because `t` is a unit. The compiler reports E304 and suggests writing `(0) t` or separating the conditions {{test:tests/v1/test_diagnostics.py::test_unit_property_clash_is_an_error_with_a_fix}}.

== The grammar

{{badge:IMPLEMENTED}} The grammar is a Lark LALR(1) grammar {{src:src/openverifiers/lang/grammar.lark}}. The EBNF below is generated from it by the build (rule `?x` marks an inlined rule in Lark; aliases `-> name` are dropped), so it cannot drift from the parser. The full grammar file is Appendix A.

{{gen:ebnf}}

`docs/LANGUAGE.md` also carries an EBNF; it is hand-written and has drifted (it lacks `law`, `definition`, `lemma`, `WHY`, `WHY NOT` and quoted unit types; Appendix J).

The railroad diagrams read left to right: yellow boxes are keywords, white boxes rules, blue boxes tokens; a dashed edge skips an optional part, a grey back edge repeats.

{{fig:rail_decls}}
{{fig:rail_brief}}
{{fig:rail_scenario}}
{{fig:rail_objects}}
{{fig:rail_okql}}
{{fig:rail_expr}}

There are five shift/reduce conflicts, all inside class bodies, and each is resolved as _shift_; a test pins the number {{src:docs/LANGUAGE.md:74-85}} {{test:tests/v1/test_objects.py::test_grammar_conflicts_are_the_documented_ones}}.

== Packages and imports <packages>

*Intuition.* A package is a file of knowledge that other files import, like a Python module: `import physics.mechanics` loads Newton's second law and the constant-acceleration class, and nothing else.

*Precise definition.* {{badge:IMPLEMENTED}} A file may start with `package name @version`; every `import dotted.name` is resolved to the file `dotted/name.ov`, first next to the importing file, then in the standard library `src/openverifiers/packages/`, and with `--drafts` also in `drafts/packages/` {{src:src/openverifiers/lang/check.py:236-256}} {{src:src/openverifiers/lang/check.py:29-32}}. The found file must declare that package name, or the import is E203. Imports are transitive; every loaded package shares one global namespace {{src:KNOWN_LIMITATIONS.md:80-84}}.

*What is not there.* {{badge:PARTIAL}} `import physics` (an umbrella for all of physics) is E203: there is no `physics.ov`. The `@version` of a package is parsed and recorded, but an import cannot name a version (`import physics.mechanics @2.0` is a syntax error E101) and nothing checks compatibility. Qualified names (`chem.organic.add`) are not supported; two packages declaring the same name clash with E202 {{src:KNOWN_LIMITATIONS.md:80-84}}. A versioned registry is planned {{mp:v4 Atlas, MP §7 package registry}}.

*The standard library at this commit* (generated from the package files):

{{gen:packages}}

{{fig:tower}}

*How packages are written like code.* A package is plain text under version control. It has tests inside it (`test name { scenario …; query …; expect … }`) that `ov run` and pytest execute; its theorems are re-proved every time the file is checked; `ov audit` reports what it rests on. Here is the audit of `physics.mechanics`:

{{run:ov audit physics.mechanics}}

*Governance: axioms, laws, definitions, theorems, lemmas* (D-017, D-025). {{badge:IMPLEMENTED}} The keyword says what kind of assumption a statement is; all kinds lower the same way, and the kind is what `ov audit` counts {{src:src/openverifiers/lang/grammar.lark:22-27}}:

#table(columns: (1fr, 1fr, 3fr),
  [*keyword*], [*kind*], [*governance*],
  [`axiom`], [foundation], [a meaning line: needs the founder's signed approval in `packages/`],
  [`law`], [empirical law], [a meaning line; counted in the claim ratio],
  [`definition`, `invariant`], [definition], [a meaning line; `ov audit` reports whether it is conservative (`p = E` defining one property) or, under the strict reading, an axiom],
  [`theorem`], [claim], [must be PROVEN; a meaning line (its statement is meaning, its proof is not)],
  [`lemma`], [helper claim], [must be PROVEN; free of the meaning gate (MP-DOL); may be used only inside its own package],
)

The meaning gate (`bench/gold_gate.py`) flags any added, changed or removed line that starts with `axiom`, `law`, `definition`, `invariant` or `theorem` in `packages/**/*.ov`, `laws/**`, or any other `.ov` file that declares a `package` outside `drafts/`, `benchmarks/**/case.ov` and `tests/` {{src:src/openverifiers/bench/gold_gate.py:69-81}}. Such a commit needs a `Meaning-Approved-By` trailer on a commit signed by the founder's key (D-032, §3.11).

*Why E407 exists.* A lemma is exempt from the meaning gate, so nothing outside its package may depend on it: a query that names one (`COUNTEREXAMPLE C.lemma`) is error E407, and a lemma is reused only by proofs in its own package {{src:src/openverifiers/objects/compile.py:670-676}} {{test:tests/v1/test_lemma_scope.py::test_a_query_may_not_name_a_lemma}}. Anything a scenario, a query or another package relies on must be a `theorem`, which the gate sees.

*`drafts/`* (D-025). {{badge:IMPLEMENTED}} Unapproved libraries live in `drafts/packages/`. They load only with `--drafts`, never with `--strict`, every result that uses one is printed PROVISIONAL, and they never count in headline numbers {{src:src/openverifiers/runner.py:69-73}} {{src:MASTERPLAN.md:492}}. At this commit `drafts/` holds `physics.rotation` and the example policy `repo_policy` (above).

== Scenarios

*Intuition.* A scenario is one situation: the packages it uses, the things in it, what is known and what is merely assumed.

*Definition.* {{badge:IMPLEMENTED}} `scenario s uses p1, p2 extends t { stmt* }` where a statement is `entity`, `fact`, `assume`, `generator … from`, `query`, `expect` or `tolerance` {{src:src/openverifiers/lang/grammar.lark:35-41}}. Each scenario lowers to one RawOV program: the used packages' axioms plus the scenario's items.

- `entity a, b: T` declares constants; `entity a: T = expr` names a structure.
- `fact lit` states a fact with origin `fact:s`; `confidence x` and `source "…"` are metadata and never change a verdict (MP pushback 6) {{src:docs/SEMANTICS.md:113}}.
- `assume name: lit` states a _named_ hypothesis with origin `assume:name`; every conclusion that uses it carries `name` in its label (§3.5), so `WHAT IF RETRACT` and `UNDER` style questions are label lookups.
- `extends t` inherits every statement of scenario `t`.

Here is a real file that uses `uses`, `extends`, a transformation and a controller; it is the scenario of {{test:tests/v1/test_lang.py::test_scenario_extends_and_controller_guard}} copied into `docs/masterbook/examples/kitchen.ov`:

{{listing:docs/masterbook/examples/kitchen.ov}}
{{run:ov run docs/masterbook/examples/kitchen.ov --verbose}}

`cooked(egg)` is PROVEN because `more` inherits `raw(egg)` from `base`, states `allowed(egg)`, and the controller lets `cook` fire only with its guard. `cooked(ham)` is UNKNOWN, and the answer names what is missing: `allowed(ham)`.

*Facts that are not atoms become checks.* {{badge:IMPLEMENTED}} `fact c.mass > 3 kg` cannot be stored as a fact; it lowers to a rule that derives `neg ov.consistent(id)` whenever its contradiction is derived, so a violated check makes the scenario INCONSISTENT. Functional fields clash: two different derived values of `c.mass` derive `neg Body.mass(c, v2)` {{src:docs/LANGUAGE.md:296-310}}:

{{listing:docs/masterbook/examples/checks.ov}}
{{run:ov run docs/masterbook/examples/checks.ov}}

== The brief's core types: Fact, Transformation, Controller, Generator <coretypes>

The brief names four core types. This section gives, for each, its exact syntax, its meaning, its lowering and its status, and says plainly where the implementation differs from the brief.

=== Fact

- *Syntax:* `fact lit [confidence n] [source "s"]` in a scenario; in a package, a ground `axiom n: p(a)` is also a fact {{src:src/openverifiers/lang/grammar.lark:37}}.
- *Semantics:* a ground atom with origin `fact:<scenario>`, label `{∅}` (true in every context). `fact x.f = unknown` states nothing: the explicit "do not guess" {{src:docs/LANGUAGE.md:236-237}}.
- *Lowering:* an atom-like fact (`p(a)`, `not p(a)`, `x.f = v`, `a in s`) becomes a RawOV fact; anything else becomes a check rule (above); `f(x) -> {C, D}` introduces unknowns (§2.6.4).
- *Status:* {{badge:IMPLEMENTED}} {{test:tests/v1/test_lang.py::test_conflicting_values_are_inconsistent}}. Domain-specific _types_ of facts are written as typed predicates (`predicate net_force(b: Body, F: Force)`); there is no separate "fact type" for rule facts (the object layer's `fact type` is a class, §2.7).

=== Transformation

- *Syntax:* `transformation n(params) requires conj ensures conj` {{src:src/openverifiers/lang/grammar.lark:28}}.
- *Semantics:* a reusable step: if the premises hold, the conclusions hold. MP §4.1 describes it as "reusable `f(facts) -> facts` with `requires`/`ensures`, lowered to rules" {{src:MASTERPLAN.md:109}}.
- *Lowering:* exactly like an axiom (one rule per conclusion), unless a controller lists it (next). The kitchen lowering in §2.9 shows the real rules.
- *Status:* {{badge:IMPLEMENTED}} as a rule schema {{test:tests/v1/test_lang.py::test_scenario_extends_and_controller_guard}}. No package in `packages/` uses `transformation`; every library rule is written as `axiom`, `law` or `definition`. A transformation is not a first-class value (it cannot be passed, composed or named in a query).

=== Controller

- *Syntax:* `controller n(params) { pipe a -> b; branch a | b; guard conj }` {{src:src/openverifiers/lang/grammar.lark:29-32}}.
- *Semantics as built:* only `guard` has meaning: each transformation a controller lists fires only with the controller's guards as extra premises. `pipe` and `branch` are checked for unknown names and otherwise ignored, because a Datalog fixpoint does not depend on rule order {{src:KNOWN_LIMITATIONS.md:89-92}}. The masterplan's description ("orders rules, never adds truths") is therefore half true: it never adds truths, and it does not order anything.
- *Status:* {{badge:PARTIAL}} guards work; ordering and branching semantics are not designed {{mp:MP §4.1 controller (no release assigned)}}.
- *Generator in the brief's "Controller/Generator":* the brief pairs them; in OV they are separate constructs.

=== Generator

*Intuition.* Some unknowns are "one of a finite list": an isomer of C#sub[5]H#sub[10], an ordering of four points. A generator names that list so the kernel can try every member and eliminate the impossible ones.

- *Rule-layer syntax:* declare `generator g(x: T) yields U from p(x)`, where `p` is a _closed_ set-valued predicate, then use `generator A, B from g(args)` in a scenario {{src:src/openverifiers/lang/grammar.lark:33-34}} {{src:src/openverifiers/packages/chem/organic.ov:67}}. A generator over an open predicate is E404: the candidate list must be complete for elimination to be sound.
- *Semantics:* the unknowns linked by statements form a component; the component gets a candidate relation; each statement eliminates the candidates whose contradiction is _derived_; a value is PROVEN only when exactly one candidate survives and the generator is complete {{src:docs/LANGUAGE.md:259-280}}.
- *Object-layer generators:* `cycles(s)`, `orderings(s)`, `subsets(s, k)`, `pairs(s)` turn a set into the orderings or subsets a quantifier ranges over (§2.7) {{src:src/openverifiers/raw/formula.py:218-231}}.
- *Status:* {{badge:IMPLEMENTED}} {{test:tests/v1/test_q11.py::test_q11_reference_answers}}. The C#sub[5]H#sub[10] list itself is written out in `chem.organic`, not generated from the formula {{src:KNOWN_LIMITATIONS.md:122-125}}.

{{fig:lower_q11}}

== The object layer: concept classes <objects>

*Intuition.* Rules are good at chains of facts; they are bad at "a square is four points with equal sides and right angles". The object layer lets you define such a concept by its _invariants_ and then ask: is this an instance? find the missing vertex; is it unique? does this theorem hold for every instance?

*Definition.* {{badge:IMPLEMENTED}} A `fact type C extends P1, P2 { member* }` is a class whose instances are the property values that satisfy every invariant of C and of its ancestors {{src:src/openverifiers/lang/grammar.lark:49-71}}. Members:

#table(columns: (1.3fr, 3fr, 0.9fr),
  [*member*], [*meaning*], [*status*],
  [`property p: T`], [typed property: a quantity type, a record (`Point`), `Set<T>`, `List<T>`, another class (composition), or a quoted unit `"W/m^2/K^4"`], [{{badge:IMPLEMENTED}} {{test:tests/v1/test_objects.py::test_square_brief_example}}],
  [`invariant n: body`], [part of the definition; trusted], [{{badge:IMPLEMENTED}} {{src:src/openverifiers/objects/compile.py:217-276}}],
  [`law n: body`], [an empirical law holding on the class (`law newton2: F = m * a`)], [{{badge:IMPLEMENTED}} {{src:src/openverifiers/packages/physics/mechanics.ov:51}}],
  [`theorem n: body`], [a claim, proved from the invariants and laws when the file is checked: PROVEN, REFUTED with a counterexample, or UNPROVEN], [{{badge:IMPLEMENTED}} {{src:src/openverifiers/objects/engine.py}}],
  [`lemma n: body`], [a theorem that serves only its own package (E407 elsewhere)], [{{badge:IMPLEMENTED}} {{test:tests/v1/test_lemma_scope.py::test_a_query_may_not_name_a_lemma}}],
  [`derived n: T = e`], [parsed, then rejected with E207], [{{badge:PLANNED}} {{src:src/openverifiers/objects/compile.py:229-232}} {{mp:MP §4.1 type construct (no release assigned)}}],
  [`invariant … because: "…"`], [not in the grammar (above)], [{{badge:PLANNED}} {{mp:D-020, MP §8 Faithfulness}}],
)

*Bodies.* A body is a conjunction of conditions written one after another; `P -> Q` is an implication; `exists v in C: …`, `none v in C: …` and `all v in C: …` range over a collection and run to the end of the body; `all i: chain` ranges over the indices of the list the chain indexes with `i`, and indices wrap around ($v_(n) = v_0$). There is no `or` inside class bodies {{src:KNOWN_LIMITATIONS.md:69-70}}.

*Inheritance and the diamond rule.* {{badge:IMPLEMENTED}} `extends` may name several parents. The class's invariant list is its linearised ancestors' invariants first, each shared ancestor's _once_, then its own {{src:src/openverifiers/objects/compile.py:204-215}}. `Square extends Rectangle, Rhombus` therefore has `Quadrilateral.four` and `Parallelogram.bisect` once each. A class that inherits from itself is E406.

{{fig:lower_classes}}

*Collections and instance patterns.* A pattern `T{field = value, …}` is a partial instance: `?x` and unspecified fields are unknowns. A set with unknown elements is split into cases by which elements coincide, so `{(3,1), ?p}` has one element when `?p = (3,1)` {{src:docs/LANGUAGE.md:373-376}}. Tuples `(3, 1)` are record values in field order.

*Composition.* A property may be typed by another class; its invariants are added to the owner as `Comp.inv@Owner.prop`, and `ov audit` counts them under the component {{src:docs/LANGUAGE.md:475-490}}. JEE phys p2q9 (§7.4) uses this: a `ChargedConductingSphere` has a `SpinningChargedShell` and a `SpinningSolidSphere`.

*A warning that exists because of the brief.* W202 warns when a theorem says `exists` over the same generator as an invariant: it may pick an ordering that pairs up sides and hold vacuously. The brief's own `Square.diagonals_equal` did exactly this; `examples/geometry/square.ov` rewrites it as "every ordering with the square's shape has equal diagonals" {{src:examples/geometry/square.ov:15-22}}.

== Native mathematics <math>

*What is native and what is a package.* Arithmetic, comparison, units, exact numbers, distances and angles, polynomial calculus, `exp`, `ln`, `sqrt`, `pi`, `sum`, `mod`, `value_at` and the set generators are built in; `ov audit` lists them as _foundations_ {{src:src/openverifiers/audit.py:44-70}}. The `math.*` packages hold vocabulary and theorems on top: `math.core` (shared vocabulary only), `math.geometry` (triangles, quadrilaterals, circles, sections, with proven theorems), `math.calculus`, `math.vectors` and `math.vector_products` {{src:src/openverifiers/packages/math/core.ov}}. Topology and the rest of mathematics are not started.

=== Equations and inequalities

{{badge:IMPLEMENTED}} In a rule, `=` is an equation, not an assignment {{test:tests/v1/test_lang.py::test_equation_solves_every_direction}}:

- in a premise it binds the one unknown variable (solving when needed) or compares;
- in a conclusion, _every slot_ that occurs once under $+ - times div$ and unary minus gets its own rule solving for it {{src:src/openverifiers/lower/lower.py:462-491}} {{src:src/openverifiers/lower/lower.py:665-714}}.

Formally, for a conclusion $L = R$ and a slot $x$ occurring once, `_solve` inverts the path from the root to $x$: $a + x = r ==> x = r - a$, $a x = r ==> x = r slash a$ (with a side condition $a != 0$ checked by the builtin), and so on. `newton2` ($F = m a$) therefore yields one rule for `mass` and one for `accel` (§2.9). A nonlinear conclusion (`b.v ^ 2 = 4`) is E402 at the rule layer; in classes, nonlinear constraints are handled by the object layer's solvers and checker. {{badge:PARTIAL}} Systems of equations at the rule layer are not solved: `x + y = 10, x - y = 4` is UNKNOWN, one of the two benchmark mismatches {{src:KNOWN_LIMITATIONS.md:198-200}}.

=== Units and dimension vectors

{{badge:IMPLEMENTED}} A dimension is a vector of rational exponents over the base dimensions
$ cal(B) = ("kg", "m", "s", "A", "K", "mol", "cd", "USD", "deg") $
{{src:src/openverifiers/lang/units.py:15}}. Write $[q] in QQ^(cal(B))$ for the dimension of a quantity $q$. A unit $u$ is a pair $(f_u, d_u)$ of a rational factor to base units and a dimension; `2 m/s^2` is parsed as $f = 1 dot 1^(-2)$, $d = e_"m" - 2 e_"s"$ {{src:src/openverifiers/lang/units.py:69-88}}. The algebra is the one physicists use, written out:

$ [a b] = [a] + [b], quad [a slash b] = [a] - [b], quad [a^k] = k [a] quad (k in QQ "constant"), $
$ a + b, quad a - b, quad a = b, quad a < b quad "are well-typed only if" [a] = [b], $

and a violation is E301 (`cannot add Mass and Length`). Quantities are stored in base units, so `500 g` and `0.5 kg` are the same RawOV term $(1 slash 2, e_"kg")$; the RawOV text prints the dimension vector after the number (`1/2{kg^1}`). Angles are their own dimension counted in degrees, so that special angles stay exact; a radian has no unit {{src:src/openverifiers/lang/units.py:45-47}}. Quantity types (`Mass`, `Force`, `Molarity`, …) are names for dimension vectors {{src:src/openverifiers/lang/units.py:51-63}}. User-declared units are not supported {{src:KNOWN_LIMITATIONS.md:93-94}}.

{{lower:units}}

=== Exact numbers

- *Rationals.* {{badge:IMPLEMENTED}} Every number is a `fractions.Fraction`; there is no floating point anywhere in the trusted path {{src:docs/LANGUAGE.md:205-206}}.
- *Quadratic surds.* {{badge:IMPLEMENTED}} `dist`, `sqrt(x)` for rational $x$, and degree-2 solver answers are elements of $QQ(sqrt(k_1), sqrt(k_2), …)$, stored as $sum_i q_i sqrt(k_i)$ with $k_i$ squarefree. Equality is exact because distinct squarefree roots are linearly independent over $QQ$; the sign of a surd is found by tightening rational bounds until they exclude 0 {{src:src/openverifiers/raw/surd.py}}. Nested roots such as $sqrt(2 + sqrt(3))$ are compared only, by their square.
- *$QQ(pi)$.* {{badge:IMPLEMENTED}} Values of the form $p(pi) slash q(pi)$ with rational polynomials $p, q$ are exact; their sign is decided by a rigorous enclosure of $pi$, and an enclosure that does not decide is a refusal, never a guess (§3.8, @fig-qpi) {{src:src/openverifiers/raw/qpi.py:54-99}}.
- *Rigorous intervals.* {{badge:IMPLEMENTED}} `raw/interval.py` encloses `exp`, `ln`, `sqrt` and `pi` by Taylor series with explicit remainder bounds and outward rounding to rationals {{src:src/openverifiers/raw/interval.py:82-165}}. A FIND that the exact solver cannot settle is answered in _numeric mode_: `PROVEN ?N = 606.5306597 (± 1.8e-56)` means the true value lies in that interval.
- *`tolerance x`* {{badge:IMPLEMENTED}} bounds that relative half-width (default $10^(-12)$); a wider enclosure is UNKNOWN(precision) {{src:docs/LANGUAGE.md:532-534}}. (`KNOWN_LIMITATIONS.md` still says `tolerance` is rejected with E207; Appendix J.)
- *Integers and `mod`.* {{badge:IMPLEMENTED}} `property n: Integer` adds the invariant `Integer.whole@C.n`; `mod(a, b) = a - b floor(a slash b)` (D-027) {{src:docs/LANGUAGE.md:602-615}}.

=== Calculus and the exp/ln ring

{{badge:IMPLEMENTED}} `integral(e, t)` is $integral_0^t e dif t$ and `deriv(e, t)` is $dif e slash dif t$ at the value of property `t`. For polynomials in $t$ the trusted evaluator decides both exactly: it samples $e$ at $t = 0, …, deg e$, recovers the coefficients, and integrates or differentiates {{src:src/openverifiers/raw/formula.py:204-216}}. In certificates the trusted normal form is a ring of polynomials in the properties and in _atoms_ for `exp(u)`, `ln(u)`, `inv(u)`, $sqrt(k)$ and $pi$, with these derivation rules (D-026, D-030) {{src:src/openverifiers/raw/certificate.py:65-160}}:

$ (dif) / (dif t) e^u = u' e^u, quad (dif) / (dif t) ln u = u' dot "inv"(u), quad (dif) / (dif t) "inv"(u) = -u' dot "inv"(u)^2, $

where `a / u` is $a dot "inv"(u)$, and $u dot "inv"(u) = 1$ may be used only with a checked witness $u = c h_1 dots.c h_k e^(dots.c) > 0$ ($c > 0$ checked, each $h_i$ a stated positive hypothesis). @fig-exp_rules draws the rules.

{{fig:exp_rules}}

Integrating `exp`, `ln` or `sqrt` _of the variable_ is refused, as is differentiating `sqrt` of the variable: treating them as constants would be unsound {{src:docs/LANGUAGE.md:517-520}}. A closed-form ODE solution is _verified_, not found: two theorems state $y' = F(t, y)$ and $y(t_0) = y_0$ (`value_at`) (D-027) {{src:docs/LANGUAGE.md:626-630}}. Solving ODEs is planned {{mp:v6 Frontier, MP §7}}.

=== Trigonometry

{{badge:PARTIAL}} An `Angle` is the pair $(cos theta, sin theta)$ with the foundation invariant $cos^2 theta + sin^2 theta = 1$; it is exact at 0, 30, 45, 60, 90, 120, 135, 150 and 180 degrees, or from given values (`Angle{ cos = 4/5, sin = 3/5 }`) {{src:docs/LANGUAGE.md:502-508}}. Any other literal angle is E405. sin and cos _of a variable_, with $dif S_u = u' C_u$, $dif C_u = -u' S_u$ and $S_u^2 + C_u^2 = 1$ in the normal form, are decision D-033, recorded in the founder's packet-3 reply and being built on `v1` after `bd2ed44` {{report:reports/APPROVAL_RECORD_2026-11-23_packet3.md}}; they are not in this commit. Inverse trigonometry is v2 {{mp:D-027, v2}}.

=== Sums and induction

{{badge:IMPLEMENTED}} `sum(E, i, n)` sums over $i = 1..n$; for a whole $n$ up to 10,000 the evaluator sums directly. A closed form $sum_(i=1)^n E(i) = F(n)$ is proved for every natural $n$ by an induction certificate: the checker verifies $F(0) = 0$ and $F(n) - F(n-1) = E(n)$ by exact normal form {{src:src/openverifiers/raw/certificate.py:228-243}} {{src:docs/LANGUAGE.md:634-641}}.

== Sugar → fundamental facts <lowering>

*Intuition.* The brief asks that "syntactic-sugar-driven logic" be broken down into fundamental facts and relations. In OV the "fundamental" level is RawOV: ground facts, Horn rules with negation and arithmetic builtins, finite domains and world policies (§3.3). Every lowering below is produced by the build: on the left the real OV lines, on the right the real RawOV items the front end generated for them (printed by `rawtext.dump`, with absolute paths shortened and spans abbreviated to `span(La-Lb)`), or, for the object layer, the compiled class formulas.

*Status.* {{badge:PARTIAL}} The rule layer lowers completely to RawOV {{test:tests/v1/test_lang.py::test_lowering_is_deterministic_and_round_trips}}. The object layer compiles to formula terms that a different trusted unit (`raw/formula.py`) decides; classes and rules are connected only by the runner {{src:KNOWN_LIMITATIONS.md:44-47}}.

=== 1. A class with invariants

`ConstantAcceleration` is defined by three invariants; velocity and displacement are integrals of acceleration (definitions), and the five SUVAT equations are theorems proved from them.

{{lower:class}}

=== 2. An equation solved in several directions

One law, $F = m a$, gives one rule per solvable slot:

{{lower:newton}}
{{fig:lower_newton}}

=== 3. A transformation (and a controller guard)

{{lower:transformation}}

The transformation `cook` became rule `kitchen.cook` with the controller's guard `allowed(X)` as an extra premise; `pipe cook` left no trace.

=== 4. A generator

{{lower:generator}}

=== 5. A scenario with an assumption

{{lower:assume}}

`assume frictionless: frictionless(floor)` became a fact with origin `assume:frictionless`; the query became a rule `ov.query.push_block_s.1` whose answers carry the label `{{frictionless}}`.

=== 6. An inheritance chain

{{lower:inherit}}

=== 7. A collection pattern

{{lower:pattern}}

=== 8. A units example

Shown in §2.8.2 above: `3 N` is the term $3 dot e_"kg" + e_"m" - 2 e_"s"$, and the answer $1 slash 2$ kg prints as `500 g`'s equal, `0.5 kg`.

=== 9. Scenario inheritance

{{lower:extends}}

=== 10. A check and a functional clash

{{lower:checks}}

== Authoring by agents; auto-derivation by solvers <authoring>

*What exists.* {{badge:PARTIAL}} {{src:benchmarks/exams/jee2025}} The project's own libraries and all 14 JEE formalizations were drafted by agents (MP-DOL: AI drafts) and are kept honest by four mechanisms:

+ *the meaning gate*: no agent-written meaning line enters `packages/` without the founder's signed approval (§3.11) {{src:src/openverifiers/bench/gold_gate.py:69-81}};
+ *the faithfulness lint* (`python -m openverifiers.bench.faithfulness`): mechanical errors F1–F5 (answer leaked into the case, a general law stated in a case, a stray package next to a case, an answer map that does not match, an `assume` in an exam case) and warnings W1–W2 {{src:src/openverifiers/bench/faithfulness.py:1-31}};
+ *the gold-blind reviewer*: a separate agent sees only the question text, the formalization and the imported libraries, never the official answer, and writes `faithfulness_review.json` {{src:benchmarks/exams/jee2025/jee2025-phys-p2q9/faithfulness_review.json}};
+ *the MCP tools*: an agent can call `check_files` (run the commit gate on OV files) and `check_tool_call` over MCP {{src:src/openverifiers/mcp_gate.py:40-58}}.

{{run:python -m openverifiers.bench.faithfulness}}

The lint reports zero warnings here partly because W1 needs the question originals in the gitignored `private/` folder, which this worktree does not have; the C7 report, run where they exist, counted 4 warnings {{report:reports/V1_EXIT_C7_2026-11-23.md}}.

*What does not exist.* There is no authoring MCP server (draft → check → explain the error → fix) and no OV-Prose round trip. Auto-derivation of OV programs by solvers is OVProver, chapter 5. {{badge:PLANNED}} {{mp:v2 Engine (OVProver), v3 Lens (OV-Prose), MP §7}}

== Error codes

{{badge:IMPLEMENTED}} Every diagnostic has a code, a file:line:column, a caret under the offending text and a one-line hint {{src:src/openverifiers/lang/errors.py:24-50}}. Appendix E is the catalogue, generated from the codes that occur in `src/`, each with a real file that triggers it and the real output.

== Limitations of the language

- One global namespace; no qualified names; one `member` predicate for `x in s` {{src:KNOWN_LIMITATIONS.md:80-88}}.
- Controllers: only guards have meaning (§2.6.3).
- `derived` properties and `because:` are not implemented (§2.7).
- No `or` inside class bodies; an object query's WHERE is exactly one pattern {{src:KNOWN_LIMITATIONS.md:63-72}}.
- Rule-layer equations: one slot at a time; no systems (§2.8.1).
- Trigonometry of a variable waits for D-033 (§2.8.5).
- The documentation of the language (`docs/LANGUAGE.md`) has drifted from the code in several places; Appendix J lists them.
