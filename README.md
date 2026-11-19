# OpenVerifiers

Write domain knowledge as code, check every conclusion with a small trusted
kernel, and answer queries with a proof, a refutation, or an honest UNKNOWN.

**Status: v1 under construction.** See [PLAN.md](PLAN.md) for milestones and
[MIGRATION.md](MIGRATION.md) for what moved. The Milestone-1 step verifier
still works under `openverifiers.m1` ([docs/m1/](docs/m1/README.md)).

```bash
uv pip install -e ".[dev]"
ruff check . && mypy && pytest -q
```
