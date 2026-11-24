# OKQL: the query language (current subset)

Queries are written inside `.ov` files as `query <OKQL>` and are answered by
`ov run`. An `expect VERDICT [values] [assuming {...}]` line after a query
asserts its answer. Milestone 4 adds WHY, WHY NOT, NEAR, DEPENDS ON, EXPLAIN
and queries over a saved OVState.

**Verdicts are always about the proposition asked.** Every answer is exactly
one of PROVEN, REFUTED, UNKNOWN(reason) or INCONSISTENT(conflict set), and
carries a `trust_base` (see below).

## Rule queries (answered from the checked model)

| form | answer |
|---|---|
| `PROVE p` | PROVEN or REFUTED with a proof and its assumptions; UNKNOWN with the missing premises; INCONSISTENT with the conflict set |
| `FIND ?x, ?y WHERE conj` | every binding with its own verdict; for scenario unknowns (`generator A from ...`) without WHERE, the value if exactly one candidate survives, else UNKNOWN with the candidates |
| `WHAT IF RETRACT f \| ASSUME a [AND ...] THEN q` | q's answer in the changed context. Assumption changes are a label lookup; retracting a fact re-runs the program |

Their trust base is `{kernel}`: the trace was accepted by the independent
checker.

## Object queries (concept classes, `docs/LANGUAGE.md`)

| form | answer |
|---|---|
| `FIND ?p: T WHERE C{...} [LIMIT n]` | every solution (default limit 16), each re-checked by the trusted evaluator |
| `PROVE UNIQUE ?p [WHERE C{...}]` | PROVEN if, after blocking the solution, the solver finds no other; REFUTED with two witnesses; REFUTED if there is none |
| `COUNT ?p WHERE C{...}` | PROVEN with the exact number of solutions; UNKNOWN(budget) past 4096 |
| `CHECK C1{...} IS C` | PROVEN, or REFUTED naming each invariant the instance fails |
| `COUNTEREXAMPLE C.theorem` | **the theorem's verdict**: REFUTED with a counterexample the evaluator confirmed; PROVEN if the theorem's negation is unsat; UNKNOWN otherwise (budget, or plugin_unknown for a model with irrational coordinates) |

## Trust base

| verdict | trust base |
|---|---|
| rule queries | `{kernel}` |
| FIND with bindings, UNIQUE refuted by two witnesses, CHECK, a refuted theorem, a consistent class | `{kernel}`: an instance was re-checked exactly |
| UNIQUE proven, COUNT | `{kernel, z3_unsat}` |
| FIND with no solution, an empty class (INCONSISTENT) | `{z3_unsat}` |
| a proven theorem (or COUNTEREXAMPLE with none) | `{z3_unsat}` plus the `red:*` reductions used, e.g. `{z3_unsat, red:fix_order, red:translate}` (SEMANTICS §7) |
| UNKNOWN | `{}` |

`ov run --strict` makes every verdict whose trust base contains `z3_unsat`
UNKNOWN(plugin_unknown). A FIND keeps its re-checked bindings but no longer
claims the list is complete.


## WHY and WHY NOT (v1)

- `WHY lit`: the verdict of `PROVE lit`, always with its checked derivation
  (each step's rule and source line; leaves are facts with their origins).
- `WHY NOT lit`: what keeps `lit` from holding. For REFUTED, the refutation;
  for UNKNOWN, the missing facts (each alternative a set that would make it
  PROVEN, re-checked against the model); if `lit` holds after all, its
  derivation.
