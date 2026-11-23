# Approval: packet 3, Part A (blob 0e233e5b7e29)

packet-hash: 0e233e5b7e29
title: packet 3 Part A: physics.quantum approved and moved to packages (Bohr radius as a theorem)
trailers: meaning
ratifies:

Prepared by the agent on the branch `approval/packet3`. The changes are staged
and nothing is committed. Approve by running
`./scripts/founder_approve.sh packet3` in your own terminal, in the folder of
the `approval/packet3` worktree. It makes one commit signed with your key
(D-032).

The packet is `reports/APPROVAL_PACKET_2026-11-23_packet3.md`. Parts A2, B, C
and D need a written reply. They are not in this commit.

## Summary

**Approved by this commit (Part A):** P001–P005 in `physics.quantum`'s
`BohrOrbit`:
- P001 `constants_positive`, STANDARD;
- P002 `coulomb_centripetal`, MODELLING, Bohr's idealisations stated in the
  class comment;
- P003 `reduced_planck`, STANDARD;
- P004 `bohr_radius`, STANDARD;
- P005 `orbit_radius`, now a theorem, proved at `{kernel}`.

With them, every statement in `physics.quantum` is approved: N034–N038, N040
and N041 were approved in packet 2. So the file moves from `drafts/packages/`
to `src/openverifiers/packages/`.

**Not in this commit:**
- N043 (`physics.rotation` stays in `drafts/`);
- M036, M013, M078/M079;
- the JEE Main source;
- the CI key-anchor variable.

## Checks run by the agent on this staged state

- **Full test suite:** 633 passed. `test_exam`'s draft-package example moves
  from `physics.quantum` to `physics.rotation`, which stays a draft.
- **Gate dry run:** `needs: meaning`. The meaning lines are the approved N034–N038,
  N040, N041 and the new P001–P005.
- **JEE phys p1q13:** solved by default and now under `--strict` too (it was
  provisional). phys p2q3 still needs `physics.rotation` (a draft).
