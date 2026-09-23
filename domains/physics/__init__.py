"""OpenVerifiers — physics domain package.

Combines the physics-specific object/property types (frames, motion
properties, PointObject) with the kinematics/dynamics/energy relation
registrations. Importing this package registers the SI units and their
display tokens via `domains.units_si`.

    from openverifiers.domains.physics import (SAVG, SUT, CONST_V_POS,
                                               ReferenceFrame, PointObject, ...)
"""

from __future__ import annotations

from openverifiers.domains.units_si import SI_SYSTEM

from .props import (ReferenceFrame, Time, MotionProperty, Position, Velocity,
                    Acceleration, Mass, PointObject, DisplacementFact)
from .relations import (VUAT, V2U2, SUT, SAVG, CONST_V_POS, FMA, KE, WFS,
                        KINEMATICS, DYNAMICS, ENERGY, ALL)

__all__ = [
    "ReferenceFrame", "Time", "MotionProperty", "Position", "Velocity",
    "Acceleration", "Mass", "PointObject", "DisplacementFact",
    "VUAT", "V2U2", "SUT", "SAVG", "CONST_V_POS", "FMA", "KE", "WFS",
    "KINEMATICS", "DYNAMICS", "ENERGY", "ALL", "SI_SYSTEM",
]