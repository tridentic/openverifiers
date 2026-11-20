# Status

Last updated: 2026-11-17 (Milestone 1, branch `m1-kernel`).

## Done (Milestone 1)

| Acceptance criterion | State | Evidence |
|---|---|---|
| 1. Kernel test suite passes, mypy strict, ruff clean | done | `pytest -q`: 310 tests (59 kernel); `mypy` strict on `openverifiers.kernel`; `ruff check .` |
| 2. Both packs through the same kernel, zero kernel changes between them | done | `git diff 5caedc4 -- openverifiers/kernel` is empty: no kernel change since the kernel commit, across both packs |
| 3. Mutation benchmark runs end to end and prints the table | done | `ov-m1 bench run` (about 5 s); latest output in `benchmarks/results/latest.md` |
| 4. Repair-loop demo | done | `ov-m1 demo repair`; `tests/test_proposers.py::test_repair_demo_acceptance_criterion` |
| 5. README explains idea, tiers, pack in < 20 lines | done | the README example runs in `tests/test_readme.py`, which also enforces the length |

Also done: the pre-M1 code moved intact to `openverifiers/legacy` (202 tests
still pass), fixing the package layout so `pip install -e .` works.

## Benchmark numbers (from `benchmarks/results/latest.md`)

| domain | mutants | no verification | mock LLM judge | kernel | kernel, right reason | kernel false rejections |
|---|---|---|---|---|---|---|
| math | 112 | 0.0% | 34.8% | 99.1% | 99.1% | 0 / 7 |
| code_requirements | 28 | 0.0% | 50.0% | 100.0% | 100.0% | 0 / 2 |

How to read these numbers honestly:

- **The near-100% is expected and is not strong evidence on its own.** The
  eight requested mutation types each break a rule the kernel was built to
  check, so this table is a regression suite. It shows the rules are wired up
  and diagnose the right failure. It says nothing about how often real
  proposer errors fall into these categories.
- **The kernel misses one mutant, and it is a real limitation:**
  `math_drop_speed~misread_given~0`. The proposer misreads the mass (2 kg ->
  4 kg) and then reasons correctly. Impact speed doesn't depend on mass, so
  the final answer is still right and the requirement passes, but the
  intermediate energy fact is wrong for the stated problem. The kernel verifies
  a proof *against its requirements*; anything the requirements don't pin
  down is not checked. `misread_given` was added beyond the eight requested
  types to expose exactly this.
- **The "mock LLM judge" is not an LLM.** It is a deterministic stand-in
  that reads only the claimed final facts. Its column shows what conclusion-only
  review misses, not what a real model does. A real judge run is the first
  M2 item.
- **The samples are small.** 7 math and 2 code base cases. The code domain
  has no units or numeric outputs, so `unit_mismatch`, `sign_error` and
  `misread_given` are n/a there.

## Known limitations

- **Code pack trusts its compiled checks.** If the tests under-specify a
  requirement, wrong code passes. Compiling requirements into checks is
  itself unverified (it is a fact in the case, not a derived one).
- **The code sandbox is isolation, not security.** It uses a subprocess,
  `python -I`, a temp dir, a scrubbed env, a timeout and a CPU rlimit, but
  untrusted code can still touch the file system. Use a container for
  hostile code.
- **Checker independence is partial.** The formula residual check uses
  sympy, the same library as the effect. Only the linear solver has an
  independent (z3) check.
- **Search proposers only cover formula-shaped problems.** Forward and
  backward search solve 4 of 7 and 3 of 7 math cases. They cannot invent
  grounded or soft steps, or decide which unnamed arithmetic to do.
- **No real LLM yet.** `LLMProposer` takes any `complete(prompt) -> str`.
  Only `ScriptedModel` is exercised.
- **Python 3.11 is declared but only 3.12 was run locally.** CI covers
  3.11-3.13 but has not run on this branch yet.
- **Kernel size:** about 740 lines (`check.py` + `model.py`, with
  docstrings), plus about 210 for JSON. That is above "a few hundred". Rejection
  messages account for much of it.
- `openwiki/` (a generated index) and the legacy docs now under `docs/legacy/`
  describe the old runtime and are stale.

## Next

1. Run a real LLM as proposer *and* as judge on the same cases, and replace
   the mock-judge column with measured numbers.
2. Proposer-error corpus: collect proofs real models actually produce, label
   them, and measure the kernel on that distribution instead of synthetic
   mutants.
3. A soft-tier example pack (e.g. an LLM-judged step) to exercise
   `conditional_on_soft_steps` end to end.
4. More cases per domain (at least 30) and a check-suite adequacy measure for the
   code pack (mutation testing of the checks themselves).
5. Trace viewer (JSON is already stable).

## Open questions for you

- **Should a failed step that no requirement depends on invalidate the
  proof?** Currently yes: any false claim makes the proof `invalid`. The
  alternative is to grade only the support set and list stray failures as
  warnings.
- **Proof format:** JSON only for now. Do you want KDScript (the `kdscript`
  branch) revived as a front end that compiles to this JSON, or retired?
- **`unverified` initial facts:** they currently downgrade the grade to
  `conditional_on_unverified_facts`. Is that the right place for
  LLM-extracted inputs, or should extraction be a soft step?
- **Legacy code:** keep `openverifiers/legacy` in the main package, or move
  it to a separate branch once nothing depends on it?
