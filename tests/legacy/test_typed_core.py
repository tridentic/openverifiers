"""Task 0 — typed core sanity: dimensions compose, units derive, macros ==
canonical. Rebuilt import block after the package split."""

import pytest

from openverifiers.legacy import ActionFact, Dimension, PhysicalObject, Quantity
from openverifiers.legacy.domains.physics import PointObject
from openverifiers.legacy.domains.units_si import (Joule, Kilogram,
                                            KilogramMeterPerSecond, Meter,
                                            MeterPerSecond,
                                            MeterPerSecondSquared, Newton,
                                            Second)


def test_dimension_arithmetic():
    assert (Dimension(mass=1) * Dimension(length=1) /
            (Dimension(time=1) ** 2)) == Dimension(mass=1, length=1, time=-2)
    assert (Dimension(length=1) / Dimension(length=1)).is_dimensionless
    assert (Dimension(length=1) ** 0).is_dimensionless


def test_compound_units_derive_from_bases():
    assert Joule().dimension == (Kilogram().dimension
                                 * (Meter().dimension ** 2)
                                 / (Second().dimension ** 2))
    assert Newton().dimension == (Kilogram().dimension * Meter().dimension
                                  / (Second().dimension ** 2))
    assert MeterPerSecondSquared().dimension == (Meter().dimension
                                                 / (Second().dimension ** 2))
    assert KilogramMeterPerSecond().dimension == (Kilogram().dimension
                                                  * Meter().dimension
                                                  / Second().dimension)


def test_quantity_dimension_derived_from_unit():
    q = Quantity(value=10.0, unit=MeterPerSecond())
    assert q.dimension == MeterPerSecond().dimension
    assert "dimension" not in Quantity.model_fields
    with pytest.raises(Exception):
        Quantity(value=1.0, unit=Meter(),
                 dimension=MeterPerSecond().dimension)


def test_canonical_construction_and_macro_equivalence():
    canonical = Quantity(value=10.0, unit=MeterPerSecond(),
                         owner=PointObject(id="car_1"))
    macro = Quantity.from_str("10 m/s", owner=PointObject(id="car_1"))
    assert macro == canonical
    assert macro.owner == PointObject(id="car_1")


def test_physical_object_base_polymorphism():
    obj = PointObject(id="car_1")
    assert isinstance(obj, PhysicalObject)
    q = Quantity(value=1.0, unit=Kilogram(), owner=obj)
    assert q.owner.id == "car_1"


def test_action_fact_is_unit_less():
    f = ActionFact(id="dep_1", kind="has_active_dependency", of="rec-7",
                   value=True, status="truth")
    assert f.kind == "has_active_dependency" and f.value is True
    with pytest.raises(AttributeError):
        f.dimension