# experimental/ — archived, NOT part of the shipped surface

These files are preserved snapshots of earlier design threads:

- `proofstore.py` — proof-tree construction from the pre-typed engine's trace.
- `grammars_logistics.py` — Z3 route-satisfaction demo grammar.
- `grammars_circuits.py` — KVL/KCL/MNA circuit solver demo.
- `grammars_examples.py` — worked examples for the above.

They predate the typed core (Dimension/Unit/Quantity/Controller) and import the
old `model.py`/`grammars/` APIs, which no longer exist. They are NOT wired into
any test or CLI path and are NOT guaranteed to import: reuse them only as
design reference, and port whatever survives onto the typed core.

Current shipped surface: `openverifiers/__init__.py` (controllers, engine,
typed facts; audit-only `.ovpv` writer) and its tests.