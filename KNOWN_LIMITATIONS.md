# Known limitations

Every shortcut, unsupported case and open question, kept current per
milestone. Newest milestone first.

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
