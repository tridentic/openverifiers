# Approval packet, 2026-11-23 (D-024)

For the founder. One reply settles everything here; the agent records exactly
what the reply says and commits only what it approves. Nothing in this packet
is approved by an agent. Read with MASTERPLAN.md §9 (approvals) and D-024..D-028.

**Suggested short reply:** "approve all STANDARD; B yes; C (a)" plus any
exceptions by id (for example "except M118").

## Part A: meaning lines (171 statements)

A gold-blind, OV-blind reviewer (a Claude subagent that saw only the library
text, never a verdict, an answer or a test) classified every meaning-carrying
statement in `src/openverifiers/packages/` and `drafts/packages/`:

| class | count | meaning |
|---|---|---|
| DERIVABLE | 7 | a result stated as a law or invariant: it must become a theorem (D-025) |
| MODELLING | 2 | an idealisation that belongs in a scenario as an `assume` |
| SUSPECT | 10 | wrong, too broad, missing a condition, or a unit problem |
| STANDARD | 152 | a correct textbook statement, with a named reference |

By origin:
- 66 pending lines from before the gate (the 71-line list);
- 58 earlier statements in `packages/`, never approved;
- 47 draft statements in `drafts/`.

The 71-line list counts physical lines; here a statement spanning several
lines is one row. References name a textbook and chapter or section. The
reviewer gave no page numbers, because it could not check them.

**What approval does.**
- An approved `packages/` line is committed with
  `Meaning-Approved-By: founder (reply to packet <hash>)`.
- An approved `drafts/` file moves into `packages/` in the same commit.
- A draft file that still contains a non-approved line stays in `drafts/`.
- A DERIVABLE, MODELLING or SUSPECT line is not proposed for approval as it
  stands. The action column says what the agent will do instead, and the
  reworked line comes back in the next packet.

| id | class | file:line | class (OV) | statement | reference | recommended action | note |
|---|---|---|---|---|---|---|---|
| M126 | **DERIVABLE** | `drafts/packages/chemistry/gases.ov:16` | VanDerWaalsGas | `invariant excluded_volume: vm > b` | Atkins, Physical Chemistry, Topic 1C.2 | make theorem | Follows from van_der_waals with p > 0, a > 0, R temp > 0. |
| M147 | **DERIVABLE** | `drafts/packages/physics/electromagnetism.ov:24` | SpinningChargedShell | `invariant sum_of_rings: 4 * R * moment = charge * omega * integral(2 * R * s - s * s, s)` | Griffiths, Electrodynamics, Ch 5 §5.4.3 (m = I a) | make theorem | Correct, but bakes in hat-box slicing, ring current and m = I pi rho^2; derive from a ring-moment law. |
| M152 | **DERIVABLE** | `drafts/packages/physics/electromagnetism.ov:45` | SpinningSolidSphere | `invariant sum_of_shells_spin: spin = 8 / 3 * pi * rho * omega * integral(r ^ 4, r)` | HRW Ch 10 Table 10-2 (thin shell 2/3 MR^2); Ch 11 L = I omega | make theorem | Presupposes thin-shell inertia and L = I omega, both derived results. |
| M156 | **DERIVABLE** | `drafts/packages/physics/gravitation.ov:15` | CircularOrbit | `law kepler_third: period * period * kepler = r * r * r` | HRW Ch 13, Kepler's laws | make theorem | Follows from GMm/r^2 = m omega^2 r; same constant needs m << M. |
| M162 | **DERIVABLE** | `drafts/packages/physics/quantum.ov:34` | BohrOrbit | `law orbit_radius: r * Z = n * n * a0` | NCERT Physics XII Ch 12, Bohr model | make theorem | From Coulomb force as centripetal force plus quantization. |
| M166 | **DERIVABLE** | `drafts/packages/physics/rotation.ov:15` | AngularOscillator | `law small_oscillation: omega * omega * inertia = kappa` | HRW Ch 15, angular SHO | make theorem | From tau = I alpha with tau = -kappa theta (needs ODE support). |
| M171 | **DERIVABLE** | `drafts/packages/physics/thermal.ov:17` | BlackGap | `law stefan_boltzmann: flux = sigma * (hot ^ 4 - cold ^ 4)` | HRW Ch 18, Radiation (P = sigma eps A T^4) | make theorem | Net exchange follows from sigma T^4 emission; the library law should be j = sigma T^4. |
| M108 | **MODELLING** | `packages/physics/mechanics.ov:61` | UniformGravity | `law weight: F = -m * g` | NCERT Physics Class 11, weight W = mg; HRW Ch 5 | fix: split 'only gravity acts' (idealisation) from the law W = mg | Conflates W = mg with the free-fall assumption. |
| M168 | **MODELLING** | `drafts/packages/physics/rotation.ov:25` | SpringOnLever | `law lever_torque: kappa = k * d * d` | HRW Ch 7; Ch 10 Torque | move to scenario assume | Small-angle linearization of k d^2 sin cos; small-angle condition missing. |
| M001 | **SUSPECT** | `packages/chem/organic.ov:64` | (package level) | `axiom c5h10: isomer_of(C5H10) = {pent-1-ene, pent-2-ene, 2-methylbut-1-ene, 3-methylbut-1-ene, 2-methylbut-2-ene, cyclopentane, methylcyclobutane, ethylcyclopropane, 1,1-dimethylcyclopropane, 1,2-dimethylcyclopropane}` | NCERT Chemistry Class 11 Part 2, Hydrocarbons, Isomerism | fix: rename to structural_isomer_of (or add stereoisomers) | A closed-world isomer_of wrongly says stereoisomers do not exist. |
| M013 | **SUSPECT** | `packages/chem/organic.ov:115` | (package level) | `axiom no_enol(p: Molecule): not alpha_h(p) -> not tautomerizes(p)` | NCERT Chemistry Class 12, Aldehydes, Ketones and Carboxylic Acids, alpha-hydrogen | fix: rename to keto_enol_tautomerizes or restrict to carbonyls | No alpha-H rules out keto-enol tautomerism only, not every tautomerism. |
| M032 | **SUSPECT** | `packages/chem/organic.ov:176` | (package level) | `axiom tie(s, t: Side, r: Reagent, cond: Condition): molecule(alkene(s, t)), regime(r, cond), side_h(s) = side_h(t) -> not has_single_major(add(alkene(s, t), r, cond))` | NCERT Chemistry Class 11 Part 2, Hydrocarbons, symmetric vs unsymmetric alkenes | fix: add s != t | False for symmetric alkenes (but-2-ene): one product. |
| M033 | **SUSPECT** | `packages/chem/organic.ov:179` | (package level) | `axiom major_first(a, b, d, e: Group, r: Reagent, cond: Condition, x: Element): molecule(alkene(side(a, b), side(d, e))), x_site(add(alkene(side(a, b), side(d, e)), r, cond)) = first, halogen(r) = x -> major(add(alkene(side(a, b), side(d, e)), r, cond)) = halide(x, c(a, b, c(h, d, e)))` | Clayden, Organic Chemistry, carbocation rearrangements | fix: exclude rearranging cations or make no-rearrangement an explicit assume | 3-methylbut-1-ene + HX rearranges; that alkene is in the library's list. |
| M034 | **SUSPECT** | `packages/chem/organic.ov:183` | (package level) | `axiom major_second(a, b, d, e: Group, r: Reagent, cond: Condition, x: Element): molecule(alkene(side(a, b), side(d, e))), x_site(add(alkene(side(a, b), side(d, e)), r, cond)) = second, halogen(r) = x -> major(add(alkene(side(a, b), side(d, e)), r, cond)) = halide(x, c(d, e, c(h, a, b)))` | Clayden, carbocation rearrangements | fix: as M033 |  |
| M036 | **SUSPECT** | `packages/chem/organic.ov:199` | (package level) | `axiom hcn_no_stereocentre(a, b: Group): molecule(carbonyl(a, b)), a = b -> not stereocentre(add(carbonyl(a, b), HCN))` | NCERT Chemistry Class 12, Haloalkanes and Haloarenes, Optical isomerism | fix: add achiral_group(a) or rename | Chiral groups a could still carry stereocentres. |
| M078 | **SUSPECT** | `packages/math/geometry.ov:36` | Quadrilateral | `invariant four: count(vertices) = 4` | NCERT Mathematics Class 9, Quadrilaterals | fix: add no-three-collinear condition | Four distinct points alone admit collinear sets. |
| M079 | **SUSPECT** | `packages/math/geometry.ov:41` | Parallelogram | `invariant bisect: exists v in cycles(vertices): v[0].x + v[2].x = v[1].x + v[3].x v[0].y + v[2].y = v[1].y + v[3].y` | NCERT Mathematics Class 9, Quadrilaterals | fix: add non-degeneracy | (0,0),(1,0),(3,0),(2,0) satisfy it. |
| M122 | **SUSPECT** | `packages/physics/mechanics.ov:101` | BodyPair | `law newton3: b2.F = -b1.F` | NCERT Physics Class 11 Part 1, Laws of Motion; HRW Ch 5/9 | fix: add an explicit isolation invariant | b.F is the net force; action-reaction needs an isolated pair, never stated. |
| M161 | **SUSPECT** | `drafts/packages/physics/quantum.ov:33` | BohrOrbit | `invariant orbit_positive: n >= 1 Z >= 1 a0 > 0` | NCERT Physics XII Ch 12, Bohr model | fix: declare n and Z as positive integers | n = 1.5 would count as a valid orbit. |
| M002 | **STANDARD** | `packages/chem/organic.ov:85` | (package level) | `axiom generated(f: Formula, m: Molecule): isomer_of(f, m) -> molecule(m)` | Definitional bookkeeping (no chemical content) | approve | Closure of the molecule domain. |
| M003 | **STANDARD** | `packages/chem/organic.ov:91` | (package level) | `axiom ozonolysis_cleaves(a, b, d, e: Group): molecule(alkene(side(a, b), side(d, e))) -> ozonolysis(alkene(side(a, b), side(d, e)), carbonyl(a, b), carbonyl(d, e))` | NCERT Chemistry Class 11 Part 2, Hydrocarbons, Ozonolysis | approve | Correct for reductive workup only; consider naming it reductive_ozonolysis. |
| M004 | **STANDARD** | `packages/chem/organic.ov:94` | (package level) | `axiom ozonolysis_products(m, p, r: Molecule): ozonolysis(m, p, r) -> molecule(p), molecule(r)` | Definitional bookkeeping (no chemical content) | approve |  |
| M005 | **STANDARD** | `packages/chem/organic.ov:95` | (package level) | `axiom carbonyl_groups(a, b: Group): molecule(carbonyl(a, b)) -> group(a), group(b)` | Definitional bookkeeping (no chemical content) | approve |  |
| M006 | **STANDARD** | `packages/chem/organic.ov:96` | (package level) | `axiom subgroups(x, y, z: Group): group(c(x, y, z)) -> group(x), group(y), group(z)` | Definitional bookkeeping (no chemical content) | approve |  |
| M007 | **STANDARD** | `packages/chem/organic.ov:104` | (package level) | `axiom alpha_h_first(y, z, b: Group): molecule(carbonyl(c(h, y, z), b)) -> alpha_h(carbonyl(c(h, y, z), b))` | NCERT Chemistry Class 12, Aldehydes, Ketones and Carboxylic Acids, alpha-hydrogen | approve |  |
| M008 | **STANDARD** | `packages/chem/organic.ov:106` | (package level) | `axiom alpha_h_second(a, y, z: Group): molecule(carbonyl(a, c(h, y, z))) -> alpha_h(carbonyl(a, c(h, y, z)))` | NCERT Chemistry Class 12, Aldehydes, Ketones and Carboxylic Acids, alpha-hydrogen | approve |  |
| M009 | **STANDARD** | `packages/chem/organic.ov:108` | (package level) | `axiom hydrogen_has_no_alpha: group(h) -> no_alpha_h_group(h)` | NCERT Chemistry Class 12, Aldehydes, Ketones and Carboxylic Acids, alpha-hydrogen | approve | Aldehydic H is not alpha. |
| M010 | **STANDARD** | `packages/chem/organic.ov:109` | (package level) | `axiom carbon_without_h(x, y, z: Group): group(c(x, y, z)), x != h -> no_alpha_h_group(c(x, y, z))` | NCERT Chemistry Class 12, Aldehydes, Ketones and Carboxylic Acids, alpha-hydrogen | approve | Relies on h-first term order; document it. |
| M011 | **STANDARD** | `packages/chem/organic.ov:111` | (package level) | `axiom no_alpha_h(a, b: Group): molecule(carbonyl(a, b)), no_alpha_h_group(a), no_alpha_h_group(b) -> not alpha_h(carbonyl(a, b))` | NCERT Chemistry Class 12, Aldehydes, Ketones and Carboxylic Acids, Cannizzaro (no alpha-H) | approve |  |
| M012 | **STANDARD** | `packages/chem/organic.ov:114` | (package level) | `axiom keto_enol(p: Molecule): alpha_h(p) -> tautomerizes(p)` | NCERT Chemistry Class 12, Aldehydes, Ketones and Carboxylic Acids, keto-enol tautomerism | approve |  |
| M014 | **STANDARD** | `packages/chem/organic.ov:121` | (package level) | `axiom grignard_methanal: molecule(carbonyl(h, h)) -> grignard_alcohol(carbonyl(h, h)) = primary` | NCERT Chemistry Class 12, Alcohols, Phenols and Ethers, Grignard reagents | approve | HCHO gives a primary alcohol. |
| M015 | **STANDARD** | `packages/chem/organic.ov:123` | (package level) | `axiom grignard_aldehyde(x, y, z: Group): molecule(carbonyl(h, c(x, y, z))) -> grignard_alcohol(carbonyl(h, c(x, y, z))) = secondary` | NCERT Chemistry Class 12, Alcohols, Phenols and Ethers, Grignard reagents | approve |  |
| M016 | **STANDARD** | `packages/chem/organic.ov:125` | (package level) | `axiom grignard_ketone(p, q, r, x, y, z: Group): molecule(carbonyl(c(p, q, r), c(x, y, z))) -> grignard_alcohol(carbonyl(c(p, q, r), c(x, y, z))) = tertiary` | NCERT Chemistry Class 12, Alcohols, Phenols and Ethers, Grignard reagents | approve |  |
| M017 | **STANDARD** | `packages/chem/organic.ov:137` | (package level) | `axiom regiochemistry: markov(HCl, none), markov(HCl, peroxide), markov(HBr, none), anti(HBr, peroxide)` | NCERT Chemistry Class 11 Part 2, Hydrocarbons, peroxide (Kharash) effect | approve | HBr only. |
| M018 | **STANDARD** | `packages/chem/organic.ov:139` | (package level) | `axiom halogens: halogen(HCl) = cl, halogen(HBr) = br` | Composition of HCl, HBr | approve |  |
| M019 | **STANDARD** | `packages/chem/organic.ov:140` | (package level) | `axiom markov_regime(r: Reagent, cond: Condition): markov(r, cond) -> regime(r, cond)` | Definition | approve |  |
| M020 | **STANDARD** | `packages/chem/organic.ov:141` | (package level) | `axiom anti_regime(r: Reagent, cond: Condition): anti(r, cond) -> regime(r, cond)` | Definition | approve |  |
| M021 | **STANDARD** | `packages/chem/organic.ov:142` | (package level) | `axiom x_on_first(a, b, d, e: Group, r: Reagent, cond: Condition, x: Element): molecule(alkene(side(a, b), side(d, e))), regime(r, cond), halogen(r) = x -> halide(x, c(a, b, c(h, d, e))) in add(alkene(side(a, b), side(d, e)), r, cond)` | NCERT Chemistry Class 11 Part 2, Hydrocarbons, addition of HX | approve |  |
| M022 | **STANDARD** | `packages/chem/organic.ov:145` | (package level) | `axiom x_on_second(a, b, d, e: Group, r: Reagent, cond: Condition, x: Element): molecule(alkene(side(a, b), side(d, e))), regime(r, cond), halogen(r) = x -> halide(x, c(d, e, c(h, a, b))) in add(alkene(side(a, b), side(d, e)), r, cond)` | NCERT Chemistry Class 11 Part 2, Hydrocarbons, addition of HX | approve |  |
| M023 | **STANDARD** | `packages/chem/organic.ov:157` | (package level) | `axiom alkene_sides(s, t: Side): molecule(alkene(s, t)) -> side_known(s), side_known(t)` | Definitional bookkeeping (no chemical content) | approve |  |
| M024 | **STANDARD** | `packages/chem/organic.ov:158` | (package level) | `axiom two_h: side_known(side(h, h)) -> side_h(side(h, h)) = 2` | Structural H count | approve |  |
| M025 | **STANDARD** | `packages/chem/organic.ov:159` | (package level) | `axiom one_h(x, y, z: Group): side_known(side(h, c(x, y, z))) -> side_h(side(h, c(x, y, z))) = 1` | Structural H count | approve |  |
| M026 | **STANDARD** | `packages/chem/organic.ov:161` | (package level) | `axiom no_h(p, q, r, x, y, z: Group): side_known(side(c(p, q, r), c(x, y, z))) -> side_h(side(c(p, q, r), c(x, y, z))) = 0` | Structural H count | approve |  |
| M027 | **STANDARD** | `packages/chem/organic.ov:163` | (package level) | `axiom markov_first(s, t: Side, r: Reagent, cond: Condition): molecule(alkene(s, t)), markov(r, cond), side_h(s) < side_h(t) -> x_site(add(alkene(s, t), r, cond)) = first` | NCERT Chemistry Class 11 Part 2, Hydrocarbons, Markovnikov rule | approve |  |
| M028 | **STANDARD** | `packages/chem/organic.ov:166` | (package level) | `axiom markov_second(s, t: Side, r: Reagent, cond: Condition): molecule(alkene(s, t)), markov(r, cond), side_h(t) < side_h(s) -> x_site(add(alkene(s, t), r, cond)) = second` | NCERT Chemistry Class 11 Part 2, Hydrocarbons, Markovnikov rule | approve |  |
| M029 | **STANDARD** | `packages/chem/organic.ov:169` | (package level) | `axiom anti_first(s, t: Side, r: Reagent, cond: Condition): molecule(alkene(s, t)), anti(r, cond), side_h(s) > side_h(t) -> x_site(add(alkene(s, t), r, cond)) = first` | NCERT Chemistry Class 11 Part 2, Hydrocarbons, peroxide effect | approve |  |
| M030 | **STANDARD** | `packages/chem/organic.ov:172` | (package level) | `axiom anti_second(s, t: Side, r: Reagent, cond: Condition): molecule(alkene(s, t)), anti(r, cond), side_h(t) > side_h(s) -> x_site(add(alkene(s, t), r, cond)) = second` | NCERT Chemistry Class 11 Part 2, Hydrocarbons, peroxide effect | approve |  |
| M031 | **STANDARD** | `packages/chem/organic.ov:175` | (package level) | `axiom single_major(rx: Reaction, s: Site): x_site(rx) = s -> has_single_major(rx)` | Definition | approve |  |
| M035 | **STANDARD** | `packages/chem/organic.ov:197` | (package level) | `axiom hcn_stereocentre(a, b: Group): molecule(carbonyl(a, b)), a != b -> stereocentre(add(carbonyl(a, b), HCN))` | NCERT Chemistry Class 12, Aldehydes, Ketones and Carboxylic Acids, HCN addition; NCERT Chemistry Class 12, Haloalkanes and Haloarenes, Optical isomerism | approve |  |
| M037 | **STANDARD** | `packages/chem/organic.ov:201` | (package level) | `axiom h_achiral: group(h) -> achiral_group(h)` | Definition | approve |  |
| M038 | **STANDARD** | `packages/chem/organic.ov:202` | (package level) | `axiom achiral_xy(x, y, z: Group): group(c(x, y, z)), x = y, achiral_group(x), achiral_group(z) -> achiral_group(c(x, y, z))` | NCERT Chemistry Class 12, Haloalkanes and Haloarenes, Optical isomerism | approve |  |
| M039 | **STANDARD** | `packages/chem/organic.ov:204` | (package level) | `axiom achiral_yz(x, y, z: Group): group(c(x, y, z)), y = z, achiral_group(x), achiral_group(y) -> achiral_group(c(x, y, z))` | NCERT Chemistry Class 12, Haloalkanes and Haloarenes, Optical isomerism | approve |  |
| M040 | **STANDARD** | `packages/chem/organic.ov:206` | (package level) | `axiom achiral_carbonyl(a, b: Group): molecule(carbonyl(a, b)), achiral_group(a), achiral_group(b) -> achiral(carbonyl(a, b))` | NCERT Chemistry Class 12, Haloalkanes and Haloarenes, Optical isomerism | approve |  |
| M041 | **STANDARD** | `packages/chem/organic.ov:208` | (package level) | `axiom planar_attack(p: Molecule): stereocentre(add(p, HCN)), achiral(p) -> racemic(add(p, HCN))` | NCERT Chemistry Class 12, Haloalkanes and Haloarenes, Optical isomerism; racemisation | approve | Assumes achiral reagent and medium. |
| M042 | **STANDARD** | `packages/chem/organic.ov:210` | (package level) | `axiom racemic_inactive(p: Molecule): racemic(add(p, HCN)) -> not optically_active(add(p, HCN))` | NCERT Chemistry Class 12, Haloalkanes and Haloarenes, Optical isomerism, racemic mixture | approve |  |
| M043 | **STANDARD** | `packages/chem/organic.ov:211` | (package level) | `axiom achiral_inactive(p: Molecule): not stereocentre(add(p, HCN)), achiral(p) -> not optically_active(add(p, HCN))` | NCERT Chemistry Class 12, Haloalkanes and Haloarenes, Optical isomerism | approve |  |
| M044 | **STANDARD** | `packages/math/calculus.ov:17` | Cubic | `theorem power_rule_2: deriv(t * t, t) = 2 * t` | Stewart, Calculus §3.1 power rule | approve |  |
| M045 | **STANDARD** | `packages/math/calculus.ov:18` | Cubic | `theorem power_rule_3: deriv(t * t * t, t) = 3 * t * t` | Stewart, Calculus §3.1 | approve |  |
| M046 | **STANDARD** | `packages/math/calculus.ov:19` | Cubic | `theorem constant_rule: deriv(c0, t) = 0` | Stewart, Calculus §3.1 | approve |  |
| M047 | **STANDARD** | `packages/math/calculus.ov:20` | Cubic | `theorem linearity: deriv(c2 * t * t + c1 * t, t) = c2 * deriv(t * t, t) + c1 * deriv(t, t)` | Stewart, Calculus §3.1 | approve |  |
| M048 | **STANDARD** | `packages/math/calculus.ov:21` | Cubic | `theorem product_rule: deriv((c0 + c1 * t) * (c2 + c3 * t), t) = c1 * (c2 + c3 * t) + (c0 + c1 * t) * c3` | Stewart, Calculus §3.2 product rule | approve |  |
| M049 | **STANDARD** | `packages/math/calculus.ov:24` | Cubic | `theorem ftc_derivative_of_integral: deriv(integral(c0 + c1 * t + c2 * t * t + c3 * t * t * t, t), t) = c0 + c1 * t + c2 * t * t + c3 * t * t * t` | Stewart, Calculus §5.3 FTC part 1 | approve |  |
| M050 | **STANDARD** | `packages/math/calculus.ov:27` | Cubic | `theorem ftc_integral_of_derivative: integral(deriv(c1 * t + c2 * t * t + c3 * t * t * t, t), t) = c1 * t + c2 * t * t + c3 * t * t * t` | Stewart, Calculus §5.3 FTC part 2 | approve |  |
| M051 | **STANDARD** | `packages/math/calculus.ov:30` | Cubic | `theorem integral_power_2: integral(t * t, t) = t * t * t / 3` | Stewart, Calculus §5.3-5.4 | approve |  |
| M052 | **STANDARD** | `packages/math/calculus.ov:39` | QuadraticExtremum | `invariant leading: a != 0` | NCERT Mathematics Class 10, Quadratic Equations | approve |  |
| M053 | **STANDARD** | `packages/math/calculus.ov:40` | QuadraticExtremum | `invariant stationary: deriv(a * t * t + b * t + c, t) = 0` | Stewart, Calculus §4.1 | approve |  |
| M054 | **STANDARD** | `packages/math/calculus.ov:41` | QuadraticExtremum | `theorem vertex: 2 * a * t = -b` | NCERT Mathematics Class 12, Application of Derivatives | approve |  |
| M055 | **STANDARD** | `packages/math/calculus.ov:42` | QuadraticExtremum | `theorem vertex_value: a * (a * t * t + b * t + c) * 4 = 4 * a * c - b * b` | NCERT Mathematics Class 12, Application of Derivatives | approve |  |
| M056 | **STANDARD** | `packages/math/calculus.ov:50` | LinearArea | `theorem trapezoid: integral(m * t + k, t) = t * (k + (m * t + k)) / 2` | Stewart, Calculus §5.2 | approve | Signed area. |
| M057 | **STANDARD** | `packages/math/core.ov:20` | QuadraticRoot | `invariant leading: a != 0` | NCERT Mathematics Class 10, Quadratic Equations | approve |  |
| M058 | **STANDARD** | `packages/math/core.ov:21` | QuadraticRoot | `invariant root: a * x * x + b * x + c = 0` | NCERT Mathematics Class 10, Quadratic Equations | approve |  |
| M059 | **STANDARD** | `packages/math/core.ov:23` | QuadraticRoot | `theorem completed_square: (2 * a * x + b) * (2 * a * x + b) = b * b - 4 * a * c` | NCERT Mathematics Class 10, Quadratic Equations | approve |  |
| M060 | **STANDARD** | `packages/math/core.ov:24` | QuadraticRoot | `theorem real_root_discriminant: b * b - 4 * a * c >= 0` | NCERT Mathematics Class 10, Quadratic Equations | approve |  |
| M061 | **STANDARD** | `packages/math/core.ov:34` | QuadraticRoots | `invariant leading: a != 0` | NCERT Mathematics Class 10, Quadratic Equations | approve |  |
| M062 | **STANDARD** | `packages/math/core.ov:35` | QuadraticRoots | `invariant root1: a * x1 * x1 + b * x1 + c = 0` | NCERT Mathematics Class 10, Quadratic Equations | approve |  |
| M063 | **STANDARD** | `packages/math/core.ov:36` | QuadraticRoots | `invariant root2: a * x2 * x2 + b * x2 + c = 0` | NCERT Mathematics Class 10, Quadratic Equations | approve |  |
| M064 | **STANDARD** | `packages/math/core.ov:37` | QuadraticRoots | `invariant distinct: x1 != x2` | NCERT Mathematics Class 10, Quadratic Equations | approve |  |
| M065 | **STANDARD** | `packages/math/core.ov:38` | QuadraticRoots | `theorem vieta_sum: a * (x1 + x2) = -b` | NCERT Mathematics Class 10, Quadratic Equations | approve |  |
| M066 | **STANDARD** | `packages/math/core.ov:39` | QuadraticRoots | `theorem vieta_product: a * x1 * x2 = c` | NCERT Mathematics Class 10, Quadratic Equations | approve |  |
| M067 | **STANDARD** | `packages/math/core.ov:40` | QuadraticRoots | `theorem positive_discriminant: b * b - 4 * a * c > 0` | NCERT Mathematics Class 10, Quadratic Equations | approve |  |
| M068 | **STANDARD** | `packages/math/core.ov:48` | NonNegativePair | `invariant a_nonneg: a >= 0` | Definition | approve |  |
| M069 | **STANDARD** | `packages/math/core.ov:49` | NonNegativePair | `invariant b_nonneg: b >= 0` | Definition | approve |  |
| M070 | **STANDARD** | `packages/math/core.ov:51` | NonNegativePair | `theorem am_gm: (a + b) * (a + b) >= 4 * a * b` | Hardy, Littlewood, Polya, Inequalities, Ch 2 | approve |  |
| M071 | **STANDARD** | `packages/math/core.ov:52` | NonNegativePair | `theorem am_gm_equality: (a + b) * (a + b) = 4 * a * b -> a = b` | Hardy, Littlewood, Polya, Ch 2 | approve |  |
| M072 | **STANDARD** | `packages/math/core.ov:58` | RealPair | `theorem square_nonneg: (a - b) * (a - b) >= 0` | Apostol, Calculus Vol 1, order axioms | approve |  |
| M073 | **STANDARD** | `packages/math/core.ov:59` | RealPair | `theorem two_squares: a * a + b * b >= 2 * a * b` | Apostol, Calculus Vol 1, order axioms | approve |  |
| M074 | **STANDARD** | `packages/math/geometry.ov:21` | Triangle | `invariant three: count(vertices) = 3` | Definition | approve |  |
| M075 | **STANDARD** | `packages/math/geometry.ov:23` | Triangle | `invariant proper: exists v in cycles(vertices): (v[1].x - v[0].x) * (v[2].y - v[0].y) - (v[2].x - v[0].x) * (v[1].y - v[0].y) != 0` | NCERT Mathematics Class 12, Determinants, area of a triangle | approve |  |
| M076 | **STANDARD** | `packages/math/geometry.ov:28` | RightTriangle | `invariant right: exists v in cycles(vertices): angle(v[0], v[1], v[2]) = 90 deg` | Definition | approve |  |
| M077 | **STANDARD** | `packages/math/geometry.ov:29` | RightTriangle | `theorem pythagoras: none v in cycles(vertices): angle(v[0], v[1], v[2]) = 90 deg dist2(v[0], v[2]) != dist2(v[0], v[1]) + dist2(v[1], v[2])` | NCERT Mathematics Class 10, Triangles, Pythagoras | approve |  |
| M080 | **STANDARD** | `packages/math/geometry.ov:44` | Parallelogram | `theorem opposite_sides: none v in cycles(vertices): v[0].x + v[2].x = v[1].x + v[3].x v[0].y + v[2].y = v[1].y + v[3].y dist(v[0], v[1]) != dist(v[2], v[3])` | NCERT Mathematics Class 9, Quadrilaterals | approve |  |
| M081 | **STANDARD** | `packages/math/geometry.ov:51` | Rectangle | `invariant right: exists v in cycles(vertices): all i: angle(v[i-1], v[i], v[i+1]) = 90 deg` | NCERT Mathematics Class 9, Quadrilaterals | approve |  |
| M082 | **STANDARD** | `packages/math/geometry.ov:52` | Rectangle | `theorem diagonals_equal: none v in cycles(vertices): all i: angle(v[i-1], v[i], v[i+1]) = 90 deg dist(v[0], v[2]) != dist(v[1], v[3])` | NCERT Mathematics Class 9, Quadrilaterals | approve |  |
| M083 | **STANDARD** | `packages/math/geometry.ov:58` | Rhombus | `invariant sides: exists v in cycles(vertices): all i: dist(v[i], v[i+1]) = dist(v[0], v[1]) > 0` | NCERT Mathematics Class 9, Quadrilaterals | approve |  |
| M084 | **STANDARD** | `packages/math/geometry.ov:60` | Rhombus | `theorem diagonals_perpendicular: none v in cycles(vertices): all i: dist(v[i], v[i+1]) = dist(v[0], v[1]) > 0 (v[2].x - v[0].x) * (v[3].x - v[1].x) + (v[2].y - v[0].y) * (v[3].y - v[1].y) != 0` | NCERT Mathematics Class 9, Quadrilaterals | approve |  |
| M085 | **STANDARD** | `packages/math/geometry.ov:67` | Square | `theorem diagonals_equal: none v in cycles(vertices): all i: angle(v[i-1], v[i], v[i+1]) = 90 deg dist(v[0], v[2]) != dist(v[1], v[3])` | NCERT Mathematics Class 9, Quadrilaterals | approve | Duplicate of Rectangle.diagonals_equal; could be dropped. |
| M086 | **STANDARD** | `packages/math/geometry.ov:70` | Square | `theorem diagonals_perpendicular: none v in cycles(vertices): all i: dist(v[i], v[i+1]) = dist(v[0], v[1]) > 0 (v[2].x - v[0].x) * (v[3].x - v[1].x) + (v[2].y - v[0].y) * (v[3].y - v[1].y) != 0` | NCERT Mathematics Class 9, Quadrilaterals | approve | Duplicate of Rhombus.diagonals_perpendicular; could be dropped. |
| M087 | **STANDARD** | `packages/math/geometry.ov:74` | Square | `theorem diagonal_length: none v in cycles(vertices): all i: dist(v[i], v[i+1]) = dist(v[0], v[1]) > 0 all i: angle(v[i-1], v[i], v[i+1]) = 90 deg dist2(v[0], v[2]) != 2 * dist2(v[0], v[1])` | NCERT Mathematics Class 10, Triangles | approve |  |
| M088 | **STANDARD** | `packages/math/geometry.ov:85` | Circle | `invariant positive: radius > 0` | NCERT Mathematics Class 9, Circles | approve |  |
| M089 | **STANDARD** | `packages/math/geometry.ov:90` | OnCircle | `invariant on: dist(p, center) = radius` | NCERT Mathematics Class 11, Conic Sections | approve |  |
| M090 | **STANDARD** | `packages/math/geometry.ov:102` | Section | `invariant positive_m: m > 0` | NCERT Mathematics Class 10, Coordinate Geometry, Section formula | approve |  |
| M091 | **STANDARD** | `packages/math/geometry.ov:103` | Section | `invariant positive_n: n > 0` | NCERT Mathematics Class 10, Coordinate Geometry, Section formula | approve |  |
| M092 | **STANDARD** | `packages/math/geometry.ov:104` | Section | `invariant section_x: (m + n) * P.x = n * A.x + m * B.x` | NCERT Mathematics Class 10, Coordinate Geometry, Section formula | approve |  |
| M093 | **STANDARD** | `packages/math/geometry.ov:105` | Section | `invariant section_y: (m + n) * P.y = n * A.y + m * B.y` | NCERT Mathematics Class 10, Coordinate Geometry, Section formula | approve |  |
| M094 | **STANDARD** | `packages/math/geometry.ov:107` | Section | `theorem ratio: n * n * dist2(A, P) = m * m * dist2(P, B)` | NCERT Mathematics Class 10, Coordinate Geometry, Section formula | approve |  |
| M095 | **STANDARD** | `packages/physics/mechanics.ov:20` | (package level) | `law newton2(b: Body, F: Force): net_force(b, F) -> F = b.mass * b.accel` | NCERT Physics Class 11 Part 1, Laws of Motion; HRW Ch 5/9 | approve |  |
| M096 | **STANDARD** | `packages/physics/mechanics.ov:34` | ConstantAcceleration | `invariant elapsed: t >= 0` | Definition | approve |  |
| M097 | **STANDARD** | `packages/physics/mechanics.ov:35` | ConstantAcceleration | `invariant velocity: v = u + integral(a, t)` | NCERT Physics Class 11 Part 1, Motion in a Straight Line; HRW Ch 2 | approve |  |
| M098 | **STANDARD** | `packages/physics/mechanics.ov:36` | ConstantAcceleration | `invariant displacement: s = integral(u + integral(a, t), t)` | NCERT Physics Class 11 Part 1, Motion in a Straight Line; HRW Ch 2 | approve |  |
| M099 | **STANDARD** | `packages/physics/mechanics.ov:37` | ConstantAcceleration | `theorem suvat_v: v = u + a * t` | NCERT Physics Class 11 Part 1, Motion in a Straight Line; HRW Ch 2 | approve |  |
| M100 | **STANDARD** | `packages/physics/mechanics.ov:38` | ConstantAcceleration | `theorem suvat_s: s = u * t + a * t * t / 2` | NCERT Physics Class 11 Part 1, Motion in a Straight Line; HRW Ch 2 | approve |  |
| M101 | **STANDARD** | `packages/physics/mechanics.ov:39` | ConstantAcceleration | `theorem suvat_timeless: v * v = u * u + 2 * a * s` | NCERT Physics Class 11 Part 1, Motion in a Straight Line; HRW Ch 2 | approve |  |
| M102 | **STANDARD** | `packages/physics/mechanics.ov:40` | ConstantAcceleration | `theorem suvat_average: s = (u + v) * t / 2` | NCERT Physics Class 11 Part 1, Motion in a Straight Line; HRW Ch 2 | approve |  |
| M103 | **STANDARD** | `packages/physics/mechanics.ov:41` | ConstantAcceleration | `theorem suvat_final: s = v * t - a * t * t / 2` | NCERT Physics Class 11 Part 1, Motion in a Straight Line; HRW Ch 2 | approve |  |
| M104 | **STANDARD** | `packages/physics/mechanics.ov:50` | ConstantForce | `invariant positive_mass: m > 0` | Definition | approve |  |
| M105 | **STANDARD** | `packages/physics/mechanics.ov:51` | ConstantForce | `law newton2: F = m * a` | NCERT Physics Class 11 Part 1, Laws of Motion; HRW Ch 5/9 | approve |  |
| M106 | **STANDARD** | `packages/physics/mechanics.ov:53` | ConstantForce | `theorem work_energy: F * s = m * v * v / 2 - m * u * u / 2` | NCERT Physics Class 11 Part 1, Work, Energy and Power; HRW Ch 7 | approve |  |
| M107 | **STANDARD** | `packages/physics/mechanics.ov:60` | UniformGravity | `invariant g_positive: g > 0` | Definition | approve |  |
| M109 | **STANDARD** | `packages/physics/mechanics.ov:62` | UniformGravity | `theorem free_fall_accel: a = -g` | NCERT Physics Class 11 Part 1, Motion in a Straight Line; HRW Ch 2 | approve |  |
| M110 | **STANDARD** | `packages/physics/mechanics.ov:64` | UniformGravity | `theorem energy_conservation: m * v * v / 2 + m * g * s = m * u * u / 2` | NCERT Physics Class 11 Part 1, Work, Energy and Power; HRW Ch 8 | approve |  |
| M111 | **STANDARD** | `packages/physics/mechanics.ov:81` | TwoBodyInteraction | `invariant elapsed: dt >= 0` | Definition | approve |  |
| M112 | **STANDARD** | `packages/physics/mechanics.ov:82` | TwoBodyInteraction | `invariant positive_m1: m1 > 0` | Definition | approve |  |
| M113 | **STANDARD** | `packages/physics/mechanics.ov:83` | TwoBodyInteraction | `invariant positive_m2: m2 > 0` | Definition | approve |  |
| M114 | **STANDARD** | `packages/physics/mechanics.ov:84` | TwoBodyInteraction | `invariant velocity1: v1 = u1 + integral(a1, dt)` | NCERT Physics Class 11 Part 1, Motion in a Straight Line; HRW Ch 2 | approve |  |
| M115 | **STANDARD** | `packages/physics/mechanics.ov:85` | TwoBodyInteraction | `invariant velocity2: v2 = u2 + integral(a2, dt)` | NCERT Physics Class 11 Part 1, Motion in a Straight Line; HRW Ch 2 | approve |  |
| M116 | **STANDARD** | `packages/physics/mechanics.ov:86` | TwoBodyInteraction | `law newton2_1: F = m1 * a1` | NCERT Physics Class 11 Part 1, Laws of Motion; HRW Ch 5/9 | approve |  |
| M117 | **STANDARD** | `packages/physics/mechanics.ov:87` | TwoBodyInteraction | `law newton2_2: F2 = m2 * a2` | NCERT Physics Class 11 Part 1, Laws of Motion; HRW Ch 5/9 | approve |  |
| M118 | **STANDARD** | `packages/physics/mechanics.ov:88` | TwoBodyInteraction | `law newton3: F2 = -F` | NCERT Physics Class 11 Part 1, Laws of Motion; HRW Ch 5/9 | approve | State isolation (no external forces) explicitly. |
| M119 | **STANDARD** | `packages/physics/mechanics.ov:89` | TwoBodyInteraction | `theorem momentum_conservation: m1 * u1 + m2 * u2 = m1 * v1 + m2 * v2` | NCERT Physics Class 11 Part 1, Laws of Motion; HRW Ch 5/9 | approve |  |
| M120 | **STANDARD** | `packages/physics/mechanics.ov:90` | TwoBodyInteraction | `theorem impulse: m1 * (v1 - u1) = F * dt` | NCERT Physics Class 11 Part 1, Laws of Motion; HRW Ch 5/9 | approve |  |
| M121 | **STANDARD** | `packages/physics/mechanics.ov:100` | BodyPair | `invariant same_time: b1.t = b2.t` | Definition | approve |  |
| M123 | **STANDARD** | `packages/physics/mechanics.ov:102` | BodyPair | `theorem momentum: b1.m * b1.u + b2.m * b2.u = b1.m * b1.v + b2.m * b2.v` | NCERT Physics Class 11 Part 1, Laws of Motion; HRW Ch 5/9 | approve | Valid once M122's isolation is explicit. |
| M124 | **STANDARD** | `packages/physics/mechanics.ov:103` | BodyPair | `theorem impulse_balance: b1.m * (b1.v - b1.u) = -(b2.m * (b2.v - b2.u))` | NCERT Physics Class 11 Part 1, Laws of Motion; HRW Ch 5/9 | approve |  |
| M125 | **STANDARD** | `drafts/packages/chemistry/gases.ov:15` | VanDerWaalsGas | `invariant positive: p > 0 temp > 0 R > 0 a > 0 b > 0` | Atkins, Physical Chemistry, Topic 1C.2 The van der Waals equation | approve | Standard domain conditions; a, b > 0 by construction of the model. |
| M127 | **STANDARD** | `drafts/packages/chemistry/gases.ov:17` | VanDerWaalsGas | `law van_der_waals: (p + a / (vm * vm)) * (vm - b) = R * temp` | Atkins Topic 1C.2; NCERT Chemistry XI (pre-2023) Ch 5, Behaviour of real gases | approve | Correct molar form; a model equation of state. |
| M128 | **STANDARD** | `drafts/packages/chemistry/gases.ov:19` | VanDerWaalsGas | `theorem cubic_in_vm: (p * vm * vm + a) * (vm - b) = R * temp * vm * vm` | Atkins, Topic 1C.2 (cubic form) | approve | Law multiplied by vm^2. |
| M129 | **STANDARD** | `drafts/packages/chemistry/gases.ov:36` | VanDerWaalsCubic | `invariant coefficients: c3 = p c2 = -(p * b + R * temp) c1 = a c0 = -(a * b)` | Atkins, Topic 1C.2 (vdW cubic in Vm) | approve | Coefficients checked; units consistent. |
| M130 | **STANDARD** | `drafts/packages/chemistry/gases.ov:37` | VanDerWaalsCubic | `theorem expansion: (p * V * V + a) * (V - b) - R * temp * V * V = c3 * V * V * V + c2 * V * V + c1 * V + c0` | Atkins, Topic 1C.2 | approve | Correct identity in V. |
| M131 | **STANDARD** | `drafts/packages/chemistry/kinetics.ov:18` | SecondOrderAR | `invariant positive: k > 0 a0 > 0 r0 > 0` | Atkins, Topic 17B Integrated rate laws | approve | Positivity of rate constant and initial concentrations. |
| M132 | **STANDARD** | `drafts/packages/chemistry/kinetics.ov:19` | SecondOrderAR | `invariant advance: a = a0 - x r = r0 - x` | Atkins, Topic 17B (A + B second order) | approve | Stoichiometry for 1:1 A + R. |
| M133 | **STANDARD** | `drafts/packages/chemistry/kinetics.ov:20` | SecondOrderAR | `invariant possible: x >= 0 a >= 0 r >= 0` | Atkins, Topic 17B | approve | Nonnegative concentrations; forward reaction. |
| M134 | **STANDARD** | `drafts/packages/chemistry/kinetics.ov:21` | SecondOrderAR | `invariant rate_law: rate = k * a * r` | NCERT Chemistry XII Ch 3, Rate law; Atkins Topic 17A | approve | First order in each reactant; units check. |
| M135 | **STANDARD** | `drafts/packages/chemistry/kinetics.ov:29` | PseudoFirstOrder | `invariant pseudo_constant: k1 = k * r0` | NCERT Chemistry XII Ch 3, Pseudo first order reaction | approve | k' = k [R]0. |
| M136 | **STANDARD** | `drafts/packages/chemistry/kinetics.ov:30` | PseudoFirstOrder | `invariant approximation: approx_rate = k1 * a` | NCERT Chemistry XII Ch 3; Atkins Topic 17A (isolation method) | approve | Exact as a definition of approx_rate; using it for rate needs r0 >> a0 (not recorded). |
| M137 | **STANDARD** | `drafts/packages/chemistry/solid_state.ov:16` | CubicCell | `invariant positive: edge > 0 avogadro > 0 molar_mass > 0` | NCERT Chemistry XII (pre-2023) Unit 1, unit cell calculations | approve | Positivity; z > 0 not stated but harmless. |
| M138 | **STANDARD** | `drafts/packages/chemistry/solid_state.ov:17` | CubicCell | `invariant cell_density: density * avogadro * edge * edge * edge = z * molar_mass` | NCERT Chemistry XII (pre-2023) Unit 1 (d = zM/(a^3 N_A)) | approve | Correct, cleared of division. |
| M139 | **STANDARD** | `drafts/packages/chemistry/solid_state.ov:26` | CcpCell | `invariant fcc_sites: corners = 8 faces = 6` | Kittel Ch 1 (fcc); NCERT Chemistry XII Unit 1 | approve | Site counts of the fcc cell. |
| M140 | **STANDARD** | `drafts/packages/chemistry/solid_state.ov:27` | CcpCell | `invariant shared_count: z = corners / 8 + faces / 2` | NCERT Chemistry XII (pre-2023) Unit 1, atoms per unit cell | approve | Corner shared by 8, face by 2. |
| M141 | **STANDARD** | `drafts/packages/chemistry/solid_state.ov:28` | CcpCell | `theorem four_per_cell: z = 4` | Kittel Ch 1 | approve | 8/8 + 6/2 = 4. |
| M142 | **STANDARD** | `drafts/packages/math/vectors.ov:19` | Triple | `invariant scalar_triple: triple = ux * (vy * wz - vz * wy) - uy * (vx * wz - vz * wx) + uz * (vx * wy - vy * wx)` | Stewart, Calculus, Ch 12 §12.4 Triple Products | approve | Cofactor expansion of u.(v x w). |
| M143 | **STANDARD** | `drafts/packages/math/vectors.ov:21` | Triple | `theorem cyclic: triple = vx * (wy * uz - wz * uy) - vy * (wx * uz - wz * ux) + vz * (wx * uy - wy * ux)` | Stewart, Calculus, Ch 12 §12.4 | approve | Cyclic permutation identity. |
| M144 | **STANDARD** | `drafts/packages/math/vectors.ov:28` | CoplanarTriple | `invariant coplanar: triple = 0` | Stewart, Calculus, Ch 12 §12.4 | approve | Coplanar iff triple product is 0, used as a definition. |
| M145 | **STANDARD** | `drafts/packages/physics/electromagnetism.ov:22` | SpinningChargedShell | `invariant positive: R > 0 omega > 0` | Griffiths, Electrodynamics, Ch 5 §5.4 | approve | Domain conditions. |
| M146 | **STANDARD** | `drafts/packages/physics/electromagnetism.ov:23` | SpinningChargedShell | `invariant full_height: s = 2 * R` | Stewart, Calculus, Ch 5 §5.3 | approve | Encoding of the integration limit 2R. |
| M148 | **STANDARD** | `drafts/packages/physics/electromagnetism.ov:25` | SpinningChargedShell | `theorem shell_moment: 3 * moment = charge * omega * R * R` | Griffiths, Electrodynamics, Ch 5 §5.4 (m = Q omega R^2/3) | approve | Checked: 4R^3/3 at s = 2R. |
| M149 | **STANDARD** | `drafts/packages/physics/electromagnetism.ov:42` | SpinningSolidSphere | `invariant positive: rho > 0 R > 0 omega > 0` | HRW, Ch 10 Rotation, rotational inertia | approve | Domain conditions. |
| M150 | **STANDARD** | `drafts/packages/physics/electromagnetism.ov:43` | SpinningSolidSphere | `invariant outer_radius: r = R` | Stewart, Calculus, Ch 5 §5.3 | approve | Encoding of the integration limit R. |
| M151 | **STANDARD** | `drafts/packages/physics/electromagnetism.ov:44` | SpinningSolidSphere | `invariant sum_of_shells_mass: mass = 4 * pi * rho * integral(r * r, r)` | Stewart Ch 6; HRW Ch 10 | approve | Mass = density x volume, summed over shells. |
| M153 | **STANDARD** | `drafts/packages/physics/electromagnetism.ov:46` | SpinningSolidSphere | `theorem mass_positive: mass > 0` | Stewart, Calculus, Ch 5 | approve | True. |
| M154 | **STANDARD** | `drafts/packages/physics/electromagnetism.ov:47` | SpinningSolidSphere | `theorem sphere_spin: 5 * spin = 2 * mass * R * R * omega` | HRW Ch 10 Table 10-2 (2/5 MR^2); Ch 11 | approve | Checked. |
| M155 | **STANDARD** | `drafts/packages/physics/gravitation.ov:14` | CircularOrbit | `invariant positive: kepler > 0 r > 0 period > 0` | HRW Ch 13, Kepler's laws | approve | Domain conditions. |
| M157 | **STANDARD** | `drafts/packages/physics/quantum.ov:12` | MatterWave | `invariant positive: h > 0 p > 0` | HRW Ch 38 Photons and matter waves | approve | Domain conditions. |
| M158 | **STANDARD** | `drafts/packages/physics/quantum.ov:13` | MatterWave | `law de_broglie: wavelength * p = h` | NCERT Physics XII Ch 11; HRW Ch 38 | approve | de Broglie relation (postulate). |
| M159 | **STANDARD** | `drafts/packages/physics/quantum.ov:21` | SlowParticle | `invariant mass_positive: m > 0` | HRW Ch 7 | approve | Domain condition. |
| M160 | **STANDARD** | `drafts/packages/physics/quantum.ov:22` | SlowParticle | `invariant kinetic_energy: p * p = 2 * m * energy` | HRW Ch 7, Ch 9; NCERT Physics XII Ch 11 | approve | Non-relativistic KE; v << c carried by the class name. |
| M163 | **STANDARD** | `drafts/packages/physics/quantum.ov:35` | BohrOrbit | `law angular_momentum: 2 * pi * p * r = n * h` | NCERT Physics XII Ch 12 (second postulate); HRW Ch 39 | approve | Bohr quantization (postulate). |
| M164 | **STANDARD** | `drafts/packages/physics/quantum.ov:37` | BohrOrbit | `theorem standing_wave: n * wavelength = 2 * pi * r` | NCERT Physics XII Ch 12 | approve | 2 pi r = n lambda. |
| M165 | **STANDARD** | `drafts/packages/physics/rotation.ov:14` | AngularOscillator | `invariant positive: inertia > 0 kappa > 0 omega > 0` | HRW Ch 15, angular SHO | approve | Domain conditions. |
| M167 | **STANDARD** | `drafts/packages/physics/rotation.ov:24` | SpringOnLever | `invariant positive: k > 0 d >= 0` | HRW Ch 7, Hooke's law | approve | Domain conditions. |
| M169 | **STANDARD** | `drafts/packages/physics/thermal.ov:15` | BlackGap | `invariant constant_positive: sigma > 0` | HRW Ch 18, Radiation | approve | Domain condition. |
| M170 | **STANDARD** | `drafts/packages/physics/thermal.ov:16` | BlackGap | `invariant absolute: hot >= 0 cold >= 0` | HRW Ch 18 (Kelvin scale) | approve | Correct. |

## Part B: the W2 gold change (retire `TwoBodyInteraction`)

**Why.** `TwoBodyInteraction` restates definitions that `BodyPair` gets by
composition: each body is a `ConstantForce`. Its two theorem lines and the
`recoil` test's `expect` line are gold, so deleting them needs
`Gold-Change-Approved-By: founder`.

**Mapping.** Each old statement has a replacement that is PROVEN and no
weaker.

| old (TwoBodyInteraction) | replacement | status of the replacement | no weaker because |
|---|---|---|---|
| `theorem momentum_conservation: m1*u1 + m2*u2 = m1*v1 + m2*v2` | `BodyPair.momentum: b1.m*b1.u + b2.m*b2.u = b1.m*b1.v + b2.m*b2.v` | PROVEN, trust {kernel} | the same equation under the renaming m1 -> b1.m, u1 -> b1.u, etc. |
| `theorem impulse: m1*(v1 - u1) = F*dt` | **new** `ConstantForce.impulse: m*(v - u) = F*t` (inherited by b1 and b2) | PROVEN, trust {kernel} (checked in a scratch class; not yet in `packages/`) | it is the same statement for every body, not only body 1 |
| (none) | `BodyPair.impulse_balance` (already there) | PROVEN, trust {kernel} | an extra consequence |
| `test recoil` (`expect PROVEN -4 m/s`) | `test recoil_by_composition` (already there, same expectation) | passes | the same query and the same expected value |

**Two things this change also needs** (both are meaning lines, listed here so
one reply covers them):
1. **The new theorem line** `theorem impulse: m * (v - u) = F * t` in
   `ConstantForce`.
2. **The isolation fix the reviewer asked for (M122 SUSPECT).**
   - The problem: `law newton3: b2.F = -b1.F` equates the two bodies' *net*
     forces, which is valid only for an isolated pair.
   - Proposed restatement: add `property push: Force` and replace the law
     with `invariant isolated: b1.F = push` and `b2.F = -push`. The pair
     feels only its mutual push, stated explicitly.
   - That makes the momentum theorems follow from a stated definition, not
     from an implicit reading.

**Recommended:** yes, together with items 1 and 2.

## Part C: HSC sources

**The question:** where do the HSC question papers come from?
- **(a)** The founder provides the papers (the folder named earlier).
- **(b)** The agent fetches question papers only from official Bangladesh
  education board websites. Gold is two independent AI solutions (separate
  sessions, no OV access); disagreements are excluded and listed. Provenance
  is tagged `dual_ai_independent` and reported apart from official-key
  results.

**Domains for (b).** Only the boards' own `.gov.bd` sites, each checked to be
the board's official site before any download:
- `educationboard.gov.bd` (the inter-board results and notice portal);
- `dhakaeducationboard.gov.bd`;
- `rajshahieducationboard.gov.bd`;
- `comillaboard.gov.bd`;
- `jessoreboard.gov.bd`;
- `bise-ctg.gov.bd`;
- `barisalboard.gov.bd`;
- `sylhetboard.gov.bd`;
- `dinajpureducationboard.gov.bd`;
- `mymensingheducationboard.gov.bd`.

I have not confirmed that these sites publish past HSC question papers; many
publish only results and notices. If none does, (b) yields nothing and HSC
waits for (a).

**Recommendation: (a).**
- The papers would then be official, and so would the board keys where they
  exist.
- (b) only as a fallback, and only for papers actually found on those
  domains.

## Part D: other decisions

1. **The `pyproject.toml` `authors` field still names a person.** It is
   package metadata and public naming, so it is the founder's call.
   *Recommendation: replace it with "OpenVerifiers contributors" and keep the
   email as the founder decides.*
2. **The scope of the meaning gate (C1 deviation 1).** Benchmark problem
   statements (`benchmarks/**/case.ov`) and test fixtures are outside it;
   every other package file is gated. *Recommendation: keep.*
3. **Rework plan for the non-STANDARD draft lines.** They stay in `drafts/`
   and are reworked in C3/C4:
   - **Kepler's third law (M156):** a theorem from Newtonian gravity plus
     circular motion.
   - **Bohr radius (M162):** a theorem from Coulomb force plus quantization.
   - **The black-plate flux (M171):** from emission σT⁴.
   - **The shell and sphere sums (M147, M152):** reduced to more basic stated
     facts.
   - **The vdW excluded volume (M126):** a theorem.
   - **The lever torque (M168):** moves into the scenario as an assumption.
   - **n and Z of a Bohr orbit (M161):** become integers once the ℤ type
     lands (C4).
   - **ω² = κ/I (M166):** needs verified ODE solutions (C4).

   *Recommendation: agree.*
4. **Real algebraic numbers (D-026 item 4) are deferred.** The exact unit is
   at 449/450 after Q(π) and the exp ring, so there is no trusted room. phys
   p1q10 stays UNKNOWN. *Recommendation: defer to after C4, or raise unit A's
   cap by about 60 lines (a founder decision on the trust budget).*
