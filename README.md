# OpenVerifiers

Write domain knowledge as code, check every conclusion with a small trusted
kernel, and answer queries with a proof, a refutation, or an honest UNKNOWN.

> Nothing becomes TRUE unless it traces, through checked rules, back to
> declared axioms and stated facts. The evaluator proposes; only the checker
> decides.

**Status: v1 Milestone 0 is done** (RawOV kernel IR, labelled evaluator,
independent checker). The `.ov` language, plugins, OKQL and the prover come
in later milestones; see [PLAN.md](PLAN.md). The definitions are in
[docs/SEMANTICS.md](docs/SEMANTICS.md) and the shortcuts in
[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md). What moved is in
[MIGRATION.md](MIGRATION.md). The Milestone-1 step verifier still works under
`openverifiers.m1` ([docs/m1/](docs/m1/README.md)).

```bash
uv pip install -e ".[dev]"
python scripts/q11_raw.py          # HSC q11 from hand-written RawOV, all four verdicts
ruff check . && mypy && pytest -q  # 413 tests
python scripts/tcb_size.py         # trusted code must stay under 1,500 lines
```

| module | role | trusted |
|---|---|---|
| `openverifiers.raw` | RawOV terms, signed assumption labels, exact unit arithmetic, canonical text, trace format | yes |
| `openverifiers.checker` | re-verifies every trace step, checks closure, computes verdicts | yes |
| `openverifiers.kernel` | stratified semi-naive evaluator with labels and budgets | no (checked) |
| `openverifiers.engine` | evaluate → check → verdict | no |
