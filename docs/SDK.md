# The OpenVerifiers Python SDK (v1)

`openverifiers.sdk` is the library side of the `ov` runtime: check OV files or
source text, read every verdict and what it rests on, export an OVState, gate an
agent's tool calls and files, and get OV-Paper blueprints.

```python
from openverifiers import sdk

report = sdk.check("examples/chem/q11.ov")
for q in report.queries:
    print(q.verdict, q.query, q.values, q.trust)
```

A runnable tour is `examples/sdk/quickstart.py` (`python examples/sdk/quickstart.py`
from the repository root). It is run by `tests/v1/test_sdk.py`.

## Install

```bash
pip install -e .
```

The SDK needs Python 3.11 or later and nothing beyond the package's own
dependencies.

## Stability

Everything in `sdk.__all__` is the public API, version `sdk.SDK_VERSION == "1.0"`.
Within v1:
- public names, parameters and result fields only grow;
- nothing is renamed or removed;
- `tests/v1/test_sdk.py::test_the_public_surface_is_stable` pins the surface.

Anything outside `sdk` (`runner`, `objects`, `raw`, ...) is internal and may change.

## Trust

The SDK is untrusted glue, and makes no verdict of its own:
- **Rule-query verdicts** come from a trace that the independent checker
  (`openverifiers.checker`, trusted) accepted.
- **Object-query verdicts** come from the trusted evaluator, certificate checker
  and record checker.

Each result says what it rests on, in `trust`:
- `("kernel",)`: the trusted checker alone;
- anything else, such as `"z3_unsat"`: the verdict also rests on a solver result
  that the kernel did not check. `strict=True` turns such verdicts into UNKNOWN.

Results that loaded unapproved draft packages list them in `provisional`.

## API

### `check(path, *, strict=False, drafts=False) -> Report`

Checks an OV file, as `ov check` does: every query, every `expect`, and every
class check (consistency and theorems).
- **`strict`:** only kernel-checked verdicts count, and draft packages never
  load.
- **`drafts`:** also loads unapproved packages from `drafts/packages/`. Results
  are then provisional.
- **Errors:** raises `OVError` (with `.diagnostics`, each with a code, a span and
  a hint) if the file does not load.

### `check_source(source, *, name="inline.ov", directory=".", strict=False, drafts=False) -> Report`

The same, for OV source text. `directory` is where imports of local files
resolve. Nothing is written to disk.

### `Report`

| field | meaning |
|---|---|
| `file` | the file checked |
| `queries` | a tuple of `QueryResult`, in file order |
| `classes` | a tuple of `ClassCheck`: class consistency and theorems |
| `provisional` | the draft packages loaded (empty if none) |
| `failed_expectations` | how many `expect` lines failed |
| `ok` | no failed expectation, no refuted theorem, no empty class (property) |
| `to_json()` | the report as plain JSON data, for agents |

### `QueryResult`

| field | meaning |
|---|---|
| `query` | the query text |
| `line` | its line in the file |
| `verdict` | `PROVEN`, `REFUTED`, `UNKNOWN` or `INCONSISTENT` |
| `trust` | what the verdict rests on: `("kernel",)`, or with solver results |
| `values` | the answers of a FIND, or the count of a COUNT |
| `assumptions` | the named assumptions a verdict depends on |
| `reason` | why the verdict is UNKNOWN: open world, missing facts, budget ... |
| `missing` | the facts whose absence blocks a PROVEN (for UNKNOWN) |
| `proven`, `kernel_checked` | convenience properties |

### `ClassCheck`

| field | meaning |
|---|---|
| `check` | the check's title |
| `verdict` | the verdict of that check |
| `trust` | what the verdict rests on |
| `reason` | why, when it is not PROVEN |

### `export_state(path, scenario=None) -> dict`

The OVState of a scenario, as `ov state` writes it: canonical JSON of its
unconditionally derived atoms, with their SHA-256. OV imports it with
`import state "file.json" as name`. Imported atoms are stated facts of the
importing scenario; trust never rises on import.

### `gate_tool_call(policy, tool, target, *, drafts=False) -> dict`

The agent tool-call gate. It returns `{"decision": ..., ...}` for one requested
call under an OV policy file (`agent.workflow`).

| decision | when |
|---|---|
| `refused` | the call is forbidden |
| `needs_human` | it needs approval, or the policy does not name the tool or target (deny by default) |
| `permitted` | neither |
| `unknown` | the policy decides nothing |

### `gate_files(paths, *, drafts=False) -> list[tuple[str, bool, str]]`

`ov gate` on these OV files. Each file must load, and its expectations and
theorems must hold.

### `blueprints(path, *, drafts=False) -> list[dict]`

OV-Paper blueprints (plain JSON) for every class theorem in the file. Each one
has:
- the statement;
- who proposed it;
- its closure by role;
- its steps;
- its lemma boundaries.

## Example output

From `python examples/sdk/quickstart.py` (q11, then the gate):

```
PROVEN    FIND ?A, ?C, ?D
          values=['2-methylbut-1-ene, butanone, methanal'] trust=['kernel'] assumptions=[]
PROVEN    FIND ?p WHERE major(add(B, HBr, peroxide)) = ?p
          values=['1-bromopentane'] trust=['kernel'] assumptions=['single_major']
REFUTED   PROVE optically_active(add(C, HCN))
UNKNOWN   WHAT IF RETRACT not tautomerizes(D) THEN FIND ?A
...
run_tests feature: permitted
push main: refused
deploy prod: needs_human
format disk: needs_human
```
