"""Claude Code plugin — HARNESS-AUTHORED frozen state and tool mapping.

This module is the ONLY place the gate's context and target are constructed.
The hook script (`pre_tool_use.py`) never builds facts or queries: it reads
this file, translates the intercepted call into a trace step, and enforces
whatever `submit()` returns.

Security model: the mapping table is closed static data — each entry names a
REGISTERED transformation by its literal registry key and binds tool input
fields to frozen fact refs. There is no per-call dynamic resolution anywhere;
everything that is not literally in `MAPPINGS` is blocked before a step is
even built.
"""

from typing import TypedDict

from openverifiers.domains.math import make_number
from openverifiers.queries import FactQuery


class MappingRef(TypedDict):
    role: str
    ref: str


class ToolMapping(TypedDict):
    grammar: str
    transformation: str
    output: str
    refs: dict[str, MappingRef]
    params: dict[str, object]

# -- frozen per-grammar contexts: fact ref -> Fact --------------------------
FROZEN_CONTEXTS = {
    "math": {
        "a": make_number(3.0, "a"),
        "b": make_number(4.0, "b"),
        "z": make_number(12.0, "z"),
    },
}

# -- harness-authored targets: grammar -> mission Query ---------------------
# The mission for "math" is: any admitted call must leave the shared fact `z`
# equal to 12 (3 * 4). A legal-shaped call whose OUTPUT violates this is
# semantically blocked — not just shape-blocked.
TARGETS = {
    # ref-string form: resolves the produced fact by id, so a violated
    # output yields "z == 9 canonical, expected 12" instead of masking the
    # value difference behind _same_fact's instance compare.
    "math": FactQuery("z", 12.0,
                      description="math gate: z must equal 12 (3*4)"),
}

# -- tool -> registered transformation --------------------------------------
# refs:  tool_input field -> {"role": transformation input role,
#                             "ref": frozen-context fact ref}
# params: tool_input field -> DSL step param (scalar passthrough)
MAPPINGS: dict[str, ToolMapping] = {
    "Tool__Math__Multiply": {
        "grammar": "math",
        "transformation": "math.mul",     # MUST exist in the Registry
        "output": "z",                    # produced fact id must clear target
        "refs": {
            "left":  {"role": "a", "ref": "a"},
            "right": {"role": "b", "ref": "b"},
        },
        "params": {},
    },
}