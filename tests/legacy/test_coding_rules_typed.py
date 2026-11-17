"""Task 3 (controller sprint) — the coding action-trace suite is a
ConditionController instance. Rebuilt after an import-split accident; content
identical to the verified original."""

import pytest

from openverifiers.legacy import ActionFact, ConditionController, Quantity
from openverifiers.legacy.domains.coding import Action, default_conditions
from openverifiers.legacy.domains.coding import PASS, FAIL, INAPPLICABLE

CTRL = ConditionController("coding-invariants", default_conditions())


def _fact(kind, of, value, status="truth", fid=None):
    return ActionFact(id=fid or f"{kind}_{of}", kind=kind, of=of,
                      value=value, status=status)


def _act(seq, type_, params=None, pre=()):
    return Action(seq=seq, type=type_, params=params or {}, pre_facts=tuple(pre))


CODE_01 = [
    _act(1, "read_file", {"file": "db.py"},
         pre=[_fact("file_exists", "db.py", True)]),
    _act(2, "auth_check", {"user": "svc-account"},
         pre=[_fact("credential_valid", "svc-account", True)]),
    _act(3, "db_write", {"file": "db.py"}),
    _act(4, "run_tests", {"result": "pass"}),
    _act(5, "deploy", {"env": "staging"}),
]

CODE_02 = [
    _act(1, "read_file", {"file": "handler.py"},
         pre=[_fact("file_exists", "handler.py", True)]),
    _act(2, "write_file", {"file": "handler.py"}),
    _act(3, "run_tests", {"result": "pass"}),
    _act(4, "deploy", {"env": "staging"}),
]

CODE_03 = [
    _act(1, "read_file", {"file": "db.py"},
         pre=[_fact("file_exists", "db.py", True)]),
    _act(2, "db_write", {"file": "db.py"}),
]

CODE_04 = [
    _act(1, "read_file", {"file": "handler.py"},
         pre=[_fact("file_exists", "handler.py", True)]),
    _act(2, "write_file", {"file": "router.py"}),
]

CODE_05 = [
    _act(1, "run_tests", {"result": "fail"}),
    _act(2, "deploy", {"env": "production"}),
]

CODE_06 = [
    _act(1, "read_file", {"file": "deps.csv"},
         pre=[_fact("file_exists", "deps.csv", True)]),
    _act(2, "delete_record", {"record": "rec-1042"},
         pre=[_fact("has_active_dependency", "rec-1042", True)]),
]

CODE_07 = [
    _act(1, "read_file", {"file": "deps.csv"},
         pre=[_fact("file_exists", "deps.csv", True)]),
    _act(2, "delete_record", {"record": "rec-77"},
         pre=[_fact("has_active_dependency", "rec-77", None, "unknown",
                    fid="dep_rec77")]),
]


def _verdicts(actions):
    per_action, _claims = CTRL.check_trace(actions)
    return [a["verdict"] for a in per_action]


def _failed_rules(actions):
    per_action, _claims = CTRL.check_trace(actions)
    out = set()
    for a in per_action:
        for name, verdict, _reason in a["rule_checks"]:
            if verdict == FAIL:
                out.add(name)
    return out


def test_code_01_clean_pass():
    assert all(v == PASS for v in _verdicts(CODE_01))


def test_code_02_clean_pass():
    assert _verdicts(CODE_02)[-1] == PASS


def test_code_03_missing_auth_fails_named_rule():
    assert _failed_rules(CODE_03) == {"auth_before_db_write"}


def test_code_04_write_unread_file_fails_named_rule():
    assert _failed_rules(CODE_04) == {"read_before_write_same_file"}


def test_code_05_deploy_after_failed_tests_fails_named_rule():
    assert _failed_rules(CODE_05) == {"tests_pass_before_deploy"}


def test_code_06_delete_active_dependency_fails_named_rule():
    assert _failed_rules(CODE_06) == {"no_delete_with_active_dependency"}


def test_code_07_unknown_dependency_is_inapplicable_never_guessed():
    assert _verdicts(CODE_07) == [PASS, INAPPLICABLE]
    _per_action, claims = CTRL.check_trace(CODE_07)
    assert claims, "an unknown fact must surface as an unverifiable claim"
    assert "dep_rec77" in claims[0]["reason"]
    assert "inapplicable" in claims[0]["reason"]


def test_controller_wraps_existing_domain_content():
    assert [c[0] for c in CTRL.conditions] == \
           [c[0] for c in default_conditions()]