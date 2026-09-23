"""FactsController — the intermediate fact state + step engine.

One object owns the working fact set for a proof run, applies registered
transformations step by step, and answers condition/type queries against it.
This is the "context as controller" surface: the Python half of what a
KDScript `context` block will become (the language declares, this executes).

The controller holds NO domain content — it is a stock registry dispatch
problem: apply step -> engine computes -> fact lands in state, with
declared guards (incl. type-inferred ones) evaluated by the engine.
"""
from __future__ import annotations

from typing import Iterator, Optional

from openverifiers.facts import Fact
from openverifiers.v2 import (Registry, TraceStep, run_trace, TraceResult)

from .proof_parser import parse_proof


class FactsController:
    def __init__(self, registry: Registry,
                 background: dict[str, Fact] | None = None):
        self.registry = registry
        self.env: dict[str, Fact] = dict(registry.facts)
        if background:
            self.env.update(background)
        self.steps: list[TraceStep] = []
        self.results: list[TraceResult] = []

    # -- state --------------------------------------------------------------
    def fact(self, fid: str) -> Optional[Fact]:
        return self.env.get(fid)

    def has(self, fid: str) -> bool:
        return fid in self.env

    def facts(self) -> dict[str, Fact]:
        return dict(self.env)

    def __iter__(self) -> Iterator[Fact]:
        return iter(self.env.values())

    # -- computation --------------------------------------------------------
    def step(self, text: str) -> tuple[str, Fact | None]:
        """Apply ONE step (or proof fragment) through the closed whitelist.

        Returns (verdict, produced fact). Engine evaluates guards — the
        agent/controller never asserts a condition result.
        """
        _, steps = parse_proof(text)
        if not steps:
            raise ValueError("no step to apply")
        result = run_trace(self.registry, self.env, steps,
                           exclusive=sum((g.exclusive for g in
                                          self.registry.grammars.values()),
                                         ()))
        self.env.update(result.env)
        self.results.append(result)
        produced = result.produced[-1] if result.produced else None
        return result.verdict, produced

    def check(self, transformation: str, inputs: dict[str, Fact]) -> str | None:
        """Consult the declared conditions (incl. type-inferred guards)
        WITHOUT applying anything. Returns None when they all hold."""
        hit = self.registry.lookup(transformation)
        if hit is None:
            return f"{transformation!r} is not registered"
        trans, _ = hit
        return trans.precond(inputs)

    def legal(self, transformation: str, inputs: dict[str, Fact]) -> bool:
        return self.check(transformation, inputs) is None

    # -- provenance ---------------------------------------------------------
    def provenance_tiers(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for f in self.env.values():
            k = f.effective_provenance
            out[k] = out.get(k, 0) + 1
        return out