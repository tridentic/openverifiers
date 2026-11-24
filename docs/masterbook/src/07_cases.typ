= Case studies <ch7>

Six problems, end to end. Every listing, output and diagram below was produced by the build from the real files. Each case shows the source, a RawOV excerpt (or, for the object layer, the compiled class it is checked against), the proof diagram, the verdict with its trust base, and the cause-and-effect chain in plain language.

== q11: organic chemistry, with WHAT IF

{{badge:IMPLEMENTED}} {{test:tests/v1/test_q11.py::test_q11_what_if_retract_not_tautomerizes}}

*Source:* `examples/chem/q11.ov`, shown in full in §1.5. *RawOV:* the candidate and elimination rules, also in §1.5, and their dependency graph:

{{fig:lower_q11}}

*Verdicts:* {{run:ov run examples/chem/q11.ov}}

*Proof DAG of the first answer*, read back from the OVTrace file. Blue nodes are facts (from `chem.organic` and the scenario); every label is `{}`: no assumption.

{{fig:dag_q11}}

*Cause and effect, in words.* Ozonolysis of 2-methylbut-1-ene gives methanal and butanone (rule `ozonolysis_cleaves`, made unordered by `ozonolysis.unordered`); that combination survives every elimination (methanal does not tautomerize; butanone's Grignard alcohol is tertiary); it is the only survivor, so `ov.value.q11.A` is 2-methylbut-1-ene, and the query rule picks it up.

*The refutation* of optical activity (27 steps): butanone + HCN has a stereocentre (`hcn_stereocentre`), but butanone is achiral (methyl and ethyl are achiral groups) and the attack is planar, so the product is racemic (`planar_attack`) and racemic mixtures are not optically active (`racemic_inactive`):

{{fig:dag_q11_ref}}

*WHAT IF.* Retracting `not tautomerizes(D)` turns off the hidden assumption `fact#q11.L6C3`; the elimination that removed 2-methylbut-2-ene (whose ozonolysis gives ethanal, which tautomerizes) no longer fires, two candidates for A survive, and the answer is UNKNOWN with both listed. Trust: `{kernel}` for the three definite answers; `{}` for the UNKNOWN.

== The incline: assumption retraction leading to UNKNOWN

#note[The masterplan's incline (`scenario incline … assume frictionless(ramp)`, MP §4.2) is an illustration in the plan, not a file in the repository. The real case with the same structure is `benchmarks/physics/push_block`: a block pushed on a floor, under the assumption that the floor is frictionless {{src:MASTERPLAN.md:138-143}}.]

{{badge:PARTIAL}} {{src:benchmarks/physics/push_block/case.ov}}

*Source:*

{{listing:benchmarks/physics/push_block/case.ov}}

*RawOV excerpt* (the scenario's items; the assumption is a fact with origin `assume:frictionless`):

{{lower:assume}}

*Verdicts:* {{run:ov run benchmarks/physics/push_block/case.ov --verbose}}

*Proof DAG:* every step after the assumption carries the label `{{frictionless}}`.

{{fig:dag_push}}

*Cause and effect.* On a frictionless floor the push is the net force (`smooth`), so Newton's second law solved for mass gives $10 "N" slash 2 "m/s"^2 = 5 "kg"$, and the answer says it rests on `{frictionless}`. Retract the assumption and only the `rough` rule could give the net force; it needs `mu(floor)` and `normal_force(block)`, which nobody stated.

*What is missing from the answer.* The gold for the second query says UNKNOWN(missing_facts) with `missing: mu, normal_force` {{src:benchmarks/physics/push_block/expected.json}}. OV answers UNKNOWN(open_world) with no `missing` list, because the missing-facts frontier is computed for PROVE, not for FIND. This is one of the two known benchmark mismatches in the ratchet {{src:tests/v1/test_bench.py:119-122}}; the answer is not wrong, but it is less useful than the gold asks. Trust: `{kernel}` for the PROVEN; `{}` for the UNKNOWN.

== The square's fourth vertex: FIND → re-check → block → unsat → UNIQUE

{{badge:IMPLEMENTED}} {{test:tests/v1/test_objects.py::test_square_brief_example}}

*Source:* `examples/geometry/square.ov` (the brief's §3.7 example, with the theorem rewritten):

{{listing:examples/geometry/square.ov:6-29}}

*Compiled form* (the object layer is checked against compiled formulas, not RawOV):

{{lower:pattern}}

*Verdicts:* {{run:ov run examples/geometry/square.ov --verbose}}

{{fig:find_seq}}
{{fig:dag_square}}

*Cause and effect.* z3 proposes $(3, 5)$; the trusted evaluator substitutes it and checks every invariant of `Square` (four distinct vertices; some cyclic ordering with equal positive sides and right angles), exactly, in rationals: the FIND is PROVEN at `{kernel}`. To claim uniqueness, the engine adds "$?p != (3, 5)$" and asks z3 again: unsat, confirmed in a fresh solver. That unsat is _not_ checked by trusted code, so UNIQUE carries `{kernel, z3_unsat}`, and `--strict` turns it into UNKNOWN (§3.8). The class theorem `diagonals_equal` is proven by z3 with three reductions (`red:fix_order`, `red:no_invariants`, `red:translate`): it holds even without the invariants once the counterexample's ordering is fixed and a point is pinned.

== One JEE problem at `{kernel}`, with its uniqueness certificate

{{badge:IMPLEMENTED}} {{src:benchmarks/exams/jee2025/jee2025-phys-p2q9/case.ov}}

*The problem* (JEE Advanced 2025, paper 2, physics Q9): a conducting solid sphere of radius $R$, mass $M$ and charge $Q$ spins at angular speed $omega$; the ratio of its magnetic moment to its angular momentum is $alpha Q slash (2M)$; find $alpha$. Official answer: 1.65 to 1.67.

*Source* (the case states only the givens; the physics is in `physics.electromagnetism`, approved):

{{listing:benchmarks/exams/jee2025/jee2025-phys-p2q9/case.ov}}

*Compiled class*, with the component invariants of the shell and the solid sphere added as `Comp.inv@Owner.prop`:

{{lower:jee}}

*Verdict*, under `--strict`:

{{run:ov run benchmarks/exams/jee2025/jee2025-phys-p2q9/case.ov --verbose --strict}}

{{fig:dag_jee}}

*The certificate*, as recorded and re-checked by `checker/objects.py`:

{{gen:records_excerpt}}

*Cause and effect.* z3's first model has floating-looking rationals for the solid sphere and fails the trusted re-check (its integrals involve $pi$); the untrusted lifter rewrites the model in $QQ(pi)$, and the re-check passes with $alpha = 5 slash 3$. Uniqueness: the certificate shows that the invariants _imply_ $alpha = 5 slash 3$: a multiplier built from positive hypotheses (charge $> 0$, radii and masses positive) times $(alpha - 5 slash 3)$ equals a combination of the invariants, as an exact identity in the normal form. So no other $alpha$ is possible, and the trust base is `{kernel}` even under `--strict`. In physics terms: the shell's moment is $Q omega R^2 slash 3$, the solid sphere's angular momentum is $2 M R^2 omega slash 5$, and their ratio is $(5 slash 3) Q slash (2M)$; 5/3 ≈ 1.667 is inside the official range. The gold-blind reviewer flagged the one reading a human must confirm: "conducting" means the charge sits on the surface {{src:benchmarks/exams/jee2025/jee2025-phys-p2q9/faithfulness_review.json}}.

== The decay law: an ODE closed form via the exp ring

{{badge:IMPLEMENTED}} {{test:tests/v1/test_forall_ode.py::test_verified_ode_solutions_in_three_domains}}

*Source* (a test fixture in three domains; no approved package uses `exp` at this commit):

{{listing:tests/v1/transcendental.ov}}

*Compiled class:*

{{lower:decay}}

*Verdicts:* {{run:ov run tests/v1/transcendental.ov --verbose}}

{{fig:dag_decay}}

*Cause and effect.* The theorem `rate_law` says $dif / (dif t) (N_0 e^(-k t)) = -k N_0 e^(-k t)$. In the trusted normal form $e^(-k t)$ is an atom $E$ with $dif E slash dif t = -k E$ (chain rule); the left side normalises to $-k N_0 E$, the right side to the same polynomial, and the certificate is an identity: `{kernel}`. The numeric FIND $N(5) = 1000 e^(-1 slash 2)$ is answered by a rigorous enclosure, $606.5306597 plus.minus 1.8 times 10^(-56)$, also `{kernel}`. The second theorem, $N > 0$, has no certificate (the finder found none), so it rests on `z3_unsat`. And the class's _consistency_ is UNKNOWN: the witness search cannot pick transcendental values {{src:KNOWN_LIMITATIONS.md:224-225}}.

The same ring with `ln` ({{commit:6b46009}}) proves three more closed forms, all at `{kernel}`:

{{run:ov run tests/v1/ln_ring.ov}}

== An agent tool-call gate decision

{{badge:IMPLEMENTED}} {{test:tests/v1/test_mcp_gate.py::test_gate_decides_tool_calls_by_the_policy}}

*Source:* the policy (a draft, `drafts/policies/repo_policy.ov`) and the approved package rules it relies on:

{{listing:drafts/policies/repo_policy.ov}}
{{listing:src/openverifiers/packages/agent/workflow.ov:37-46}}

*RawOV* of the one-call scenario the gate builds (`mcp_gate.py` builds this source text; the build lowers it the same way):

{{gen:mcp_rawov}}

*Decisions* (the MCP session of §3.11):

{{run:python -m openverifiers.mcp_gate drafts/policies/repo_policy.ov --drafts @@ stdin=docs/masterbook/inputs/mcp_session.jsonl}}

*Forbidden:* `push` to `main` is refused.

{{fig:dag_mcp}}

*Allowed:* `open_pr` on `feature` is permitted.

{{fig:dag_mcp_ok}}

*Cause and effect.* `refused(push, main)` follows from `gate_refuse`: the request exists and `forbidden(push, main)` is an axiom of the policy (`no_push_to_main`). `permitted(open_pr, feature)` follows from `gate_permit`: the request exists, and both `forbidden(open_pr, feature)` and `needs_approval(open_pr)` are _not derivable_ in the closed world (the dashed nodes are closed-world negations: the trace records each as absent, and the checker verifies the absence against a complete lower stratum). `deploy prod` needs a human because `deploy_needs_approval`; `rm_rf home` is not named by the policy at all, so the gate answers `needs_human` _without_ claiming a kernel verdict (trust `[]`). The rule each decision falls under is the rule at the bottom of its proof. One caveat: the policy is an unapproved draft, and the replies do not say so (`"provisional": []`, Appendix J).
