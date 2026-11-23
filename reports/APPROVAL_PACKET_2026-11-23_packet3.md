# Approval packet 3 (C7), 2026-11-23 (D-024, D-032)

For the founder. It covers:
- every meaning-carrying statement added or changed since packet 2;
- the packet-2 items held back;
- the C7 decisions only the founder can take.

The agent records exactly what the reply says. Approval is one signed commit
(D-032): on the branch `approval/packet3` the agent has staged Part A's
change, and nothing is committed. If you approve Part A, run this in your own
terminal:

```
./scripts/founder_approve.sh packet3
```

Parts B to E need a written reply first. Each approved change then gets its own
approval branch.

## Part A: the Bohr radius as a theorem (N039 rework, 5 statements)

Packet 2's reply said N039 is "DERIVABLE: rewrite [it] as [a theorem] and prove
[it]; [it is] not approved as [a law]." `physics.quantum`'s `BohrOrbit` now
derives the radius from:
- the Coulomb–centripetal balance;
- the approved quantization N040 (unchanged);
- the definition of ħ;
- the definition of a0.

The class is consistent. Both of its theorems are at `{kernel}`, and JEE phys
p1q13 is still solved.

A gold-blind, OV-blind reviewer (a Claude subagent that saw only the library
text) classified the new lines:

| id | statement | class | reference | recommended action | note |
|---|---|---|---|---|---|
| P001 | `invariant constants_positive: m > 0 k > 0 e > 0` | STANDARD | Griffiths, Electrodynamics Ch. 2; Eisberg & Resnick Ch. 4 | approve | e is the elementary charge's magnitude; the comment now says the electron's charge is −e |
| P002 | `law coulomb_centripetal: p * p * r = m * k * Z * e * e` | **MODELLING** | Eisberg & Resnick Ch. 4; Bransden & Joachain Ch. 1 | approve as a stated idealisation | Bohr's idealisations: a classical circular orbit, non-relativistic p = m v, an infinitely heavy nucleus. The class comment now states them |
| P003 | `invariant reduced_planck: 2 * pi * hbar = h` | STANDARD | Griffiths & Schroeter Ch. 1 | approve | the definition ħ = h / 2π |
| P004 | `invariant bohr_radius: m * k * e * e * a0 = hbar * hbar` | STANDARD | Griffiths & Schroeter Ch. 4; Eisberg & Resnick Ch. 4 | approve | the infinite-nuclear-mass Bohr radius, consistent with P002 |
| P005 | `theorem orbit_radius: r * Z = n * n * a0` (replaces the law) | DERIVABLE, a theorem | Eisberg & Resnick Ch. 4 | approve | the reviewer checked that it follows from N040, P001–P004. OV proves it at `{kernel}` |

**What approval does:** with P001–P005 approved, every statement in
`physics.quantum` is approved: N034–N038, N040 and N041 were approved in
packet 2. The file then moves to `src/openverifiers/packages/`. That move is the
staged change on `approval/packet3`.

## Part A2: N043 (ω² = κ/I) cannot be proved yet

Packet 2 also asked for N043 to become a theorem. It follows from
I θ'' = −κ θ only if sine or cosine (or a complex exponential) is in the
certificate normal form. It is not: OV's ring has exp, ln and 1/u (D-030), not
trigonometric functions.

- (a) **Recommended:** `physics.rotation` stays in `drafts/` until trigonometric
  derivatives are in the normal form (a v2 item). JEE phys p2q3 stays
  provisional.
- (b) Approve N043 as a MODELLING law ("small oscillations are simple
  harmonic with ω² = κ/I"), with the derivation noted as outside OV.

## Part B: packet-2 Part B items held back (unapplied)

**B1. M036** (`chem.organic`, the HCN-addition stereocentre).
- **Fix as approved in packet 2:** call the predicate `new_stereocentre` (it
  speaks of the new carbinol carbon only).
- **Why it was held:** applied to the one axiom only, `not stereocentre` would
  no longer be derived. The package test `propanone_cyanohydrin_has_no_stereocentre`
  and benchmark `racemic_trap` would then turn UNKNOWN.
- **The consistent form** renames the predicate everywhere: `chem.organic`
  (axioms and tests), `benchmarks/chemistry/racemic_trap` (case.ov, and the
  `query` string in its expected.json), `examples/chem/q11.ov`,
  `tests/v1/test_q11.py`, docs/LANGUAGE.md and the raw kernel demo
  (`examples/raw/q11.rawov`).
- **Gold change:** racemic_trap's expected.json query text. The verdicts
  (PROVEN, REFUTED) are unchanged.
- *Recommendation: approve the rename everywhere.*

**B2. M013** (`chem.organic`, keto–enol tautomerism).
- **Fix:** `not alpha_h(p) -> not keto_enol_tautomerizes(p)`.
- **Why it was held:** applied alone, the package test
  `methanal_does_not_tautomerize` (expect REFUTED) turns UNKNOWN.
- **The consistent form** renames `tautomerizes` to `keto_enol_tautomerizes`
  everywhere: `chem.organic`, `benchmarks/chemistry/ethanal_tautomerizes`,
  `benchmarks/chemistry/q11` (case.ov and the expected.json query strings),
  the q11 example and test, docs, the raw demo and `scripts/q11_raw.py`.
- **Gold change:** two expected.json query strings. The verdicts are unchanged.
- **One reading changes:** q11's given "D does not tautomerize" becomes "D
  shows no keto–enol tautomerism". That is the sense the question uses (it
  pairs it with the α-H test).
- *Recommendation: approve the rename everywhere.*

**B3. M078 / M079** (`math.geometry`, Quadrilateral).
- **Why they were held:** the proposed `no_three_collinear` invariant adds a
  hypothesis under Parallelogram's and Rectangle's PROVEN theorems, so it
  weakens them. That is the reply's exception.
- **The facts:** the class today admits degenerate quadrilaterals. Every
  theorem is PROVEN over that larger class, so each also holds for proper
  quadrilaterals.
- (a) **Recommended:** close M078/M079 with no change, and add a comment that
  the class includes degenerate cases.
- (b) Add the invariant, accepting weaker theorems.

## Part C: JEE Main 2025 sources (D-031): blocked, not substituted

D-031 says: fetch papers and final keys only from official NTA domains. Here is
what happened when the agent checked:

| domain | result (read-only, headless browser) |
|---|---|
| `jeemain.nta.nic.in` (the JEE Main site, linked from nta.ac.in) | **403 Access Denied** (Akamai) to automated browsers. Not bypassed: bot detection is off-limits |
| `jeemain.nta.ac.in` | timed out |
| `nta.ac.in` (Downloads) | loads. It lists JEE (Main) **2026** final answer keys; the 2025 items and any question papers are on `jeemain.nta.nic.in`. NTA publishes "question papers with recorded responses" only through candidate logins, as far as the listings show |
| `exams.nta.ac.in/JEEMAIN/` | 404 |

No other source was used. *Decision needed:*
- (a) **Recommended:** you open `jeemain.nta.nic.in` in your own browser and
  download the JEE Main 2025 final answer keys and, if published, the question
  papers into `private/sources/jee-main/`. The agent then draws the 45 problems
  mechanically, commits the gold first and alone, and formalizes them.
- (b) If NTA does not publish the papers publicly, D-031's own rule applies:
  criterion 1's JEE Main tier cannot run, and it needs a new masterplan
  decision.

## Part D: the CI key anchor

CI now compares `.approvers/allowed_signers` with your GitHub signing keys
(read-only). Your key is not on GitHub yet, so the check warns. Once you add it
(docs/APPROVALS.md, step 5), set the repository variable
`FOUNDER_SIGNING_KEY_ON_GITHUB` to `true` to make a mismatch fail. *No change
is staged; this is your action.*

## Part E: JEE Advanced, the 9 problems still not formalized (C7 step 3)

math p2q9 is now solved at `{kernel}`, using ln from D-030. The other nine stay
unformalized, for these reasons:

| problem | what it needs | category |
|---|---|---|
| math p1q1 | a quantifier over the reals ("f(x) ≠ g(x) for every real x") and "a cubic has a real root" | language (v2) |
| math p1q13 | sin² and cos² coefficients, and a limit x → 0⁺ | language (v2: trigonometry, limits) |
| math p2q6 | areas between curves, i.e. integrals of square roots | language |
| phys p1q5 | exp(ln u) = u in the normal form, and an electromagnetic-induction library | language + library |
| phys p1q1 | rolling-constraint and small-oscillation energy library | library (not drafted) |
| phys p1q7 | a waves library: reflection phase, wavenumber across string junctions | library (not drafted) |
| phys p2q6 | a geometric-optics library: mirror equation, slab shift, and the two image-on-S cases | library (not drafted) |
| phys p1q16 | descriptive atomic and nuclear physics (Moseley, binding energy) | library (knowledge base) |
| chem p1q1 | descriptive inorganic chemistry (decomposition products) | library (knowledge base) |

*No decision needed. The library rows become draft libraries, and so meaning
lines for a later packet, if you want them in v1.*

Anything not named in the reply stays unapproved.
