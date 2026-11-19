"""Mutation benchmark: catch rate and false-rejection rate for three setups.

Setups
  no_verification   accept every proposed proof (what you get by default)
  mock_llm_judge    a deterministic stand-in for an LLM judge: it reads only
                    the claimed final facts and checks them against the
                    requirements, the way a reviewer skimming the answer
                    would. It is NOT a real model; its numbers are a
                    placeholder until a real judge is wired into the adapter.
  kernel            openverifiers.m1.kernel.check

Metrics
  catch rate        mutants rejected / mutants
  right reason      mutants rejected with a failure code that matches the
                    mutation label (kernel only; see EXPECTED_CODES)
  false rejection   valid base cases rejected / valid base cases
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openverifiers.m1.case import Case, load_case
from openverifiers.m1.domains import load
from openverifiers.m1.kernel import DomainPack, Fact, Verdict, check

from .mutations import MUTATIONS, Mutant, Perturb, mutate

ROOT = Path(__file__).resolve().parent
CASES = ROOT / "cases"
RESULTS = ROOT / "results"


# ---- per-domain value perturbations (benchmark tooling, not trusted) ----------------

def _perturb_number(f: Fact) -> Any:
    if isinstance(f.value, int | float) and not isinstance(f.value, bool):
        return f.value * 1.5 + 1
    return None


def _perturb_code(f: Fact) -> Any:
    if f.type == "source" and isinstance(f.value, str) and "return " in f.value:
        return f.value.replace("return ", "return 1 + ", 1)
    if f.type == "check_report" and isinstance(f.value, dict):
        return {**f.value, "passed": not f.value.get("passed", True)}
    return None


PERTURB: dict[str, Perturb] = {"math": _perturb_number, "code_requirements": _perturb_code}


# ---- setups ------------------------------------------------------------------------------

def no_verification(c: Case, pack: DomainPack) -> tuple[bool, list[str]]:
    return True, []


def mock_llm_judge(c: Case, pack: DomainPack) -> tuple[bool, list[str]]:
    """Accept iff every requirement's fact is claimed somewhere and, for
    value requirements, the claimed number matches when units are spelled
    the same. Intermediate steps are never inspected."""
    claimed: dict[str, Fact] = {f.id: f for f in c.facts if f.status not in ("target",)}
    for s in c.proof.steps:
        claimed.update({o.id: o for o in s.outputs.values()})
    for r in c.requirements:
        f: Fact | None
        if r.selector.fact_id is not None:
            f = claimed.get(r.selector.fact_id)
        else:
            hits = [g for g in claimed.values()
                    if all(g.attributes.get(k) == v for k, v in r.selector.where.items())]
            f = hits[0] if hits else None
        if f is None:
            return False, [f"judge: nothing claims {r.id}"]
        want = r.args.get("value")
        if isinstance(want, int | float) and isinstance(f.value, int | float) \
                and r.args.get("unit", f.unit) == f.unit \
                and not math.isclose(want, f.value, rel_tol=1e-3):
            return False, [f"judge: {f.id} = {f.value}, wanted {want}"]
    return True, []


def kernel(c: Case, pack: DomainPack) -> tuple[bool, list[str]]:
    v: Verdict = check(c.facts, c.requirements, c.proof, pack)
    return v.valid, [f.code for f in v.failures]


SETUPS: dict[str, Callable[[Case, DomainPack], tuple[bool, list[str]]]] = {
    "no_verification": no_verification,
    "mock_llm_judge": mock_llm_judge,
    "kernel": kernel,
}


# ---- running ---------------------------------------------------------------------------------

@dataclass
class Tally:
    total: int = 0
    rejected: int = 0
    right_reason: int = 0

    def rate(self, n: int) -> str:
        return "n/a" if self.total == 0 else f"{n / self.total:6.1%}"


@dataclass
class Report:
    base: dict[str, dict[str, Tally]] = field(default_factory=dict)  # domain -> setup
    mutants: dict[tuple[str, str], dict[str, Tally]] = field(default_factory=dict)  # (domain, kind)
    misses: list[dict[str, Any]] = field(default_factory=list)
    false_rejections: list[dict[str, Any]] = field(default_factory=list)
    wrong_reason: list[dict[str, Any]] = field(default_factory=list)


def load_cases(domains: Iterable[str]) -> dict[str, list[Case]]:
    return {d: [load_case(p) for p in sorted((CASES / d).glob("*.json"))] for d in domains}


def run(domains: Iterable[str] = ("math", "code_requirements")) -> Report:
    rep = Report()
    for domain, cases in load_cases(domains).items():
        pack = load(domain)
        rep.base[domain] = {s: Tally() for s in SETUPS}
        for c in cases:
            for name, setup in SETUPS.items():
                ok, codes = setup(c, pack)
                t = rep.base[domain][name]
                t.total += 1
                t.rejected += not ok
                if not ok and name == "kernel":
                    rep.false_rejections.append({"case": c.id, "codes": codes})
            mutants: list[Mutant] = mutate(c, PERTURB.get(domain), pack)
            for m in mutants:
                tallies = rep.mutants.setdefault((domain, m.kind), {s: Tally() for s in SETUPS})
                for name, setup in SETUPS.items():
                    ok, codes = setup(m.case, pack)
                    t = tallies[name]
                    t.total += 1
                    t.rejected += not ok
                    right = bool(set(codes) & m.expected_codes)
                    t.right_reason += (not ok) and right
                    if name == "kernel" and ok:
                        rep.misses.append({"mutant": m.case.id, "note": m.note})
                    elif name == "kernel" and not right:
                        rep.wrong_reason.append({"mutant": m.case.id, "note": m.note,
                                                 "codes": codes})
    return rep


def render(rep: Report) -> str:
    setups = list(SETUPS)
    lines = ["## Catch rate (invalid proofs rejected)", ""]
    head = "| domain | mutation | n | " + " | ".join(setups) + " | kernel right reason |"
    lines += [head, "|" + "---|" * (len(setups) + 4)]
    for domain in rep.base:
        for kind in MUTATIONS:
            tallies = rep.mutants.get((domain, kind))
            if tallies is None:
                lines.append(f"| {domain} | {kind} | 0 | " + " | ".join("n/a" for _ in setups)
                             + " | n/a |")
                continue
            k = tallies["kernel"]
            lines.append(f"| {domain} | {kind} | {k.total} | "
                         + " | ".join(tallies[s].rate(tallies[s].rejected) for s in setups)
                         + f" | {k.rate(k.right_reason)} |")
        agg = {s: Tally() for s in setups}
        for (d, _), tallies in rep.mutants.items():
            if d == domain:
                for s in setups:
                    agg[s].total += tallies[s].total
                    agg[s].rejected += tallies[s].rejected
                    agg[s].right_reason += tallies[s].right_reason
        lines.append(f"| **{domain}** | **all** | {agg['kernel'].total} | "
                     + " | ".join(agg[s].rate(agg[s].rejected) for s in setups)
                     + f" | {agg['kernel'].rate(agg['kernel'].right_reason)} |")
    lines += ["", "## False-rejection rate (valid proofs rejected)", "",
              "| domain | n | " + " | ".join(setups) + " |", "|" + "---|" * (len(setups) + 2)]
    for domain, tallies in rep.base.items():
        n = tallies["kernel"].total
        lines.append(f"| {domain} | {n} | "
                     + " | ".join(tallies[s].rate(tallies[s].rejected) for s in setups) + " |")
    lines += ["", f"Kernel misses (mutants accepted): {len(rep.misses)}"]
    lines += [f"- {m['mutant']}: {m['note']}" for m in rep.misses]
    lines += [f"Kernel false rejections: {len(rep.false_rejections)}"]
    lines += [f"- {m['case']}: {m['codes']}" for m in rep.false_rejections]
    lines += [f"Kernel rejections with an unexpected reason: {len(rep.wrong_reason)}"]
    lines += [f"- {m['mutant']}: {m['note']} -> {m['codes']}" for m in rep.wrong_reason]
    return "\n".join(lines)


def to_json(rep: Report) -> dict[str, Any]:
    def tal(t: Tally) -> dict[str, int]:
        return {"total": t.total, "rejected": t.rejected, "right_reason": t.right_reason}
    return {
        "base": {d: {s: tal(t) for s, t in ts.items()} for d, ts in rep.base.items()},
        "mutants": [{"domain": d, "mutation": k, **{s: tal(t) for s, t in ts.items()}}
                    for (d, k), ts in rep.mutants.items()],
        "misses": rep.misses, "false_rejections": rep.false_rejections,
        "wrong_reason": rep.wrong_reason,
    }


def main(domains: Iterable[str] = ("math", "code_requirements"), write: bool = True) -> str:
    rep = run(domains)
    text = render(rep)
    if write:
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / "latest.json").write_text(json.dumps(to_json(rep), indent=2) + "\n")
        (RESULTS / "latest.md").write_text(text + "\n")
    return text


if __name__ == "__main__":
    print(main())
