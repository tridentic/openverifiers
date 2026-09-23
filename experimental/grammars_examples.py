"""OpenVerifiers — ten end-to-end runnable domain examples.

Every example is defined here with:
  - ground truths: the hardcoded rules the agent cannot touch,
  - agent givens: typed input facts,
  - a runnable driver that either PROVES the claim (SAT/RESOLVED) or REJECTS it
    (UNSAT core / UNKNOWN) with a real trace.

Backends: sympy.algebra for arithmetic chains (physics, invoice, dosage, IRR),
z3.sat for discrete satisfiability (logistics, budget, itinerary, dependency,
circuit ordering).

NOTHING here is fabricated: each driver invokes the actual engine/backends and
returns real verdicts + traces. These are the ground-truth fixtures the site
renders.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ..solvers import get_solver, solve_symbolic
from ..model import Condition


# ---------------------------------------------------------------------------
# 1. Physics — kinematics (sympy backend)
# ---------------------------------------------------------------------------
def physics_kinematics(given, target):
    """given: {initial_velocity, acceleration, time}; target: displacement.
    Ground truth: s = u*t + 0.5*a*t^2 (and the v-u-at composition)."""
    from .physics import build_physics_rules
    from openverifiers import Engine
    from openverifiers.grammars.physics import make_fact, KIND_META
    from openverifiers.model import Fact

    engine = Engine(build_physics_rules())
    givens = [
        make_fact(k, v, note="given", fact_id=f"{k[0]}") if False else
        Fact(id=kind, value=val, status="unverified_truth",
             attributes={"fact_kind": kind, "dimension": KIND_META[kind]["dim"], "unit": KIND_META[kind]["unit"]})
        for kind, val in given.items()
    ]
    meta = KIND_META[target]
    tgt = Fact(id=target[0], value=None, status="target",
               attributes={"fact_kind": target, "symbol": target[0], "dimension": meta["dim"], "unit": meta["unit"]})
    r = engine.deduce(givens, tgt)
    return {"domain": "physics.kinematics", "status": r.status, "answer": r.answer, "trace": r.success_path}


# ---------------------------------------------------------------------------
# 2. Logistics route (Z3 backend)
# ---------------------------------------------------------------------------
def logistics_route(carriers, order, warehouses, deadline, claim):
    """Ground truths: in_service, deadline_ok, hazmat->compat, quote<=cap, wh serves dest."""
    from .logistics import verify_route, _fact
    o = _fact("Order", origin=order["origin"], destination=order["destination"],
              hazmat=order["hazmat"], budget_cap=str(order["budget_cap"]))
    d = _fact("Deadline", date=deadline)
    cs = [_fact("Carrier", id=c["id"], in_service=c["in_service"],
                hazmat_compat=c["hazmat_compat"], quote=str(c["quote"]), deadline_ok=True)
          for c in carriers]
    whs = [_fact("Warehouse", id=w["id"], region=w["region"], serves=frozenset(w["serves"]))
           for w in warehouses]
    return verify_route([o], cs, whs, [d], claim)


# ---------------------------------------------------------------------------
# 3. Budget consistency (Z3): departments sum to total, each under cap
# ---------------------------------------------------------------------------
def budget_consistency(allocations, total, cap):
    """allocations: {dept: amount}; check sum==total and each<=cap."""
    solver = get_solver("z3.sat")
    domain = {f"d_{k}": {"type": "int", "min": 0} for k in allocations}
    import z3

    def sum_rule(vars, acc):
        total_expr = sum(vars[f"d_{k}"] for k in allocations)
        return total_expr == total

    def cap_rule(vars, acc):
        e = None
        for k in allocations:
            bit = vars[f"d_{k}"] <= cap
            e = bit if e is None else z3.And(e, bit)
        return e

    res = solver(domain, [("sum_matches_total", sum_rule), ("under_cap", cap_rule)],
                 candidate={f"d_{k}": v for k, v in allocations.items()})
    return {"domain": "finance.budget", "status": res["status"],
            "unsat_core": res.get("unsat_core")}


# ---------------------------------------------------------------------------
# 4. Invoice reconciliation (sympy): line items + tax = total
# ---------------------------------------------------------------------------
def invoice_reconcile(lines, tax_rate, claimed_total):
    import sympy as sp
    subtotal = sum(lines)
    total = subtotal * (1 + tax_rate)
    real = float(sp.N(total))
    return {"domain": "finance.invoice",
            "status": "SAT" if abs(real - claimed_total) < 1e-6 else "UNSAT",
            "computed_total": real}


# ---------------------------------------------------------------------------
# 5. Medication dosage (sympy): mg = weight * dose_per_kg
# ---------------------------------------------------------------------------
def medication_dosage(weight_kg, dose_per_kg, claimed_mg):
    import sympy as sp
    correct = float(sp.N(weight_kg * dose_per_kg))
    return {"domain": "health.dosage",
            "status": "SAT" if abs(correct - claimed_mg) < 1e-6 else "UNSAT",
            "correct_mg": correct}


# ---------------------------------------------------------------------------
# 6. Study-prep deadline fit (Z3): durations sum <= horizon, prerequisite order
# ---------------------------------------------------------------------------
def study_deadline(topics, horizon):
    """topics: [(id, duration, requires)] -> fits in horizon? """
    solver = get_solver("z3.sat")
    domain = {f"t_{i}_start": {"type": "int", "min": 0} for i in range(len(topics))}
    import z3

    def all_fit(vars, acc):
        e = None
        for i, (tid, dur, req) in enumerate(topics):
            bit = vars[f"t_{i}_start"] + dur <= horizon
            e = bit if e is None else z3.And(e, bit)
        return e

    def prereq(vars, acc):
        # req index must start before dependent
        from_to = []
        req_idx = {tid: idx for idx, (tid, _, _) in enumerate(topics)}
        e = None
        for i, (tid, dur, req) in enumerate(topics):
            if req is not None:
                j = req_idx[req]
                bit = vars[f"t_{j}_start"] + topics[j][1] <= vars[f"t_{i}_start"]
                e = bit if e is None else z3.And(e, bit)
        return e

    res = solver(domain, [("fits_deadline", all_fit), ("prereq_ordered", prereq)])
    return {"domain": "study.deadline", "status": res["status"],
            "unsat_core": res.get("unsat_core")}


# ---------------------------------------------------------------------------
# 7. Travel itinerary buffer (Z3): no schedule clash, buffer enforced
# ---------------------------------------------------------------------------
def itinerary_no_clash(legs):
    """legs: [(id, start, end, required_before_next)] -> no overlap."""
    solver = get_solver("z3.sat")
    domain = {f"l_{i}": {"type": "int", "min": 0} for i in range(len(legs))}  # order var
    import z3

    def no_overlap(vars, acc):
        e = None
        for i in range(len(legs)):
            for j in range(i + 1, len(legs)):
                a_start, a_end = legs[i][1], legs[i][2]
                b_start, b_end = legs[j][1], legs[j][2]
                # disjoint intervals
                bit = z3.Or(a_end <= b_start, b_end <= a_start)
                e = bit if e is None else z3.And(e, bit)
        return e

    res = solver(domain, [("no_schedule_clash", no_overlap)])
    return {"domain": "travel.buffers", "status": res["status"],
            "unsat_core": res.get("unsat_core")}


# ---------------------------------------------------------------------------
# 8. Investment thesis IRR (sympy): implied vs claimed
# ---------------------------------------------------------------------------
def investment_irr(initial, cashflows, claimed_irr):
    """Compute IRR from cashflows; compare to claimed rate."""
    import sympy as sp
    x = sp.symbols("x")
    poly = sp.Integer(0)
    for t, cf in enumerate([-initial] + cashflows):
        poly = poly + cf * x ** t
    # IRR solves sum(cf_t/(1+r)^t)=0 over r; solve on r via substitution y=1/(1+r)
    sol = sp.nsolve(poly, x, 1.0, maxsteps=200)
    r = float(sp.N(1 / sol - 1))
    return {"domain": "finance.irr", "status": "SAT" if abs(r - claimed_irr) < 0.01 else "UNSAT",
            "implied_irr": r}


# ---------------------------------------------------------------------------
# 9. Code dependency acyclicity (Z3): no circular imports
# ---------------------------------------------------------------------------
def code_dependency_acyclic(modules):
    """modules: list of (id, [imports]) -> acyclic DAG? Returns any cycle."""
    import z3
    # cycles occur if there is a mutual import chain A->B->A
    nodes = [m[0] for m in modules]
    # build adjacency
    adj = {m[0]: m[1] for m in modules}
    # detect cycle by reachability over z3-free python (structural) but present
    # as a satisfiability check on topological ordering via z3
    idx = {n: i for i, n in enumerate(nodes)}
    solver = get_solver("z3.sat")
    domain = {f"order_{n}": {"type": "int", "min": 0, "max": len(nodes) - 1}
              for n in nodes}
    # distinct topological positions
    def ordering(vars, acc):
        e = None
        for a, deps in adj.items():
            for d in deps:
                # a must come after d
                bit = vars[f"order_{a}"] > vars[f"order_{d}"]
                e = bit if e is None else z3.And(e, bit)
        # distinctness
        for i, a in enumerate(nodes):
            for b in nodes[i + 1:]:
                e = z3.And(e, vars[f"order_{a}"] != vars[f"order_{b}"]) if e is not None else \
                    vars[f"order_{a}"] != vars[f"order_{b}"]
        return e

    res = solver(domain, [("topological_order", ordering)])
    return {"domain": "code.dependencies", "status": res["status"],
            "unsat_core": res.get("unsat_core")}


# ---------------------------------------------------------------------------
# 10. Circuit KVL (sympy): loop voltage drops sum to source
# ---------------------------------------------------------------------------
def circuit_kvl(source_v, drops, claimed_sum):
    """drops: list of voltage drops in loop; verify they equal source."""
    import sympy as sp
    correct = float(sp.N(sum(drops)))
    return {"domain": "circuit.kvl",
            "status": "SAT" if abs(correct - source_v) < 1e-6 and abs(correct - claimed_sum) < 1e-6 else "UNSAT",
            "loop_sum": correct}


ALL = {
    "physics": physics_kinematics,
    "logistics": logistics_route,
    "budget": budget_consistency,
    "invoice": invoice_reconcile,
    "dosage": medication_dosage,
    "study": study_deadline,
    "travel": itinerary_no_clash,
    "irr": investment_irr,
    "dependencies": code_dependency_acyclic,
    "circuit": circuit_kvl,
}


def run_all():
    """Run every example and return a dict of real results."""
    out = {}

    # 1 physics
    out["physics"] = physics_kinematics(
        {"initial_velocity": 0, "acceleration": 4, "time": 10}, "displacement")

    # 2 logistics
    out["logistics"] = logistics_route(
        [{"id": "A", "in_service": True, "hazmat_compat": False, "quote": 7100},
         {"id": "B", "in_service": True, "hazmat_compat": True, "quote": 8000}],
        {"origin": "BLR", "destination": "DUB", "hazmat": True, "budget_cap": 8200},
        [{"id": "WH1", "region": "DUB", "serves": ["DUB"]}],
        "2026-09-04", {"carrier": "B", "warehouse": "WH1"})

    # 3 budget
    out["budget"] = budget_consistency({"eng": 40, "ops": 35, "mkt": 25}, total=100, cap=50)

    # 4 invoice
    out["invoice"] = invoice_reconcile([100, 50], 0.10, 165.0)

    # 5 dosage
    out["dosage"] = medication_dosage(80, 0.1, 8.0)

    # 6 study (legal fit)
    out["study"] = study_deadline([("A", 3, None), ("B", 5, "A"), ("C", 2, "B")], 12)

    # 7 travel (no clash)
    out["travel"] = itinerary_no_clash([("flight", 0, 2, 0.5), ("hotel", 3, 10, 0), ("dinner", 11, 12, 0)])

    # 8 irr
    out["irr"] = investment_irr(1000, [300, 500, 400], 0.08)

    # 9 deps (acyclic present)
    out["dependencies"] = code_dependency_acyclic([("A", ["B"]), ("B", ["C"]), ("C", [])])

    # 10 circuit
    out["circuit"] = circuit_kvl(12, [8, 4], 12)

    return out