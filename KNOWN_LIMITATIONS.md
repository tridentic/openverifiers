# Known limitations

Every shortcut, unsupported case and open question, kept current per
milestone. Newest milestone first.

## Milestone 1b (object layer: concept classes)

- **Solving is nonlinear real arithmetic, and z3 is weak at finding rational
  points.** A model must be rational to be re-checked exactly. Two
  consequences, both giving UNKNOWN or UNPROVEN, never a wrong answer:
  - an instance that has no rational solution (an equilateral triangle with
    two given rational vertices) is UNKNOWN(plugin_unknown);
  - a counterexample that lies on a curved variety may not be found. A
    small-scope pass (integer coordinates in [-4, 4], a 10,000-node budget, about
    200 ms here; a node count, so the answer does not depend on machine speed) finds
    many of them: "a rhombus has equal diagonals" is REFUTED with
    (0,0), (1,2), (3,3), (2,1)-style witnesses. Counterexamples with no small
    integer point still depend on z3. The pass runs first only for searches
    for something that may exist (FIND and its variants, class consistency,
    COUNTEREXAMPLE). A theorem check runs z3 first and uses small-scope only
    when z3 neither proves nor refutes, so it never runs on a proof that
    succeeds.
- **Unsat is trusted to z3, and says so.** UNIQUE, COUNT, theorem PROVEN and
  empty classes rest on unsat answers. These cannot be checked by
  substitution. They are re-solved in a fresh solver, as the brief allows,
  but the same solver runs both times. Their `trust_base` names `z3_unsat`,
  and `--strict` turns them into UNKNOWN. An independent unsat certificate
  (e.g. a Positivstellensatz witness) is open; a cvc5 cross-check is planned
  as an optional extra.
- **Theorem-proving reductions are trusted assumptions.** Five rewrites
  (fix ordering, invariant-free negation, drop implied invariants,
  translation pinning, inheritance) shrink the unsat problem. They are argued
  sound in docs/SEMANTICS.md §7 and tested on random cases, not checked.
  Each one used is listed in `trust_base` as `red:<name>`, and
  `--no-reductions` turns them off (much slower: `math.geometry` takes
  about 5 minutes instead of 3.5 s).
- **The object path is not mutation-tested.** Object-layer steps (solve,
  re-check, block, unsat, reductions) are text in the answer, not OVTrace
  records, so no checker reads them and no mutation test covers them.
  Geometry results carry this label until they do (Condition B).
- **Theorems need bounded collections.** The generic instance takes each
  collection's size from a `count(p) = n` invariant. Otherwise the theorem is
  UNPROVEN.
- **Theorems use only the invariants.** The brief says "from the invariants
  and the imported axioms". Classes cannot yet refer to Datalog predicates,
  and `T(x)` cannot be used inside axioms: classes and rules are two separate
  worlds connected only by the runner.
- **Angles** are exact only for 0, 30, 45, 60, 90, 120, 135, 150 and 180
  degrees, and compare only by `=` and `!=`. Distances compare with numbers,
  properties or other distances, not inside arithmetic (use `dist2`).
- **`exists` in a theorem is weak** (it may choose any ordering). W202 warns
  about it. The brief's own `Square.diagonals_equal` did this and is
  rewritten in `examples/geometry/square.ov` as `all v in cycles(...): ... ->
  ...`.
- **Symmetry.** Orderings whose expansion is identical are merged, a
  theorem's counterexample ordering over a generic set is fixed (its elements
  are interchangeable), and points are pinned by translation when every
  constraint allows it. With `Settings(symmetry=False)` query answers are
  identical in the tests. Class checks never disagree, but the solver then
  runs out of time on the rewritten `Square.diagonals_equal` (UNKNOWN
  (budget), even at 60 s).
- **Smaller gaps.**
  - `CHECK x IS T` takes an instance written as a pattern, not a scenario
    entity.
  - An object query's WHERE is exactly one pattern; extra conditions on the
    unknowns belong in a class.
  - `derived` properties are rejected (E207) until they are unit-checked and
    support `requires`.
  - No `or` inside class bodies (implication `->` and `none` cover the
    cases met so far).
  - FIND stops after 16 solutions (LIMIT), COUNT after 64; past that the
    answer says more exist, or UNKNOWN(budget) for COUNT.
  - Steps are listed per answer (`--verbose`), not yet written into the
    OVTrace JSON-lines file (M3).

## Milestone 1 (OV front end)

### Language

- **One global namespace.** Every loaded package shares one table of types,
  predicates, functions and entities. Two packages that declare the same
  name clash (E202). Qualified names (`chem.organic.add`) are not supported.
- **`x in s` needs one `member` predicate.** It lowers to `member(s, x)`, so
  only one package can declare `member`. Typed overloading is open.
- **Equations.** A conclusion equation is solved only for slots that occur
  once under `+ - * /` and unary minus. Powers, repeated occurrences and
  systems of equations are E402 until the sympy and z3 plugins (Milestone 2).
- **`not x in [a, b]` in a premise is rejected** (E206). Write two axioms.
- **Controllers have guards only.** `pipe` and `branch` are checked for
  unknown names, but they do not change the meaning: a fixpoint does not
  depend on rule order. A transformation listed in a controller fires only
  with that controller's guards.
- **No user-declared units or dimensions yet.** USD is built in. `count`
  dimensions and `unit` declarations are open.
- **`tolerance` is rejected (E207).** Floats only arrive through plugins
  (Milestone 2).
- **`import state`** is parsed and rejected (E207) until Milestone 3.
- **Undeclared types are a warning, not an error** (W201), and opaque entity
  sorts. Under `--strict` they are error E208. The brief's §3.5 example now
  declares `type Surface`.
- **`2 m` after a number is a quantity.** A variable named like a unit must
  be multiplied explicitly (`2 * m`).

### Unknowns and queries

- **Candidate elimination needs a derived contradiction.** A statement about
  an unknown removes a candidate only when its contradiction is *derived*.
  A statement the rules cannot decide removes nothing, so more candidates
  survive and the answer is UNKNOWN, never wrong.
- **Unknown values are global to a component.** Unknowns linked by any
  statement are solved together. The candidate relation is their joint
  domain, which can be large for many linked generators.
- **The query set is small.** It covers PROVE, FIND (with WHERE) and
  `WHAT IF RETRACT/ASSUME ... THEN`. WHY, WHY NOT, NEAR, DEPENDS ON and
  EXPLAIN come with OKQL in Milestone 4.
- **The runner only runs queries in the file it is given.** It runs the
  scenarios and tests written there, not those of imported packages. To run
  a package's tests, pass its file to the runner.

### Chemistry (`chem.organic`)

- **C5H10 candidates are listed in the package.** The five alkenes are given
  as structures and the five cycloalkanes as structureless symbols. These
  are candidates, not answers. Milestone 2 replaces the list with a structure
  generator.
- **The other Milestone-0 limits still apply:** E/Z isomers, regioselectivity
  by H count, product sets.

## Milestone 0 (RawOV, kernel, checker)

### Semantics

- **An incomplete stratum stops evaluation.** When a budget runs out, a
  label is truncated, or a domain is partial, nothing above that stratum is
  evaluated, even the parts that never negate over it. This is sound but
  loses answers that could still have been proven. Finer-grained completeness
  tracking is open.
- **PROVEN under a budget cut-off.** A PROVEN derivation found before the cut
  is sound, but a contradiction that would have been found later is not
  detected. With a complete model, such a query would have been INCONSISTENT.
- **INCONSISTENT is global.** Following the brief, any nogood satisfied by the
  context makes *every* query INCONSISTENT, even unrelated ones. Relevance
  filtering ("paraconsistent" answers) is not offered.
- **Conflict sets are not always minimal.** The conflict set is the facts used
  in *one* derivation of p and one of neg p. It is not the minimum over all
  derivations. The Why-semiring in M2 can provide the minimum.
- **Retracting a fact is a re-run, not a lookup.** Facts have the label `{∅}`.
  Only assumption changes are label lookups. An opt-in fact-token mode is
  planned for M4.
- **Signed labels can grow exponentially.** Closed-world negation over a
  label with many environments makes hitting sets. The `max_label` budget
  caps this, and the cap makes the result UNKNOWN(budget), never a wrong
  answer.

### Evidence and tooling

- **The `missing` frontier is shallow.** It is a depth-1 heuristic: the first
  body literal each rule gets stuck on. It is untrusted. The checker only
  confirms that the listed ground atoms are not established.
- **Blocked derivations are not in the trace yet.** The evaluator reports them
  as a side list (`Run.blocked`), not as `blocked` steps inside the trace. The
  checker already accepts and ignores `blocked` steps. M3 writes them.
- **The TCB line count excludes docstrings.** The 1,500-line gate counts
  non-blank, non-comment, non-docstring lines. The current count is 1,210.
  `scripts/tcb_size.py` also prints the physical count (about 1,700).

### q11 (hand-written RawOV)

- **Chemistry scope.** q11 is encoded by hand, ahead of the `.ov` front end.
  Its chemistry is limited to:
  - acyclic alkenes, carbonyls and alkyl halides as canonical substituent
    trees;
  - E/Z isomers not distinguished;
  - cycloalkanes as structureless candidates.
- **Regioselectivity.** It is decided by H counts on the two alkene carbons.
  Equal counts mean "no single major product". Carbocation rearrangements and
  real radical-stability ordering beyond H count are not modelled.
- **`2-chloropentane in add(B, HCl)`** is read as "is in the product set,
  major or minor".
- **Names come from a table.** Structure → name facts are used only to print
  answers. They are not used to reason.

## Open questions

- Should INCONSISTENT be scoped to queries whose proofs touch the conflict?
- Should fact retraction become a label lookup by default (fact tokens), at
  the cost of larger labels?

## Found by the first benchmark run (2026-11-21)

- **FIND does not say what is missing.** An UNKNOWN FIND reports
  `open_world` with no missing facts. PROVE reports the missing atoms.
  Example: `physics/push_block` with `frictionless` retracted should say
  "missing: mu, normal_force".
- **A retracted assumption shows up as a missing `assume` atom.** It should
  show as the statement itself (`reviewed(v2)` in
  `agentic/deploy_checklist`).
- **No linear-system solving.** Each equation is solved for one slot, so
  `x + y = 10, x - y = 4` gives UNKNOWN, not x = 7
  (`mathematics/linear_system`). Planned for Milestone 5.

## M-CAP library layer (2026-11-22)

- **Trigonometry is symbolic or exact-special only.** An `Angle` is
  (cos, sin) with cos² + sin² = 1.
  - It is exact at the special angles, or from the problem's given values.
  - A general angle in degrees (37 deg without its sine given) is refused
    (E405) until the interval mode lands.
  - Answers with a square root print without their unit (`10√3`, not
    `10√3 N`).
- **No sums with a symbolic number of terms.** The sum of an arithmetic
  progression with n terms needs induction or a sum operator, so it is not
  stated yet.
- **Nested roots are compared, not computed.** √(2 + √3) can be compared
  by its square but not added; sqrt of an irrational is refused.
- **Calculus covers polynomials in one property.** `integral(e, t)` and
  `deriv(e, t)` need `e` polynomial in `t`. Non-polynomial integrands (1/t,
  exponentials) are refused, and there are no numeric ODEs.
- **Axiom ratios are far from the 0.25 target:** physics.mechanics 0.64,
  math.geometry 0.68. Theorems will be added as exam problems need them, not
  to move the ratio.
- **The trusted code is at 1,470 of 1,500 lines** after adding exact
  calculus to `raw/formula.py`. The next trusted addition needs the agreed
  split: `raw/formula.py` as its own audited unit, capped at 400.
- **Dependencies from `ov audit --dag` can be larger than minimal.** Each
  deletion trial has a shorter time limit, and a premise is kept when the
  trial times out. Never smaller than the real set.
