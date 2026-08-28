"""OpenVerifiers — schema-forced extraction for physics word problems.

Turns a natural-language physics problem into `unverified_truth` fact nodes + a
target kind, per ARCHITECTURE.md §5 / README "schema-forced extraction".

Scope note: extraction vocab is tuned to the JEE/CBSE/HSC kinematics-mechanics
word-problem register. It is deliberately regex/deterministic — no LLM involved in
this slice. (An LLM-assisted extraction layer is a future adapter; the driver
interface stays identical.)
"""

from __future__ import annotations

import re
from typing import Optional

from ..model import Fact, TARGET
from .physics import make_fact


# ---------------------------------------------------------------------------
# number + unit
# ---------------------------------------------------------------------------
NUM = r"(-?\d+(?:\.\d+)?)"
U_VEL = r"(?:m/s|m\s*s\s*-1|ms-1|m\s?s\s?[-1]|m/s\^?2?)"
U_ACC = r"(?:m/s\^2|m/s2|m\s?/?s\^2|ms-2|m\s?/\s?s\^2)"
U_TIME = r"(?:s(?:econds?)?)"
U_DIST = r"(?:m(?:etres?|eters)?)"
U_MASS = r"(?:kg|kilograms?)"
U_FORCE = r"(?:N|newtons?)"
U_ENERGY = r"(?:J|joules?)"

# ---------------------------------------------------------------------------
# detection rules: (regex, fact_kind, unit-hint)
# ---------------------------------------------------------------------------
GIVEN_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"initial velocity (?:of )?" + NUM + r"\s*" + U_VEL, re.I), "initial_velocity"),
    (re.compile(r"initial (?:velocity|speed) (?:of )?" + NUM, re.I), "initial_velocity"),
    (re.compile(r"final velocity (?:of )?" + NUM + r"\s*" + U_VEL, re.I), "final_velocity"),
    (re.compile(r"speed (?:of )?" + NUM + r"\s*" + U_VEL, re.I), "final_velocity"),
    (re.compile(r"(?<!initial )(?<!final )velocity (?:of )?" + NUM + r"\s*" + U_VEL, re.I), "final_velocity"),
    (re.compile(r"(?:moving|travelling|traveling|runs|runs at) at " + NUM + r"\s*" + U_VEL, re.I), "final_velocity"),
     (re.compile(r"(?:acceleration|accelerat(?:es|ing|ed)(?: uniformly)? at|accelerated at) (?:of )?" + NUM + r"\s*" + U_ACC, re.I), "acceleration"),
     (re.compile(r"(?:acceleration|accelerat(?:es|ing|ed)(?: uniformly)? at|accelerated at) (?:of )?" + NUM, re.I), "acceleration"),
    (re.compile(r"accelerat\w*\s+(?:from rest\s+)?at\s+" + NUM + r"\s*" + U_ACC, re.I), "acceleration"),
    (re.compile(r"(?:after|in|for|within) " + NUM + r"\s*" + U_TIME, re.I), "time"),
    (re.compile(r"(?:distance|displacement|trav(?:els|elled|elling|els|ers|ersed|elling)|covers|moves|falls|through|over) (?:of )?" + NUM + r"\s*" + U_DIST, re.I), "displacement"),
    (re.compile(r"(?:distance|displacement|through|over) (?:of )?" + NUM, re.I), "displacement"),
    (re.compile(r"(?:mass) (?:of )?" + NUM + r"\s*" + U_MASS, re.I), "mass"),
    (re.compile(r"mass (?:of )?" + NUM, re.I), "mass"),
    (re.compile(r"(?:force) (?:of )?" + NUM + r"\s*" + U_FORCE, re.I), "force"),
    (re.compile(r"(?:kinetic energy|KE) (?:of )?" + NUM + r"\s*" + U_ENERGY, re.I), "kinetic_energy"),
    (re.compile(r"(?:work done|work) (?:of )?" + NUM + r"\s*" + U_ENERGY, re.I), "work"),
    (re.compile(r"(?:time taken|time) (?:of )?" + NUM + r"\s*" + U_TIME, re.I), "time"),
]

# implicit givens
IMPLICIT: list[tuple[re.Pattern, str, float]] = [
    (re.compile(r"(?:starts|starting|begins|dropped|released|accelerates|accelerating) (?:from rest|at rest)", re.I), "initial_velocity", 0.0),
    (re.compile(r"(?:starts|starting|begins|dropped|released) ", re.I), "initial_velocity", 0.0),
    (re.compile(r"(?:comes|brought) to rest", re.I), "final_velocity", 0.0),
    (re.compile(r"(?:freely|free fall|falling freely|freed from rest)", re.I), "acceleration", 9.8),
    (re.compile(r"under gravity|due to gravity|g\s*=\s*9\.?8", re.I), "acceleration", 9.8),
]

# ---------------------------------------------------------------------------
# target detection
# ---------------------------------------------------------------------------
TARGET_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"find .{0,20}(?:kinetic energy|KE)", re.I), "kinetic_energy"),
    (re.compile(r"(?:what is|calculate|determine|find|obtain).{0,20}(?:kinetic energy)", re.I), "kinetic_energy"),
    (re.compile(r"find .{0,20}work done", re.I), "work"),
    (re.compile(r"(?:what is|calculate|determine|find|obtain).{0,20}(?:work done|work)", re.I), "work"),
    (re.compile(r"find .{0,20}(?:final\s+)?velocity", re.I), "final_velocity"),
    (re.compile(r"(?:what is|calculate|determine|find|obtain).{0,20}(?:speed|velocity)", re.I), "final_velocity"),
    (re.compile(r"find .{0,20}(?:initial\s+)?velocity", re.I), "initial_velocity"),
    (re.compile(r"(?:what|how long|calculate|find|determine).{0,20}(?:time|seconds|duration)", re.I), "time"),
    (re.compile(r"find .{0,10}acceleration", re.I), "acceleration"),
    (re.compile(r"(?:what is|calculate the|determine the).{0,10}(?:acceleration)", re.I), "acceleration"),
    (re.compile(r"(?:how far|distance|displacement|travelled|travel)", re.I), "displacement"),
    (re.compile(r"(?:mass of the|find .{0,20}mass|what is the mass|weight of)", re.I), "mass"),
    (re.compile(r"(?:force|required force|force exerted)", re.I), "force"),
    (re.compile(r"(?:work done|work)", re.I), "work"),
]


def parse_problem(text: str, explicit: Optional[dict] = None,
                  explicit_target: Optional[str] = None) -> tuple[list[Fact], Optional[str]]:
    """Extract (givens, target_kind) from a problem sentence.

    explicit: optional {kind: value} overrides for numbers the regexes miss.
    explicit_target: optional target kind when auto-detection is ambiguous.
    """
    givens: dict[str, float] = {}

    # explicit overrides first (strongest)
    if explicit:
        for kind, val in explicit.items():
            givens[kind] = float(val)

    # regexes
    for pat, kind in GIVEN_PATTERNS:
        m = pat.search(text)
        if m and kind not in givens:
            givens[kind] = float(m.group(1))

    # implicit (rest, gravity ...)
    for pat, kind, val in IMPLICIT:
        if pat.search(text) and kind not in givens:
            givens[kind] = val

    # target
    target = explicit_target
    if target is None:
        for pat, kind in TARGET_PATTERNS:
            if pat.search(text):
                target = kind
                break

    facts = [make_fact(kind, val, status="unverified_truth", note="extracted from problem")
             for kind, val in givens.items()]
    return facts, target


def make_target_fact(kind: str) -> Fact:
    from .physics import KIND_META, DEFAULT_ID
    meta = KIND_META[kind]
    return Fact(
        id=DEFAULT_ID[kind],
        value=None,
        status=TARGET,
        attributes={"fact_kind": kind, "symbol": meta["symbol"],
                    "dimension": meta["dim"], "unit": meta["unit"]},
        source="target",
    )