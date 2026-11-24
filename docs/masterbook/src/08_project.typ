= How the project is run <ch8>

== The roles

{{badge:IMPLEMENTED}} The masterplan's working agreement (MP §9) {{src:MASTERPLAN.md:441-457}}:

{{listing:MASTERPLAN.md:443-447}}

In practice, at this commit: the founder signs approval commits (D-032) and replies to packets in writing; the CTO writes directives and decisions (most of D-009…D-027 are "Claude (CTO)"); Claude Code writes code, tests and checkpoint reports and prepares approval packets. This book was written by a Claude Code subagent (the Author) under a CTO directive, in a separate worktree, with a second agent (the Fact-Checker) auditing it afterwards.

== The masterplan and its decision log

`MASTERPLAN.md` (MP-1.3) is the single reference: thesis, architecture, languages, multi-domain handling, the six releases with exit criteria, the cross-cutting programs, the working agreement, risks and the decision log {{src:MASTERPLAN.md:1-5}}. Changes are versioned (MP-1.0 → 1.3) and each adds a decision row; only the founder approves (MP §9.6). Appendix I reproduces the log (D-001 … D-032). Three later decisions (D-033 sin/cos in the normal form, D-034 the CI-streak rule, D-031b JEE Main without a source) are recorded in the founder's packet-3 reply and go into `MASTERPLAN.md` through packet 4's signed commit, on `v1` after `bd2ed44` {{report:reports/APPROVAL_RECORD_2026-11-23_packet3.md}}.

== Checkpoints and reports

D-028: Claude Code works through engineering checkpoints without waiting, writes a report at each, and stops only for a false PROVEN, a trusted-code cap, CI red it cannot fix, or a gold or meaning approval {{src:MASTERPLAN.md:489}}. Every report has one shape (MP §9.3): what was done against the scope, exit-criteria status with evidence, the cross-cutting numbers, deviations, shortcuts found, decisions needed {{src:MASTERPLAN.md:453}}. The reports at this commit:

{{gen:reports}}

== Approval packets and the signed-approval flow

D-024 made approvals one-pass: the agent batches every meaning and gold line into one packet, each line classified by a reviewer and given a reference; the founder approves or rejects in one reply; the agent records exactly that decision. D-032 made the founder's approval a signed commit made outside any agent session (§3.11, @fig-approvals). Three packets have gone through:

#table(columns: (1.3fr, 1.2fr, 3fr),
  [*packet*], [*settled by*], [*what it decided*],
  [packet 1 (c8c9af15519e)], [written reply, recorded], [152 STANDARD statements approved (19 not: derivable, modelling or suspect); `chemistry.kinetics`, `chemistry.solid_state`, `math.vectors` moved into `packages/`; HSC sourcing; D-029 recorded {{report:reports/APPROVAL_RECORD_2026-11-23.md}}],
  [packet 2 (dd2d4fd885a8)], [the founder's signed commit {{commit:299262f}}], [47 STANDARD lines approved; N039 and N043 must become proven theorems, not laws; `repo_policy.ov` moved to `drafts/`; 9 fixes; D-030, D-031; ratification of earlier agent-stamped approvals {{report:reports/APPROVAL_RECORD_2026-11-23_packet2.md}}],
  [packet 3 (0e233e5b7e29)], [signed commit {{commit:7e45263}} for Part A; written reply for the rest], [physics.quantum approved (Bohr radius as a theorem); N043 kept UNPROVEN in drafts; M013, M036, M078, M079 rejected; D-031b applies; D-033, D-034 {{report:reports/APPROVAL_RECORD_2026-11-23_packet3.md}}],
)

== The anti-reward-hacking rules

The project is built by agents that are rewarded for passing checks, so the checks are designed so that the cheap way to pass is the honest way. The rules, and where each is enforced:

#table(columns: (2fr, 2.4fr),
  [*rule*], [*enforced by*],
  [Gold is written by hand, first and alone, before OV runs on the case], [the gold gate over the history {{src:src/openverifiers/bench/gold_gate.py:1-60}}],
  [Gold never changes without the founder's signed trailer], [the gold gate + `.approvers/allowed_signers` (D-032)],
  [Agents never write approval trailers], [D-032; the gate fails unsigned commits with a trailer {{src:docs/APPROVALS.md:1-36}}],
  [Meaning lines (axioms, laws, definitions, invariants, theorem statements) need the founder], [the meaning gate (D-023, D-025)],
  [A derivable result is a theorem, never a law], [D-025 {{src:MASTERPLAN.md:493}}; `ov audit`'s claim ratio],
  [A theorem stated too strongly is fixed in the definition, never by weakening a PROVEN theorem], [the founder's packet-3 reply (Part B) {{report:reports/APPROVAL_RECORD_2026-11-23_packet3.md}}],
  [The failing set may only shrink (the ratchet)], [`KNOWN_MISMATCHES` in {{test:tests/v1/test_bench.py::test_benchmark_suites_against_gold}}],
  [Exam problems are drawn mechanically before the library is built], [`DRAW_RULE.md` committed before `list.json` {{src:benchmarks/exams/DRAW_RULE.md:1-10}}],
  [No trusted check is removed or weakened to fit a cap], [D-030; restored loader checks {{commit:b2cfdb5}}],
  [Answers in exam cases may not be leaked, assumed or legislated], [the faithfulness lint F1–F5],
  [A reviewer that never sees the gold], [`faithfulness_review.json` per case],
  [Every number comes from a script anyone can re-run], [`reproduce.sh` (MP-v1 exit 6)],
  [Deviations and shortcuts are reported, not hidden], [the report shape (MP §9.3); each report has both sections],
)

== Timeline: M0 to the stamped commit

The repository's history starts in August 2026 with earlier prototypes (now `src/openverifiers/legacy/` and `m1/`); v1 as described in this book starts at M0 ({{commit:1f9c42b}}, 2026-11-20). Selected milestones, generated from `git log` (subjects containing a milestone, checkpoint, packet or decision tag):

{{fig:timeline}}
{{gen:timeline}}

{{fig:roadmap}}
