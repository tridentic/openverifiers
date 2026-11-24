# Approval: packet 4, Parts A, B and C (blob d1c83e7ef19e)

packet-hash: d1c83e7ef19e
title: packet 4 A-C: MP-1.4 (D-033, D-034, D-031b); physics.rotation with N043; M078
trailers: meaning
ratifies:

Prepared by the agent on the branch `approval/packet4`. The changes are staged
and nothing is committed. Approve by running
`./scripts/founder_approve.sh packet4` in your own terminal, in the folder of
the `approval/packet4` worktree. It makes one commit signed with your key
(D-032).

The packet is `reports/APPROVAL_PACKET_2026-11-24_packet4.md`. Part D needs a
written reply and is not in this commit.

## Summary

**Approved by this commit:**
- **Part A (MASTERPLAN MP-1.4).** Decision-log rows D-033, D-034 and D-031b,
  in the words of the reply to packet 3. v1 exit criterion 1 per D-031b (one
  official-key exam tier; JEE Main and HSC in v1.1).
- **Part B (`physics.rotation`).** R001 `amplitude_positive` (MODELLING),
  R005 `newton_rotation_at_release` (STANDARD) and R004 `small_oscillation`
  (N043, a theorem PROVEN at `{kernel}`). With N042, approved in packet 2,
  every statement is approved, so the file moves from `drafts/packages/` to
  `src/openverifiers/packages/`.
- **Part C (M078).** `math.geometry` Quadrilateral gets
  `invariant proper` (no three vertices collinear). All 8 geometry theorems
  keep their text and stay PROVEN.

**Not in this commit:** Part D (the nightly schedule, macOS 3.11, the
formula-unit lines, p2q3's assumption).

## Checks run by the agent on this staged state

- **Full test suite** on the staged state: 653 passed.
- **Test changes:**
  - `test_exam`: the draft-loading tests use their own temporary draft package,
    since no library is a draft any more. The end-to-end exam test checks p2q3
    under `--strict`, with its stated assumption.
  - `test_objects`: the diamond list includes `Quadrilateral.proper` once.
  - `test_trig_ring` and `test_object_mutants`: the path of `physics.rotation`.
- **`ov check`:** `math/geometry.ov`: 13 / 13 expectations, 18 class checks
  proven. `physics/rotation.ov`: 3 class checks proven (N043 at `{kernel}`).
- **Gate dry run:** `needs: meaning`.
- **JEE p2q3:** solved under `--strict` (no draft any more), still stating N043
  as its assumption.
