"""OpenVerifiers — generic units machinery (domain-agnostic core).

`Dimension` is a vector over the seven SI base dimensions with integer
exponents; `__mul__`/`__truediv__`/`__pow__` compose it algebraically.
`Unit` is a real type carrying a `Dimension` plus a `scale` to SI canonical
form. `UnitSystem` is a dimension->default-unit registry — one instance per
system, and neither `Quantity` nor `Unit` ever references a system.

No concrete SI unit lives here: they are application-level registrations in
`domains/units_si.py`. `Vector3` is plain math (an n-tuple with arithmetic),
usable by any domain producing multi-component data — not physics.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Dimension(BaseModel):
    model_config = ConfigDict(frozen=True)

    length: int = 0
    mass: int = 0
    time: int = 0
    current: int = 0
    temperature: int = 0
    amount: int = 0
    luminous: int = 0

    def __mul__(self, other: "Dimension") -> "Dimension":
        return Dimension(
            length=self.length + other.length,
            mass=self.mass + other.mass,
            time=self.time + other.time,
            current=self.current + other.current,
            temperature=self.temperature + other.temperature,
            amount=self.amount + other.amount,
            luminous=self.luminous + other.luminous,
        )

    def __truediv__(self, other: "Dimension") -> "Dimension":
        return self * Dimension(
            length=-other.length, mass=-other.mass, time=-other.time,
            current=-other.current, temperature=-other.temperature,
            amount=-other.amount, luminous=-other.luminous,
        )

    def __pow__(self, exponent: int) -> "Dimension":
        if not isinstance(exponent, int):
            raise TypeError("dimension exponents must be integers")
        return Dimension(
            length=self.length * exponent, mass=self.mass * exponent,
            time=self.time * exponent, current=self.current * exponent,
            temperature=self.temperature * exponent, amount=self.amount * exponent,
            luminous=self.luminous * exponent,
        )

    @property
    def is_dimensionless(self) -> bool:
        return not any(v for v in self.model_dump().values())

    def __str__(self) -> str:
        parts = []
        for name in ("length", "mass", "time", "current", "temperature",
                     "amount", "luminous"):
            exp = getattr(self, name)
            if exp:
                parts.append("L" if name == "length" else
                             "M" if name == "mass" else
                             "T" if name == "time" else
                             "I" if name == "current" else
                             "K" if name == "temperature" else
                             "N" if name == "amount" else "J")
                parts[-1] = parts[-1] if exp == 1 else f"{parts[-1]}^{exp}"
        return "*".join(parts) if parts else "1"


class Unit(BaseModel):
    """Typed unit: a dimension plus a scale to SI canonical form.

    scale = the multiplicative factor converting one of this unit's values
    to its dimension's SI canonical form (meter=1.0, kilometer=1000.0).
    Comparisons and arithmetic canonicalize through `scale` FIRST, so
    different units of the same dimension never compare raw values."""

    model_config = ConfigDict(frozen=True)

    dimension: Dimension
    scale: float = 1.0


class UnitSystem(BaseModel):
    """Dimension -> default Unit registry. One system per instance; neither
    Quantity nor Unit references a system — a second system is registry-only."""

    model_config = ConfigDict(frozen=True)

    name: str
    base_units: dict[Dimension, Unit]

    def unit_for(self, dimension: Dimension) -> Unit:
        return self.base_units[dimension]

    def default_unit(self, dimension: Dimension) -> Unit:
        return self.base_units.get(dimension)


def to_canonical(value: float, unit: Unit) -> float:
    """One value in `unit` -> the same value in the dimension's SI canonical
    scale (value * scale). All cross-unit comparisons go through this."""
    return value * unit.scale


class Vector3(BaseModel):
    """A 3D vector whose components share one Unit. Pure math: component-wise
    arithmetic only. No cross product, no rotation, no coordinate transforms —
    and no physics assumptions baked in."""

    model_config = ConfigDict(frozen=True)

    x: float
    y: float
    z: float
    unit: Unit

    def __add__(self, other: "Vector3") -> "Vector3":
        return Vector3(x=self.x + other.x, y=self.y + other.y,
                       z=self.z + other.z, unit=self.unit)

    def __sub__(self, other: "Vector3") -> "Vector3":
        return Vector3(x=self.x - other.x, y=self.y - other.y,
                       z=self.z - other.z, unit=self.unit)

    def component(self, axis: int) -> float:
        return (self.x, self.y, self.z)[axis]

    @classmethod
    def x_only(cls, value: float, unit: Unit) -> "Vector3":
        return cls(x=value, y=0.0, z=0.0, unit=unit)

    def __str__(self) -> str:
        from .facts import unit_display
        return f"({self.x}, {self.y}, {self.z}) {unit_display(self.unit)}"

    @property
    def is_axis_aligned(self) -> bool:
        return (self.y == 0.0 and self.z == 0.0) or \
               (self.x == 0.0 and self.z == 0.0) or \
               (self.x == 0.0 and self.y == 0.0)