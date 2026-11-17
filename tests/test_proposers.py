from __future__ import annotations

import json
from pathlib import Path

import pytest

from openverifiers.case import load_case
from openverifiers.cli import main
from openverifiers.demo import run_repair_demo
from openverifiers.domains import load
from openverifiers.kernel import Proof, check
from openverifiers.proposers import (
    BackwardDecomposer,
    Feedback,
    ForwardChainer,
    LLMProposer,
    ProposalError,
    ScriptedModel,
    parse_reply,
    repair,
)

MATH = Path(__file__).resolve().parents[1] / "benchmarks" / "cases" / "math"
PACK = load("math")


@pytest.mark.parametrize("name", ["math_car_distance", "math_braking_force",
                                  "math_displacement", "math_linear_equation"])
def test_forward_chainer_solves_formula_cases(name: str) -> None:
    c = load_case(MATH / f"{name}.json")
    proof = ForwardChainer().propose(c.facts, c.requirements, PACK)
    assert check(c.facts, c.requirements, proof, PACK).valid


@pytest.mark.parametrize("name", ["math_car_distance", "math_braking_force",
                                  "math_displacement"])
def test_backward_decomposer_solves_formula_cases(name: str) -> None:
    c = load_case(MATH / f"{name}.json")
    proof = BackwardDecomposer().propose(c.facts, c.requirements, PACK)
    v = check(c.facts, c.requirements, proof, PACK)
    assert v.valid and len(proof.steps) == len(c.proof.steps)


def test_search_proposers_cannot_invent_grounded_steps() -> None:
    c = load_case(MATH / "math_drop_speed.json")  # needs constant.lookup (no effect)
    with pytest.raises(ProposalError):
        BackwardDecomposer().propose(c.facts, c.requirements, PACK)
    assert not check(c.facts, c.requirements,
                     ForwardChainer().propose(c.facts, c.requirements, PACK), PACK).valid


def test_parse_reply_accepts_fenced_json_and_rejects_garbage() -> None:
    assert parse_reply('```json\n{"steps": []}\n```') == Proof(())
    for bad in ["no proof here", '{"steps": [{"id": "s"}]}', '{"stepz": []}']:
        with pytest.raises(ProposalError):
            parse_reply(bad)


def test_repair_loop_feeds_failures_back_and_logs_every_attempt() -> None:
    c = load_case(MATH / "math_car_distance.json")
    good = json.dumps({"steps": [{
        "id": "s1", "transformation": "kinematics.distance.solve_d",
        "inputs": {"v": "v", "t": "t"},
        "outputs": {"d": {"id": "d", "type": "quantity", "value": 1800, "unit": "m"}}}]})
    model = ScriptedModel(["not json", good.replace("1800", "30"), good])
    log: list[dict[str, object]] = []
    result = repair(LLMProposer(model), c.facts, c.requirements, PACK, max_attempts=5,
                    log=log.append)
    assert result.accepted and len(result.attempts) == 3 and len(log) == 3
    assert result.attempts[0].error and "not a valid proof" in result.attempts[0].error
    assert "unparseable_proposal" in model.prompts[1]
    assert "output_mismatch" in model.prompts[2] and '"step_id": "s1"' in model.prompts[2]


def test_repair_loop_gives_up_after_max_attempts() -> None:
    c = load_case(MATH / "math_car_distance.json")
    result = repair(LLMProposer(ScriptedModel(["{}", "{}"])), c.facts, c.requirements, PACK,
                    max_attempts=2)
    assert not result.accepted and len(result.attempts) == 2


def test_feedback_is_rendered_in_prompt() -> None:
    from openverifiers.kernel import Failure
    from openverifiers.proposers import build_prompt
    c = load_case(MATH / "math_car_distance.json")
    fb = Feedback(1, (Failure("cycle", "s1 and s2 form a cycle", step_id="s1"),))
    prompt = build_prompt(c.facts, c.requirements, PACK, fb)
    assert "Attempt 1 was rejected" in prompt and "kinematics.distance.solve_d" in prompt


def test_repair_demo_acceptance_criterion() -> None:
    result, lines = run_repair_demo()
    first, second = result.attempts
    assert first.verdict is not None and not first.verdict.valid
    assert {f.code for f in first.verdict.failures} >= {"output_mismatch", "dependency_failed"}
    assert second.verdict is not None and second.verdict.valid
    assert "Second prompt carried the kernel's structured failures: True" in lines


def test_cli(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    case = str(MATH / "math_car_distance.json")
    assert main(["check", case]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True
    assert main(["trace", case, "--filter", "success_path"]) == 0
    assert [e["subject"] for e in json.loads(capsys.readouterr().out)["trace"]] == ["s1", "goal"]
    doc = json.loads(Path(case).read_text())
    doc["candidate_proof"]["steps"][0]["outputs"]["d"]["value"] = -1800
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(doc))
    assert main(["check", str(bad)]) == 1
    assert json.loads(capsys.readouterr().out)["failures"][0]["code"] == "output_mismatch"
    bad.write_text("{}")
    with pytest.raises(SystemExit) as exc:
        main(["check", str(bad)])
    assert exc.value.code == 2
    assert main(["solve", case, "--proposer", "backward"]) == 0
