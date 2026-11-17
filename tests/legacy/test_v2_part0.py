"""Part 0 — correctness fixes and consolidation regressions."""

import pytest

from openverifiers.legacy import (Quantity, ActionFact, Premise, FactQuery,
                           ThresholdQuery, Specifier, DerivationRecord,
                           BooleanValue, NumericValue, EnumValue, tag_value,
                           RoleMismatchError)
from openverifiers.legacy.domains.units_si import Meter, MeterPerSecondSquared, Second


def test_boolean_never_coerces_to_numeric():
    """isinstance(True, int) is True — the old ad hoc typing let booleans
    pass as numbers. Tagged dispatch must make that impossible."""
    assert tag_value(True) == "boolean"
    assert tag_value(1.0) == "number"
    assert tag_value(None) == "none"
    flag = ActionFact(id="approved", kind="approval", value=True)
    result = Specifier(Premise.of(facts={"flag": flag}),
                       FactQuery(flag, 1.0)).verify()
    assert result.verdict == "inapplicable"
    assert "boolean" in result.reason
    thr = Specifier(Premise.of(facts={"flag": flag}),
                    ThresholdQuery(flag, max=5.0)).verify()
    assert thr.verdict == "inapplicable"


def test_explicit_value_wrappers_carry_tags():
    assert tag_value(BooleanValue(value=True)) == "boolean"
    assert tag_value(NumericValue(value=2.0)) == "number"
    assert tag_value(EnumValue(value="green", enum="light")) == "enum"


def test_condition_engine_imports_from_core():
    from openverifiers.legacy.conditions import (PASS, FAIL, INAPPLICABLE,
                                          aggregate, apply_conditions)
    assert aggregate(["pass", "fail"]) == "fail"
    assert aggregate(["pass", "inapplicable"]) == "inapplicable"
    assert aggregate(["pass"]) == "pass"
    assert apply_conditions([("alive", lambda env, c: ("pass", ""))],
                            (), object()) == [("alive", "pass", "")]
    from openverifiers.legacy.domains.coding import PASS as DOMAIN_PASS
    assert DOMAIN_PASS is PASS


def test_single_tolerance_constant():
    from openverifiers.legacy.constants import REL_TOL
    from openverifiers.legacy.queries import REL_TOL as Q_TOL
    from openverifiers.legacy.domains.conservation import REL_TOL as C_TOL
    assert Q_TOL is REL_TOL and C_TOL is REL_TOL and REL_TOL == 1e-6


def test_single_given_semantics():
    from openverifiers.legacy.queries import is_given
    g = Quantity(value=1.0, unit=Meter(), id="g")
    d = Quantity(value=2.0, unit=Meter(), id="d", status="derived",
                 derivation=DerivationRecord(controller_name="X",
                                             rule_name="r"))
    frozen = {id(g)}
    assert is_given(g) is True
    assert is_given(g, frozen_given_ids=frozen) is True
    assert is_given(d, frozen_given_ids=frozen) is False


def test_shared_guard_still_rejects_wrong_role():
    from openverifiers.legacy import Vector3
    from openverifiers.legacy.domains.physics import (VUAT, Acceleration,
                                               ReferenceFrame)
    ground = ReferenceFrame(name="ground")
    wrong = Acceleration(value=Vector3.x_only(2.0, MeterPerSecondSquared()),
                         unit=MeterPerSecondSquared(), frame=ground)
    with pytest.raises(RoleMismatchError, match="role mismatch"):
        VUAT.solve_for("v", u=wrong,
                       a=wrong.model_copy(),
                       t=Quantity(value=2.0, unit=Second()), axis=0)