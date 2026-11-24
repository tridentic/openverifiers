#counter(heading).update(0)
#set heading(numbering: "A.1")

= Appendix: the full OV grammar <appA>

{{badge:IMPLEMENTED}} The parser's grammar file, verbatim {{src:src/openverifiers/lang/grammar.lark}}. Chapter 2.3 has the EBNF generated from it and the railroad diagrams.

{{listing:src/openverifiers/lang/grammar.lark}}

= Appendix: the OKQL grammar <appB>

*Implemented* (generated from `grammar.lark`):

{{gen:okql_ebnf}}
{{fig:rail_okql}}

*Designed* (MASTERPLAN §5.1, verbatim; every head not in the implemented grammar is PLANNED, ch. 4):

{{listing:MASTERPLAN.md:186-204}}

= Appendix: CLI reference <appC>

Every help text the `ov` command offers, captured by the build. Some subcommands do not implement `--help` and instead treat it as an argument; the outputs show exactly what happens (Appendix J).

{{gen:cli}}

The MCP server's usage is its module docstring {{src:src/openverifiers/mcp_gate.py:1-24}}; `reproduce.sh` takes an output folder {{src:reproduce.sh:1-7}}.

= Appendix: file-format schemas <appD>

*Terms, atoms, literals, spans* (the trusted canonical JSON):

{{listing:src/openverifiers/raw/canon.py:1-17}}

*Programs* (`program_to_json`):

{{listing:src/openverifiers/raw/canon.py:137-155}}

*OVTrace* (one JSON object per line after a header):

{{listing:src/openverifiers/raw/trace.py:71-107}}

*OVState:*

{{listing:src/openverifiers/state/hash.py:1-31}}

*Benchmark gold* (`expected.json`):

{{listing:src/openverifiers/bench/run.py:1-31}}

*Exam answer maps* (`answer.json`) and outcomes are documented in `ov exam --help` (Appendix C).

= Appendix: the error-code catalogue <appE>

Generated from the codes that occur in `src/openverifiers` (excluding `legacy/` and `m1/`) and in `docs/LANGUAGE.md`. Each example file is written by the build into `build/work/errors/` (most are package files, which must not be committed outside `drafts/`) and run with `ov run`; the build fails if the file does not produce its code.

{{gen:errors}}

= Appendix: the module map <appF>

Every module of `src/openverifiers` except the pre-v1 `legacy/` and `m1/`, with its physical line count and whether `scripts/tcb_size.py` counts it as trusted.

{{gen:modules}}
{{fig:imports_pkg}}
{{fig:imports}}

= Appendix: the package catalogue <appG>

Generated from the package files and from `ov audit --json` on every approved package (run by the build).

{{gen:packages}}

*Axioms by kind, theorems, ratios* (ratio = axioms / (axioms + theorems); claim ratio counts foundations, laws and non-conservative axioms only; strict claim counts an invariant as a definition only if it is `p = E`):

{{gen:audits}}

*Every theorem, with status and trust base:*

{{gen:theorems}}

{{fig:audit_dag}}

= Appendix: glossary <appH>

/ ATMS: assumption-based truth maintenance: each derived atom carries the set of assumption environments under which it holds (its _label_).
/ assumption: a named hypothesis, `assume n: lit`; it appears in the labels of everything that uses it.
/ axiom, law, definition: the three kinds of stated (unproved) knowledge; `ov audit` counts them (§2.4).
/ certificate: a polynomial identity (multiplier, ideal coefficients, squares, witnesses) that proves a claim and that `raw/certificate.py` checks exactly.
/ checker: the trusted code that accepts or rejects a trace (`checker/check.py`) or a record (`checker/objects.py`).
/ claim ratio: (foundations + laws + non-conservative axioms) / (those + theorems): how much of a package is assumed rather than proven.
/ closed world: a predicate declared `world closed`; "not derivable" means false. Default is open.
/ context: the set of active assumptions a verdict is computed in.
/ drafts: `drafts/`, unapproved libraries; loaded only with `--drafts`, results PROVISIONAL.
/ environment: a consistent set of assumption literals ($a$ or $not a$).
/ gold: the hand-written expected answer of a benchmark case, committed before OV runs on it.
/ invariant: a class member that is part of the class's definition.
/ kernel: the trusted code as a whole (L0 and L1); `{kernel}` in a trust base means it checked everything.
/ label: an antichain of environments; the exact set of contexts in which an atom holds.
/ lemma: a theorem that only its own package may use; exempt from the meaning gate.
/ lowering: translating OV into RawOV (rules) or compiled class formulas (objects).
/ meaning gate: the check that meaning-carrying lines change only with the founder's signed approval.
/ MP-DOL: AI drafts, OV decides, humans own meaning.
/ MP-INV: nothing becomes TRUE unless it traces through checked rules to declared axioms and facts.
/ nogood: an environment in which both $p$ and $"neg" p$ hold.
/ OKQL: the query language (ch. 4).
/ OVState: a checked model's unconditional atoms, canonical JSON plus SHA-256.
/ OVTrace: the evaluator's JSON-lines record of every derivation step.
/ packet: an approval packet: all pending gold and meaning lines, classified, for one founder reply.
/ provisional: a result that used a draft package.
/ RawOV: the kernel language: facts, rules, domains, world policies.
/ record: a JSON object behind an object-layer kernel verdict (a model or a certificate).
/ reduction (`red:*`): an untrusted rewrite that shrinks a theorem's unsat problem; listed in the trust base.
/ stratum: a layer of predicates such that closed-world negation only looks down.
/ trust base: what a verdict rests on: `kernel`, `z3_unsat`, `red:*`.
/ UNPROVEN: the printed name of an UNKNOWN theorem check.
/ witness: for `ln u` or `1/u`, a checked factorisation $u = c h_1 dots.c h_k e^(dots.c)$ showing $u > 0$.

= Appendix: the decision log <appI>

From `MASTERPLAN.md` §11 at the code commit, generated; newest first. D-033, D-034 and D-031b are in the founder's packet-3 reply and are added to `MASTERPLAN.md` on `v1` after `bd2ed44` {{report:reports/APPROVAL_RECORD_2026-11-23_packet3.md}}.

{{gen:decisions}}

= Appendix: Findings <appJ>

Bugs and inconsistencies the Author noticed while writing. None was fixed (docs only); each is listed for the supervisor and the founder. "Docs drift" means a document disagrees with the code at `bd2ed44`.

#table(columns: (0.3fr, 1.6fr, 3.4fr),
  [*\#*], [*where*], [*finding*],
  [J1], [{{src:src/openverifiers/state/export.py:31-44}}], [`ov state --help` crashes with a Python traceback (`FileNotFoundError: '--help'`): any unknown option is taken as the file path.],
  [J2], [{{src:src/openverifiers/audit.py}}], [`ov audit --help` looks for a package named `--help` and fails with "no package file …/--help.ov".],
  [J3], [{{src:src/openverifiers/gate.py}}], [`ov gate --help` ignores the flag and runs the gate ("ok (0 OV file(s))"); `ov bench --help` reports "unknown option --help"; `ov run --help` prints usage and exits 2. Only `ov --help` and `ov exam --help` print help (Appendix C).],
  [J4], [{{src:src/openverifiers/cli.py:39-66}}], [The brief's form `ov program.ov --verbose` is rejected ("unknown command"); only `ov run program.ov --verbose` works.],
  [J5], [{{src:reproduce.sh:32-34}}], [The mutant step keeps only lines starting with `{`, but pytest `-s` prints the tallies after progress dots, so `mutants.txt` holds only "22 passed"; the per-path mutant counts the C7 report quotes are not regenerated by `reproduce.sh`.],
  [J6], [{{src:src/openverifiers/lang/errors.py:1-17}}], [The docstring lists E104 (bad number), which no code raises, and omits E304, E405, E406, E407 and E208.],
  [J7], [{{src:src/openverifiers/lower/lower.py:724}} {{src:src/openverifiers/runner.py:93}}], [E208 means two different things: "undeclared type under `--strict`" (runner) and "OVState file refused" (lowering); `docs/LANGUAGE.md` documents only the first.],
  [J8], [{{src:docs/LANGUAGE.md:87-164}}], [Docs drift: the hand-written EBNF lacks `law`, `definition`, `lemma`, `WHY`, `WHY NOT` and quoted unit types, all in `grammar.lark`.],
  [J9], [{{src:docs/LANGUAGE.md:16-18}} {{src:docs/LANGUAGE.md:570}}], [Docs drift: "`ov run` arrives in Milestone 3" (it exists); the E207 row says `import state` and `tolerance` are unsupported (both are implemented; `tolerance` in a non-object context is now E206).],
  [J10], [{{src:docs/LANGUAGE.md:207-224}} {{src:src/openverifiers/lang/units.py:15-49}}], [Docs drift: the units table omits `dm`, `nm`, `pm`, `atm`, `deg`, and the dimension list omits the `deg` dimension; quantity types `Density`, `Integer`, `Real`, `Angle` are missing.],
  [J11], [{{src:docs/LANGUAGE.md:369}} {{src:docs/OKQL.md:29}} {{src:docs/LANGUAGE.md:609-610}}], [Contradiction: COUNT's budget is "64" in two places and "4096" (D-027) in a third.],
  [J12], [{{src:docs/OKQL.md:3-6}}], [Docs drift: "Milestone 4 adds WHY, WHY NOT, NEAR, DEPENDS ON, EXPLAIN and queries over a saved OVState": WHY and WHY NOT exist (documented later in the same file); the others do not.],
  [J13], [{{src:KNOWN_LIMITATIONS.md:95-97}} {{src:KNOWN_LIMITATIONS.md:23-24}} {{src:KNOWN_LIMITATIONS.md:37-38}} {{src:KNOWN_LIMITATIONS.md:113-115}} {{src:KNOWN_LIMITATIONS.md:163-165}} {{src:KNOWN_LIMITATIONS.md:229-230}}], [`KNOWN_LIMITATIONS.md` is stale in at least six entries: `tolerance` rejected; `import state` rejected; unsat always trusted to z3; the object path not mutation-tested; the query set lacks WHY/WHY NOT; the TCB described against the old 1,500-line gate.],
  [J14], [{{src:docs/SEMANTICS.md:1-7}} {{src:docs/OKQL.md:38-49}}], [Docs drift: SEMANTICS says it covers Milestone 0 and that plugins and OKQL "will extend it"; the trust-base tables in SEMANTICS §6 and OKQL do not mention certificates, which now give `{kernel}` to theorems and uniqueness claims.],
  [J15], [{{src:src/openverifiers/lang/grammar.lark:49-58}} {{src:MASTERPLAN.md:157}} {{src:MASTERPLAN.md:497}}], [MP §4.2, §8 and D-020 require a `because:` on every invariant; the grammar has no `because` clause and no file uses one.],
  [J16], [{{src:MASTERPLAN.md:510}}], [D-007 decides "three trust levels", but no document defines them (§1.3 gives the book's reading).],
  [J17], [{{src:src/openverifiers/runner.py:69-73}} {{src:src/openverifiers/mcp_gate.py:72-85}}], [Tool-call gate decisions from `drafts/policies/repo_policy.ov` report `"provisional": []`: `draft_packages` recognises only `drafts/packages/`, so a draft policy is not marked provisional.],
  [J18], [{{src:src/openverifiers/runner.py:182-186}}], [A rule FIND with no solution over a closed-world predicate answers UNKNOWN(open_world) (the probe atom is the open query predicate), where "no solutions" (REFUTED by the closed world) is the honest answer; shown in §4.2 with `violation`.],
  [J19], [{{src:scripts/tcb_size.py:24-25}}], [The comment on `EXACT` says "cap 450"; the cap `EXACT_LIMIT` is 700 (D-030).],
  [J20], [{{src:src/openverifiers/cli.py:24-25}} {{src:src/openverifiers/runner.py:1-8}}], [Stale docstrings: `cli.py` says `gate` arrives with a milestone (it exists); `runner.py` calls itself the Milestone-1 runner that `ov run` "(Milestone 3)" will wrap and OKQL "(Milestone 4)" will replace.],
  [J21], [{{src:src/openverifiers/bench/faithfulness.py:22-25}}], [The faithfulness lint's W1 needs the gitignored originals in `private/`; without them it silently reports 0 warnings, so the warning count depends on the machine (C7: 4; this build: 0).],
  [J22], [{{src:benchmarks/faithfulness/dropped_ball_negative_time/review.json}}], [The adversarial faithfulness case has `review.json` but no `expected.json`, so `ov bench` does not run it and nothing runs the reviewer against it automatically.],
  [J23], [{{src:reproduce.sh}}], [`reproduce.sh` does not print the `{kernel}` share of library theorems or any latency numbers, both of which the reports and the packet-3 work order quote as `reproduce.sh` numbers; the book computes the first with `ov audit` and takes latency from `bench/summary.csv`.],
  [J24], [{{src:MASTERPLAN.md:161-172}}], [The masterplan's proof hints (`by rewrite`, `by induction`, `by certificate …`) and its §4.2 example syntax (`over t: Time`, `derived`, entity patterns `Body { mass = 2 kg }`) are not accepted by the grammar. They are planned, but the masterplan presents them without a status.],
)

= Appendix: how to rebuild the book <appK>

*One command.* From the repository root, in a virtualenv with the dev and docs extras:

{{listing:docs/masterbook/build_commands.txt}}

*What the build does* is described in the script's docstring:

{{listing:scripts/build_masterbook.py:1-34}}

*Numbers.* `docs/masterbook/repro/<code-commit>/` holds the outputs of `reproduce.sh` for the commit the book describes (the last commit that touched anything outside the book's own files). When the code changes, the build refuses to run until `reproduce.sh` is run for the new commit (`--run-repro`, about 11 minutes on the build machine at `bd2ed44`).

*Snapshots.* Every command output is compared with `docs/masterbook/snapshots/`; a changed output fails the build until someone runs `make masterbook-accept` and reviews the diff. Runs use `PYTHONHASHSEED=0` and the build replaces the absolute repository path by `.`; a few timing fields are masked (`<masked>`), and each mask is visible in the marker that requested it.

*CI.* `.github/workflows/masterbook.yml` builds the book on every push to `docs/masterbook`, with the committed numbers (it does not rerun the 11-minute `reproduce.sh`), runs every command, fails on an unfilled placeholder, a failing or changed example, a badge without evidence, a broken citation, and uploads the PDF as an artifact:

{{listing:.github/workflows/masterbook.yml}}

*Fonts and layout.* Typst compiles with its embedded fonts only (`ignore_system_fonts`), so the layout is the same on every machine; diagrams are SVG from Graphviz `dot`.
