# Approval record: reply to packet c8c9af15519e (reports/APPROVAL_PACKET_2026-11-23.md)

Packet: `reports/APPROVAL_PACKET_2026-11-23.md`, git blob `c8c9af15519e`
(committed in `4aa1d04`). The founder's reply, recorded exactly as received:

```
REPLY TO APPROVAL PACKET 2026-11-23 (the founder's decisions)
- Part A: approve all STANDARD. DERIVABLE, MODELLING and SUSPECT lines are not approved: rework them per your Part D plan and include them in the C6 packet.
- Part B: yes (W2 mapping, ConstantForce.impulse, BodyPair isolation fix).
- Part C: (b) official Bangladesh education board sites only (list the domains in the C5 report), gold from two independent AI solutions, provenance `dual_ai_independent`, disagreements excluded and listed, reported separately from official-key results.
- Part D: authors metadata = "OpenVerifiers contributors". Gate scope (case files and tests excepted): accepted. Rework plan for non-standard drafts: approved as a plan; the resulting lines still need approval in the next packet. Real-algebraic deferral: accepted.
- Anything in the packet not named above stays unapproved.
Record these decisions exactly, with trailers quoting this reply and the packet hash.
```

## What the reply approves, applied

**Approved (Part A, STANDARD): 152 statements.** Their ids are the packet
rows marked STANDARD.
- In `packages/`: 114 statements. They stay where they are; this record and
  its commit trailer are the approval.
- In `drafts/`: 38 statements.
  - A draft file whose statements are all STANDARD moves into `packages/`:
    `chemistry.kinetics`, `chemistry.solid_state` and `math.vectors`.
  - Every other draft file still holds a non-approved statement, so it stays
    in `drafts/`, with its STANDARD statements recorded as approved here.

**Not approved: 19 statements** (7 DERIVABLE, 2 MODELLING, 10 SUSPECT).
- In `packages/`: M001, M013, M032, M033, M034, M036, M078, M079, M108,
  M122.
- In `drafts/`: M126, M147, M152, M156, M161, M162, M166, M168, M171.
- They are reworked per the packet's Part D plan and go into the C6 packet.
- M122 (`BodyPair.newton3`) is replaced under Part B by the isolation fix,
  which the reply approved by name.

**Part B, approved.**
- W2 retires `TwoBodyInteraction` and its `recoil` test.
- `theorem impulse: m * (v - u) = F * t` is added to `ConstantForce`.
- The BodyPair isolation fix is applied: `property push: Force`,
  `invariant isolated: b1.F = push b2.F = -push`, replacing `law newton3`.

**Part C:** option (b). The domains are listed in the C5 report.

**Part D.**
- `authors` becomes "OpenVerifiers contributors".
- The gate scope is accepted.
- The rework plan is approved as a plan only; the reworked lines go in the
  next packet.
- The real-algebraic deferral is accepted.

**Trailers used on the applying commits:**
- `Meaning-Approved-By: founder (reply to packet c8c9af15519e)`
- `Gold-Change-Approved-By: founder (reply to packet c8c9af15519e)`
