# Known limitations

Every shortcut, unsupported case and open question, kept current per
milestone. Newest milestone first.

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
- **`tolerance` is parsed and stored but unused.** Floats only arrive through
  plugins (Milestone 2).
- **`import state`** is parsed and rejected (E207) until Milestone 3.
- **Undeclared types are a warning, not an error** (W201). The brief's
  physics example uses `Surface` without declaring it, and the brief says
  that example must run exactly as written. Undeclared types are treated as
  opaque entity sorts.
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
