# Benchmarks

`benchmarks/<suite>/<case>/case.ov` is the problem; `expected.json` next to it
is the gold. The seven suites are the brief's §9.2 table:

- physics
- chemistry
- mathematics
- geometry
- logic
- agentic
- adversarial

Run them with `ov bench` (see `src/openverifiers/bench/run.py` for the gold
format and the outputs).

Rules (change order v1.1):
- **Gold is written by hand.** Each entry has a `why`. It is never generated
  by running OV.
- **Gold is committed first.** A new case's `case.ov` and `expected.json` go
  in a commit that touches nothing outside `benchmarks/`, before OV is run on
  the case. The gold gate (`python -m openverifiers.bench.gold_gate`, CI job
  `gold-gate`) enforces this. `git log` shows the order.
- **Gold is never edited to make a case pass.** A change to an existing
  `expected.json` needs the trailer `Gold-Change-Approved-By: <human>`.
  Disputed gold is listed in the step reports, not silently changed.
- **Exception, disclosed:** `chemistry/q11` restates the brief's reference
  problem. OV has run on `examples/chem/q11.ov` since M1, so that case's gold
  cannot predate every OV run. Its gold is the brief's, derived by hand.
