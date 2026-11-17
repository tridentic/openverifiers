"""The repair loop: propose, check, feed the kernel's failures back, retry."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from openverifiers.kernel import (
    DomainPack,
    Fact,
    Failure,
    Proof,
    Requirement,
    Verdict,
    check,
    proof_to_dict,
    verdict_to_dict,
)

from .base import Feedback, ProposalError, Proposer


@dataclass(frozen=True)
class Attempt:
    number: int
    proof: Proof | None
    verdict: Verdict | None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt": self.number,
            "proof": proof_to_dict(self.proof) if self.proof else None,
            "verdict": verdict_to_dict(self.verdict, "failure_trail") if self.verdict else None,
            "error": self.error,
        }


@dataclass
class RepairResult:
    accepted: bool
    attempts: list[Attempt] = field(default_factory=list)

    @property
    def final(self) -> Verdict | None:
        return self.attempts[-1].verdict if self.attempts else None


def repair(proposer: Proposer, facts: Sequence[Fact], requirements: Sequence[Requirement],
           pack: DomainPack, max_attempts: int = 3,
           log: Callable[[dict[str, Any]], None] | None = None) -> RepairResult:
    """Up to ``max_attempts`` propose/check rounds. Every attempt is logged
    (as a JSON-ready dict) whether it was accepted, rejected or unparseable."""
    result = RepairResult(accepted=False)
    feedback: Feedback | None = None
    for n in range(1, max_attempts + 1):
        try:
            proof = proposer.propose(facts, requirements, pack, feedback)
        except ProposalError as exc:
            attempt = Attempt(n, None, None, str(exc))
            feedback = Feedback(n, (Failure("unparseable_proposal", str(exc)),))
        else:
            verdict = check(facts, requirements, proof, pack)
            attempt = Attempt(n, proof, verdict)
            feedback = Feedback(n, verdict.failures)
        result.attempts.append(attempt)
        if log is not None:
            log(attempt.to_dict())
        if attempt.verdict is not None and attempt.verdict.valid:
            result.accepted = True
            break
    return result


def jsonl_logger(path: str) -> Callable[[dict[str, Any]], None]:
    def write(record: dict[str, Any]) -> None:
        with open(path, "a") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
    return write
