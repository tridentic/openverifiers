"""KDScript DomainIR — pure-data records.

Every structure here is a plain dict/list of JSON-safe scalars. Nothing in
this module imports the runtime; the compiler (`compiler.py`) is the only
place IR meets Python objects. A non-Python reimplementation reads only
these shapes.

Document conventions:
  * a unit reference is always a token string resolved through the unit
    table (kern/units.py) or the domain's own `units` declaration;
  * an expression is a string in sympy-compatible syntax (`**` for powers,
    `sqrt(...)`, bare names for variables, `pi` for the constant).
"""

DOMAIN_IR_VERSION = 1

# ---------------------------------------------------------------------------
# Shapes (documented; a RuntimeContract test pins them as JSON-safe)
# ---------------------------------------------------------------------------

# DomainIR = {
#   "ir_version": 1,
#   "kind": "domain",
#   "name": str,
#   "doc": str,
#   "units": {token: {"dimension": {7 SI fields}, "scale": float}},
#   "facts": [{"id": str, "kind": "quantity"|"action",
#              "value": float|str, "unit": token|None,
#              "of": str|None, "source": str}],
#   "relations": [{"name": str, "expr": str,
#                  "units": {var: token}, "out": var, "doc": str}],
#   "transforms": [{"name": str, "builtin": str,
#                   "param": [str], "input": [str],
#                   "guard": [guard], "doc": str}],
#   "judgements": [{"name": str, "model": str,
#                   "input": [{"role": str, "kind": str}],
#                   "schema": {field: {"type": str, "options": [str]?}},
#                   "doc": str}],
#   "exclusive": [[token, ...], ...],
# }
#
# guard = {"op": "same_owner"|"frame_eq"|"kind"|"unit"|"positive",
#          "args": [str, ...]}


def new_domain(name: str, doc: str = "") -> dict:
    return {
        "ir_version": DOMAIN_IR_VERSION,
        "kind": "domain",
        "name": name,
        "doc": doc,
        "units": {},
        "facts": [],
        "objects": [],
        "relations": [],
        "transforms": [],
        "judgements": [],
        "exclusive": [],
    }