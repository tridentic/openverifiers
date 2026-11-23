# Approval record: the founder's reply to packet 3 (blob 0e233e5b7e29)

Part A was settled by the founder's signed commit `7e45263` (`G founder`):
`physics.quantum` is approved and in `packages/`. The reply, quoted exactly:

```
REPLY TO PACKET 3 (the founder's decisions)
- Part A (Bohr radius rework): settled by the founder's signed command.
- Part A2 (N043): keep as an UNPROVEN theorem in drafts. Any answer using it carries it as an explicit assumption. Retry the proof after D-033.
- Part B: reject M013, M036, M078, M079 for now. Re-propose any that fixes a real error, with a one-line justification each. A theorem stated too strongly is fixed in the definition (invariant), never by weakening a PROVEN theorem.
- Part C: if private/sources/jee_main/ holds papers + official NTA keys, run the JEE Main tier (draw → gold first → formalize). If it's empty, D-031b applies.
- Part D: the founder is adding the key on GitHub as a signing key; switch the CI check from warn to fail once the API shows it.
Masterplan changes below (D-033, D-034, D-031b): stage them in MASTERPLAN.md on the approval branch, so the founder's signed packet-3 commit covers them. If that commit has already landed, put them in packet 4.

D-033 (CTO; the founder approves via signature): sin/cos of a variable in the trusted normal form. Indeterminates S_u and C_u with dS_u = u'·C_u, dC_u = −u'·S_u, and the reduction S_u² + C_u² = 1. At most ~40 trusted lines in unit A. Differential tests for each construct. Shown in 3 domains (SHM/torsion, AC circuits, a trig identity in math). Then prove N043. Inverse trig stays v2.

D-034 (CTO): the CI streak counts push runs on distinct commits plus one nightly scheduled run (add the cron workflow). Manual re-runs of the same commit don't count. Report the streak with run IDs.

D-031b (only if no JEE Main source): v1 exit criterion 1 counts JEE Advanced 30 + agentic 20 + breadth 35 + adversarial 50. JEE Main and HSC become v1.1 tiers. The exit report must say plainly that v1 has one official-key exam tier.

WORK ORDER (no waiting; stop only on D-028 triggers or for packet 4)
1. Fix the exit report: §3 must contain the actual reproduce.sh numbers table (TCB per unit and total, unsound mutants by path, {kernel} share, --strict rates, false PROVEN by suite, JEE default/strict, latency, differential, CI streak with run IDs). Add a CI check that fails if any report contains an unfilled placeholder.
2. D-033, then retry N043 and any JEE problem trig unblocks.
3. JEE Main tier if its source exists.
4. A documented Python SDK surface (v1 scope): docs/SDK.md, stable public API, examples, tests.
5. Keep building the CI streak under D-034 until 20.
6. Final v1 exit report with every criterion evidenced, plus packet 4 for anything new and meaning-carrying.
Do not start v2 work.
```

## How each decision is applied

| decision | applied as |
|---|---|
| Part A | the founder's signed commit `7e45263`; nothing more to do |
| Part A2 | `physics.rotation`'s N043 becomes `theorem small_oscillation` (UNPROVEN) in `drafts/`. JEE phys p2q3 restates it in its case as a commented assumption, and its `answer.json` lists it under `assumptions`, which the exam report shows. The proof is retried after D-033 |
| Part B | M013, M036, M078 and M079 are rejected and stay as they are. Any that fixes a real error may be re-proposed, with a one-line justification |
| Part C | `private/sources/jee_main/` does not exist, so **D-031b applies** |
| Part D | the CI anchor switches from warn to fail once the GitHub API shows the founder's signing key |
| D-033, D-034, D-031b | the signed packet-3 commit had landed, so they go to MASTERPLAN.md through packet 4's signed commit. The work they order goes ahead now (no waiting, per the work order) |

The headline TCB stays the total (D-030). Anything not named in the reply stays
unapproved.
