# Approval record: the founder's reply to packet 2 (blob dd2d4fd885a8)

Packet: `reports/APPROVAL_PACKET_2026-11-23_C6.md`, git blob `dd2d4fd885a8`.
The reply, quoted exactly:

```
REPLY TO APPROVAL PACKET 2 (blob dd2d4fd885a8): the founder's decisions
- Part A: approve all 47 STANDARD. N039 (Bohr radius) and N043 (ω² = κ/I) are DERIVABLE: rewrite them as theorems and prove them; they are not approved as laws.
- Part A2: approve moving examples/policies/repo_policy.ov to drafts/ (this approves removing P001–P004 from the gated path). Record the approval so the whole-history gate in reproduce.sh no longer flags 3c29133.
- Part B: approve the 9 fixes, except any that removes or weakens the statement of a PROVEN theorem. List those separately in the next packet, unapplied.
- Part C: HSC is no longer required for v1 (see D-031 below). If HSC papers arrive later, the tier runs in v1.1.
- Masterplan changes approved by the founder in this message: D-030 and D-031 below. Add them to MASTERPLAN.md's decision log as MP-1.2, quoting this reply.
Record these decisions exactly, with trailers quoting this reply and the packet hash. Anything in packet 2 not named here stays unapproved.

D-030: trusted-code budget (the founder approves; CTO rationale)
- New caps: unit A 700, raw/formula.py 450, main 1,150; total 2,300 (hard). The total stays the headline number in every report.
- New rule, MP §8 Trust: "No trusted check may ever be removed or weakened to fit a cap. If a cap blocks work, report it; caps change only by a masterplan decision."
- Restore, first, the OVState loader's sortedness and groundness checks, and their tests (unsorted states refused again).
- Then spend, in this order:
  (1) surd-valued uniqueness certificates, Q(√d) multipliers and values; report how many JEE answers reach {kernel};
  (2) π in integrands;
  (3) ln in the exp ring (d ln u = u'/u with u > 0 checked).
- Real algebraic numbers: deferred to v2 (only phys p1q10 needs them).

D-031: v1 exit criterion 1 amendment (the founder approves)
- Replace "HSC 45" with "JEE Main 2025: 45 problems drawn mechanically (15 per subject), gold from NTA's official final answer keys". Fetch papers and keys only from official NTA domains (list them in the report). If NTA does not publish both papers and keys, stop and report instead of substituting another source.
- HSC becomes a v1.1 tier, run when papers are supplied.
```

## How each decision is applied

| decision | applied as | status |
|---|---|---|
| Part A, 47 STANDARD | the six draft files whose statements are all STANDARD move to `src/openverifiers/packages/`: `agent.workflow`, `chemistry.gases`, `math.vector_products`, `physics.electromagnetism`, `physics.gravitation`, `physics.thermal`. The STANDARD lines of `physics.quantum` (N034–N038, N040, N041) and `physics.rotation` (N042) are approved but their files stay in `drafts/` until N039 and N043 are theorems | pending (see below) |
| Part A, N039 and N043 | not approved as laws. To be rewritten as theorems and proved; any new law they need goes to packet 3 | C7 work |
| Part A2 | `examples/policies/repo_policy.ov` moves to `drafts/policies/`. `RETRO_APPROVALS` records the approval of `3c29133` (kind `meaning`); the gold gate now reads that file at the head of the checked range, and a line in it counts only if its own commit carries the founder's trailer | pending (see below) |
| Part B | applied: M001, M032, M033, M034, M108. Held, unapplied, for packet 3: M078 and M079 (the new Quadrilateral hypothesis weakens the PROVEN theorems of Parallelogram and Rectangle); M013 and M036 (as proposed, each turns a package `expect` or a benchmark gold verdict, which needs a gold approval the reply does not give) | pending (see below) |
| Part C | HSC is not required for v1; a v1.1 tier | recorded in MASTERPLAN §7 |
| D-030, D-031 | MASTERPLAN MP-1.2: decision log, §3 L0/L1 caps, §7 v1 exit criteria 1 and 5, §8 Trust rule; `scripts/tcb_size.py` caps 1,150 / 450 / 700 / 2,300 | done |
| D-030, loader checks | `state/load.py` refuses unsorted and non-ground states again; `tests/v1/test_state.py` tests both | done |

Anything in packet 2 not named above stays unapproved.
