"""PART 3/4 regressions: NO pre-composed scenario transformations; chase +
two structurally different problems solved with ONLY registered primitives
composed in the agent-authored trace."""

import pytest

from openverifiers.legacy.v2 import Registry, run_trace, parse_dsl
from openverifiers.legacy.domains.algebra import ALGEBRA
from openverifiers.legacy.domains.physics_primitives import PRIMITIVES
from openverifiers.legacy.domains.units_si import (Meter, MeterPerSecond,
                                            MeterPerSecondSquared, Newton,
                                            Kilogram, Joule, Ohm, Volt,
                                            Kelvin)
from openverifiers.legacy.units import Unit
from openverifiers.legacy import Quantity

REG = Registry([ALGEBRA, PRIMITIVES])


def test_no_scenario_classes_registered():
    """Registry contains ONE relation per transformation — no CatchTime /
    pre-solved archetypes anywhere."""
    names = set(REG.transforms)
    assert "physics_trace.catch_time" not in names
    assert "physics_trace.cover_time" not in names
    assert not any("catch" in n or "chase" in n or "cover" in n
                   for n in names)
    from openverifiers.legacy.domains.physics_primitives import Primitive
    assert all(isinstance(t, Primitive) for n, t in REG.transforms.items()
               if n not in ("alg.equate", "alg.add"))


# -- chase (pursuit) on primitives -------------------------------------------
CHASE_BG = {
    "deer.start": Quantity(value=100.0, unit=Meter(), id="deer.start"),
    "deer.speed": Quantity(value=5.0, unit=MeterPerSecond(), id="deer.speed"),
    "v0": Quantity(value=0.0, unit=MeterPerSecond(), id="v0"),
    "tiger.a": Quantity(value=1.0, unit=MeterPerSecondSquared(),
                        id="tiger.a"),
    "zero": Quantity(value=0.0, unit=Meter(), id="zero"),
    "run": Quantity(value=300.0, unit=Meter(), id="run"),
}
CHASE = """
sd = kin.suvat_s_s0_vt(s0=deer.start, v=deer.speed)
st = kin.suvat_s_ut_athalf(u=v0, a=tiger.a)
catch_time = alg.equate(a=sd, b=st) with variable=t
deer_position = kin.suvat_s_s0_vt(s0=deer.start, v=deer.speed, t=catch_time)
"""


def test_chase_on_primitives_matches_v1_numbers():
    r = run_trace(REG, CHASE_BG, parse_dsl(CHASE))
    assert r.verdict == "pass", r.reason
    assert abs(r.env["catch_time"].value - 20.0) < 1e-9
    assert abs(r.env["deer_position"].value - 200.0) < 1e-9


# -- incline (work-energy, 1st paper) -----------------------------------------
INCLINE_BG = {
    "mass": Quantity(value=2.0, unit=Kilogram(), id="mass"),
    "vel": Quantity(value=10.0, unit=MeterPerSecond(), id="vel"),
    "g": Quantity(value=9.8, unit=MeterPerSecondSquared(), id="g"),
    "theta": Quantity(value=30.0, unit=Meter(), id="theta"),
    "mu": Quantity(value=0.3, unit=Meter(), id="mu"),
    "kezero": Quantity(value=0.0, unit=Joule(), id="kezero"),
}
INCLINE = """
ke = en.kinetic(m=mass, v=vel)
w = dyn.weight(m=mass, g=g)
fp = dyn.parallel_force(F=w, theta=theta)
N = dyn.normal_force(F=w, theta=theta)
ff = dyn.friction_kinetic(mu=mu, N=N)
wg = en.work(F=fp) with theta=180
wf = en.work(F=ff) with theta=180
wtot = alg.add(a=wg, b=wf)
kf = en.wet_ke_ke0_work(ke0=ke, work=wtot)
d = alg.equate(a=kf, b=kezero) with variable=d
"""


def test_incline_work_energy_exact():
    r = run_trace(REG, INCLINE_BG, parse_dsl(INCLINE))
    assert r.verdict == "pass", r.reason
    # v^2 / (2 g (sin30 + mu cos30)) = 100 / (2*9.8*0.5 + 2*9.8*0.3*0.8660)
    expected = 100.0 / (2 * 9.8 * (0.5 + 0.3 * (3 ** 0.5) / 2))
    assert abs(r.env["d"].value - expected) < 1e-6


# -- heater (circuits x heat, 2nd paper) --------------------------------------
CWATER = Unit(dimension=Joule().dimension /
              (Kilogram().dimension * Kelvin().dimension))
HEATER_BG = {
    "volts": Quantity(value=220.0, unit=Volt(), id="volts"),
    "R": Quantity(value=40.0, unit=Ohm(), id="R"),
    "mw": Quantity(value=1.0, unit=Kilogram(), id="mw"),
    "cwater": Quantity(value=4200.0, unit=CWATER, id="cwater"),
    "dtemp": Quantity(value=75.0, unit=Kelvin(), id="dtemp"),
}
HEATER = """
i = ckt.ohms(v=volts, r=R)
p = ckt.power_i2r(i=i, r=R)
q = th.q_mc_dt(m=mw, c=cwater, dT=dtemp)
ep = en.power_work_time(P=p)
t = alg.equate(a=ep, b=q) with variable=t
"""


def test_heater_circuits_x_heat_exact():
    r = run_trace(REG, HEATER_BG, parse_dsl(HEATER))
    assert r.verdict == "pass", r.reason
    expected = (1.0 * 4200.0 * 75.0) / (220.0 ** 2 / 40.0)
    assert abs(r.env["t"].value - expected) < 1e-6


def test_same_primitives_different_compositions():
    """The three problems share registered primitives; only the TRACE
    differs — the generality claim."""
    used = set()
    for trace in (CHASE, INCLINE, HEATER):
        for step in parse_dsl(trace):
            if step.op == "transform":
                used.add(step.transformation_name)
    assert used - set(REG.transforms) == set()  # all dispatched via registry
    shared = {"alg.equate"}
    assert shared <= used
    # each problem composes a different multisubset
    counts = {}
    for label, trace in (("chase", CHASE), ("incline", INCLINE),
                         ("heater", HEATER)):
        names = [s.transformation_name for s in parse_dsl(trace)
                 if s.op == "transform"]
        counts[label] = sorted(set(names))
    assert counts["chase"] != counts["incline"]
    assert counts["chase"] != counts["heater"]
    assert counts["incline"] != counts["heater"]