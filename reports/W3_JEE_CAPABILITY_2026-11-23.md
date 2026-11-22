# OpenVerifiers v1: W2.5 and W3 report (JEE capability)

**To:** CTO · **Date:** 2026-11-23 · **Branch:** `v1` at `9455bf8` and the report commit after it

`MASTERPLAN.md` is still not in the repo (checked on the remote today). §2 is
therefore still provisional and does not cite MP sections. W2 has not started:
Arjo's `Gold-Change-Approved-By` trailer has not landed.

## 1. Done vs scope (your order: W2.5, then W2 when the trailer lands, then W3)

| item | status | commit |
|---|---|---|
| **W2.5** JSON-only traces; the RawOV text parser out of the trusted base | done | `165df8f` |
| Decision 3: lemma scope, E407 | done | `7616613` |
| Decision 5 (interim): exp chain-rule cross-check; refusals per expression class | done | `7616613` |
| **W2** retire `TwoBodyInteraction` | waiting for Arjo's trailer | |
| **W3** JEE tier: harness, lint, gold-blind reviewer, libraries, formalizations | done, at the coverage below | `2626300`, `9455bf8` |

**W2.5.**
- The checker now reads its input only as canonical JSON, using the
  standard-library `json` module (`checker.check_json`, `raw/canon.py`):
  - the program is one JSON document;
  - the trace is JSON lines;
  - every term has exactly one encoding;
  - anything non-canonical is rejected (for example `"6/4"`, `"1.5"`, or
    dimensions out of order).
- The engine sends every run through this form, so what the checker checks
  is exactly what a stored trace file says.
- `raw/text.py` moved to `openverifiers.rawtext`, which is untrusted.
- A test confirms that no trusted module imports `rawtext`, `re` or `lark`.

**Lemma scope (E407).**
- A lemma is reused only inside its own package's proofs. When a class in
  another package inherits it, that class proves the statement itself.
- A query that names a lemma (`COUNTEREXAMPLE C.lemma`) is error E407.
- Tests cover both rules. Removing the guard makes the test fail.

**Decision 5 interim (differential suite).**
- Derivatives of exp bodies are now cross-checked against central finite
  differences of the trusted evaluator: step 2⁻⁶⁴, intervals with 200 bits
  of precision, relative tolerance 10⁻²⁰. This check is untrusted.
- A solver value that still mentions a variable counts as a disagreement.
- A planted bug that treats `exp(u(x))` as a constant is caught.

## 2. Gap table (PROVISIONAL: MP §7 is not available)

These rows change the W1 gap table; all other rows are as in the W1 report.

| v1 item | status | evidence |
|---|---|---|
| JSON-only traces, `raw/text.py` out of the TCB (pulled forward from W5) | done | `165df8f`; `tests/v1/test_canon.py` |
| Lemma relabelling guard | done | E407; `tests/v1/test_lemma_scope.py` |
| JEE formalized + capability report (W3) | done at 10/30 formalized, 8/30 solved (provisional) | §3 |
| Faithfulness lint + reviewer agent | done | `bench/faithfulness.py`; 10 reviews |
| Exp chain rule in the trusted normal form | not started | after W2.5, as decided; interim cross-check is in place |
| W2 (`TwoBodyInteraction`) | blocked | needs Arjo's trailer |

## 3. JEE 2025 capability

The 30 problems are the ones drawn earlier (`0ecd7df`). The gold is the
official answer key in `list.json`, committed before any formalization. Run
it with `ov exam --drafts` (or `--strict`).

### Matrix

| problem | type | official | OV (default, `--drafts`) | trust | rests on draft library |
|---|---|---|---|---|---|
| phys p1q10 radiation shields | numeric | 3 | UNKNOWN (engine) | — | physics.thermal |
| phys p1q13 de Broglie / Bohr | numeric | 72 | UNKNOWN (engine) | — | physics.quantum |
| phys p2q3 rod with springs | single | C | **√10/2 = C** | kernel + z3_unsat | physics.rotation |
| phys p2q9 spinning conductor | numeric | 1.65–1.67 | **5/3** | kernel + z3_unsat | physics.electromagnetism |
| phys p2q12 counter-rotating satellite | numeric | 2.3–2.4 | **2.331** | kernel + z3_unsat | physics.gravitation |
| chem p1q10 van der Waals cubic | numeric | −7.2 to −7 | **−7.1** | kernel | chemistry.gases |
| chem p2q9 ccp density | numeric | 10.85–11.1 | **11.0** | kernel | chemistry.solid_state |
| chem p2q12 pseudo-first-order error | numeric | 4–4.25 | **4.1667 (25/6)** | kernel + z3_unsat | chemistry.kinetics |
| math p1q7 Apollonius circle | multi | A, D | **A, D** | **kernel** (certificates) | none |
| math p2q12 coplanar vectors | numeric | −2 | **−2** | kernel + z3_unsat | math.vectors |
| 20 others | | | not formalized | | |

**Totals.**

| | default (`--drafts`) | `--strict` |
|---|---|---|
| solved | **8** | **1** (math p1q7) |
| unknown | 2 | 0 |
| wrong | **0** | 0 |
| error | 0 | 9 |
| not formalized | 20 | 20 |
| solved on draft libraries | 7 | — |

- `--strict` never loads drafts, so the 9 draft-dependent cases fail to load
  there.
- Of the 8 solved, 5 PROVE UNIQUE results also rest on z3's unsat for
  uniqueness, so `--strict` would demote them as well.

**By subject (default).**

| subject | solved | unknown | not formalized |
|---|---|---|---|
| physics | 3 | 2 | 5 |
| chemistry | 3 | 0 | 7 |
| mathematics | 2 | 0 | 8 |

### Failure taxonomy (22 not solved)

**engine (2): stated, but undecided.**
- phys p1q10: every model needs four fourth powers in arithmetic progression.
  These have no rational solution, and the checker cannot represent the
  quartic roots, so z3 gives no usable model.
- phys p1q13: z3 finds α = 72, but every model contains π (h = 2π p r / n).
  The exact checker rejects such models, so the result is UNKNOWN. This is the
  intended behaviour: it is not a false PROVEN.

**language (8): OV cannot state the problem.**
- math p1q13, p2q9: differential equations.
- phys p1q5: differential equations.
- math p1q1: a quantifier over the reals.
- math p1q4: integer-valued properties or matrices.
- math p1q10: sequences over a finite alphabet, and COUNT is capped at 64.
- math p2q3: inverse trigonometric functions.
- math p2q6: integrals of non-polynomials.

**structures (6):** organic and structural chemistry: chem p1q4, p1q7,
p1q13, p1q16, p2q3, p2q6.

**library (4): stateable, but no library exists, even as a draft.**
- phys p1q7: waves at junctions.
- phys p1q16: atomic and nuclear phenomenology.
- phys p2q6: geometric optics.
- chem p1q1: decomposition products.

**not attempted (2):** phys p1q1 (rolling inside a ring) and math p1q16
(cross-product system). Both are expressible; I ran out of W3 time.

### Faithfulness

**Lint** (`python -m openverifiers.bench.faithfulness`): 0 errors, 2
warnings.
- Both warnings are numbers in the question text that are figure labels or
  garbled option text (`W1`).
- The lint enforces:
  - no answer leak;
  - no general law inside a case;
  - no stray package beside a case;
  - the answer map matches the queries;
  - no `assume`.

**Reviewer.**
- A separate Claude agent reviewed the 10 cases. It saw only the question
  text, the case, `answer.json` and the libraries the case imports: no
  answers and no OV results.
- Verdicts: 4 faithful, 6 faithful with notes, 0 unfaithful.
- Notes worth your eye:
  - **math p1q7:** "a circle with centre c" is encoded as "all points of S
    are equidistant from c". That is necessary, not sufficient (S could be
    empty), and the radius options are measured from (A)'s centre.
  - **phys p2q9:** the problem's real work is that "conducting" means the
    charge is on the surface. It is in the case's Reading note, but a human
    should confirm it.
  - **chem p1q10:** the signed ratio is read literally.
- The reviews are in `benchmarks/exams/jee2025/<id>/faithfulness_review.json`.

### Libraries drafted for W3 (`drafts/packages/`, unapproved)

| package | meaning lines | claim ratio (strict) |
|---|---|---|
| physics.thermal | 3 | 1.00 (1.00) |
| physics.quantum | 8 | 0.80 (0.89) |
| physics.rotation | 4 | 1.00 (1.00) |
| physics.gravitation | 2 | 1.00 (1.00) |
| physics.electromagnetism | 4 | 1.00 (1.00) |
| chemistry.gases | 7 | 0.50 (0.71) |
| chemistry.kinetics | 6 | 1.00 (1.00) |
| chemistry.solid_state | 5 | 0.50 (0.80) |
| math.vectors | 5 | 0.50 (0.67) |
| **total** | **44** | |

These libraries are mostly claims: most of what they say is trusted, not
proven. Two results are stated without derivation, because OV has no surface
or volume integrals:
- the moment of a spinning charged shell;
- the inertia of a solid sphere.

### Weaknesses (ranked by how many problems they block)

1. **No ODEs, no ∀ over the reals, no integers or sequences, no inverse
   trig.** These block 8 of 30.
2. **Models that must contain π or high-degree algebraic numbers cannot be
   re-checked.** This blocks 2. Many physics problems put π into a model, so
   this is the next engine priority.
3. **Most solved answers rest on unapproved drafts:** 7 of 8 move to
   `--strict` only after Arjo approves the 44 lines.
4. **PROVE UNIQUE rests on z3 unsat** in 5 of 8 solved problems. A uniqueness
   certificate would move them to `{kernel}`.
5. **Unit names collide with identifiers:** `t > 0 p > 0` parses `0 t` as
   zero tonnes. I renamed properties to work around it; it should become a
   diagnostic.
6. **Division by a non-constant does not expand.** The vdW law's own
   consistency check is UNKNOWN. The case avoids it through the cubic class.
7. **No organic or structural chemistry.** This blocks 6, out of v1 scope.

## 4. Cross-cutting numbers

| number | value |
|---|---|
| **TCB** | main **1,015** / 1,500 (was 1,219); formula 382 / 400; exact 362 / 450; **total 1,759 / 2,000** (was 1,963) |
| trusted code imports `rawtext`, `re` or `lark` | none (test) |
| library theorems at `{kernel}` | 30 / 40 (unchanged) |
| `--strict` bench | 31 / 36; default 34 / 36 (unchanged); false PROVEN 0 |
| JEE (default / strict) | 8 / 1 solved of 30; **0 wrong** |
| differential (seed 0, 5,000 cases) | 4,833 agree, 167 refused, **0 disagree** |
| refusal reasons (all 167 by the trusted side) | 162 square roots of a non-rational value; 4 exp arguments over 4,096; 1 radicand too large to factor |
| exp-derivative cross-check (1,000 cases) | 973 agree, 27 refused (exp argument over 4,096), **0 disagree** |
| tests | 582 passed |
| coverage, raw + kernel + checker | 98% (`raw/canon.py` 100%, `raw/trace.py` 100%) |
| CI | green up to `6330145`. The runs for `7616613` and `9455bf8` were still in progress when this was written. Not reported as green. |

**Refusals per expression class** (cases are counted in every class they
contain; all refusals are by the trusted side):

| class | cases | refused | refusal rate |
|---|---|---|---|
| sqrt | 763 | 164 | 21% |
| division | 1,410 | 69 | 4.9% |
| exp | 796 | 63 | 7.9% |
| ln | 784 | 58 | 7.4% |
| pi | 817 | 48 | 5.9% |
| power | 782 | 19 | 2.4% |
| integral | 415 | 13 | 3.1% |
| deriv | 403 | 5 | 1.2% |
| arithmetic | 1,488 | 0 | 0% |

The other classes' refusals are the same `sqrt` cases, counted under every
class those expressions also use. The single gap is that the trusted
evaluator takes the square root of rationals only, never of irrational
values.

## 5. Meaning lines changed

- **`packages/` and `laws/`: none.** The freeze held.
- **New lemma statements: none.**
- **44 drafted lines** in `drafts/packages/`. They are listed by the
  meaning-gate function over each file. They are not in the standard library,
  are loaded only by `--drafts`, and never under `--strict`.
- **Problem-specific class invariants** in the 10 case files state the
  problems themselves. The reviewer checked them.

## 6. Deviations

1. **The drafts directory.**
   - Decision 7 froze meaning edits, but W3 needs new libraries.
   - So the libraries live in `drafts/packages/`:
     - outside the gate's path;
     - loaded only by `--drafts`;
     - refused under `--strict`;
     - marked PROVISIONAL in every output.
   - Nothing there counts as library.
2. **Ten formalized, not thirty.**
   - 20 problems are classified instead.
   - 2 of those were within reach but not attempted (time).
3. **Engine changes made during W3** (untrusted; no trusted lines):
   - unit-string property types;
   - new units: pm, nm, dm and atm;
   - type `Density`.
4. **The reviewer was a Claude subagent.**
   - It runs in-session from a generated packet.
   - No Anthropic SDK dependency was added.

## 7. Shortcuts found

1. **A package file beside a case would bypass the meaning gate.** The loader
   searches the case's own directory. The lint now rejects it (F3), but the
   gate itself does not cover it.
2. **The original question text in `questions_2025.json` includes the
   official answer.** The reviewer packet cuts everything from "Answer:"
   onward, and I checked the packets for the word.
3. **Two questions lost their formulas in PDF extraction** (phys p2q9,
   p2q12).
   - I read the PDF pages and gave the reviewer the missing text.
   - That text is a transcription, and a human should spot-check it.
4. **`answer.json` option values are my transcriptions.** The reviewer
   confirmed them for phys p2q3.

## 7a. Dates

- **JEE report:** due about 10 Dec, delivered today.
- **HSC (W4):** waiting for the folder.
- **v1 exit (about 30 Dec):** at risk if the meaning approvals (71 + 44 lines)
  and W2's trailer take long. Every provisional result depends on them.

## 8. Decisions needed

1. **Approve or revise the 44 drafted library lines** (in
   `drafts/packages/`), together with the 71 pending ones.
   *Recommendation: one review session; approved files move to `packages/`
   with the trailer, and the strict JEE count rises to 8 minus the
   z3-uniqueness ones.*
2. **Accept or reject the `drafts/` mechanism** (deviation 1).
   *Recommendation: accept, and extend the gate to cover any `package` file
   outside `packages/` and `drafts/` (shortcut 1).*
3. **Next engine priority.**
   *Recommendation: exact π-carrying models (π as a field element in the
   checker, and certificates over ℚ(π)), then uniqueness certificates. These
   unblock phys p1q13 and move 5 solved answers to `{kernel}`.*
4. **Language extensions for v1.** Should ODE solutions, ∀ over the reals,
   integers and inverse trig be in v1 scope?
   *Recommendation: integers and ∀-over-reals via certificates are in scope;
   ODEs and inverse trig are v2.*
5. **"go" for the next step** (W4, or the engine priority above). I am
   stopping here as instructed.
