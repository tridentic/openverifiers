"""OpenVerifiers — object hierarchy: frames, typed properties, PointObject.

ReferenceFrame is identity/consistency this sprint, not a kinematics engine.

Position/Velocity/Acceleration/Mass are Quantity subtypes with unit-dimension
validators. The three motion properties carry a MANDATORY frame:

    Position(value=100.0, unit=Meter(), frame=ground)   # explicit
    with deer.relative_to(ground):                      # implicit
        deer.position = Position(value=100.0, unit=Meter())

The `with` block supplies the default frame= kwarg to constructors inside it.
It cannot reframe or take ownership of a property built elsewhere: assignment
rejects frame disagreement, and block entry rejects object/frame mismatch.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import ClassVar, Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from openverifiers.units import Vector3
from openverifiers.domains.units_si import (Meter, MeterPerSecond,
                                            MeterPerSecondSquared, Kilogram,
                                            Second)
from openverifiers.facts import Quantity
from openverifiers.objects import PhysicalObject, active_owner
from openverifiers.errors import OwnerMismatchError


class Time(Quantity):
    """Elapsed-time property, owned by a ReferenceFrame (frame.time), not by
    any PointObject. Scalar — time is not a vector in this model."""

    @field_validator("unit")
    @classmethod
    def _time_unit(cls, v):
        if v.dimension != Second().dimension:
            raise ValueError(f"Time requires a unit of dimension "
                             f"{Second().dimension}, got {v.dimension}")
        return v


class ReferenceFrame(BaseModel):
    """An identity for a frame of reference. Consistency check only this
    sprint. Mutable so `frame.time = Time(...)` is the intended API; Time is
    owned by the frame, not by any object."""

    model_config = ConfigDict(frozen=False, extra="forbid")

    name: str
    time: Optional[Time] = None


# -- active `with` construction contexts -------------------------------------
# context-local (not a mutable global): nested blocks and concurrent usage
# each see their own stack.
_FRAME_STACK: contextvars.ContextVar[list] = contextvars.ContextVar(
    "verifier_frame_stack", default=[])


class MotionProperty(Quantity):
    """A 3D-vector Quantity that must carry a reference frame.

    `value` is a Vector3 — never silently 1D. Both scalar-allowed base field
    and the vector carry units; the vector's unit must equal the property's
    own unit (the property unit is the single authority)."""

    frame: ReferenceFrame
    value: Vector3
    expected_dimension: ClassVar[Optional[object]] = None

    @model_validator(mode="after")
    def _vector_unit_matches_own_unit(self):
        if self.value.unit != self.unit:
            raise ValueError(
                "vector unit does not match the property unit: "
                f"{self.value.unit!r} vs {self.unit!r}")
        return self

    def __init__(self, /, **data):
        if data.get("frame") is None:
            stack = _FRAME_STACK.get()
            if not stack:
                raise ValueError(
                    "no active reference frame — use `with "
                    "obj.relative_to(frame):` or pass frame= explicitly")
            data["frame"] = stack[-1][1]
        # typed ownership (pythonic-verifiers `owner=car`): no owner naming
        # convention anywhere — a real PhysicalObject reference is required,
        # defaulted from the active `with <object> as owner:` scope.
        owner = data.setdefault("owner", active_owner())
        if owner is not None:
            owner_frame = getattr(owner, "frame", None)
            if owner_frame is not None and owner_frame != data["frame"]:
                raise OwnerMismatchError(
                    f"{type(self).__name__} owner "
                    f"{getattr(owner, 'name', owner.id)!r} is bound to "
                    f"frame {owner_frame.name!r} but the property is "
                    f"constructed in frame {data['frame'].name!r}")
        super().__init__(**data)

    @field_validator("unit")
    @classmethod
    def _check_dimension(cls, v):
        expected = cls.expected_dimension
        if expected is not None and v.dimension != expected:
            raise ValueError(f"{cls.__name__} requires a unit of dimension "
                             f"{expected}, got {v.dimension}")
        return v


class Position(MotionProperty):
    expected_dimension: ClassVar[Optional[object]] = Meter().dimension


class Velocity(MotionProperty):
    expected_dimension: ClassVar[Optional[object]] = MeterPerSecond().dimension


class Acceleration(MotionProperty):
    expected_dimension: ClassVar[Optional[object]] = MeterPerSecondSquared().dimension


class Mass(Quantity):
    """Mechanical property, frame-free in this model."""

    @field_validator("unit")
    @classmethod
    def _mass_unit(cls, v):
        expected = Kilogram().dimension
        if v.dimension != expected:
            raise ValueError(f"Mass requires a unit of dimension {expected}, "
                             f"got {v.dimension}")
        return v


# ---------------------------------------------------------------------------
# `with` frame-context block
# ---------------------------------------------------------------------------
class _RelativeTo:
    def __init__(self, obj: "PointObject", frame: ReferenceFrame):
        if obj.frame is not None and obj.frame != frame:
            raise ValueError(
                f"frame mismatch: object {obj.name!r} is bound to frame "
                f"{obj.frame.name!r}, block declares {frame.name!r} — a "
                f"`with` block cannot reframe an object")
        self._obj = obj
        self._frame = frame

    def __enter__(self):
        _FRAME_STACK.get().append((self._obj, self._frame))
        return self._obj

    def __exit__(self, *exc) -> bool:
        stack = _FRAME_STACK.get()
        if stack and stack[-1][0] is self._obj:
            stack.pop()
        return False


# ---------------------------------------------------------------------------
# PointObject — typed attributes, not a bag of Facts
# ---------------------------------------------------------------------------
class PointObject(PhysicalObject):
    # mutable: attribute assignment is the intended API (deer.position = ...)
    model_config = ConfigDict(frozen=False, extra="forbid")

    id: str = "?"
    name: str = "?"
    frame: Optional[ReferenceFrame] = None
    mass: Optional[Mass] = None
    position: Optional[Position] = None
    velocity: Optional[Velocity] = None
    acceleration: Optional[Acceleration] = None

    _MOTION_FIELDS = frozenset({"position", "velocity", "acceleration"})

    def relative_to(self, frame: ReferenceFrame) -> _RelativeTo:
        return _RelativeTo(self, frame)

    def __setattr__(self, key, value):
        if key in self._MOTION_FIELDS and value is not None:
            prop_frame = getattr(value, "frame", None)
            if prop_frame is not None and self.frame is not None:
                if prop_frame != self.frame:
                    raise ValueError(
                        f"frame mismatch: {self.name!r}.{key} carries frame "
                        f"{prop_frame.name!r}, object bound to frame "
                        f"{self.frame.name!r} — cannot assign a property "
                        f"built in another frame")
        super().__setattr__(key, value)


# ---------------------------------------------------------------------------
# Qualified process outcome: NOT a bare Quantity
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DisplacementFact:
    """A time-spanning, owned, framed physical process outcome — 'how far
    something moved' between two instants — fully self-describing instead of
    a bare Quantity. A bare Quantity remains correct only for genuinely
    context-free scalars (e.g. a polynomial's discriminant)."""

    quantity: Quantity
    frame: ReferenceFrame
    object: PointObject
    time_start: Time
    time_end: Time