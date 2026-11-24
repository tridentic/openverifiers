= Trust and evaluation <ch6>

== An informal soundness argument

*Claim.* If OV prints PROVEN with trust base `{kernel}`, then either the claim follows from the stated axioms, facts and listed assumptions, or there is a bug in one of the trusted files of @fig-trust. A wrong lowering, a wrong evaluator, a lying z3 or a hallucinating agent cannot, on their own, produce a false `{kernel}` PROVEN.

*Why, for rules.* The verdict is computed by `checker/verdict.py` from a `CheckedModel`, and a `CheckedModel` exists only if `checker/check.py` accepted the trace {{src:src/openverifiers/engine.py:36-39}}. The checker re-derives every step from the program's own rules and facts, as read from canonical JSON by `raw/canon.py`. By induction on trace position, every environment in every label is entailed (each is a union of premise environments, premises occur earlier, and negation references point to final labels of complete lower strata); complete strata are exactly the least labelled model (closure gives "contains", local justification gives "contained in"). So a PROVEN reads only entailed environments ({{src:docs/SEMANTICS.md:149-164}}). What remains to trust is: the RawOV data model and canonical JSON (`raw/program.py`, `raw/terms.py`, `raw/canon.py`), the label algebra (`raw/labels.py`), the builtins (`raw/builtins.py`), the trace format (`raw/trace.py`), the checker and the verdict function.

*Why, for objects.* A `{kernel}` object verdict rests on a JSON record that `checker/objects.py` re-decides with `raw/formula.py` (an instance satisfies every invariant, evaluated exactly) or `raw/certificate.py` (a polynomial identity in exact normal form), taking the invariants and theorem from the compiled class, never from the record {{src:src/openverifiers/checker/objects.py:48-73}}. If that re-check fails, the runner withdraws the verdict {{src:src/openverifiers/runner.py:124-139}}. What remains to trust is: those three files, the exact-arithmetic unit (surds, intervals, $QQ(pi)$, numeric checks), and the class compiler's faithfulness to the source.

*The honest gaps in this argument.*

+ *The front end is trusted for meaning.* If `lang/` or `lower/` or `objects/compile.py` mistranslates a statement, the kernel faithfully checks the wrong program. Rule programs round-trip through RawOV text and lowering is deterministic {{test:tests/v1/test_lang.py::test_lowering_is_deterministic_and_round_trips}}, but nothing _checks_ that the lowering means what the source says. This is the formalization risk MP §10 names first {{src:MASTERPLAN.md:463}}.
+ *`z3_unsat` and `red:*`* are not covered; they are named in the trust base and refused by `--strict`.
+ *The record checker trusts the compiled class*, so an `objects/compile.py` bug that drops an invariant would weaken what is checked.
+ *Python, `fractions`, `json` and `hashlib`* are trusted, as they must be.

{{fig:trust}}

== Mutation testing

*Rule path.* {{badge:IMPLEMENTED}} `tests/v1/test_checker.py` corrupts real traces in nine ways (wrong substitution, missing or swapped premise, swapped or weakened label, wrong or negated conclusion, wrong `prev`, wrong negation reference, dropped step, fabricated fact) and requires the checker to reject every non-equivalent mutant {{test:tests/v1/test_checker.py::test_checker_kills_every_trace_mutant}}. *Object path* (Condition B): `tests/v1/test_object_mutants.py` corrupts certificate and model records (a false claim, a moved uniqueness value, an unknown class, an unchecked lemma, positive-sum and witness mutants) and requires every false claim to be rejected {{test:tests/v1/test_object_mutants.py::test_no_unsound_mutant_is_accepted}}.

`reproduce.sh` runs both, but its filter drops the tallies (§3.11, Appendix J); this is the same command, run by the build, keeping them:

{{run:python -m pytest -q -s tests/v1/test_checker.py tests/v1/test_object_mutants.py | grep -E "killed|rejected|passed" @@ mask=in [0-9.]+s( [(][0-9:]+[)])?}}

Read: every non-equivalent mutant of the q11 RawOV trace, the q11 OV trace and the reachability trace is killed; on the object path, every record claiming something false was rejected (`rejected / claim False`), and the records accepted are ones whose claim is still true (`accepted / claim True`) or makes no claim (`accepted / claim None`). The masterplan's criterion, "0 unsound mutants accepted, including the object path", is met at this commit.

== Differential testing

{{badge:IMPLEMENTED}} `python -m openverifiers.bench.differential` generates random expressions in nine classes and compares the solver-side symbolic layer (sympy) with the trusted evaluator; a case is _refused_ when the trusted side declines to decide it (for example a nested root), and a _disagreement_ would be a bug on one side {{src:src/openverifiers/bench/differential.py}}. At the code commit, with seed 0: {{num:diff.cases}} cases, {{num:diff.agree}} agree, {{num:diff.refused}} refused, {{num:diff.disagree}} disagree. Since D-030 it also differential-tests the trusted additions: surd normal form {{num:diff.surd_normal_form.agree}}/{{num:diff.surd_normal_form.cases}} agree; positive sums {{num:diff.positive_sums.accepted}} accepted, {{num:diff.positive_sums.rejected}} rejected, {{num:diff.positive_sums.disagree}} wrong; ln derivatives {{num:diff.ln_derivatives.agree}} agree, {{num:diff.ln_derivatives.refused}} refused; exp derivatives {{num:diff.exp_derivatives.agree}} agree, {{num:diff.exp_derivatives.refused}} refused, {{num:diff.exp_derivatives.disagree}} disagree.

{{gen:diff_table}}

The refusal rate is highest for `sqrt` ({{num:diff.by_class.sqrt.refused:trusted}} of {{num:diff.by_class.sqrt.cases}}) and `pi` ({{num:diff.by_class.pi.refused:trusted}} of {{num:diff.by_class.pi.cases}}): refusals are the price of never guessing.

== The benchmark program

=== Suites, gold provenance, gold first, the ratchet

{{badge:IMPLEMENTED}} Seven suites under `benchmarks/`, each case a `case.ov` and a hand-written `expected.json` with a `why` for every query {{src:benchmarks/README.md:1-25}}. The rules (D-010, D-018):

- *gold is written by hand, never generated by running OV;*
- *gold first and alone*: a new case's gold is committed in a commit that touches nothing else, before OV runs on it; the gold gate checks the order over the history;
- *no gold edit without the founder's signed `Gold-Change-Approved-By`* (D-032);
- *the ratchet*: the failing set may only shrink. It is a test: `KNOWN_MISMATCHES` lists the two known failures and the suite fails if any other case fails {{src:tests/v1/test_bench.py:119-138}}.

The disclosed exception: `chemistry/q11` restates the brief's reference problem, so its gold cannot predate every OV run {{src:benchmarks/README.md:27-29}}.

{{fig:gold_first}}

*Results at the code commit* (`reproduce.sh` `bench/summary.csv`): {{num:bench.line}} (default); {{num:bench_strict.line}} (`--strict`).

{{gen:bench_table}}
{{fig:bench_chart}}

The two default failures are the two `KNOWN_MISMATCHES`: `mathematics/linear_system` (no linear-system solving at the rule layer) and `physics/push_block` (an UNKNOWN FIND does not name the missing facts, §7.2). Neither is a wrong answer; both are less informative answers than the gold asks for. The four additional `--strict` failures are verdicts that rest on `z3_unsat` turning into UNKNOWN.

=== The agentic, breadth and adversarial suites

- *Agentic* (22 cases): refund approvals, change tickets, two-person rules, PII exports, cross-tenant reads, plans that delete outside a workspace; 10 of them import the approved `agent.workflow` package ({{commit:85f8cf5}}). All pass, default and `--strict`. {{badge:IMPLEMENTED}} {{src:benchmarks/agentic}}
- *Breadth* (physics, chemistry, mathematics, geometry, logic; 35 cases): small problems that exercise one feature each (unit traps, closed-world inequality, syllogisms, default with exception). {{badge:IMPLEMENTED}} {{commit:98df202}}
- *Adversarial* (50 cases): contradictory facts, liar rules, non-stratifiable programs, unit traps (`mass_in_joules`), unknowns that must stay unknown (`unknown_allergy`), assumptions that must not leak (`assumed_approval`), budget exhaustion. All pass, with {{num:bench.suite.adversarial.false_proven}} false PROVEN. {{badge:IMPLEMENTED}} {{commit:e468103}}

The masterplan's v1 exit criterion 1 counts "agentic 20, breadth 35, adversarial 50" {{src:MASTERPLAN.md:309}}; the suites have 22, 35 and 50.

=== The JEE capability matrix

*How the problems were chosen.* {{badge:IMPLEMENTED}} The draw rule was committed before any paper was read: for each subject, number the questions of JEE Advanced 2025 Papers 1 and 2 in order, take positions $1, 1 + N, 1 + 2N, …$ with $N = floor(n slash 10)$, skip only figure-dependent or dropped questions (recorded), stop at 10 per subject {{src:benchmarks/exams/DRAW_RULE.md:1-30}}. Gold is NTA's official final answer key (`list.json`, committed first). Originals stay in the gitignored `private/`.

*Results at the code commit* (from `reproduce.sh`'s `exam.json` and `exam_strict.json`):

{{fig:jee}}
{{gen:jee_table}}

- *Default (drafts loaded):* {{num:exam.outcomes.solved}} solved, {{num:exam.outcomes.unknown}} unknown, {{num:exam.outcomes.not_formalized}} not formalized, *0 wrong*. {{num:exam.provisional}} solved answer is provisional (phys p2q3 uses the draft `physics.rotation` and carries the UNPROVEN N043 as an explicit assumption, per the founder's packet-3 reply).
- *`--strict` (no drafts, no `z3_unsat`):* {{num:exam_strict.outcomes.solved}} solved, {{num:exam_strict.outcomes.unknown}} unknown, {{num:exam_strict.outcomes.error}} error, *0 wrong*. The three math answers whose last step rests on z3 (p1q4, p1q10, p1q16) become UNKNOWN; phys p2q3 is an `error` because its draft package does not load under `--strict`.
- *Failure taxonomy* of the not-formalized and unknown (default): {{num:exam.categories.out_of_scope}} out of scope for v1, {{num:exam.categories.language}} language, {{num:exam.categories.library}} library, {{num:exam.categories.engine}} engine, {{num:exam.categories.not_attempted}} not attempted. Chapter 9 lists what blocks each.

The C7 exit report quoted `--strict` 8 solved; at `bd2ed44` it is {{num:exam_strict.outcomes.solved}}, because that commit recorded the packet-3 reply and fixed a checker crash {{commit:bd2ed44}} {{report:reports/V1_EXIT_C7_2026-11-23.md}}.

*JEE Main* (D-031) has no source: NTA's site refused automated access, and the founder's reply applies D-031b (v1 counts JEE Advanced 30 + agentic + breadth + adversarial; JEE Main and HSC become v1.1 tiers) {{report:reports/APPROVAL_RECORD_2026-11-23_packet3.md}}. {{badge:PLANNED}} {{mp:D-031, D-031b; v1.1 tier}}

=== Library theorems at `{kernel}`

From `ov audit` over every approved package, run by this build (`reproduce.sh` does not print this number): {{num:audit.kernel}} of {{num:audit.theorems}} theorems are PROVEN at `{kernel}` ({{num:audit.kernel_pct}}; criterion 4 asks for 60%); {{num:audit.proven}} are PROVEN at any trust. The C7 report counted 38/50 {{report:reports/V1_EXIT_C7_2026-11-23.md}}; the denominator grew when `physics.quantum` was approved in packet 3 ({{commit:7e45263}}). Appendix G lists every theorem.

{{gen:audits}}

== The faithfulness program

*What it is.* The kernel checks that conclusions follow from the formalization; the faithfulness program checks that the formalization says what the problem says (MP §8 Faithfulness) {{src:MASTERPLAN.md:436}}. Its layers:

#table(columns: (1.2fr, 2.6fr, 1fr),
  [*layer*], [*what it does*], [*status*],
  [scenarios hold only the givens], [F2 (no laws in a case), F3 (no stray package), F5 (no `assume` in an exam case)], [{{badge:IMPLEMENTED}} {{src:src/openverifiers/bench/faithfulness.py:6-20}}],
  [leaked-answer lint], [F1: the asked property set to a number], [{{badge:IMPLEMENTED}} {{src:src/openverifiers/bench/faithfulness.py:8-10}}],
  [gold-blind reviewer agent], [reads only the question, the case and the libraries; writes `faithfulness_review.json`], [{{badge:IMPLEMENTED}} {{src:benchmarks/exams/jee2025/jee2025-phys-p2q9/faithfulness_review.json}}],
  [`because:` on every invariant], [not in the grammar], [{{badge:PLANNED}} {{mp:D-020, MP §8}}],
  [`EXPLAIN --nl` for human comparison], [not built], [{{badge:PLANNED}} {{mp:v3 Lens, MP §8}}],
  [mistranslation cases in the adversarial suite], [`benchmarks/faithfulness/dropped_ball_negative_time`: a model without $t >= 0$ admits a second answer], [{{badge:PARTIAL}} {{src:benchmarks/faithfulness/dropped_ball_negative_time/review.json}}],
)

*What it has caught*, from the reports: the missing $t >= 0$ in `physics.mechanics` (found 2026-11-22; `ConstantAcceleration.elapsed` now states it, and the dropped-ball case was made a reviewer test) {{src:benchmarks/faithfulness/dropped_ball_negative_time/review.json}}; the reviewer's notes on math p1q7 ("a circle with centre c" encoded as "equidistant from c", necessary but not sufficient) and phys p2q9 (the conducting-sphere reading) {{src:reports/W3_JEE_CAPABILITY_2026-11-23.md:149-160}}; and the brief's own vacuous `Square.diagonals_equal`, which led to warning W202. At the code commit the lint reports {{num:faithfulness.line}} (§2.10 explains why warnings need the originals). Note that the dropped-ball case is not run by `ov bench` (it has `review.json`, not `expected.json`), and nothing runs the reviewer against it automatically.
