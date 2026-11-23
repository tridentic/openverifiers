# Approval: packet 2 (blob dd2d4fd885a8)

packet-hash: dd2d4fd885a8
title: packet 2 decisions (Part A, A2, B); D-032; ratification of agent-stamped approvals
trailers: meaning gold
ratifies: aed910b b2cfdb5 600984a 68428c7 6f53603 3c29133 D-029 D-030 D-031

Prepared by the agent on the branch `approval/packet2`. The changes are staged
and nothing is committed. The founder approves by running
`./scripts/founder_approve.sh packet2` in their own terminal. That makes one
commit signed with the founder's key (D-032, docs/APPROVALS.md).

The packet is `reports/APPROVAL_PACKET_2026-11-23_C6.md`. The founder's reply
is recorded in `reports/APPROVAL_RECORD_2026-11-23_packet2.md`.

## Summary

**Approved and applied in this commit:**
- **Part A, 39 of the 47 STANDARD statements.** Six draft files move to
  `src/openverifiers/packages/`:
  - `agent.workflow` (N001–N011);
  - `chemistry.gases` (N012–N018);
  - `math.vector_products` (N019–N021);
  - `physics.electromagnetism` (N022–N031);
  - `physics.gravitation` (N032–N033);
  - `physics.thermal` (N044–N049).
- **Part A, the other 8 STANDARD statements are approved but stay in
  `drafts/`:** `physics.quantum` (N034–N038, N040, N041) and
  `physics.rotation` (N042). Their files also hold N039 and N043.
- **Part A2:** `examples/policies/repo_policy.ov` moves to `drafts/policies/`.
  This removes P001–P004 from the gated path.
- **Part B:** M001, M032, M033, M034 and M108.
  - **M001:** `isomer_of` is renamed `structural_isomer_of`.
  - **M032:** the tie rule needs `s != t`.
  - **M033/M034:** the Markovnikov rules need `no_rearrangement(alkene)`,
    stated per scenario as an `assume`.
  - **M108:** `law weight: W = m * g` with `invariant gravity_only: F = -W`.
- **D-032:** MASTERPLAN MP-1.3 adds the decision-log row for signed founder
  approvals.

**Held, unapplied, for packet 3:**
- **N039 (Bohr radius) and N043 (ω² = κ/I).** Not approved as laws; they are
  to be rewritten as theorems and proved.
- **M078 and M079 (Quadrilateral).** The new hypothesis weakens the PROVEN
  theorems of Parallelogram and Rectangle (the founder's exception).
- **M013 (keto–enol) and M036 (new stereocentre).** As proposed, each turns a
  package `expect` or a benchmark's gold verdict. The reply gives no gold
  approval.

**Ratified by this commit** (`Ratifies:`). These are approvals an agent
stamped, which D-032 replaces:

| commit | what it is | whole-history gate today |
|---|---|---|
| `aed910b` | the record of the packet-2 reply; MP-1.2 (D-030, D-031) | unsigned approval trailer |
| `b2cfdb5` | the OVState loader checks restored (D-030); the gate change that D-032 replaced | no trailer; named by the founder |
| `600984a` | the record of the packet-1 reply; D-029 | unsigned approval trailer |
| `68428c7` | packet 1 Part A: kinetics, solid_state, vectors moved into `packages/` | meaning lines under an unsigned trailer |
| `6f53603` | packet 1 Part B: W2 mapping, ConstantForce.impulse, BodyPair fix | gold and meaning under an unsigned trailer (so this commit carries the gold trailer too) |
| `3c29133` | the example policy committed without approval (Part A2) | meaning lines, no trailer |

`D-029 D-030 D-031` in the same trailer name the masterplan records, as
the founder asked. The gate reads only commit hashes; the D-ids are for people.

**Not in this commit:** CI history, the C7 engineering work and packet 3.

## Checks run by the agent on this staged state

- **Full test suite:** see the agent's report for this branch.
- **Gate dry run** (`python -m openverifiers.bench.gold_gate --staged`):
  `needs: meaning`. The gold trailer is added only for the ratification of
  `6f53603`.
- **Whole-history gate after signing:** the script runs it before pushing. With
  this commit signed, it should report `ok`.
