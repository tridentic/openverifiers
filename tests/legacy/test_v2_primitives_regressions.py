"""Three-defect regressions: all-bound return value, unit typing audit,
dataset constant leaks. Every fix has a test here that FAILS on the old
code."""

import csv
import re
from pathlib import Path

import pytest

from openverifiers.legacy import Quantity
from openverifiers.legacy.domains.physics_primitives import PRIMITIVES, DIMENSIONLESS
from openverifiers.legacy.domains.units_si import (Newton, Kilogram,
                                            MeterPerSecondSquared, Watt,
                                            Ampere, Ohm, Meter, Second,
                                            Volt, Coulomb, Kelvin, Joule)
from openverifiers.legacy.units import Dimension
from openverifiers.legacy.v2 import Registry

REG = Registry([PRIMITIVES])

M3 = Meter().dimension ** 3
MOL = Dimension(amount=1)
SPEC_HEAT = Joule().dimension / (Kilogram().dimension * Kelvin().dimension)
GAS_R = Joule().dimension / (MOL * Kelvin().dimension)


def _unit(rule, var):
    return PRIMITIVES.transformations[rule].rule["units"][var]


# -- DEFECT 1: fully-bound primitives return the bound OUTPUT value ---------
def test_all_bound_returns_bound_output_value():
    """Regression: the consistency-check branch must return the actual
    bound output (10), not the residual (~0). Zero coverage existed for the
    all-inputs-bound path — this is that coverage."""
    fma = REG.transforms["dyn.fma"]
    out = fma.apply({"F": Quantity(value=10.0, unit=Newton(), id="F"),
                     "m": Quantity(value=2.0, unit=Kilogram(), id="m"),
                     "a": Quantity(value=5.0,
                                   unit=MeterPerSecondSquared(), id="a")})
    assert out.value == 10.0
    assert out.unit.dimension == Newton().dimension


def test_all_bound_inconsistent_still_rejected():
    fma = REG.transforms["dyn.fma"]
    with pytest.raises(ValueError, match="not satisfied"):
        fma.apply({"F": Quantity(value=11.0, unit=Newton(), id="F"),
                   "m": Quantity(value=2.0, unit=Kilogram(), id="m"),
                   "a": Quantity(value=5.0,
                                 unit=MeterPerSecondSquared(), id="a")})


def test_all_bound_second_relation_power_rule():
    p = REG.transforms["ckt.power_i2r"]
    out = p.apply({"p": Quantity(value=100.0, unit=Watt(), id="p"),
                   "i": Quantity(value=5.0, unit=Ampere(), id="i"),
                   "r": Quantity(value=4.0, unit=Ohm(), id="r")})
    assert out.value == 100.0


# -- DEFECT 2: unit audit — every mislabeled constant is a composite unit ---
def test_unit_audit_constant_dimensions():
    checks = {
        # angles -> dimensionless (degrees convention)
        "kin.projectile_range": {"theta": DIMENSIONLESS.dimension},
        "kin.projectile_max_height": {"theta": DIMENSIONLESS.dimension},
        "dyn.parallel_force": {"theta": DIMENSIONLESS.dimension},
        "dyn.normal_force": {"theta": DIMENSIONLESS.dimension},
        "en.work": {"theta": DIMENSIONLESS.dimension},
        "opt.snell": {"n1": DIMENSIONLESS.dimension,
                      "n2": DIMENSIONLESS.dimension,
                      "t1": DIMENSIONLESS.dimension,
                      "t2": DIMENSIONLESS.dimension},
        "opt.critical": {"n1": DIMENSIONLESS.dimension,
                         "n2": DIMENSIONLESS.dimension,
                         "tc": DIMENSIONLESS.dimension},
        # dimensionless coefficients / counts / indices
        "dyn.friction_kinetic": {"mu": DIMENSIONLESS.dimension},
        "mag.flux_change_emf": {"N": DIMENSIONLESS.dimension},
        "opt.magnification": {"m": DIMENSIONLESS.dimension},
        "mod.hydrogen_en": {"n": DIMENSIONLESS.dimension},
        "mod.half_life": {"N": DIMENSIONLESS.dimension,
                          "N0": DIMENSIONLESS.dimension},
        # law constants: proper SI composites
        "el.coulomb": {"k": (Newton().dimension * Meter().dimension ** 2
                             / Coulomb().dimension ** 2)},
        "el.field_point": {"k": (Newton().dimension * Meter().dimension ** 2
                                 / Coulomb().dimension ** 2)},
        "dyn.grav_force": {"G": (Newton().dimension * Meter().dimension ** 2
                                 / Kilogram().dimension ** 2)},
        # material params
        "ckt.resistivity": {"rho": Ohm().dimension * Meter().dimension,
                            "A": Meter().dimension ** 2},
        "th.expansion_len": {"alpha": Kelvin().dimension ** -1},
        "th.q_mc_dt": {"c": SPEC_HEAT},
        "th.pv_nrt": {"V": M3, "n": MOL, "R": GAS_R, "T": Kelvin().dimension},
    }
    failures = []
    for rule, wants in checks.items():
        for var, want in wants.items():
            got = _unit(rule, var).dimension
            if got != want:
                failures.append(f"{rule}.{var}: {got} != {want}")
    assert not failures, "\n".join(failures)


def test_no_bare_meter_masquerades_as_constant():
    """Structural guard: none of the audited constant variables may carry
    the plain meter dimension (the old mislabel fingerprint)."""
    meter_dim = Meter().dimension
    for rule, vars_ in {
        "kin.projectile_range": ("theta",),
        "dyn.parallel_force": ("theta",),
        "en.work": ("theta",),
        "opt.snell": ("n1", "n2", "t1", "t2"),
        "opt.critical": ("n1", "n2", "tc"),
        "dyn.friction_kinetic": ("mu",),
        "mag.flux_change_emf": ("N",),
        "el.coulomb": ("k",),
        "dyn.grav_force": ("G",),
        "ckt.resistivity": ("rho", "A"),
        "th.expansion_len": ("alpha",),
    }.items():
        for var in vars_:
            assert _unit(rule, var).dimension != meter_dim, \
                f"{rule}.{var} still mislabeled as Meter"


# -- DEFECT 3: dataset must not zero out physical constants ---------------
DS = Path(__file__).resolve().parents[2] / "openverifiers" / "legacy" / "datasets" / \
    "physics_syllabus_problems.csv"


def test_dataset_has_no_zeroed_physical_constants():
    rows = list(csv.DictReader(open(DS)))
    bad = []
    for r in rows:
        t = r["problem"]
        for pat in (r"G = 0\b", r"coefficient is 0 ", r"mass 0 kg",
                    r"= 0 /K"):
            if re.search(pat, t):
                bad.append((r["id"], pat, t[:70]))
    assert not bad, "\n".join(str(b) for b in bad)


def test_dataset_gravitational_rows_carry_real_G():
    rows = list(csv.DictReader(open(DS)))
    g_rows = [r for r in rows if "G = 6.674e-11" in r["problem"]]
    assert len(g_rows) >= 8          # P018/P054/P056/P124 + satellites
    for r in g_rows:
        assert "G = 0" not in r["problem"]


def test_dataset_tiny_constants_render_nonzero():
    rows = list(csv.DictReader(open(DS)))
    text = " ".join(r["problem"] for r in rows)
    for token in ("6.674e-11", "1.2e-05", "9.11e-31", "6.64e-27",
                  "6.626e-34"):
        assert token in text, f"{token} lost in regenerate"