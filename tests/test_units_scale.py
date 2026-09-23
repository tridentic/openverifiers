from openverifiers import (FactQuery, Premise, Quantity, Specifier, ThresholdQuery, Unit, UnitSystem, to_canonical)

from openverifiers.domains.physics import (PointObject, Position, ReferenceFrame)
from openverifiers.domains.units_si import (Kilometer, Meter, MeterPerSecond, SI_SYSTEM, Second)
"""Task 2 — units carry a real scale; comparisons canonicalize first."""

import pytest



GROUND = ReferenceFrame(name="ground")


def test_unit_scale_is_structural():
    assert Meter().scale == 1.0
    assert Kilometer().scale == 1000.0
    assert to_canonical(1.0, Kilometer()) == 1000.0
    assert to_canonical(1000.0, Meter()) == 1000.0


def test_si_system_registry_and_hook():
    assert SI_SYSTEM.unit_for(Meter().dimension) == Meter()
    assert SI_SYSTEM.unit_for(Second().dimension) == Second()
    alt = UnitSystem(name="alt", base_units={Meter().dimension: Kilometer()})
    assert alt.default_unit(Meter().dimension) == Kilometer()
    # no Quantity/Unit change required for a second system — registry only


def test_km_and_m_positions_compare_in_canonical_scale():
    """1 km and 1000 m are the same length: comparisons canonicalize through
    each unit's scale before comparing — never raw values."""
    q_km = Quantity(value=1.0, unit=Kilometer(), id="qkm")
    q_m = Quantity(value=1000.0, unit=Meter(), id="qm")
    assert Specifier(Premise.of(facts={"a": q_km}),
                     FactQuery("a", 1000.0)).verify().verdict == "pass"
    assert Specifier(Premise.of(facts={"a": q_m}),
                     FactQuery("a", 1000.0)).verify().verdict == "pass"
    # threshold bounds are SI-canonical: 1 km is below 1500 m, above 500 m
    assert Specifier(Premise.of(facts={"a": q_km}),
                     ThresholdQuery("a", max=500.0)).verify().verdict == "fail"
    assert Specifier(Premise.of(facts={"a": q_km}),
                     ThresholdQuery("a", min=1000.0, max=1500.0)).verify().verdict == "pass"

