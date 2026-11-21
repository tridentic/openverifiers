# OpenVerifiers v1 semantics

This file defines what the RawOV kernel computes, which verdicts follow, and
why the checker's acceptance of a trace makes those verdicts sound. It covers
Milestone 0: RawOV, labels, verdicts, stratified negation and budgets.
Plugins (M2) and OKQL (M4) will extend it. §6 and §7 cover what object-layer
verdicts rest on, and the solver reductions behind PROVEN theorems.

## 1. Programs

A RawOV program has four parts:

- **World policies:** `world p open|closed`. Open is the default.
- **Ground facts.** Each fact has an origin: `axiom:`, `fact:`, `import:`,
  `domain:` or `assume:<name>`.
- **Finite domains.** `domain d: pred(args) = {v1, …} complete|partial` stands
  for the facts `pred(args, vi)`.
- **Rules.** `head :- l1, …, ln`. A body literal is one of:
  - a positive atom `p(t̄)` or `neg p(t̄)`. The strong negation `neg p` is a
    separate relation, written `neg p`;
  - `not a`;
  - `X is e`;
  - a comparison `e1 op e2`.

Terms are symbols, strings, exact rational quantities with a dimension vector,
variables, and compound terms.

**Well-formedness** (`raw.validate`):
- ids are unique and facts are ground;
- rules are safe when read left to right. Positive literals bind variables;
  `not`, `is` and comparisons only read variables that are already bound;
  `is` binds a fresh variable; every head variable is bound.

**World policy rewrite** (`effective_body`):
- For an *open* predicate p, `not p(t̄)` means `neg p(t̄)` is derived.
  Not-derived is not enough. The literal is rewritten to the positive literal
  `neg p(t̄)`, and `not neg p(t̄)` to `p(t̄)`.
- Only closed-world `not` remains as negation-as-failure.

**Stratification.** An assignment `s` from predicate keys to ℕ must satisfy:
- `s(head) ≥ s(b)` for every positive body key `b`;
- `s(head) > s(b)` for every closed-world `not b`.

Programs without such an assignment are rejected with the offending cycle
(`NotStratifiable`).

## 2. Labels

**Assumptions.** `A` is the set of names in `assume:` origins.

**Literals and environments.** A literal is `a` (assumption a is active) or
`¬a` (it is not). An environment `e` is a consistent finite set of literals.

**Satisfaction.** A context `C ⊆ A` is the set of active assumptions. It
satisfies `e` when `pos(e) ⊆ C` and `neg(e) ∩ C = ∅`.

**Labels.** A label is an antichain of environments under ⊆, with no
inconsistent members. `L` holds in C when some `e ∈ L` is satisfied by C.
- Facts with any origin other than `assume:` have the label `TRUE = {∅}`.
- `assume a` has the label `{{a}}`.
- `FALSE = {}`.

**Operations.** Write `min` for removing inconsistent environments and
supersets.

| operation | definition | meaning |
|---|---|---|
| conjunction | `L1 ⊗ L2 = min{e1 ∪ e2}` | holds where both hold |
| disjunction | `L1 ⊕ L2 = min(L1 ∪ L2)` | holds where either holds |
| negation | `¬L = min{ {flip(ℓ_e) : e ∈ L} : ℓ_e ∈ e }`: the minimal hitting sets with every literal flipped | holds in C exactly when L does not (property-tested) |

**Labelled least model.** Evaluate stratum by stratum. Within a stratum, take
the least fixpoint of

    label(h) ⊇ label(b1) ⊗ … ⊗ label(bk) ⊗ ¬label(c1) ⊗ … ⊗ ¬label(cm)

over every ground rule instance `h :- b1..bk, not c1..cm, builtins` whose
builtins hold. Here `label(c)` is the final label of c from a lower stratum.

Because negation uses exact labels from completed lower strata, the result
satisfies the following.

> **Context independence.** For every C ⊆ A and atom p, label(p) holds in C
> iff p is in the stratified model of the program whose `assume:` facts are
> restricted to C.

So changing the active assumptions (`WHAT IF ASSUME/RETRACT <assumption>`) is
a label lookup. `tests/v1/test_kernel.py::test_what_if_by_label_lookup_equals_rerun`
checks this against a full re-run on random programs.

**Nogoods.** `N = min{e1 ∪ e2 : e1 ∈ label(p), e2 ∈ label(neg p)}`. These are
the environments in which a contradiction holds.

## 3. Verdicts

For a ground query `q` and context C, by default C = A:

1. `INCONSISTENT(conflict_set)` if C satisfies some n ∈ N. The conflict set is
   the facts (and assumptions) used in the derivations of `p` and `neg p` for
   that nogood. If n = ∅, the base theory itself is inconsistent.
2. `PROVEN(proof, e)` if C satisfies some e ∈ label(q). The proof is the set of
   trace steps of one derivation valid under e.
3. `REFUTED(proof, e)` if C satisfies some e ∈ label(neg q). It is also
   REFUTED with `closed_world` set if q's predicate is closed, its stratum is
   complete, and q is not PROVEN; then e ∈ ¬label(q) is satisfied by C.
4. `UNKNOWN(missing, reason)` otherwise, where reason is:
   - `budget` if q's or neg q's stratum is incomplete or a label was truncated;
   - `missing_facts` if q holds under other contexts, in which case `missing`
     lists the assume/retract changes needed. It is also `missing_facts` if
     the (untrusted) frontier search names premises a derivation is stuck on;
   - `open_world` otherwise.

Confidence and source metadata never enter labels or verdicts.

## 4. Traces and the checker

The evaluator emits a trace: an ordered list of steps. A fired step records:
- the fact or rule id and its substitution;
- the premise step ids;
- for each closed `not c`, a reference to c's final step (or "absent");
- `prev`, the conclusion's previous step;
- the conclusion's *cumulative* label after the firing.

The checker accepts the trace only if all of the following hold.

1. **Valid strata.** The program is well-formed and the claimed strata satisfy
   §1.
2. **Local justification**, step by step in order:
   - the instantiated head equals the conclusion, and each instantiated body
     atom equals its premise's conclusion;
   - premises occur earlier in the trace;
   - builtins hold;
   - `label = min(label(prev) ∪ ⊗(premise labels, ¬final labels))`.
3. **Negation.** Each negation reference names the final step of that atom,
   in a stratum that is complete.
4. **Closure.** For every stratum claimed complete, with all lower strata
   complete and no truncated label: every rule instance over the final model
   yields an environment set already covered by the head's label, and every
   fact is present.

**Soundness sketch.**

- **Claimed environments are entailed.** By induction on trace position,
  every environment in every step label is entailed: it is a union of premise
  environments that are entailed by earlier steps, and earlier-only references
  make the induction well-founded. Negation references use final labels of
  complete lower strata, so by the inductive hypothesis for those strata they
  are exact.
- **Complete strata are exactly the least model.** Closure says the claimed
  labels are a pre-fixpoint, so they contain the least labelled model. Local
  justification says they are contained in it.
- **Verdicts follow.**
  - PROVEN and neg-REFUTED rest only on entailed environments.
  - Closed-world REFUTED rests on exactness of a complete stratum.
  - INCONSISTENT rests on entailed environments of p and neg p.
  - Nothing else is asserted; everything else is UNKNOWN.

**Mutation evidence.** `tests/v1/test_checker.py` corrupts real traces in nine
ways: wrong substitution, missing or swapped premise, swapped or weakened
label, wrong or negated conclusion, wrong `prev`, wrong negation reference,
dropped step, fabricated fact. The checker rejects every non-equivalent mutant
of complete traces, and no mutant of any trace changes a verdict.
- Dropping a step from a stratum that is *already incomplete* can be accepted.
  The result is a smaller but still sound model, which can only turn answers
  into `UNKNOWN(budget)`. Such mutants are counted separately as "weakened".

## 5. Budgets

- **Limits:** steps, atoms, term depth, label size and wall time.
- **Cut-off.** Exceeding any of them marks the current stratum incomplete, and
  evaluation stops there. Positive results already derived stay sound.
- **Truncation.** A label over the size cap keeps only its smallest
  environments; the atom is marked truncated and its stratum becomes
  incomplete.
- **Partial domains.** A `partial` domain makes its predicate's stratum
  incomplete from the start.

## 6. Object layer: what a verdict rests on

Object-layer verdicts (brief §3.7) come from two sources, and every answer
lists which in `trust_base`, like Lean's `#print axioms`:

- **`kernel`:** the exact evaluator in `raw/formula.py` (trusted) re-checked an
  instance: a FIND binding, a consistency witness, a counterexample.
- **`z3_unsat`:** an unsat answer from z3, re-solved in a fresh solver but not
  checked by any trusted code. UNIQUE, COUNT, "no more solutions", empty
  classes and every PROVEN theorem rest on one.
- **`red:<name>`:** a reduction (§7) the unsat was computed under. Listed only
  when the verdict rests on `z3_unsat`; a kernel-checked instance needs none.

`ov run --strict` turns every verdict that rests on `z3_unsat` into
UNKNOWN(plugin_unknown), and so also every verdict that rests on a reduction.
`--no-reductions` computes every unsat on the full problem instead.

## 7. Theorem-proving reductions

A theorem check asks z3 whether the class's invariants and the theorem's
negation have a common instance (unsat means PROVEN). Five rewrites make
that problem smaller. They run outside the trusted checker but decide PROVEN
verdicts, so they are trusted assumptions until a checker covers them. Each
must lose no model: if the reduced problem is unsat, the full one is.

Notation:
- `I` is the conjunction of the invariants over the generic instance (fresh
  unknowns for every property, sets split into cases by which elements
  coincide).
- `N` is the theorem's negation.
- PROVEN needs `I ∧ N` unsat.

**`red:no_invariants`** (try the negation alone first). If `N` alone is unsat,
then `I ∧ N` is unsat, because adding conjuncts removes models and never adds
them. The theorem then holds for every instance, which is stronger than what
was asked.

**`red:fix_order`** (fix the counterexample's ordering). This applies to a
theorem `none v in cycles(p): B` or `all v in cycles(p): B` (also
`orderings`), where `p` is a set property of the generic instance and the
case has all of `p`'s elements distinct.
- In that case `p` is `{P0, …, Pn-1}`, with each `Pi` a tuple of fresh
  unknowns. Nothing in `I` or `N` can tell the elements apart: they occur only
  inside the set, and set operations (`count`, membership, the generators)
  are invariant under permuting its elements. The case condition (pairwise
  distinct) is symmetric too.
- A counterexample is an assignment plus an ordering `v` of `p` with `¬B(v)`.
  Renaming the unknowns along the permutation that maps `v` to the listed
  order `(P0, …, Pn-1)` gives another counterexample. Its ordering is the
  listed one.
- So `I ∧ N` is satisfiable if and only if `I ∧ ¬B(P0, …, Pn-1)` is.
- The precondition is checked by `_wlog`: the collection must be
  `cycles`/`orderings` of a property whose generic value is a set.

**`red:drop_implied`** (leave out invariants the negation already implies).
This only applies within `fix_order`.
- An invariant `exists w in C: B'`, over the same collection `C`, is
  implied when `B'` at the fixed ordering is a conjunction whose conjuncts
  all appear among the conjuncts of `¬B` at that ordering. The fixed ordering
  is a member of `C`, so it witnesses the exists.
- Dropping a conjunct that the remaining conjuncts imply does not change
  satisfiability.
- **How the implication is checked:** syntactically, as a subset test on the
  canonical constraint forms (`_conj_parts` in `objects/engine.py`). It does
  not call z3, so this step does not rest on `z3_unsat`. That corrects the
  change order's premise. It does rest on the untrusted expander producing
  the same canonical form for the same constraint. A wrong form could make it
  drop an invariant that is not implied, which is why it is listed in the
  trust base.

**`red:translate`** (pin a point to the origin).
- The unknowns of the generic instance's points are grouped by coordinate
  (all x, all y). For a group `g`, `translation_invariant` checks exactly, on
  the expanded polynomials, that every constraint (including case conditions)
  is unchanged when every variable of `g` is shifted by the same `t`.
- If so, any model shifted by `t = -g[0]` is still a model and has
  `g[0] = 0`, so adding `g[0] = 0` keeps satisfiability.
- The check is done in `objects/expand.py` (untrusted) and covers
  polynomials only. A bug in it could pin a coordinate that matters, which is
  why it is listed in the trust base.

**`red:inherit`** (reuse an ancestor's proof).
- If an ancestor proved a theorem whose formula is identical, then the class
  includes every invariant of that ancestor (the linearised ancestor list), so
  its instances are a subset of the ancestor's, and the theorem holds on
  them.
- The inherited answer also lists the ancestor proof's reductions.

**Not reductions:**
- **Merging identical disjuncts.** Constraints are kept as sets of canonical
  terms, so two orderings giving the same constraint are one disjunct; this
  is `A ∨ A = A`.
- **Small-scope search.** It only proposes instances, and the kernel
  re-checks every one. It never yields an unsat.

**Evidence:**
- `python -m openverifiers.bench.reductions` generates random small classes
  and theorems. It checks each one with the reductions on and off
  (`Settings(reductions=False, symmetry=False)`), each side with its own time
  limit, and fails on any pair of different definite verdicts.
- A small fixed-seed sample of it runs in the test suite
  (`test_reductions_never_change_a_definite_verdict`).
- This is testing, not proof. A checker for these steps (Condition B: the
  object-layer trace) is the way to drop them from the trust base.
