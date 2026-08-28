A knowledge wiki for the OpenVerifiers repository: the design history, the
reasoning-engine architecture, and the research that informs open design
questions.

This wiki is a project wiki, not a pure code wiki: it documents intent,
decisions, and open questions. Sources of truth:

- `docs/design.md` — canonical design history (finalized v1 decisions).
- `docs/newer-additions.md` — newer design additions, each marked
  finalized-v1 / out-of-scope-v1 / open-research.
- `docs/research/` — research briefs (01–06) + `synthesis.md` (decision
  recommendations and conflict flags).
- `ARCHITECTURE.md` — implementation spec of the built engine.
- The Python SDK under `openverifiers/` (package) and `tests/`.
- `RESULTS.md` — physics benchmark record.

Page conventions: every page that states a decision or an open question must
mark it with one of: `[v1]` finalized v1 scope, `[out-v1]` explicitly out of
scope for v1, `[open]` open research feeding a not-yet-finalized decision.
Ground claims in the sources above with repo:// or docs:// references. Never
invent numbers, systems, or citations. Where research findings conflict with a
prior decision, say so explicitly on the page and link the conflict to
`docs/research/synthesis.md`.
