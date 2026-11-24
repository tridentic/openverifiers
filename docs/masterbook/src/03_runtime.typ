= Component 2: the `ov` CLI, runtime and library <ch3>

== Every command, with a real run <cli>

*Intuition.* `ov` is a thin dispatcher: each subcommand calls one module, and every verdict it prints comes from the kernel.

{{badge:PARTIAL}} The dispatcher accepts `run`, `check`, `audit`, `gate`, `state`, `exam` and `bench` {{src:src/openverifiers/cli.py:39-66}}. Anything else, including the brief's form `ov program.ov --verbose`, prints "unknown command" and exits 2. There is no `ov query`, `ov lower`, `ov trace` or `ov explain`; the module docstring lists `lower`, `query` and `explain` as arriving "with their milestones" {{src:src/openverifiers/cli.py:24-25}}. The help texts are in Appendix C; several subcommands do not handle `--help` (Appendix J).

#table(columns: (1.1fr, 3.3fr, 0.9fr),
  [*command*], [*what it does*], [*status*],
  [`ov run F.ov … [--verbose] [--strict] [--no-reductions] [--drafts]`], [check, lower, evaluate, check the trace, answer the queries, check `expect` lines and class theorems; exit 1 on any failure {{src:src/openverifiers/runner.py:402-438}}], [{{badge:IMPLEMENTED}} {{test:tests/v1/test_lang.py::test_failed_expectation_is_reported}}],
  [`ov check F.ov …`], [the same work, one summary line per file (for loops and hooks)], [{{badge:IMPLEMENTED}} {{src:src/openverifiers/runner.py:384-399}}],
  [`ov audit PKG|FILE [--dag T] [--json]`], [axioms by kind, theorems with status and trust, ratios, dependency DAGs], [{{badge:IMPLEMENTED}} {{src:src/openverifiers/audit.py:1-24}}],
  [`ov state F.ov [--scenario S] [--out P]`], [write a scenario's checked model as an OVState], [{{badge:IMPLEMENTED}} {{test:tests/v1/test_state.py::test_export_import_round_trip}}],
  [`ov gate [--base REV] [--staged] [--drafts] [PATH…]`], [the commit gate (§3.11)], [{{badge:IMPLEMENTED}} {{src:src/openverifiers/gate.py:1-17}}],
  [`ov exam [DIR] [--strict] [--drafts] [--json]`], [run the drawn exam problems and report capability], [{{badge:IMPLEMENTED}} {{src:src/openverifiers/bench/exam.py}}],
  [`ov bench [DIR] [--suite S] [--case C] [--seeds N] [--out D] [--strict]`], [run the gold-first suites; write `results.jsonl`, `summary.csv`, `summary.md`], [{{badge:IMPLEMENTED}} {{src:src/openverifiers/bench/run.py}}],
)

`ov run` was shown on q11 in §1.5. `ov check` on the three example files:

{{run:ov check examples/chem/q11.ov examples/physics/newton2.ov examples/geometry/square.ov}}

`ov bench` on one suite (the full runs are part of `reproduce.sh`, ch. 6):

{{run:ov bench --suite logic --out docs/masterbook/build/work/bench-logic @@ mask=[0-9]+[.][0-9]+s}}

`ov gate` on a file:

{{run:ov gate examples/geometry/square.ov}}

== The library surface <library>

{{badge:PARTIAL}} There is no documented SDK at this commit (packet 3's work order item 4 asks for `docs/SDK.md` {{report:reports/APPROVAL_RECORD_2026-11-23_packet3.md}}). What exists is the set of Python functions the CLI and the tests call. The ones a caller needs:

#table(columns: (2fr, 3fr),
  [`openverifiers.runner.run_file(path, settings=…)`], [the whole pipeline for a file; returns `FileResult` with `answers`, `objects`, `classes`, `runs` {{src:src/openverifiers/runner.py:86-121}}],
  [`openverifiers.engine.run(program, budget)`], [evaluate a RawOV `Program` and check its trace; returns `Run(trace, model, blocked)` {{src:src/openverifiers/engine.py:36-39}}],
  [`openverifiers.engine.ask(run, atom, context)`], [a verdict, with the untrusted missing-facts frontier added to UNKNOWN {{src:src/openverifiers/engine.py:42-48}}],
  [`openverifiers.checker.verdict / find`], [trusted verdicts over a `CheckedModel` {{src:src/openverifiers/checker/verdict.py:108-155}}],
  [`openverifiers.rawtext.parse / dump`], [RawOV text in and out (untrusted convenience) {{src:src/openverifiers/rawtext.py:1-30}}],
  [`openverifiers.state.export.export`, `state.load.facts`], [OVState out and in {{src:src/openverifiers/state/export.py:20-29}}],
  [`openverifiers.paper.blueprints(result)`], [the OV-Paper hooks for theorems (v3 renders them) {{src:src/openverifiers/paper.py:1-25}}],
)

A real program using them (the build runs it):

{{gen:sdk}}

== The pipeline in depth: OV → RawOV → OVTrace → OVState <pipeline>

{{fig:pipeline}}

=== RawOV

*Definition* {{src:docs/SEMANTICS.md:10-35}} {{src:src/openverifiers/raw/program.py}}. {{badge:IMPLEMENTED}} A RawOV program is a 4-tuple $P = (W, F, D, R)$:

- $W$: world policies `world p open|closed` (open by default);
- $F$: ground facts, each with an origin `axiom:`, `fact:`, `import:`, `domain:` or `assume:name`;
- $D$: finite domains `domain d: pred(args) = {v1, …} complete|partial`, standing for the facts `pred(args, vi)`;
- $R$: rules $h arrow.l l_1, …, l_n$ where a body literal is a positive atom `p(t)` or `neg p(t)` (strong negation is a separate relation), `not a`, `X is e`, or a comparison `e1 op e2`.

Terms are symbols, strings, exact rational numbers with a dimension vector, variables and compound terms {{src:src/openverifiers/raw/terms.py:17-56}}. A program is well formed when ids are unique, facts are ground and every rule is _safe_ read left to right: positive literals bind variables; `not`, `is` and comparisons read only bound variables; `is` binds one fresh variable; every head variable is bound {{src:src/openverifiers/raw/program.py:176-232}}. The safety check surfaces in OV as E403.

*World-policy rewrite.* For an open predicate, `not p(t)` is rewritten to the positive literal `neg p(t)` (it must be _derived_ false), and `not neg p(t)` to `p(t)`; only closed-world `not` stays negation as failure {{src:src/openverifiers/raw/program.py:159-170}}.

=== Formats: canonical JSON

{{badge:IMPLEMENTED}} The trusted path reads programs and traces _only_ as canonical JSON, with the standard library's `json`, and every value has exactly one encoding {{src:src/openverifiers/raw/canon.py:1-17}}:

{{listing:src/openverifiers/raw/canon.py:7-14}}

The program document, as written for `push_block` (the first three rows of each list):

{{gen:program_json}}

An *OVTrace* is JSON lines: one header (`strata`, `complete` per stratum, `truncated` atoms) and one object per step with `id`, `kind`, `rule_id`, `subst`, `premises`, `naf` (each closed-world negation with the step of that atom's final label, or null for "absent"), `prev`, `conclusion`, `label`, `stratum` and `source_span` {{src:src/openverifiers/raw/trace.py:86-107}}. The labels example below prints a complete trace. An *OVState* is `{"sha256": …, "body": {"version": 1, "atoms": […]}}` (§3.9). Appendix D collects the three schemas.

=== The evaluator: semi-naive, stratified, budgeted

*Intuition.* Datalog evaluation repeats "fire every rule on what is known" until nothing new appears. Semi-naive evaluation only fires a rule when at least one of its premises is _new_ since the last round, which avoids re-deriving the same thing quadratically.

*Definition.* {{badge:IMPLEMENTED}} `kernel/evaluate.py` (untrusted) evaluates stratum by stratum. Within stratum $s$, with $Delta_k$ the atoms whose label grew in round $k$, a rule fires on a substitution only if some positive premise matches an atom in $Delta_k$ ({{src:src/openverifiers/kernel/evaluate.py:150-213}}). Each firing appends a trace step. The naive mode exists for differential testing ({{src:src/openverifiers/kernel/evaluate.py:214-218}}).

*Stratification.* {{badge:IMPLEMENTED}} An assignment $s$ from predicate keys to $NN$ must satisfy $s("head") >= s(b)$ for every positive body key and $s("head") > s(c)$ for every closed-world `not c`. `kernel/strata.py` finds the smallest such $s$ by Bellman-Ford-style relaxation; a value above the number of keys means a cycle through negation, reported with its path ({{src:src/openverifiers/kernel/strata.py:18-45}}). The adversarial suite has `non_stratifiable`, `liar_rule` and `winner_if_not_winner` cases for this.

*Budgets* (D-015). {{badge:IMPLEMENTED}} Deterministic limits on steps, atoms, term depth and label size, plus wall time as a backstop {{src:src/openverifiers/kernel/evaluate.py:51-57}}:

{{listing:src/openverifiers/kernel/evaluate.py:51-57}}

Exceeding any of them marks the current stratum incomplete and stops there; what was derived stays sound, and queries that depend on the incomplete strata become UNKNOWN(budget) {{src:docs/SEMANTICS.md:166-176}}.

=== Signed ATMS labels <labels>

*Intuition.* Instead of re-running the program for every combination of assumptions, OV computes _once_, for every atom, the exact set of assumption combinations under which it holds. That set is its label. Then "what if I drop assumption $a$?" is a lookup.

*Definitions* (`docs/SEMANTICS.md` §2, `raw/labels.py`). Let $A$ be the set of assumption names. A _literal_ is $a$ or $not a$ for $a in A$. An _environment_ $e$ is a consistent finite set of literals; write $"pos"(e)$ and $"neg"(e)$ for its positive and negative names. A _context_ is the set $C subset.eq A$ of active assumptions, and

$ C tack.r.double e quad <==> quad "pos"(e) subset.eq C and "neg"(e) inter C = emptyset. $

A _label_ $L$ is an antichain of environments under $subset.eq$ (no member contains another) with no inconsistent member. $L$ _holds_ in $C$ if some $e in L$ is satisfied by $C$. Facts that are not assumptions have $L = top = {emptyset}$; `assume a` has ${{a}}$; $bot = {}$. Writing $min$ for "drop inconsistent environments and supersets":

$ L_1 times.o L_2 = min{e_1 union e_2 : e_1 in L_1, e_2 in L_2} quad "(conjunction)" $
$ L_1 plus.o L_2 = min(L_1 union L_2) quad "(disjunction)" $
$ not L = min { {"flip"(ell_e) : e in L} : (ell_e)_(e in L) "with" ell_e in e } quad "(negation: minimal hitting sets, flipped)" $

{{src:src/openverifiers/raw/labels.py:37-78}}. Negation is the reason the labels are _signed_: closed-world `not wet` holds exactly in the contexts where `wet`'s label does not, and that set needs negative literals to describe.

*Label propagation.* Evaluate stratum by stratum; within a stratum take the least fixpoint of

$ "label"(h) supset.eq "label"(b_1) times.o dots.c times.o "label"(b_k) times.o not "label"(c_1) times.o dots.c times.o not "label"(c_m) $

over every ground rule instance $h arrow.l b_1..b_k, "not" c_1..c_m$ whose builtins hold, where each $"label"(c_j)$ is final because $c_j$ lives in a lower, complete stratum. The result has the property the whole design rests on {{src:docs/SEMANTICS.md:85-93}}:

#note[*Context independence.* For every $C subset.eq A$ and atom $p$: $"label"(p)$ holds in $C$ if and only if $p$ is in the stratified model of the program whose `assume:` facts are restricted to $C$. {{test:tests/v1/test_kernel.py::test_what_if_by_label_lookup_equals_rerun}} checks this against a full re-run on random programs.]

*Nogoods.* $N = min{e_1 union e_2 : e_1 in "label"(p), e_2 in "label"("neg" p)}$: the environments in which a contradiction holds.

*A worked example.* Two assumptions, `rain` and `sprinkler`; `wet` and `dry` are closed-world:

{{listing:docs/masterbook/examples/labels.rawov}}

The evaluator's trace, as written to the OVTrace file:

{{gen:labels_trace}}

Read it as equations. `wet(lawn)` first gets ${{"rain"}}$ (step 3), then step 4 adds ${{"sprinkler"}}$ with `prev = 3`: its cumulative label is ${{"rain"}, {"sprinkler"}}$. `dry(lawn)` needs `not wet(lawn)`, so its label is

$ not {{"rain"}, {"sprinkler"}} = {{not "rain", not "sprinkler"}} $

(the only hitting set of the two environments, flipped). `warn(lawn)` needs `slippery` and `not dry`; $not {{not "rain", not "sprinkler"}} = {{"rain"}, {"sprinkler"}}$, so `warn` holds exactly when it rains or the sprinkler is on.

{{fig:labels}}
{{fig:strata}}

Asking the checked model in four contexts (the build computes these with `checker.verdict`):

{{gen:labels_verdicts}}

`dry(lawn)` and `wet(lawn)` are closed-world, so "not derivable in this context, stratum complete" is REFUTED, and the environment shown is the one in which the negation holds. `slippery` and `warn` are open-world, so in the empty context they are not refuted: they are UNKNOWN(missing_facts), because they hold under other contexts and the verdict can name the assumption changes that would make them PROVEN.

=== Verdicts, formally <verdict-semantics>

For a ground query $q$ and context $C$ (by default $C = A$, every declared assumption active), `checker/verdict.py` returns the first that applies {{src:src/openverifiers/checker/verdict.py:108-135}} {{src:docs/SEMANTICS.md:117-137}}:

+ $"INCONSISTENT"("conflict_set") quad "if" exists n in N : C tack.r.double n$. The conflict set is the facts and assumptions used in one derivation of $p$ and one of $"neg" p$ for that nogood.
+ $"PROVEN"("proof", E) quad "if" exists E in "label"(q) : C tack.r.double E$ (the smallest such $E$ is reported, and its derivation is the proof).
+ $"REFUTED"("proof", E) quad "if" exists E in "label"("neg" q) : C tack.r.double E$; or, if $q$'s predicate is closed, its stratum is complete and $q$ is not PROVEN, REFUTED with `closed_world` (then some $E in not "label"(q)$ is satisfied).
+ $"UNKNOWN"("missing", "reason")$ otherwise, with reason `budget` if $q$'s or $"neg" q$'s stratum is incomplete or a label was truncated; `missing_facts` if $q$ holds under other contexts (then `missing` lists the assumption changes) or if the untrusted frontier search names stuck premises; else `open_world`.

{{fig:verdicts}}

INCONSISTENT is global: any satisfied nogood makes _every_ query INCONSISTENT, even an unrelated one {{src:KNOWN_LIMITATIONS.md:149-151}}. Confidence and source metadata never enter labels or verdicts.

=== Solvers and plugins: trusted for nothing

{{badge:IMPLEMENTED}} The object layer (`objects/`) uses three untrusted proposers {{src:src/openverifiers/objects/engine.py}}:

- *z3* finds models (instances, counterexamples) and says unsat. A model must be rational (or lifted into $QQ(pi)$ or surds) so that the trusted evaluator can re-check it exactly; an unsat is re-solved in a fresh solver but stays `z3_unsat` in the trust base unless a certificate replaces it.
- *sympy* (in `objects/certify.py`) searches for certificates: Gröbner-basis and pseudo-division for ideal membership, an exact LDL decomposition for sums of squares, factorisations into positive hypotheses, with deterministic budgets (at most 150 pseudo-divisions and 200 terms, {{commit:2e97802}}) {{src:src/openverifiers/objects/certify.py}}.
- *small-scope search* tries integer points in $[-4, 4]$ with a 10,000-node budget (a node count, so the result does not depend on machine speed) before z3, for questions that ask whether something exists {{src:src/openverifiers/objects/smallscope.py}}.

*Reductions* (`red:*`) shrink a theorem's unsat problem: fix the counterexample's ordering, try the negation without the invariants, drop implied invariants, pin a point by translation, inherit an ancestor's proof. They are argued sound in `docs/SEMANTICS.md` §7 and tested on random cases, not checked, so each one used is listed in the trust base {{src:docs/SEMANTICS.md:203-289}}. `--no-reductions` turns them all off.

#table(columns: (1fr, 2fr, 2fr),
  [*proposer*], [*what it may propose*], [*how the answer is re-checked*],
  [z3 (sat)], [a model], [substituted into every invariant by `raw/formula.py`; a failing model is never reported],
  [z3 (unsat)], [no model exists], [not re-checked unless a certificate is found: trust `z3_unsat`],
  [sympy finder], [a certificate], [`raw/certificate.py` normal form (§3.8)],
  [small-scope], [an integer instance], [the same exact re-check as a z3 model],
  [reductions], [a smaller unsat problem], [not checked; listed as `red:*`],
  [rule evaluator], [a trace], [`checker/check.py` (§3.7)],
)

=== The trusted checker <checker>

*What it verifies, step by step* (`checker/check.py`, {{src:src/openverifiers/checker/check.py:103-157}}). It reads the program and trace from JSON and accepts only if:

+ *valid strata*: the program is well formed and the claimed strata satisfy the stratification inequalities;
+ *local justification*, for each step in order: the instantiated head equals the conclusion; each instantiated body atom equals the conclusion of a premise step that occurs _earlier_; builtins hold; and the label equals $min("label"("prev") union times.o_i "label"("premise"_i) times.o not "final"(c_j))$ {{src:src/openverifiers/checker/check.py:172-262}};
+ *negation*: each `naf` reference names the final step of that atom, in a complete stratum;
+ *closure*: for every stratum claimed complete (with all lower strata complete and no truncated label), every rule instance over the final model yields an environment set already covered by its head's label, and every fact is present {{src:src/openverifiers/checker/check.py:301-327}}.

*Why that is enough* (the soundness sketch of `docs/SEMANTICS.md` §4, made informal in §6.1): by induction on trace position every environment in every label is entailed; closure makes complete strata a pre-fixpoint, so they contain the least labelled model, and local justification makes them contained in it; verdicts read only entailed environments or exact complete strata.

*The object-record checker* (`checker/objects.py`, Condition B) re-decides every JSON record behind an object-layer kernel verdict: a `model` record by evaluating every invariant on the instance, a `certificate` record with `raw/certificate.py`. The invariants, theorem and hypotheses come from the compiled class, never from the record, so a record cannot weaken what it claims; a lemma may be used only after its own certificate passed earlier in the run {{src:src/openverifiers/checker/objects.py:1-14}}.

*The trusted units, with live line counts* (D-030; the table is generated from `reproduce.sh`'s `tcb.txt`):

{{gen:tcb}}
{{fig:tcb_chart}}

*What it deliberately does not trust:* the parser and type checker, the lowering, the evaluator, z3, sympy, the small-scope search, the reductions, the frontier search behind `missing`, the RawOV text parser, the CLI, the gates and every benchmark tool. Each of these can make OV say UNKNOWN when it should not; none can make it say PROVEN alone. The exceptions are named in the trust base (`z3_unsat`, `red:*`) or in §6.1.

=== Certificates, with the mathematics <certificates>

*Intuition.* A solver that says "unsat" gives no reason. A certificate is the reason, in a form that is easy to check: polynomial identities that a few hundred lines of exact arithmetic can verify.

*The general shape* ({{src:src/openverifiers/raw/certificate.py:1-49}}). For a goal $L "op" R$ with op $in {=, >=}$ ($<=$ is flipped) under hypotheses $h_i$, a certificate supplies a multiplier $M$, ideal coefficients $c_i$, and weighted squares. The checker computes, in exact normal form,

$ T = M dot (L - R) - sum_i c_i (A_i - B_i) - sum_j w_j q_j^2 - sum_k w_k (product_(l in S_k) f_l) r_k^2 $

and accepts iff $T = 0$ identically {{src:src/openverifiers/raw/certificate.py:253-337}}. On any instance satisfying the hypotheses each $A_i - B_i = 0$, so $M (L - R) = sum w_j q_j^2 + dots.c >= 0$; then $M != 0$ gives $L = R$ and $M > 0$ gives $L >= R$.

#table(columns: (1.1fr, 3fr),
  [*kind*], [*what is checked*],
  [identity], [no hypotheses used: $L - R$ normalises to 0 (e.g. the decay rate law, §7.5)],
  [ideal membership], [$M (L - R) = sum_i c_i (A_i - B_i)$ with $M$ a product of hypotheses $f != 0$, $f > 0$, $f < 0$ (for an equation) or $f > 0$, $f < 0$ (for an inequality), and of closed constants whose sign the checker decides itself (e.g. $pi$)],
  [SOS / positive sums], [inequalities: squares $w q^2$ with $w >= 0$; squares weighted by stated positive hypotheses $w f_1 dots.c f_k q^2$ (D-027); and _positive sums_ joining the multiplier, $sum c f_1 dots.c f_k [q^2]$ with $c > 0$ decided by the checker and at least one term without a square, so the sum is $> 0$ (D-030)],
  [$QQ(pi)$], [$pi$ is an indeterminate of the ring; a closed constant such as $p(pi) slash q(pi)$ enters $M$ only after `raw/formula.py` decides its sign by enclosure (@fig-qpi)],
  [surds], [$sqrt(k)$ is an indeterminate reduced by $(sqrt(k))^2 = k$ ({{commit:788e599}}); a reduction by a relation the true value satisfies keeps every identity true of it],
  [exp/ln], [atoms $e^u$, $ln u$, $"inv"(u)$ with the derivation rules of §2.8.4; every $ln u$ and $1 slash u$ in the goal needs a _witness_ $u = c f_1 dots.c f_k e^(dots.c)$ with $c > 0$, and only then may the relation $u dot "inv"(u) - 1 = 0$ be used as an ideal generator (`@pos<i>`) ({{commit:6b46009}})],
  [induction], [for $sum_(i=1)^n E = F(n)$: $F(0) = 0$ and $F(n) - F(n-1) = E(n)$ by normal form, with hypotheses `isint(n)` and $n >= 0$],
  [uniqueness], [the goal is "the asked property equals the found value", e.g. $alpha = 5 slash 3$; the givens of the query are filled in from the compiled plan, not from the record ({{src:src/openverifiers/runner.py:124-131}}); then it is an ideal-membership certificate as above],
)

{{fig:cert_flow}}

*The $QQ(pi)$ sign decision, computed.* {{fig:qpi}}

The certificate behind a real uniqueness answer (JEE phys p2q9, §7.4), as the engine recorded it:

{{gen:records_excerpt}}

=== `trust_base` and `--strict` <strict>

{{badge:IMPLEMENTED}} Every verdict prints its trust base (D-011). The rules, from the code {{src:docs/OKQL.md:38-49}}:

#table(columns: (3fr, 2fr),
  [*verdict*], [*trust base*],
  [rule queries (PROVE, FIND, WHY, WHAT IF on rules)], [`{kernel}` (the checker accepted the trace)],
  [FIND with re-checked bindings; CHECK; REFUTED with a counterexample; a consistent class], [`{kernel}`],
  [a theorem or uniqueness with an accepted certificate], [`{kernel}`],
  [UNIQUE or COUNT whose completeness rests on z3], [`{kernel, z3_unsat}`],
  [a theorem proven by unsat with reductions], [`{z3_unsat, red:…}`],
  [UNKNOWN], [`{}`],
)

`--strict` turns every verdict whose trust base contains `z3_unsat` into UNKNOWN(plugin_unknown) and undeclared types (W201) into error E208. The square, default and strict:

{{run:ov run examples/geometry/square.ov --strict @@ exit=1}}

The FIND keeps its re-checked binding; the UNIQUE, which rested on z3's unsat for "no other solution", and the theorem `diagonals_equal`, which rested on z3 and three reductions, become UNKNOWN/UNPROVEN.

=== OVState: hashing, loading, import <ovstate>

*Intuition.* A checked model is valuable; OVState lets another program start from it. The danger is obvious: if a state file could inject "derived" truths, it would bypass the kernel. So a state is imported as _stated facts_, and the hash only proves the file was not altered, not that its content is true.

*Definition.* {{badge:IMPLEMENTED}} `ov state` keeps the atoms whose label contains $emptyset$ (true with no assumption) {{src:src/openverifiers/state/export.py:1-29}}. `state/hash.py` (trusted) sorts their canonical JSON, serialises the body with sorted keys and no spaces, and takes SHA-256, so equal sets of atoms give equal bytes {{src:src/openverifiers/state/hash.py:1-31}}. `state/load.py` (trusted) refuses a file unless it has exactly `sha256` and `body`, the version is 1, the recomputed hash matches, every atom is ground and the atoms are sorted; the atoms become facts with origin `import:<name>` {{src:src/openverifiers/state/load.py:22-44}}. D-030 restored the sortedness and groundness checks after C6 removed them to fit a cap ({{commit:b2cfdb5}}).

{{fig:state_life}}

The lifecycle, run for real. The files come from {{test:tests/v1/test_state.py::test_export_import_round_trip}}; the build writes them to `build/work/` (they are package files, so committing them would put meaning lines under the gate):

{{listing:tests/v1/test_state.py:18-37}}
{{run:ov state docs/masterbook/build/work/fam.ov --out docs/masterbook/build/work/fam.json}}
{{gen:state_excerpt}}
{{run:ov run docs/masterbook/build/work/use.ov}}

`ancestor(ann, cy)` is PROVEN in one step: it is an imported fact. `ancestor(cy, ann)` is REFUTED by the closed world, because `parent(cy, ann)` was only an assumption in `fam.ov` and was not exported. A copy with one name changed:

{{run:ov run docs/masterbook/build/work/use_tampered.ov @@ exit=1}}

*Why trust never rises on import.* An imported atom enters with the label $top$ and origin `import:kin`; it is a premise, not a conclusion, and the answers that use it name it in their proof. The trust base of a later answer is still `{kernel}`, meaning "the kernel checked every step from these premises"; the premises themselves are only as good as the run that produced them, which the hash identifies.

*What is not there.* {{badge:PARTIAL}} Only unconditional rule-layer atoms are saved: no rules, no labelled atoms, no object-layer results, no record of which program or commit produced the state. Querying a state by name (`… USING state`) is not built {{mp:MP §5.1 USING state}}.

== Gates and governance <gates>

=== The gold gate and the meaning gate

{{badge:IMPLEMENTED}} `bench/gold_gate.py` runs in CI on every push to `v1` and over the whole history in `reproduce.sh` {{src:src/openverifiers/bench/gold_gate.py:1-60}}. For each commit in a range it checks:

- *gold*: a commit that changes benchmark gold (`expected.json`, `list.json`, reviewer gold, `expect` lines in packages) needs a `Gold-Change-Approved-By` trailer; new gold must be committed _first and alone_, before any formalization of that case (D-010);
- *meaning*: a commit that changes a meaning-carrying line (§2.4) needs `Meaning-Approved-By` (D-023, D-025);
- *signatures* (D-032): a trailer counts only if its commit is signed with an SSH key listed in `.approvers/allowed_signers` under the principal `founder`, read from the _parent_ commit (so a commit cannot approve itself by adding a key); an unsigned commit carrying any approval trailer fails; `Ratifies:` on a signed approval commit clears earlier agent-stamped approvals {{src:docs/APPROVALS.md:1-36}}.

The whole-history result at the code commit: {{num:gold_gate.line}} ({{num:gold_gate.lines}} line of output).

{{fig:approvals}}

*The founder's flow* (D-032): the agent prepares `approval/<packet>` with the changes staged and a note in `approvals/`; the founder runs `scripts/founder_approve.sh <packet>` in their own terminal; the script shows the summary, asks y/N, makes one signed commit, runs the gate over the whole history and pushes. The script refuses agent and CI environments and non-interactive shells; `docs/APPROVALS.md` says plainly that this refusal is a speed bump and the real protection is the key's passphrase {{src:docs/APPROVALS.md:56-62}}. Approval records quote the founder's reply exactly ({{report:reports/APPROVAL_RECORD_2026-11-23_packet3.md}}).

=== `ov gate`: CLI, pre-commit, GitHub Action, MCP

{{badge:IMPLEMENTED}} `ov gate` checks every changed `.ov` file the way `ov check` does and, with `--base`, also runs the gold and meaning gates over `base..HEAD` {{src:src/openverifiers/gate.py:1-17}}. It is wired three ways:

{{listing:.pre-commit-hooks.yaml}}
{{listing:action.yml}}

and over MCP, where `check_files` runs it on paths an agent names {{src:src/openverifiers/mcp_gate.py:94-101}}.

=== The MCP tool-call gate

{{badge:IMPLEMENTED}} `python -m openverifiers.mcp_gate POLICY.ov` is a Model Context Protocol server on stdio (JSON-RPC 2.0, standard library only) with one decision tool, `check_tool_call(tool, target)`. For each call it builds a one-call scenario (`fact request(t, x)`) on the policy, runs the kernel, and answers `refused`, `needs_human`, `permitted` or `unknown`; a tool or target the policy does not name is `needs_human` with an empty trust base, never permitted by default {{src:src/openverifiers/mcp_gate.py:1-24}} {{test:tests/v1/test_mcp_gate.py::test_gate_decides_tool_calls_by_the_policy}}. A real session (input `docs/masterbook/inputs/mcp_session.jsonl`):

{{run:python -m openverifiers.mcp_gate drafts/policies/repo_policy.ov --drafts @@ stdin=docs/masterbook/inputs/mcp_session.jsonl}}

{{fig:mcp}}

The decisions carry `"provisional": []` although `repo_policy.ov` is an unapproved draft: the provisional marker only recognises `drafts/packages/`, not `drafts/policies/` (Appendix J). §7.6 shows the proofs.

=== `reproduce.sh`

{{badge:IMPLEMENTED}} One script regenerates every number of the reports (MP-v1 exit 6) {{src:reproduce.sh}}. At the code commit it ran in about {{num:repro.minutes}} minutes on the build machine. One of its steps loses information: the mutant tallies are printed by the tests on a line that starts with dots, and the script keeps only lines starting with `{`, so `mutants.txt` holds only "{{num:mutants.raw}}" (Appendix J; ch. 6 runs the tests directly to show the tallies).

== Performance

{{badge:PARTIAL}} The masterplan's targets are `ov check` p95 under 300 ms for rule scenarios and under 2 s for objects, q11 under 1 s, an incremental re-check under 100 ms and 10k facts under 5 s {{src:MASTERPLAN.md:437}}. What is measured:

- `ov bench` records per-case wall time; over all 107 cases the default run had p50 {{num:bench.suite.all.p50_s}} s and p95 {{num:bench.suite.all.p95_s}} s, the slowest suite being geometry (p95 {{num:bench.suite.geometry.p95_s}} s) and chemistry (p95 {{num:bench.suite.chemistry.p95_s}} s) (from `reproduce.sh`'s `bench/summary.csv`).
- The wall-clock tests (10k facts, q11, `ov check` p95) are marked `bench` and run in a separate uninstrumented CI job; `reproduce.sh` does not run them. The build runs them:

{{run:python -m pytest -q -m bench tests/v1 @@ mask=in [0-9.]+s}}

What drives the numbers: rule scenarios are dominated by the Python evaluator and the checker's closure pass (both linear-ish in trace size for these programs); object queries by z3 and the sympy certificate search. Incremental evaluation is not built {{mp:v2 Engine, MP §7 incremental evaluation}}, so every query re-runs from scratch; retracting a _fact_ (not an assumption) re-runs the program {{src:KNOWN_LIMITATIONS.md:155-157}}.
