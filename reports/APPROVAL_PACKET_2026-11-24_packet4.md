# Approval packet 4 (C7, final), 2026-11-24 (D-024, D-032)

For the founder. It covers:
- every meaning-carrying statement added or changed since packet 3;
- the masterplan changes from the reply to packet 3;
- the one item re-proposed under that reply's Part B rule;
- the decisions only the founder can take.

**What to do:**
- **Parts A, B and C are staged** on the branch `approval/packet4`, in the
  folder `openverifiers-approval-packet4` next to this repository. Approve them
  with one signed command in your own terminal:

  ```
  cd ~/Work/snayu/research/research_root/openverifiers-approval-packet4
  ./scripts/founder_approve.sh packet4
  ```

- **Part D needs a written reply.** Anything not named in your reply stays
  unapproved.

## Part A: masterplan MP-1.4 (D-033, D-034, D-031b)

Packet 3's reply ordered these into packet 4, because the signed packet-3 commit
had already landed. The rows quote the reply exactly. The staged MASTERPLAN.md
changes:

- **Header:** MP-1.3 becomes MP-1.4.
- **Decision log:** three rows, D-033, D-034 and D-031b, in the reply's words.
- **§7 v1 exit criterion 1 (D-031b):** it now counts JEE Advanced 30 + agentic
  20 + breadth 35 + adversarial 50. JEE Main and HSC become v1.1 tiers.
  - **Why it applies:** `private/sources/jee_main/` does not exist.
  - **What the exit report says:** v1 has one official-key exam tier.

The work these decisions ordered is already done on `v1`:
- **D-033:** sin and cos in the normal form, `23ba5d2`, `03681e7`.
- **D-034:** the streak script and the nightly workflow, `b989370`.

## Part B: `physics.rotation`, N043 as a theorem (3 statements)

Packet 3's reply (A2): "Retry the proof after D-033." The retry succeeded.
- **AngularOscillator** keeps no equation of motion. An equation with
  cos(ωt) in it cannot be re-checked numerically, so object queries over it
  (JEE p2q3) stay polynomial.
- **The new subclass TorsionMotion** states the motion θ = A cos(ωt) and
  Newton's law for rotation at the release instant. N043 is proved from them at
  `{kernel}`, and the class is consistent.

A gold-blind, OV-blind reviewer (a Claude subagent that saw only the library
text) classified the lines. Its first round found a real problem: a second law,
"the time derivative of Newton's law at one instant", was SUSPECT. It doesn't
follow from a law asserted at one instant, and with the first law it restated
ω²I = κ. **That law and its partner were withdrawn** (`03681e7`). The second
round:

| id | statement | class | reference | recommended action | note |
|---|---|---|---|---|---|
| R001 | `invariant amplitude_positive: amplitude > 0` | MODELLING | Taylor, Classical Mechanics Ch. 5; HRW Ch. 15 | approve as a stated convention | release at a positive angle; the small-oscillation idealisation is stated in the class comment |
| R005 | `law newton_rotation_at_release: inertia * value_at(deriv(deriv(amplitude * cos(omega * t), t), t), t, 0) = -kappa * value_at(amplitude * cos(omega * t), t, 0)` | STANDARD | HRW Ch. 10, 15; Kleppner & Kolenkow Ch. 7 | approve | I θ″ = −κ θ at t = 0. The reviewer's remark that `t` is unused is a misreading: OV's calculus needs its variable to be a numeric property |
| R004 | `theorem small_oscillation: omega * omega * inertia = kappa` (N043, moved from AngularOscillator) | DERIVABLE, a theorem | HRW Ch. 15; Taylor Ch. 5 | approve | "no hidden circularity" (reviewer). OV proves it at `{kernel}` |

**What approval does:** with R001, R004 and R005 approved, every statement in
`physics.rotation` is approved (N042 was approved in packet 2). The file moves
to `src/openverifiers/packages/`, which is staged. JEE phys p2q3 then stops
being provisional. It still states N043 as its assumption, because queries
cannot use theorems before v2.

## Part C: M078 re-proposed (Part B rule of packet 3)

The reply: "Re-propose any that fixes a real error, with a one-line
justification each. A theorem stated too strongly is fixed in the definition
(invariant), never by weakening a PROVEN theorem."

- **M078**, `math.geometry` Quadrilateral. **Justification:** the definition
  admits three collinear "vertices", which are not a quadrilateral; the fix adds
  `invariant proper` (no three vertices collinear) to the definition.
  - Every theorem's text is unchanged, and all 8 geometry theorems stay PROVEN.
  - All 13 expectations still pass (checked on a copy of the file).
  - This is staged.
- **Not re-proposed:**
  - **M013 and M036** are about names and scope within the library's stated
    meaning (keto–enol only; the new carbinol carbon only), not errors.
  - **M079** needs no change.

## Part D: decisions (written reply)

1. **The nightly schedule (D-034).** GitHub fires a schedule only from the
   default branch's workflow files, and the default is `main`.
   `.github/workflows/nightly.yml` is on `v1`. Choose:
   - (a) copy that file to `main`;
   - (b) make `v1` the default branch.

   *Recommendation: (a). It changes nothing else on `main`.*
2. **macOS 3.11 moved off push runs** onto the nightly run (`b989370`).
   - **Why:** GitHub's macOS queue cancelled that job before it started, 3
     times on 2026-11-23, and each cancellation breaks the D-034 streak.
   - **Coverage:** it still runs daily.
   - **Your call:** approve it, or restore it to push runs.
3. **A D-033 deviation:** unit A grew 22 lines, within D-033's "~40".
   `raw/formula.py` grew 29 lines (now 449 / 450), which D-033 did not name.
   - **What they do:** the evaluator differentiates exp, ln, 1/u, sin and cos
     bodies through the certificate normal form, and evaluates sin and cos.
   - **Why they're needed:** without them, models of classes with these laws
     cannot be re-checked.
   - **Your call:** accept, or name a fix.
4. **JEE p2q3's assumption.** It keeps N043 as a stated assumption, because
   queries cannot use theorems before v2. Confirm this is acceptable for v1.

The CI key anchor needs no decision: it arms itself once your GitHub account
shows a signing key, and today it shows none.
