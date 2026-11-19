# Migration notes

Breaking changes, newest first. Each entry says what changed, why, and what
to do.

## v1 restructure (branch `v1`)

| change | before | after | what to do |
|---|---|---|---|
| src layout | package at repo root `openverifiers/` | `src/openverifiers/` | reinstall: `uv pip install -e ".[dev]"`. Running from a checkout without installing needs `PYTHONPATH=src` |
| Milestone-1 verifier moved | `openverifiers.kernel`, `.domains`, `.proposers`, `.case`, `.cli`, `.demo` | `openverifiers.m1.kernel`, `openverifiers.m1.domains`, … | replace `openverifiers.` with `openverifiers.m1.` in imports. The API is unchanged and frozen |
| M1 benchmark moved | top-level `benchmarks` package, cases in `benchmarks/cases/` | `openverifiers.m1.benchmarks`, cases in `src/openverifiers/m1/benchmarks/cases/` | `python -m openverifiers.m1.benchmarks.run`. The top-level `benchmarks/` now holds the v1 `.ov` suites |
| `openverifiers.kernel` means something new | M1 step-DAG checker | v1 labelled Datalog evaluator (untrusted; the trusted parts are `openverifiers.raw` and `openverifiers.checker`) | code importing the old kernel must switch to `openverifiers.m1.kernel` |
| M1 docs moved | `README.md`, `STATUS.md`, `DECISIONS.md`, `docs/architecture.md` | `docs/m1/` | the root README now describes v1 |
| legacy hook path | `.claude/settings.json` ran `openverifiers/legacy/plugin/pre_tool_use.py` | `src/openverifiers/legacy/plugin/pre_tool_use.py` | none |
| `ov` CLI | M1 commands | still M1 until v1 Milestone 3, then the v1 CLI (`run, check, lower, query, prove, bench, add, serve`). M1 commands move to `ov-m1` | scripts calling `ov check <case.json>` should switch to `ov-m1` once M3 lands |
| license (planned, M7) | MIT | Apache-2.0, as requested by the v1 brief | none for users; contributors note the relicense |
