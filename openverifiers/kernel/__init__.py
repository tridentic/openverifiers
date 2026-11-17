"""The trusted verification kernel.

Small, pure and deterministic: stdlib only, no LLM, no network. Everything
domain-specific arrives through a ``DomainPack``. See ``check.py`` for the
rules it enforces.
"""

from .check import check, facts_equal, flatten, select
from .model import (
    BUILTIN_PREDICATES,
    FAILURE_CODES,
    DomainPack,
    Fact,
    FactType,
    Failure,
    Precondition,
    Proof,
    Provenance,
    Requirement,
    Selector,
    Step,
    TraceEvent,
    Transformation,
    Verdict,
)
from .serialize import (
    TRACE_FILTERS,
    FormatError,
    fact_from_dict,
    fact_to_dict,
    filter_trace,
    proof_from_dict,
    proof_to_dict,
    requirement_from_dict,
    requirement_to_dict,
    verdict_to_dict,
)

__all__ = [
    "BUILTIN_PREDICATES",
    "FAILURE_CODES",
    "TRACE_FILTERS",
    "DomainPack",
    "Fact",
    "FactType",
    "Failure",
    "FormatError",
    "Precondition",
    "Proof",
    "Provenance",
    "Requirement",
    "Selector",
    "Step",
    "TraceEvent",
    "Transformation",
    "Verdict",
    "check",
    "fact_from_dict",
    "fact_to_dict",
    "facts_equal",
    "filter_trace",
    "flatten",
    "proof_from_dict",
    "proof_to_dict",
    "requirement_from_dict",
    "requirement_to_dict",
    "select",
    "verdict_to_dict",
]
