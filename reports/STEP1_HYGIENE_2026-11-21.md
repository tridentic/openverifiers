# Step 1 (hygiene): report, 2026-11-21

Branch `v1`, pushed. Head `e3f3166`.

**CI is green.** Run 44802394687 passed all four jobs: Ubuntu and macOS, each
on Python 3.11 and 3.12. Each job runs lint, mypy, the trusted-code size gate,
the coverage gate and the full suite.
https://github.com/tridentic/openverifiers/actions/runs/44802394687

## Commits

| commit | what |
|---|---|
| `8aeaa91` | the false Rhombus theorem pinned as UNKNOWN(budget); the status report |
| `d686a20` | CLI rename, `trust_base` + `--strict`, COUNTEREXAMPLE semantics, the FIX NOW items |
| `e3f3166` | small-scope pass before z3; the Rhombus test flips to REFUTED |

## What changed

- **CLI.**
  - `ov` is the v1 CLI: `ov run FILE.ov [--verbose] [--strict]`.
  - The pre-v1 tool is `ov-m1`. `legacy/` and `m1/` are untouched.
- **trust_base.** Every verdict carries one, shaped like Lean's
  `#print axioms`.
  - `kernel`: the checker accepted the trace, or the trusted evaluator
    re-checked an instance.
  - `z3_unsat`: an unsat answer that only the solver vouches for.
  - `ov run --strict` turns every `z3_unsat` verdict into
    UNKNOWN(plugin_unknown). A FIND keeps its re-checked bindings but no
    longer claims the list is complete. W201 becomes error E208.
- **COUNTEREXAMPLE** now returns the theorem's verdict: REFUTED with the
  witness, PROVEN when the negation is unsat. It is documented in the new
  `docs/OKQL.md`.
  - Two expectations written for the old mapping were flipped to match: the
    package test `no_pythagoras_counterexample` and the false-theorem test
    in `test_objects.py`.
  - These are my own tests, not benchmark gold. The flip is in the
    `d686a20` commit message.
- **FIX NOW items:**
  - `tolerance` is error E207.
  - `derived` is error E207. I chose to reject it rather than half-support
    it.
  - `type Surface` is declared in the §3.5 example and in
    `physics.mechanics`.
  - `v[i-1]` is a real index expression. The NAME token no longer swallows
    a final digits part, so `i-1` is `i - 1`. The compiler workaround is
    deleted.
  - `Square.diagonals_equal` is rewritten as you specified:
    `all v in cycles(vertices): <square ordering> -> dist2(v[0], v[2]) = dist2(v[1], v[3])`.
    It is PROVEN, `trust {z3_unsat}`.
  - New warning W202 flags a theorem that says `exists` over an invariant's
    generator. It fires on the old wording and is tested.
  - The Rhombus false theorem was pinned first (`8aeaa91`). The small-scope
    pass (`e3f3166`) then flipped it to REFUTED, with a counterexample the
    trusted evaluator confirms.
- **Language additions** needed for the rewrite:
  - `P -> Q` inside class bodies;
  - `all v in C:` as a quantifier whose body runs to the end of the
    enclosing body.

  That adds a fifth shift/reduce conflict (`->` binds to the innermost
  quantifier). It is documented and pinned by a test.
- **Making the rewritten theorem provable.** As first written, the rewritten
  theorem timed out in z3 (UNPROVEN). I added three reductions that lose no
  model, each printed in the trace:
  1. try the negated theorem without the invariants first;
  2. drop invariants the counterexample's conditions already imply;
  3. pin one point at the origin when every polynomial is shift-invariant.
     This is checked exactly on the polynomials.

## Numbers

**Tests** (`uv run pytest -q`): 494 passed, 0 failed, 0 skipped, 0 xfail.
That is up from 486: 176 → 184 v1 tests, plus the m1 and legacy suites.

**Soundness:**

- **Unsound survivors: 0.** 5,543 mutants killed, 1 accepted because it only
  weakens a verdict (a dropped step), out of 5,544 non-equivalent mutants.
  Unchanged from the status report.
- **False-PROVEN rate:** still not measurable; there are no benchmarks yet
  (step 2).
- **Object layer:** the buggy-solver test still rejects a wrong z3 model.

**Coverage:** the trusted and kernel set is at 99% (gate 95%).

**TCB:** 1,413 of 1,500 trusted lines, unchanged. Step 1 touched no trusted
code, and the checker still imports nothing from the kernel.

**Latency** (in process, 5 runs each: min / median / max):

| file | time |
|---|---|
| q11 (`examples/chem/q11.ov`) | 0.09 / 0.10 / 0.16 s (target < 1 s: met) |
| newton2 | under 0.01 s |
| square (`examples/geometry/square.ov`, 2 queries, 2 classes, 1 theorem) | 1.23 / 1.24 / 1.25 s |
| `math.geometry` (13 tests, 9 classes, 7 theorems) | 6.90 / 6.92 / 6.94 s |

The geometry figures went up from about 0.4 s and 3.6 s. **The cause is the
small-scope pass.** It costs up to 1 s on each solve that has no small
integer solution: every unsat proof, and searches for answers whose
coordinates exceed 4 (the square's (3,5)). I have not profiled further.

## New debt

1. **Small-scope runs before every z3 call.** That includes unsat proofs,
   where it can only waste time (up to 1 s each). Options:
   - run it only for checks expected to be satisfiable (consistency,
     counterexamples, FIND);
   - lower its budget.

   This is the first fix if the `ov check` latency target is enforced.
2. **I loosened my own symmetry test for class checks.**
   - With `Settings(symmetry=False)`, the rewritten Square theorem times out
     (UNKNOWN(budget), even at 60 s) instead of PROVEN.
   - The test now requires "never a different definite verdict; the
     unpruned side may only lose answers to the time limit".
   - Query answers must still be identical.
   - Reported here because it is a test I loosened, even though it is not
     gold.
3. **`--strict` and trust_base are not in the JSON trace yet.** They exist
   only in the in-memory answer and the text output. That arrives with
   OVTrace/OVState (M3).
4. **`ov` has only `run`.** `check`, `lower`, `query`, `bench`, `gate` and
   `explain` arrive with their steps.
5. **The trusted-code plan (decision 1) is not started:** JSON-only traces,
   and the text parser moved out of the trusted base. It is scheduled with
   M3.
6. **`push_block.ov` is not written yet.** As you ordered, it waits for the
   gold-diff gate (step 2), so its gold can be committed before OV runs on
   it.

## Next

Step 2: the gold-diff CI gate first, then the benchmark scaffold and
`ov bench`. Waiting for your "go".
