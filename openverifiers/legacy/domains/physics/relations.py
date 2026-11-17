"""OpenVerifiers — declared physics equations and controllers (typed).

One EquationController per relation family — not one function per solve
direction. Any of the three domains (kinematics, dynamics, energy) can be
solved for any of their variables; momentum conservation is a CONDITION
(see `domains.conservation`), not an equation-solve.
"""

from __future__ import annotations

import sympy as sp

from openverifiers.legacy.domains.units_si import (Meter, Second, MeterPerSecond,
                                            MeterPerSecondSquared, Newton,
                                            Joule, Kilogram)
from openverifiers.legacy.controllers import EquationController
from .props import Position, Velocity, Acceleration, Time, Mass

v, u, a, t, s, s0, m, F, K, W = sp.symbols("v u a t s s0 m F K W")

VUAT = EquationController(
    "kinematics: v = u + a*t", v - (u + a * t),
    vars={"v": MeterPerSecond(), "u": MeterPerSecond(),
          "a": MeterPerSecondSquared(), "t": Second()},
    role_types={"v": Velocity, "u": Velocity, "a": Acceleration, "t": Time})

V2U2 = EquationController(
    "kinematics: v^2 = u^2 + 2 a s", v**2 - (u**2 + 2 * a * s),
    vars={"v": MeterPerSecond(), "u": MeterPerSecond(),
          "a": MeterPerSecondSquared(), "s": Meter()},
    role_types={"v": Velocity, "u": Velocity, "a": Acceleration,
                "s": Position})

SUT = EquationController(
    "kinematics: s = u t + (1/2) a t^2",
    s - (u * t + sp.Rational(1, 2) * a * t**2),
    vars={"s": Meter(), "u": MeterPerSecond(),
          "t": Second(), "a": MeterPerSecondSquared()},
    role_types={"s": Position, "u": Velocity, "t": Time,
                "a": Acceleration})

SAVG = EquationController(
    "kinematics: s = (u + v)/2 * t",
    s - sp.Rational(1, 2) * (u + v) * t,
    vars={"s": Meter(), "u": MeterPerSecond(),
          "v": MeterPerSecond(), "t": Second()},
    role_types={"s": Position, "u": Velocity, "v": Velocity, "t": Time})

# constant-velocity POSITION, the a=0 specialization of the full SUVAT law;
# the displacement-only forms above cannot express an initial offset.
CONST_V_POS = EquationController(
    "kinematics: s = s0 + v t  (a=0)",
    s - (s0 + v * t),
    vars={"s": Meter(), "s0": Meter(), "v": MeterPerSecond(), "t": Second()},
    role_types={"s": Position, "s0": Position, "v": Velocity, "t": Time})

# dynamics: force and mass must describe the same physical object
FMA = EquationController(
    "dynamics: F = m a", F - m * a,
    vars={"F": Newton(), "m": Kilogram(), "a": MeterPerSecondSquared()},
    shared_owner=True,
    role_types={"m": Mass, "a": Acceleration})

KE = EquationController(
    "energy: KE = (1/2) m v^2", K - sp.Rational(1, 2) * m * v**2,
    vars={"K": Joule(), "m": Kilogram(), "v": MeterPerSecond()},
    role_types={"m": Mass, "v": Velocity})

WFS = EquationController(
    "energy: W = F s", W - F * s,
    vars={"W": Joule(), "F": Newton(), "s": Meter()},
    role_types={"s": Position})

KINEMATICS = [VUAT, V2U2, SUT, SAVG, CONST_V_POS]
DYNAMICS = [FMA]
ENERGY = [KE, WFS]

ALL = KINEMATICS + DYNAMICS + ENERGY