from openverifiers import (ConditionController, Engine, Quantity)

from openverifiers.domains.physics import (PointObject)
from openverifiers.domains.units_si import (MeterPerSecond, MeterPerSecondSquared, Second)
"""Task 1/3 — the engine runs Transformations and never knows which controller
kind produced them. The .ovpv audit trace is written after the run and read
back only as JSON (never parsed back as input).
"""

import json

from openverifiers.domains.physics import VUAT, FMA
from openverifiers.domains.coding import (Action, default_conditions)
from openverifiers.controllers import ConditionController
from openverifiers.engine import Engine
from openverifiers.facts import Quantity
from openverifiers.formats import save_audit
from openverifiers.domains.units_si import (MeterPerSecond, MeterPerSecondSquared, Second)


ENGINE = Engine()


def test_engine_runs_equationcontroller_transformation():
    t = VUAT.as_transformation("v")
    result = ENGINE.run(t, {
        "u": Quantity(value=0.0, unit=MeterPerSecond()),
        "a": Quantity(value=2.0, unit=MeterPerSecondSquared()),
        "t": Quantity(value=5.0, unit=Second()),
    }, target="v")
    assert result.status == "RESOLVED"
    assert result.answer.value == 10.0
    assert result.trace[0]["type"] == "derive"
    assert result.trace[0]["rule"] == "kinematics: v = u + a*t[v]"


def test_engine_rejects_when_precondition_fails_owner_mismatch():
    t = FMA.as_transformation("a")
    from openverifiers.domains.physics import PointObject
    result = ENGINE.run(t, {
        "F": Quantity(value=100.0, unit=FMA.vars["F"],
                      owner=PointObject(id="car-a")),
        "m": Quantity(value=20.0, unit=FMA.vars["m"],
                      owner=PointObject(id="car-b")),
    }, target="a")
    assert result.status == "UNRESOLVED"
    assert any("owner mismatch" in e["reason"] for e in result.trace
               if e["type"] == "reject")


def test_engine_runs_conditioncontroller_transformation():
    ctrl = ConditionController("coding-invariants", default_conditions())
    t = ctrl.as_transformation("auth_before_db_write")
    db_write = Action(seq=2, type="db_write", params={"file": "db.py"})
    auth_done = Action(seq=1, type="auth_check", params={"user": "svc"})

    # no preceding auth_check -> precondition rejects
    bad = ENGINE.run(t, {"action": db_write, "performed": ()}, target="auth")
    assert bad.status == "UNRESOLVED"
    assert any(e["type"] == "reject" and "auth_check must precede" in e["reason"]
               for e in bad.trace)

    # with preceding auth_check -> passes, verdict fact emitted
    good = ENGINE.run(t, {"action": db_write, "performed": (auth_done,)},
                      target="auth")
    assert good.status == "RESOLVED"
    assert good.answer.value == "pass"


def test_audit_trace_written_and_read_as_json(tmp_path):
    t = VUAT.as_transformation("v")
    result = ENGINE.run(t, {
        "u": Quantity(value=0.0, unit=MeterPerSecond()),
        "a": Quantity(value=2.0, unit=MeterPerSecondSquared()),
        "t": Quantity(value=5.0, unit=Second()),
    }, target="v")
    out = tmp_path / "audit.ovpv"
    audit = save_audit(str(out), result)
    assert audit["result"] == "pass"
    with open(out) as fh:
        reloaded = json.load(fh)
    assert reloaded["format"] == "ovpv"
    assert reloaded["trace"][0]["rule"] == "kinematics: v = u + a*t[v]"
    assert reloaded["answer"] == "10.0 m/s"  # audit stringifies the Quantity