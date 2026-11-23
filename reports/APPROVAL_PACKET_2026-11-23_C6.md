# Approval packet 2 (C6), 2026-11-23 (D-024)

For the founder. It covers every meaning-carrying statement added or changed
since packet `c8c9af15519e`. One reply settles it; the agent records exactly
what the reply says and commits only what it approves. Read with MASTERPLAN.md
§9 and D-024..D-029.

**Suggested short reply:** "approve all STANDARD; B: approve fixes 1-9;
C (a)", plus any exceptions by id.

## Part A: draft statements (49)

A gold-blind, OV-blind reviewer (a Claude subagent that saw only the library
text) classified every statement now in `drafts/packages/`:
- 47 STANDARD;
- 2 DERIVABLE;
- 0 MODELLING;
- 0 SUSPECT.

They include:
- the reworked lines from packet 1: M126, M147/M152, M161, M168, M171;
- new libraries: `agent.workflow` (11 statements) and
  `math.vector_products` (3 statements).

The reworks of M126 (vdW excluded volume, now a theorem), M171
(Stefan–Boltzmann net flux, now a theorem from emission) and M161 (Bohr n and
Z as `Integer`) are now classified STANDARD.

**Not in Part A:** M168 (the lever torque) moved out of the library into the
JEE p2q3 case as a stated small-angle reading, as the reviewer recommended.

**What approval does:** a draft file whose statements are all approved moves to
`packages/` with the meaning trailer. If all STANDARD lines are approved, these
files move:
- `agent.workflow`;
- `chemistry.gases`;
- `math.vector_products`;
- `physics.electromagnetism`;
- `physics.gravitation`;
- `physics.thermal`.

`physics.quantum` (N039) and `physics.rotation` (N043) stay in `drafts/`.

| id | class | file:line | class (OV) | statement | reference | action | note |
|---|---|---|---|---|---|---|---|
| N039 | **DERIVABLE** | `drafts/packages/physics/quantum.ov:35` | BohrOrbit | `law orbit_radius: r * Z = n * n * a0` | NCERT Physics Class 12 Ch 12 (Bohr radius) | make theorem | Follows from quantization plus Coulomb-centripetal balance; needs those added first. |
| N043 | **DERIVABLE** | `drafts/packages/physics/rotation.ov:15` | AngularOscillator | `law small_oscillation: omega * omega * inertia = kappa` | HRW Ch 15 (torsion pendulum) | make theorem | Follows from I theta'' = -kappa theta; needs verified ODE solutions with trig. |
| N001 | **STANDARD** | `drafts/packages/agent/workflow.ov:31` | (package level) | `axiom by_approver(p: Plan, i: Number, r: Role): approved(p, i, r), approver(r) -> approval_given(p, i)` | policy framework (no textbook) | approve | Approval counts only when given by a designated approver. |
| N002 | **STANDARD** | `drafts/packages/agent/workflow.ov:32` | (package level) | `axiom forbidden_step(p: Plan, i: Number, t: Tool, x: Target): step(p, i, t, x), forbidden(t, x) -> violation(p, i)` | policy framework (no textbook) | approve | A forbidden call is a violation, named by step number. |
| N003 | **STANDARD** | `drafts/packages/agent/workflow.ov:34` | (package level) | `axiom unapproved_step(p: Plan, i: Number, t: Tool, x: Target): step(p, i, t, x), needs_approval(t), not approval_given(p, i) -> violation(p, i)` | policy framework (no textbook) | approve | An approval-requiring step without approval is a violation (stratified). |
| N004 | **STANDARD** | `drafts/packages/agent/workflow.ov:36` | (package level) | `axiom any_violation(p: Plan, i: Number): violation(p, i) -> violates(p)` | policy framework (no textbook) | approve | Any violating step makes the plan violate. |
| N005 | **STANDARD** | `drafts/packages/agent/workflow.ov:37` | (package level) | `axiom valid_plan(p: Plan): plan(p), not violates(p) -> valid(p)` | policy framework (no textbook) | approve | Valid = declared plan with no violation. |
| N006 | **STANDARD** | `drafts/packages/agent/workflow.ov:44` | (package level) | `axiom gate_refuse(t: Tool, x: Target): request(t, x), forbidden(t, x) -> refused(t, x)` | policy framework (no textbook) | approve | A forbidden requested call is refused. |
| N007 | **STANDARD** | `drafts/packages/agent/workflow.ov:45` | (package level) | `axiom gate_human(t: Tool, x: Target): request(t, x), not forbidden(t, x), needs_approval(t) -> needs_human(t, x)` | policy framework (no textbook) | approve | Not forbidden but needs approval: to a human. |
| N008 | **STANDARD** | `drafts/packages/agent/workflow.ov:47` | (package level) | `axiom gate_permit(t: Tool, x: Target): request(t, x), not forbidden(t, x), not needs_approval(t) -> permitted(t, x)` | policy framework (no textbook) | approve | Permit only when neither forbidden nor approval-requiring; outcomes exhaustive and exclusive. |
| N009 | **STANDARD** | `drafts/packages/agent/workflow.ov:60` | (package level) | `axiom reach_start(s: State): start(s) -> reach(s, nothing, 0)` | policy framework (no textbook) | approve | Start states reachable by the empty path. |
| N010 | **STANDARD** | `drafts/packages/agent/workflow.ov:61` | (package level) | `axiom reach_step(s: State, s2: State, p: Path, n: Number, m: Number, k: Number, t: Tool, x: Target): reach(s, p, n), horizon(k), n < k, transition(s, t, x, s2), not forbidden(t, x), not needs_approval(t), m = n + 1 -> reach(s2, then(p, t, x), m)` | policy framework (no textbook) | approve | Bounded search over freely permitted calls only. |
| N011 | **STANDARD** | `drafts/packages/agent/workflow.ov:64` | (package level) | `axiom reached_goal(s: State, p: Path, n: Number): reach(s, p, n), goal(s) -> solution(p)` | policy framework (no textbook) | approve | A path reaching a goal is a solution; the start state is not recorded (minor). |
| N012 | **STANDARD** | `drafts/packages/chemistry/gases.ov:15` | VanDerWaalsGas | `invariant positive: p > 0 temp > 0 R > 0 a > 0 b > 0` | Atkins Topic 1C | approve |  |
| N013 | **STANDARD** | `drafts/packages/chemistry/gases.ov:16` | VanDerWaalsGas | `invariant molar_volume_positive: vm > 0` | Atkins Topic 1C | approve |  |
| N014 | **STANDARD** | `drafts/packages/chemistry/gases.ov:17` | VanDerWaalsGas | `law van_der_waals: (p + a / (vm * vm)) * (vm - b) = R * temp` | NCERT Chemistry Class 11 Ch 5; Atkins Topic 1C | approve |  |
| N015 | **STANDARD** | `drafts/packages/chemistry/gases.ov:19` | VanDerWaalsGas | `theorem excluded_volume: vm > b` | Atkins Topic 1C | approve |  |
| N016 | **STANDARD** | `drafts/packages/chemistry/gases.ov:21` | VanDerWaalsGas | `theorem cubic_in_vm: (p * vm * vm + a) * (vm - b) = R * temp * vm * vm` | Atkins Topic 1C (cubic form) | approve |  |
| N017 | **STANDARD** | `drafts/packages/chemistry/gases.ov:38` | VanDerWaalsCubic | `invariant coefficients: c3 = p c2 = -(p * b + R * temp) c1 = a c0 = -(a * b)` | Atkins Topic 1C | approve |  |
| N018 | **STANDARD** | `drafts/packages/chemistry/gases.ov:39` | VanDerWaalsCubic | `theorem expansion: (p * V * V + a) * (V - b) - R * temp * V * V = c3 * V * V * V + c2 * V * V + c1 * V + c0` | Atkins Topic 1C | approve |  |
| N019 | **STANDARD** | `drafts/packages/math/vector_products.ov:18` | Cross | `invariant components: cx = ay * bz - az * by cy = az * bx - ax * bz cz = ax * by - ay * bx` | Stewart Calculus 12.4; HRW Ch 3 | approve |  |
| N020 | **STANDARD** | `drafts/packages/math/vector_products.ov:19` | Cross | `theorem orthogonal_to_a: ax * cx + ay * cy + az * cz = 0` | Stewart Calculus 12.4 | approve |  |
| N021 | **STANDARD** | `drafts/packages/math/vector_products.ov:20` | Cross | `theorem orthogonal_to_b: bx * cx + by * cy + bz * cz = 0` | Stewart Calculus 12.4 | approve |  |
| N022 | **STANDARD** | `drafts/packages/physics/electromagnetism.ov:22` | SpinningChargedShell | `invariant positive: R > 0 omega > 0` | Griffiths Ch 5 | approve |  |
| N023 | **STANDARD** | `drafts/packages/physics/electromagnetism.ov:23` | SpinningChargedShell | `invariant full_height: s = 2 * R` | Griffiths Ch 5 (integration limit) | approve |  |
| N024 | **STANDARD** | `drafts/packages/physics/electromagnetism.ov:24` | SpinningChargedShell | `invariant sum_of_rings: 4 * R * moment = charge * omega * integral(2 * R * s - s * s, s)` | Griffiths 5.4 (m = I a), hat-box slicing | approve |  |
| N025 | **STANDARD** | `drafts/packages/physics/electromagnetism.ov:25` | SpinningChargedShell | `theorem shell_moment: 3 * moment = charge * omega * R * R` | Griffiths Ch 5 | approve |  |
| N026 | **STANDARD** | `drafts/packages/physics/electromagnetism.ov:42` | SpinningSolidSphere | `invariant positive: rho > 0 R > 0 omega > 0` | HRW Ch 10 | approve |  |
| N027 | **STANDARD** | `drafts/packages/physics/electromagnetism.ov:43` | SpinningSolidSphere | `invariant outer_radius: r = R` | HRW Ch 10 (integration limit) | approve |  |
| N028 | **STANDARD** | `drafts/packages/physics/electromagnetism.ov:44` | SpinningSolidSphere | `invariant sum_of_shells_mass: mass = 4 * pi * rho * integral(r * r, r)` | HRW Ch 10 | approve |  |
| N029 | **STANDARD** | `drafts/packages/physics/electromagnetism.ov:45` | SpinningSolidSphere | `invariant sum_of_shells_spin: spin = 8 / 3 * pi * rho * omega * integral(r ^ 4, r)` | HRW Ch 10-11 | approve |  |
| N030 | **STANDARD** | `drafts/packages/physics/electromagnetism.ov:46` | SpinningSolidSphere | `theorem mass_positive: mass > 0` | HRW Ch 10 | approve |  |
| N031 | **STANDARD** | `drafts/packages/physics/electromagnetism.ov:47` | SpinningSolidSphere | `theorem sphere_spin: 5 * spin = 2 * mass * R * R * omega` | HRW Ch 10 (2/5 M R^2) | approve |  |
| N032 | **STANDARD** | `drafts/packages/physics/gravitation.ov:14` | CircularOrbit | `invariant positive: kepler > 0 r > 0 period > 0` | NCERT Physics Class 11 Ch 8 | approve |  |
| N033 | **STANDARD** | `drafts/packages/physics/gravitation.ov:15` | CircularOrbit | `law kepler_third: period * period * kepler = r * r * r` | NCERT Physics Class 11 Ch 8; HRW Ch 13 (Kepler constant GM/4pi^2, M >> m) | approve |  |
| N034 | **STANDARD** | `drafts/packages/physics/quantum.ov:12` | MatterWave | `invariant positive: h > 0 p > 0` | NCERT Physics Class 12 Ch 11 | approve |  |
| N035 | **STANDARD** | `drafts/packages/physics/quantum.ov:13` | MatterWave | `law de_broglie: wavelength * p = h` | NCERT Physics Class 12 Ch 11 | approve |  |
| N036 | **STANDARD** | `drafts/packages/physics/quantum.ov:21` | SlowParticle | `invariant mass_positive: m > 0` | NCERT Physics Class 12 Ch 11 | approve |  |
| N037 | **STANDARD** | `drafts/packages/physics/quantum.ov:22` | SlowParticle | `invariant kinetic_energy: p * p = 2 * m * energy` | NCERT Physics Class 12 Ch 11 (non-relativistic) | approve |  |
| N038 | **STANDARD** | `drafts/packages/physics/quantum.ov:34` | BohrOrbit | `invariant orbit_positive: n >= 1 Z >= 1 a0 > 0` | NCERT Physics Class 12 Ch 12 | approve |  |
| N040 | **STANDARD** | `drafts/packages/physics/quantum.ov:36` | BohrOrbit | `law angular_momentum: 2 * pi * p * r = n * h` | NCERT Physics Class 12 Ch 12 (second postulate) | approve |  |
| N041 | **STANDARD** | `drafts/packages/physics/quantum.ov:38` | BohrOrbit | `theorem standing_wave: n * wavelength = 2 * pi * r` | NCERT Physics Class 12 Ch 12 | approve |  |
| N042 | **STANDARD** | `drafts/packages/physics/rotation.ov:14` | AngularOscillator | `invariant positive: inertia > 0 kappa > 0 omega > 0` | HRW Ch 15 | approve |  |
| N044 | **STANDARD** | `drafts/packages/physics/thermal.ov:19` | BlackGap | `invariant constant_positive: sigma > 0` | NCERT Physics Class 11 Ch 11 | approve |  |
| N045 | **STANDARD** | `drafts/packages/physics/thermal.ov:20` | BlackGap | `invariant absolute: hot >= 0 cold >= 0` | NCERT Physics Class 11 Ch 11 | approve |  |
| N046 | **STANDARD** | `drafts/packages/physics/thermal.ov:21` | BlackGap | `law stefan_boltzmann_hot: emit_hot = sigma * hot ^ 4` | NCERT Physics Class 11 Ch 11; HRW Ch 18 | approve |  |
| N047 | **STANDARD** | `drafts/packages/physics/thermal.ov:22` | BlackGap | `law stefan_boltzmann_cold: emit_cold = sigma * cold ^ 4` | NCERT Physics Class 11 Ch 11; HRW Ch 18 | approve |  |
| N048 | **STANDARD** | `drafts/packages/physics/thermal.ov:23` | BlackGap | `invariant net_transfer: flux = emit_hot - emit_cold` | HRW Ch 18 (net exchange; idealised class) | approve |  |
| N049 | **STANDARD** | `drafts/packages/physics/thermal.ov:24` | BlackGap | `theorem net_flux: flux = sigma * (hot ^ 4 - cold ^ 4)` | NCERT Physics Class 11 Ch 11; HRW Ch 18 | approve |  |

## Part B: proposed fixes for the 9 unapproved statements in `packages/`

These were classified SUSPECT or MODELLING in packet 1, and they are still in
`packages/`, unapproved. Each fix below is a proposal. None is applied until
the founder approves it.

| # | id | file | now | proposed |
|---|---|---|---|---|
| 1 | M001 | `chem/organic.ov:64` | `axiom c5h10: isomer_of(C5H10) = {...10 constitutional isomers}` (closed world: denies stereoisomers) | rename the predicate `structural_isomer_of` (statement unchanged otherwise) |
| 2 | M013 | `chem/organic.ov:115` | `not alpha_h(p) -> not tautomerizes(p)` | `not alpha_h(p) -> not keto_enol_tautomerizes(p)` (only keto–enol is ruled out) |
| 3 | M032 | `chem/organic.ov:176` | tie rule when `side_h(s) = side_h(t)` | add `s != t` (a symmetric alkene gives one product, not a tie) |
| 4 | M033 | `chem/organic.ov:179` | Markovnikov major product, first site | add the premise `no_rearrangement(alkene)`, stated per scenario as an `assume` (hydride shifts) |
| 5 | M034 | `chem/organic.ov:183` | same, second site | as 4 |
| 6 | M036 | `chem/organic.ov:199` | `a = b -> not stereocentre(add(carbonyl(a, b), HCN))` | rename the predicate `not new_stereocentre(...)` (it speaks of the new carbinol carbon only) |
| 7 | M078 | `math/geometry.ov:36` | `invariant four: count(vertices) = 4` | add `invariant no_three_collinear: all v in subsets(vertices, 3): area(v) != 0`, or the existing `Triangle.proper` shape (exact form chosen at implementation, reviewed again) |
| 8 | M079 | `math/geometry.ov:41` | `Parallelogram.bisect` | no change needed once 7 holds (the collinear counterexample is excluded) |
| 9 | M108 | `physics/mechanics.ov:61` | `law weight: F = -m * g` | split into `property W: Force`, `law weight: W = m * g` and `invariant gravity_only: F = -W` (the idealisation is stated as the class's definition) |

## Part C: HSC sources

Option (b) yielded nothing. The ten official board domains were checked
read-only (C5 report §1):
- nine load;
- `educationboard.gov.bd` does not;
- none publishes HSC question papers, only results, forms and notices.

**Question:** may the HSC tier use (a), the founder's folder?
*Recommendation: yes. Without a source, HSC stays "not started" in the v1
exit report, and MP-v1 exit criteria 1 and 2 stay partial.*

## Part D: other decisions

1. **The trusted budget is used up.**
   - main 1,090 / 1,090;
   - `raw/formula.py` 408 / 410;
   - unit A 492 / 500;
   - total 1,990 / 2,000.

   What remains on D-029's list (π inside integrands, ln in the exp ring,
   surd-valued certificates, real algebraic numbers) all needs trusted lines.
   *Recommendation: keep 2,000 for v1. Ship v1 without these, and plan a
   trusted-code refactor (for example, shared helpers between
   `raw/formula.py` and `raw/certificate.py`) before v2 raises any cap.*
2. **10 in-scope JEE problems remain unformalized** (C4 report).
   *Recommendation: report them in the v1 capability report as they stand.*
3. **Theorem reuse in queries** (CTO decision 4) is noted for v2 in the exit
   report. *No action now.*

## Part A2: an example agent policy (4 statements)

`examples/policies/repo_policy.ov` is an example policy package for the
tool-call gate. I committed it there without approval (`3c29133`), and the
D-025 meaning gate caught it in CI. I tried to move it to `drafts/`, but the
gate counts removing meaning lines from its scope as a meaning change too, so
the move also needs your approval. The file stays where it is until you
decide. These are institutional rules (MP §4.1, `law` in the sense of a company
policy), not textbook statements. Nobody reviewed them; they are listed for
your decision.

**Decision A2:** either (a) approve P001 to P004 in place, or (b) approve moving
the file to `drafts/policies/` (the commit then carries your trailer for the
removal). *Recommendation: (b); an example policy should not be a library.*

| id | statement | recommended action |
|---|---|---|
| P001 | `axiom no_push_to_main: forbidden(push, main)` | per Decision A2 |
| P002 | `axiom no_deleting_main: forbidden(delete_branch, main)` | as P001 |
| P003 | `axiom deploy_needs_approval: needs_approval(deploy)` | as P001 |
| P004 | `axiom lead_approves: approver(lead)` | as P001 |
