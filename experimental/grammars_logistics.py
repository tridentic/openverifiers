"""OpenVerifiers — logistics domain grammar (discrete satisfiability).

Ground truths are defined here, hardcoded as the rule library. The agent supplies
only facts (Order, Deadline, Carrier, Warehouse, candidate route). The engine +
Z3 SAT backend satisfies or rejects the route against every hardcoded rule, and
an unsat-core names the minimal violated rule set.

Facts (typed attributes, carrying owner scoping + discrete domains):
    Order      origin, destination, hazmat(bool), budget_cap(money)
    Deadline   date (iso), priority
    Carrier    id, in_service(bool), hazmat_compat(bool), quote(money)
    Warehouse  region, serves(frozenset)
Rule library (transformations, each Z3-checkable):
    delivers_by   (carrier, deadline)
    within_budget (carrier, order)
    hazmat_compat (order, carrier)
    warehouse_serves (warehouse, order)
    route_sat     (all rules + candidate route) -> route_satisfaction verdict
The route_sat transformation invokes the z3.sat solver: SAT model or UNSAT core.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

from ..model import Fact, Transformation, Condition, UNVERIFIED_TRUTH, TARGET
from ..solvers import get_solver

# ---------------------------------------------------------------------------
# Fact-kind registry (logistics)
# ---------------------------------------------------------------------------
KINDS = ["Order", "Deadline", "Carrier", "Warehouse", "route"]
DEFAULT_ID = {k: k for k in KINDS}


def _fact(kind: str, **attrs) -> Fact:
    return Fact(
        id=attrs.pop("id", DEFAULT_ID[kind]),
        value=attrs.pop("value", None),
        status=attrs.pop("status", UNVERIFIED_TRUTH),
        attributes=attrs,
        source=attrs.pop("source", f"given {kind}"),
    )


# ---------------------------------------------------------------------------
# Rule library — the hardcoded ground truths. The agent cannot touch these.
# ---------------------------------------------------------------------------
def make_logistics_rules() -> list[Transformation]:
    rules = []

    def _mk(name, out_kind, in_kinds, conds, relation):
        rules.append(Transformation(
            name, output_kind=out_kind, input_kinds=in_kinds,
            conditions=conds, relation=relation, solver_hook="z3.sat",
        ))

    def _ast_cond(name, kind, roles, expr):
        return Condition(name=name, kind=kind, roles=tuple(roles), expr=expr)

    # --- delivers_by: carrier must meet deadline; carrier must be in_service ---
    _mk(
        "logistics.delivers_by", "delivery_satisfaction", ["Carrier", "Deadline"],
        [
            _ast_cond("carrier_in_service", "bool", ["Carrier"], "carrier.in_service = True"),
            _ast_cond("deadline_satisfied", "satisfies", ["Carrier", "Deadline"], "carrier.deadline_ok = True"),
        ],
        lambda f: (_fact("delivery_satisfaction", value=True,
                         attributes={"rule": "delivers_by"}), "delivers_by ok"),
    )

    # --- within_budget: carrier.quote <= order.budget_cap ---
    _mk(
        "logistics.within_budget", "budget_satisfaction", ["Carrier", "Order"],
        [
            _ast_cond("quote_within_cap", "arithmetic", ["Carrier", "Order"], "carrier.quote <= order.budget_cap"),
        ],
        lambda f: (_fact("budget_satisfaction", value=True,
                         attributes={"rule": "within_budget"}), "within budget ok"),
    )

    # --- hazmat_compat: hazmat orders require a hazmat-capable carrier ---
    _mk(
        "logistics.hazmat_compat", "hazmat_satisfaction", ["Order", "Carrier"],
        [
            _ast_cond("hazmat_requires_compat", "implies", ["Order", "Carrier"],
                      "IF order.hazmat THEN carrier.hazmat_compat = True"),
        ],
        lambda f: (_fact("hazmat_satisfaction", value=True,
                         attributes={"rule": "hazmat_compat"}), "hazmat ok"),
    )

    # --- warehouse_serves: warehouse.region must match order.destination ---
    _mk(
        "logistics.warehouse_serves", "service_satisfaction", ["Warehouse", "Order"],
        [
            _ast_cond("warehouse_in_region", "member_of", ["Warehouse", "Order"],
                      "order.destination IN warehouse.serves"),
        ],
        lambda f: (_fact("service_satisfaction", value=True,
                         attributes={"rule": "warehouse_serves"}), "warehouse ok"),
    )

    return rules


# ---------------------------------------------------------------------------
# Driver: check a candidate route against ALL hardcoded rules via Z3 SAT.
# Returns a VerificationResult-shaped dict: SAT model or UNSAT core.
# ---------------------------------------------------------------------------
def verify_route(order_facts, carrier_facts, warehouse_facts, deadline_facts,
                 candidate_route) -> dict:
    """Run the discrete satisfiability check.

    order_facts:    list of Fact (kind Order)
    carrier_facts:  list of Fact (kind Carrier)
    warehouse_facts:list of Fact (kind Warehouse)
    deadline_facts: list of Fact (kind Deadline)
    candidate_route: {carrier: <id>, warehouse: <id>}

    Ground truth: returns
      {"status":"SAT", "model": {...}, "which_rules": [...]}
      {"status":"UNSAT", "unsat_core": ["rule_a","rule_c"], "which_rules": [...]}
    """
    solver = get_solver("z3.sat")

    # build domain over every carrier/warehouse as enum
    domain = {}
    carrier_ids = [c.id for c in carrier_facts]
    wh_ids = [w.id for w in warehouse_facts]
    domain["carrier"] = {"type": "enum", "domain": carrier_ids}
    domain["warehouse"] = {"type": "enum", "domain": wh_ids}

    # facts as lookup for rule conditions
    carriers = {c.id: c for c in carrier_facts}
    whs = {w.id: w for w in warehouse_facts}
    order = order_facts[0] if order_facts else None
    deadline = deadline_facts[0] if deadline_facts else None

    import z3

    constraints = []
    assert_names = []

    # Each hardcoded rule contributes a Z3 constraint over carrier/warehouse enums.
    # Helper to map enum carrier -> a bool per property.
    # Encode per-carrier bools as separate z3 bools indexed by domain.

    # carrier.in_service, carrier.hazmat_compat, carrier.deadline_ok, carrier.quote_ok
    prop = {}
    for cid in carrier_ids:
        c = carriers[cid]
        prop[(cid, "in_service")] = bool(c.attributes.get("in_service", False))
        prop[(cid, "hazmat_compat")] = bool(c.attributes.get("hazmat_compat", False))
        if deadline:
            prop[(cid, "deadline_ok")] = bool(c.attributes.get("deadline_ok", False))
        if order:
            cap = Decimal(str(order.attributes.get("budget_cap", 0)))
            quote = Decimal(str(c.attributes.get("quote", 0)))
            prop[(cid, "quote_ok")] = quote <= cap

    # warehouses serving region
    wh_serves_dest = {}
    dest = order.attributes.get("destination") if order else None
    for wid in wh_ids:
        wh_serves_dest[wid] = (dest is not None and dest in whs[wid].attributes.get("serves", ()))

    # Constraint 1: candidate carrier must be in_service
    def rule_in_service(vars, acc):
        c = acc.at("carrier")
        expr = None
        for i, name in enumerate(carrier_ids):
            bit = z3.Implies(c == i, True if prop[(name, "in_service")] else False)
            expr = bit if expr is None else z3.And(expr, bit)
        return expr

    # Constraint 2: deadline
    def rule_deadline(vars, acc):
        if not deadline:
            return None
        c = acc.at("carrier")
        expr = None
        for i, name in enumerate(carrier_ids):
            bit = z3.Implies(c == i, True if prop[(name, "deadline_ok")] else False)
            expr = bit if expr is None else z3.And(expr, bit)
        return expr

    # Constraint 3: hazmat — if order.hazmat, chosen carrier must be hazmat_compat
    def rule_hazmat(vars, acc):
        c = acc.at("carrier")
        expr = None
        hazmat_req = order is not None and bool(order.attributes.get("hazmat", False))
        for i, name in enumerate(carrier_ids):
            target = True if (prop[(name, "hazmat_compat")] or not hazmat_req) else False
            # even for non-hazmat, correctness: an incompatible carrier is acceptable;
            # for hazmat order it must be compatible
            if hazmat_req:
                bit = z3.Implies(c == i, True if prop[(name, "hazmat_compat")] else False)
            else:
                bit = z3.Implies(c == i, True)  # no restriction
            expr = bit if expr is None else z3.And(expr, bit)
        return expr

    # Constraint 4: budget
    def rule_budget(vars, acc):
        if not order:
            return None
        c = acc.at("carrier")
        expr = None
        for i, name in enumerate(carrier_ids):
            ok = prop[(name, "quote_ok")]
            bit = z3.Implies(c == i, True if ok else False)
            expr = bit if expr is None else z3.And(expr, bit)
        return expr

    # Constraint 5: warehouse serves destination
    def rule_warehouse(vars, acc):
        w = acc.at("warehouse")
        expr = None
        for i, name in enumerate(wh_ids):
            ok = wh_serves_dest[name]
            bit = z3.Implies(w == i, True if ok else False)
            expr = bit if expr is None else z3.And(expr, bit)
        return expr

    constraints = [
        ("carrier_in_service", rule_in_service),
        ("deadline_satisfied", rule_deadline),
        ("hazmat_compat", rule_hazmat),
        ("within_budget", rule_budget),
        ("warehouse_serves", rule_warehouse),
    ]

    result = solver(domain, constraints, candidate=candidate_route,
                    target=("carrier" if candidate_route else None))

    if result["status"] == "SAT":
        model = result["model"]
        return {"status": "SAT", "model": model, "which_rules": [n for n, _ in constraints]}

    if result["status"] == "UNSAT":
        return {"status": "UNSAT", "unsat_core": result["unsat_core"], "sat": False}
    return {"status": "UNKNOWN", "sat": None, "reason": "solver returned UNKNOWN"}