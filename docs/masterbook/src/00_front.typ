#set heading(numbering: none)
#page(header: none, footer: none)[
  #v(3cm)
  #align(center)[
    #text(size: 30pt, weight: "bold")[The OpenVerifiers Masterbook]
    #v(0.6em)
    #text(size: 14pt)[A walkthrough of the whole stack, as it exists at one commit]
    #v(2.5em)
    #text(size: 11pt)[For the founder's line-by-line review]
    #v(3em)
    #table(columns: (auto, auto), stroke: none, align: (right, left),
      [code commit described], [#raw(META.code_commit) (branch `v1`)],
      [book built from], [#raw(META.head) (branch `docs/masterbook`)],
      [build date], [#META.date],
      [numbers from], [#raw("bash reproduce.sh") at #raw(META.code_commit)],
    )
    #v(4em)
    #text(size: 9pt, fill: luma(80))[Written by the Author agent (Claude Code) under the CTO directive. Every listing and every output in this book was extracted from a real file or captured from a real command by `scripts/build_masterbook.py` during the build stamped in the footer. Status badges: #badge("IMPLEMENTED") #badge("PARTIAL") #badge("PLANNED").]
  ]
]

#page(header: none)[
  #outline(depth: 2, indent: 1em)
]

= Executive summary <exec>

*What OpenVerifiers is.* OpenVerifiers (OV) is a language for writing down knowledge (packages of laws, definitions and theorems), scenarios (facts and assumptions about a situation) and questions, plus a small trusted kernel that decides the answers. Everything else, including the parser, the evaluator, z3, sympy and any AI agent, may only _propose_; an answer counts only after trusted code has re-checked it (the masterplan's invariant MP-INV, {{src:MASTERPLAN.md:11-13}}). Every answer is one of four verdicts (PROVEN, REFUTED, UNKNOWN, INCONSISTENT) and names its trust base: `{kernel}` when trusted code checked everything, or a list such as `{z3_unsat, red:translate}` when it rests on an unchecked solver result.

*What works today*, as of commit `bd2ed44` (each item is explained, with evidence, in the chapter named):

- The trusted core: a RawOV data model, an independent trace checker, signed ATMS labels, stratified negation, verdicts, a certificate checker over exact $QQ$, square roots, $QQ(pi)$ and an exp/ln ring, and an OVState hash and loader (ch. 3). {{badge:IMPLEMENTED}} {{src:scripts/tcb_size.py}}
- The OV language: packages, imports, types with units, predicates, axioms, laws, definitions, transformations, a guard-only controller, generators, scenarios with `assume`, and the object layer (`fact type`, invariants, theorems, lemmas, multiple inheritance, collections) (ch. 2). {{badge:IMPLEMENTED}} {{src:src/openverifiers/lang/grammar.lark}}
- OKQL inside `.ov` files: PROVE, FIND, PROVE UNIQUE, COUNT, CHECK … IS, COUNTEREXAMPLE, WHY, WHY NOT and WHAT IF (ch. 4). NEAR, DEPENDS ON, querying a saved state with `USING`, and every v2/v3 mode are not built. {{badge:PARTIAL}} {{src:src/openverifiers/lang/grammar.lark:78-90}}
- The `ov` command (`run`, `check`, `audit`, `state`, `gate`, `exam`, `bench`), a commit gate, an MCP tool-call gate, signed founder approvals and a whole-history gold/meaning gate (ch. 3). The brief's bare form `ov program.ov --verbose` is not accepted: it is `ov run program.ov --verbose`. {{badge:PARTIAL}} {{src:src/openverifiers/cli.py:39-66}}
- OVProver: only the `target` syntax and its type check exist, plus search pieces that a prover would use. {{badge:PLANNED}} {{mp:v2 Engine, MP §7 "OVProver PLAN with abduction and gap reports"}}

*Headline numbers* (from `reproduce.sh` at `bd2ed44`, ch. 6):

#table(columns: (2.2fr, 3fr),
  [trusted code (D-030 headline)], [{{num:tcb.total}} of {{num:tcb.total_cap}} lines (main {{num:tcb.main}}/{{num:tcb.main_cap}}, `raw/formula.py` {{num:tcb.formula}}/{{num:tcb.formula_cap}}, unit A {{num:tcb.exact}}/{{num:tcb.exact_cap}})],
  [tests], [{{num:tests.all_passed}} passed (whole suite); trusted-code coverage {{num:coverage.trusted}}],
  [benchmarks (gold-first)], [{{num:bench.pass}}/{{num:bench.total}} default, {{num:bench_strict.pass}}/{{num:bench_strict.total}} `--strict`; false PROVEN {{num:bench.false_proven}} and {{num:bench_strict.false_proven}}],
  [JEE Advanced 2025 (30 drawn)], [default with drafts: {{num:exam.outcomes.solved}} solved, {{num:exam.outcomes.unknown}} unknown, {{num:exam.outcomes.not_formalized}} not formalized, 0 wrong; `--strict`: {{num:exam_strict.outcomes.solved}} solved, {{num:exam_strict.outcomes.unknown}} unknown, {{num:exam_strict.outcomes.error}} error, 0 wrong],
  [differential testing], [{{num:diff.cases}} cases: {{num:diff.agree}} agree, {{num:diff.refused}} refused, {{num:diff.disagree}} disagree],
  [library theorems at `{kernel}`], [{{num:audit.kernel}} of {{num:audit.theorems}} ({{num:audit.kernel_pct}}) over {{num:audit.packages}} approved packages (from `ov audit`, run by this build; `reproduce.sh` does not print it)],
  [gold and meaning gate, whole history], [{{num:gold_gate.line}}],
)

*The biggest gaps*, in the order the founder is likely to care about:

+ *OVProver does not exist.* Component 4 of the brief is design only (ch. 5). {{badge:PLANNED}} {{mp:v2 Engine, MP §7}}
+ *OKQL's "near match" does not exist.* There is no NEAR, no DEPENDS ON and no query against a saved OVState by name; WHY NOT's missing-facts frontier is the closest thing (ch. 4). {{badge:PARTIAL}} {{src:docs/OKQL.md:1-10}}
+ *v1 has not exited.* Criterion 1 is partial (JEE Main has no source; the founder's packet-3 reply applies D-031b) and criterion 6 needs 20 green CI runs in a row {{report:reports/V1_EXIT_C7_2026-11-23.md}} {{report:reports/APPROVAL_RECORD_2026-11-23_packet3.md}}.
+ *Theorems still rest on z3 in places.* {{num:audit.kernel}} of {{num:audit.theorems}} library theorems are at `{kernel}`; the rest name `z3_unsat` and reductions in their trust base, and `--strict` turns them into UNKNOWN (ch. 6).
+ *Trigonometry of a variable is not in the trusted normal form* (D-033 is being built on `v1` after `bd2ed44`), which blocks N043 and some JEE problems (ch. 9).
+ *Documentation drift.* `docs/LANGUAGE.md`, `docs/OKQL.md` and `KNOWN_LIMITATIONS.md` describe some features as not yet built that are built, and the reverse. Appendix J lists every case found.

= How to read this book

*The order of every chapter* is the one the directive asks for: intuition first, then the precise definition (with equations), then a real example, then the status, then the limitations.

*Status badges.* Every feature, construct, command and claim about capability carries one badge:

- {{badge:IMPLEMENTED}} in code, tested, and used by examples. The evidence marker next to it says where. {{src:tests/v1}}
- {{badge:PARTIAL}} part works; the text says precisely which part does and which does not. {{src:KNOWN_LIMITATIONS.md}}
- {{badge:PLANNED}} not built. It always names its masterplan release or decision, and it is never described in the present tense. {{mp:MP §7 release plan}}

The build fails if a badge has no evidence marker next to it, or if a PLANNED badge has no masterplan reference.

*Evidence markers* are the small grey brackets:

- #ev("src", "path:A-B"): a file and line range at the stamped commit. The build checks that the file exists and has those lines.
- #ev("test", "path::name"): a test function; the build checks it exists.
- #ev("commit", "hash"): a commit; the build checks it is in the history.
- #ev("report", "path"): a report in `reports/`.
- #ev("plan", "text"): a masterplan release, section or decision ID (checked against `MASTERPLAN.md`).

*Real listings and real runs.* A box headed #raw("file  path") is an excerpt of that file, cut by the build. A blue box headed #raw("$ command") is the output of that command, run by the build from the repository root with the worktree's `ov`; its exit code is shown. Each output is compared with a committed snapshot in `docs/masterbook/snapshots/`, so a changed output fails the build until a person accepts it. Long outputs are cut, and the cut says how many lines are missing.

*Numbers.* A number in #num("blue bold") was read by the build from the outputs of `reproduce.sh` at the code commit in the footer, stored in `docs/masterbook/repro/`. A few numbers come from other commands run by the build (for example `ov audit`); the sentence then says so.

*How to reproduce everything.* Appendix K. In short:

#listing("commands", "bash", "python3 -m venv .venv && .venv/bin/pip install -e \".[dev,docs]\"\nbash reproduce.sh docs/masterbook/build/repro      # about 11 minutes on the build machine\n.venv/bin/python scripts/build_masterbook.py        # or: make masterbook")

*Words.* The founder is "the founder". "The CTO" is Claude in claude.ai, which owns the masterplan. "Claude Code" or "the agent" is the engineering agent in the repository (MP §9, {{src:MASTERPLAN.md:441-457}}).

= Brief compliance table <compliance>

This is the table to check first. Each row is one bullet of the founder's four-component brief (quoted verbatim in @brief), where it lives, its status, the evidence, and what remains.

#table(columns: (1.35fr, 1fr, 0.75fr, 2.5fr, 1.7fr),
  [*brief bullet*], [*where in this book*], [*status*], [*evidence (one line)*], [*what remains*],
  [1.1 Domain-specific packages, authorable like code: `import physics`], [§2.4], [{{badge:PARTIAL}}], [`import physics.mechanics` resolves a dotted name to `physics/mechanics.ov` next to the file, then in `packages/` (and `drafts/` with `--drafts`) {{src:src/openverifiers/lang/check.py:236-256}}. A bare `import physics` is E203: there is no umbrella package.], [umbrella packages; versioned imports (a package states `@0.1` but imports cannot ask for a version); registry {{mp:v4 Atlas, MP §7}}],
  [1.2 Scenario with domain types of Facts, Transformation, Controller], [§2.5, §2.6], [{{badge:PARTIAL}}], [`scenario`, `fact`, `assume`, `transformation … requires … ensures`, `controller { pipe; branch; guard }` parse and lower {{src:src/openverifiers/lang/grammar.lark:28-45}}; a controller's `pipe` and `branch` are checked for names but carry no meaning, only `guard` does {{src:KNOWN_LIMITATIONS.md:89-92}}], [controller ordering semantics; no repository file outside one test uses `transformation` or `controller` {{test:tests/v1/test_lang.py::test_scenario_extends_and_controller_guard}}],
  [1.2 Native equation / inequality support; `math` package for the rest], [§2.8], [{{badge:IMPLEMENTED}}], [exact $QQ$ quantities with dimension vectors, `=` solved for each slot, comparisons, surds, $QQ(pi)$, exp/ln, intervals {{src:src/openverifiers/raw/formula.py}}; `math.core`, `math.geometry`, `math.calculus`, `math.vectors`, `math.vector_products` packages {{src:src/openverifiers/packages/math}}], [sin/cos of a variable (D-033, on `v1` after `bd2ed44`); real algebraic numbers {{mp:v2, D-030}}; topology etc. not started],
  [1.2 Core types Fact, Transformation, Controller / Generator], [§2.6], [{{badge:PARTIAL}}], [Fact and Generator are used throughout (q11's `generator A, B from isomers(C5H10)` {{src:examples/chem/q11.ov:4}}); object-layer generators `cycles`, `orderings`, `subsets`, `pairs` {{src:docs/LANGUAGE.md:346-347}}], [see the Controller row],
  [1.2 Generated by an Agent], [§2.10], [{{badge:PARTIAL}}], [every JEE formalization was written by an agent and reviewed by a gold-blind reviewer agent (`faithfulness_review.json`) {{src:benchmarks/exams/jee2025/jee2025-phys-p2q9/faithfulness_review.json}}; faithfulness lint {{src:src/openverifiers/bench/faithfulness.py}}; MCP `check_files` tool {{src:src/openverifiers/mcp_gate.py:51-58}}], [an authoring MCP server (draft → check → fix loop) and a documented SDK do not exist],
  [1.2 Auto-derived by algorithmic solvers (later planned)], [§2.10, ch. 5], [{{badge:PLANNED}}], [no OV source is ever produced by a solver; solvers only answer queries {{mp:v2 Engine, MP §7 OVProver}}], [the whole of OVProver],
  [1.3 Sugar broken down into fundamental facts and relations], [§2.9], [{{badge:PARTIAL}}], [rules, equations, generators, assumptions, transformations, controllers, units lower to RawOV facts and rules, each with its source span {{src:src/openverifiers/lower/lower.py}}; ten side-by-side lowerings in §2.9 are generated by the build], [the object layer compiles to formula terms checked by `raw/formula.py`, not to RawOV facts: classes and rules are "two separate worlds" {{src:KNOWN_LIMITATIONS.md:44-47}}],
  [2.1 `ov program.ov --verbose`], [§3.1], [{{badge:PARTIAL}}], [`ov run program.ov --verbose` works; `ov program.ov` exits 2 with "unknown command" {{src:src/openverifiers/cli.py:64}}], [accept the bare form, or document the subcommand as the interface],
  [2.1 … or be exposed as a library], [§3.2], [{{badge:PARTIAL}}], [`openverifiers.runner.run_file`, `engine.run`, `checker.verdict`, `rawtext.parse` are importable and used by the tests; a real call is shown in §3.2 {{src:docs/masterbook/examples/sdk_demo.py}}], [no documented, stable SDK; `docs/SDK.md` is item 4 of the packet-3 work order {{report:reports/APPROVAL_RECORD_2026-11-23_packet3.md}}],
  [2.2 OV → RawOV], [§3.3], [{{badge:IMPLEMENTED}}], [`lower/lower.py`; canonical JSON in `raw/canon.py`; a printable RawOV text form {{src:src/openverifiers/rawtext.py:1-30}}], [no `ov lower` command to print RawOV (cli.py docstring lists it as future) {{src:src/openverifiers/cli.py:24-25}}],
  [2.2 RawOV → OVTrace], [§3.3–3.4], [{{badge:PARTIAL}}], [the evaluator writes a JSON-lines trace and the checker re-reads exactly that text {{src:src/openverifiers/engine.py:36-39}}], [no command writes the trace to a file (this book writes them with the library); object-layer steps are JSON records, not OVTrace steps],
  [2.2 —(success)→ OVState, trusted, importable and reusable], [§3.9], [{{badge:IMPLEMENTED}}], [`ov state` writes canonical JSON + SHA-256; `import state "f.json" as n` loads it through the trusted loader {{src:src/openverifiers/state/load.py}}; round trip {{test:tests/v1/test_state.py::test_export_import_round_trip}}], [only unconditional atoms are saved (no rules, no labelled atoms, no object-layer results); querying a state directly (`USING`) is not built {{mp:MP §5.1}}],
  [3.1 Check whether a fact was derived], [§4.2], [{{badge:IMPLEMENTED}}], [PROVE, WHY, FIND, CHECK … IS {{test:tests/v1/test_why.py::test_why_and_why_not}}], [—],
  [3.1 … or a near match], [§4.3], [{{badge:PARTIAL}}], [WHY NOT reports the missing premises that would make a fact PROVEN; FIND lists candidates; WHAT IF changes assumptions {{src:src/openverifiers/runner.py:352-369}}], [NEAR claim WITHIN k and DEPENDS ON are not built {{mp:MP §5.1}}],
  [3.2 "A lot of potential"], [§4.4], [{{badge:PLANNED}}], [PROPAGATE, COMPUTE, OPTIMIZE, PARETO, WHY NOT option, WHAT WOULD IT TAKE, PLAN, EXPLAIN are designed in MP §5.1 {{mp:v2 Engine and v3 Lens, MP §7}}], [all of them],
  [4.1 OVProver: generate a program that satisfies a target, or the maximum], [ch. 5], [{{badge:PLANNED}}], [`target n { must …; prefer … }` parses and is type-checked, and nothing consumes it {{src:src/openverifiers/lang/check.py:395-398}}; bounded plan synthesis inside `agent.workflow` {{src:src/openverifiers/packages/agent/workflow.ov:48-62}}], [backward chaining, abduction, proposers, scoring, gap reports {{mp:v2 Engine, MP §7}}],
)

The table's evidence is checked by the build; the narrative in each section gives the details, and Appendix J lists the inconsistencies found while writing it.
