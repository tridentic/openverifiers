= Component 4: OVProver <ch5>

*Intuition.* Chapters 2–4 describe a system that _checks_: you write the program, OV tells you what follows. The brief's fourth component inverts the direction: you write what you want (a target), and the prover writes a program (a plan, a set of assumptions, a construction) that achieves it, or as much of it as possible, and then hands that program to the same kernel to check. It is the most ambitious component, and at `bd2ed44` it is almost entirely design.

== What exists today, precisely

=== `target` syntax and type checking

{{badge:IMPLEMENTED}} `target name { must conj … prefer conj … }` is a top-level item {{src:src/openverifiers/lang/grammar.lark:43-45}}. The checker type-checks every literal in it against the loaded packages, in the global scope {{src:src/openverifiers/lang/check.py:395-398}}. Nothing else reads it: no lowering, no query, no command uses a target {{src:docs/LANGUAGE.md:187}}.

{{listing:docs/masterbook/examples/target.ov}}
{{run:ov run docs/masterbook/examples/target.ov}}

The target asks for a valid release; the draft plan is not valid (its deploy step needs an approval nobody gave), and OV says so, but it does not search for a plan that would satisfy the target. A target that names an undeclared predicate is rejected, which is the whole of its "type checking":

{{run:ov run docs/masterbook/examples/target_bad.ov @@ exit=1}}

Two things a prover will need are not there yet: the masterplan's separate `goal` construct (`must`/`minimize`/`maximize`/`prefer`/`priority`, for trade-offs) is not in the grammar at all {{src:MASTERPLAN.md:114-115}} {{mp:v2 Engine, MP §7 goal syntax}}, and nothing says which scenario or state a target is relative to (`PLAN FROM state TO target`) {{src:MASTERPLAN.md:201}}.

=== The search pieces that already work

These are the parts of OV that _search_ rather than check. Each is a building block a prover would use; none of them is a prover.

- *FIND over class patterns* (z3 + small-scope + exact re-check): finds instances satisfying a class's invariants, i.e. a construction that meets a specification (§7.3). {{badge:IMPLEMENTED}} {{test:tests/v1/test_objects.py::test_square_brief_example}}
- *Uniqueness and counterexample search*: PROVE UNIQUE blocks each found solution and re-solves; COUNTEREXAMPLE searches for an instance violating a theorem; both answer with checked evidence (§4.2). {{badge:IMPLEMENTED}} {{test:tests/v1/test_objects.py::test_false_theorem_is_refuted_with_a_checked_counterexample}}
- *Small-scope search*: Alloy-style enumeration of integer points in $[-4, 4]$ with a 10,000-node deterministic budget {{commit:839c1d5}}. {{badge:IMPLEMENTED}} {{src:src/openverifiers/objects/smallscope.py}}
- *Certificate search*: the sympy finder searches for ideal-membership and positive-sum certificates (§3.8). It proves; it does not plan. {{badge:IMPLEMENTED}} {{src:src/openverifiers/objects/certify.py}}
- *Bounded plan synthesis in `agent.workflow`*: `reach`/`solution` rules compute, by Datalog reachability, every sequence of permitted, approval-free tool calls that reaches a goal state within a horizon; the path is a term `then(then(nothing, t1, x1), t2, x2)`. {{badge:IMPLEMENTED}} {{src:src/openverifiers/packages/agent/workflow.ov:48-62}}

{{listing:src/openverifiers/packages/agent/workflow.ov:48-62}}
{{run:ov run tests/v1/workflow_repo.ov}}

The last answer is a synthesised plan: run the tests, open a PR, merge, avoiding the forbidden `push main`. This is the closest thing in the repository to "generate a program which satisfies the target", and it is worth being precise about how far it is from OVProver: the search space is spelled out as `transition` facts, the horizon is fixed, the target is a `goal` predicate rather than a `target` block, there is no notion of "satisfy the maximum", and it works only because Datalog enumerates all reachable states.

=== What is not built

{{badge:PLANNED}} Everything else in the brief's component 4 and the masterplan's v2 scope: backward chaining over an AND–OR graph, abduction of minimal assumptions, proposer plugins, scoring, gap reports, `PLAN FROM … TO …`, and "satisfy the maximum" {{mp:v2 Engine, MP §7 "OVProver PLAN with abduction and gap reports"}}.

== The design (masterplan v2)

Everything in this section is a design. The masterplan fixes the outline (MP §3 L7, §5.1 PLAN, §7 v2); the details below are how the pieces would fit the existing kernel, labelled as this book's reading where the masterplan is silent.

{{fig:prover}}

=== Backward chaining over an AND–OR graph

{{badge:PLANNED}} {{mp:v2 Engine, MP §7}} Start from each `must` literal $g$. An OR node for $g$ has one child per rule whose head unifies with $g$; an AND node for a rule instance has one child per body literal. A leaf is _closed_ if the current program derives it (the kernel already has its label), _open_ if nothing derives it. A solution is a sub-tree in which every AND node has all children and every OR node one child, and whose open leaves form the set of things to add. Closed-world `not` literals become _protected_ leaves: adding anything that derives them would break the plan.

=== Abduction of minimal assumptions

{{badge:PLANNED}} {{mp:v2 Engine, MP §7 "abduction"; D-016}} The open leaves of a solution are candidate assumptions. The prover will keep only _minimal_ sets $S$ (no proper subset also closes the tree) and check each by running the kernel on the program plus $S$ as `assume` facts. The existing labels make this cheap to verify: the label of a target literal over the extended program lists exactly the minimal environments that make it hold, the same machinery as `missing` (D-016's verified antichain).

=== Proposers

{{badge:PLANNED}} {{mp:v2 Engine, MP §3 L3}} Three kinds, all untrusted:

- *search*: exhaustive or best-first over the AND–OR graph within a deterministic node budget (D-015);
- *constraint*: z3, MaxSAT, OMT or MIP for numeric and combinatorial targets (the masterplan's L3 optimizers);
- *LLM*: an agent drafts candidate OV (lemmas, constructions, plans) from the gap report; MP-DOL makes it a proposer like any other.

=== Scoring

{{badge:PLANNED}} {{mp:v2 Engine, MP §5.1 OPTIMIZE; MP pushback 7}} Candidates that satisfy every `must` are ranked by `prefer` literals satisfied, number and kind of assumptions (a law-level assumption costs more than a fact), and size; with a `goal`, by its weights. Humans own the weights (MP pushback 7). "Satisfy the maximum" becomes: maximise the number (or weight) of `must` literals PROVEN, and report the rest in the gap report.

=== Gap reports

{{badge:PLANNED}} {{mp:v2 Engine, MP §7 "gap reports"}} For every `must` that no candidate proves, the report will name the blocked frontier: the open leaves, as source-level statements, with the alternatives that would close them (MP §8 Clarity: "every UNKNOWN names source-level facts, never internal atoms").

=== The boundary rule

{{badge:PLANNED}} {{mp:MP §3 "Proposers can't write truth"; MP-INV}} The prover is a proposer. It will never write OVState and never skip the kernel: its output is an OV program (or a set of `assume` lines), which `ov run` lowers, evaluates and checks like any other. A plan is reported as PROVEN only if the kernel proves every `must` on it; otherwise the answer is the gap report. This is the same rule that keeps z3 and sympy out of the trust base today.

== A worked design example (illustrative)

#honest[This section traces a target through the _planned_ algorithm by hand. Nothing here was computed by OVProver, which does not exist. The program and target are the real files `tests/v1/workflow_repo.ov` and `docs/masterbook/examples/target.ov`; the steps are the design above, applied on paper.]

*Target:* `must valid(release)`, `must not violates(release)`, `prefer step(release, 1, run_tests, feature)`, for the draft plan with only step 2 (`deploy prod`, which needs approval).

+ *OR node* `valid(release)`: one rule, `valid_plan: plan(p), not violates(p) -> valid(p)` {{src:src/openverifiers/packages/agent/workflow.ov:35}}. *AND node*: `plan(release)` (closed: a fact) and `not violates(release)` (protected).
+ `violates(release)` is currently derived through `unapproved_step` at step 2: `step(release, 2, deploy, prod)`, `needs_approval(deploy)`, `not approval_given(release, 2)`. To protect `not violates`, one body literal of that instance must fail. The candidates are: retract the step (a change to the plan), or make `approval_given(release, 2)` hold.
+ *OR node* `approval_given(release, 2)`: one rule, `by_approver: approved(p, i, r), approver(r)`. With `approver(lead)` given, the open leaf is `approved(release, 2, lead)`.
+ *Abduction* gives two minimal candidate sets: ${"approved(release, 2, lead)"}$ (an assumption a human must make true) and ${"remove step 2"}$ (a plan edit). Both close every `must`.
+ *Scoring*: neither satisfies the `prefer` literal; adding `step(release, 1, run_tests, feature)` is a plan edit that violates nothing, so both candidates are extended with it. The approval candidate keeps the deploy and costs one human assumption; the removal candidate costs no assumption but drops the deploy. The ranking is the humans' weights' call (MP pushback 7).
+ *Kernel check*: each candidate is written back as OV and run. The first is exactly `docs/masterbook/examples/whatif.ov`'s situation, which the kernel already answers PROVEN under `{signed_off}` (§4.2); the second is its WHAT IF RETRACT, PROVEN with no assumption.
+ *Output*: two plans, each with its trace and its assumptions, and an empty gap report.

The example shows why the masterplan puts OVProver after the kernel: every hard step (is the candidate correct? which assumptions does it really rest on?) is already a kernel query. What is missing is the search that proposes the candidates.

== Limitations and open questions

- The `target` block has no scenario or state attached, and cannot express optimisation goals.
- "Satisfy the maximum" needs a scoring rule the masterplan leaves to v2.
- Abduction over the object layer (constructions, not just facts) has no design yet.
- Performance: AND–OR search over packages the size of `chem.organic` will need the incremental evaluation the masterplan also schedules for v2 {{mp:v2 Engine, MP §7 incremental evaluation}}.
